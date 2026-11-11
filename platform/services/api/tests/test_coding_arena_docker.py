"""Real Docker integration tests, gated to the dedicated CI job.

These tests require pre-pulled images and an active Docker Linux daemon. No
host-side execution fallback exists. Run only on a trusted CI/developer host.
"""
import os
import pytest

from app.coding_arena import DockerRunner, PROBLEMS

pytestmark = pytest.mark.skipif(
    os.environ.get("PREPEZY_RUN_DOCKER_TESTS") != "1",
    reason="Explicit Docker integration opt-in required",
)

SOLUTIONS = {
    "python": "a, b = map(int, input().split())\nprint(a + b)\n",
    "javascript": "const [a,b] = require('fs').readFileSync(0,'utf8').trim().split(/\\s+/).map(Number);\nconsole.log(a+b);\n",
    "java": "import java.util.*; public class Main { public static void main(String[] args) { Scanner s = new Scanner(System.in); long a=s.nextLong(), b=s.nextLong(); System.out.println(a+b); } }\n",
}


@pytest.mark.parametrize("language", ["python", "javascript", "java"])
def test_genuine_container_execution(language):
    judge = DockerRunner()
    assert judge.available(language), "Docker image must be pulled by CI before test"
    checks = judge.run(language, SOLUTIONS[language], PROBLEMS["sum-pair"]["cases"][:2])
    assert len(checks) == 2, checks
    assert all(item["status"] == "accepted" for item in checks), checks


def test_real_wrong_answer_caught():
    judge = DockerRunner()
    checks = judge.run("python", "print(999999)\n", PROBLEMS["sum-pair"]["cases"][:1])
    assert checks[0]["status"] == "wrong_answer"


def test_real_infinite_loop_time_limit():
    judge = DockerRunner()
    checks = judge.run("python", "while True: pass\n", PROBLEMS["sum-pair"]["cases"][:1])
    assert checks[0]["status"] == "time_limit", checks


def test_real_java_compiler_error_is_reported():
    judge = DockerRunner()
    checks = judge.run("java", "public class Main { broken code }", PROBLEMS["sum-pair"]["cases"][:1])
    assert checks[0]["status"] == "compile_error", checks


def test_live_api_session_submission_updates_skillgraph():
    """Full Docker -> API -> SQLite -> SkillGraph path; real Python execution."""
    from fastapi.testclient import TestClient
    from app.core import DemoEngine
    from app.local_lab import LocalLab
    from app.main import create_app

    client = TestClient(create_app(DemoEngine(), local_lab=LocalLab()))
    ready = client.get("/api/local/arena/status").json()["availability"]["ready"]
    assert ready["python"], "The CI job must pre-pull Python"
    start = client.post("/api/local/arena/sessions", json={
        "mode": "timed", "duration_minutes": 15
    })
    assert start.status_code == 200, start.text
    session_id = start.json()["id"]
    submitted = client.post("/api/local/arena/submissions", json={
        "session_id": session_id, "problem_id": "sum-pair", "language": "python",
        "source": SOLUTIONS["python"]
    })
    assert submitted.status_code == 200, submitted.text
    result = submitted.json()["result"]
    assert result["all_passed"] is True, result
    assert result["tests_passed"] == result["tests_total"] == 4
    graph = client.get("/api/local/skillgraph").json()
    coding = next(s for s in graph["skills"] if s["id"] == "coding")
    assert coding["distinct_assessments"] == 1
    assert coding["first_try_correct_unassisted"] == 1
    assert graph["sources"]["coding_arena"] == 1
    assert client.delete("/api/local/data").status_code == 200
    assert client.get("/api/local/arena/evidence").json()["attempts"] == []


# Stage 11: Actual project milestone programs, not contract/mocked judge results.
PROJECT_KV_SOLUTIONS = {
    "python": """import sys
rows = sys.stdin.read().strip().splitlines()
n = int(rows[0])
data = {}
output = []
for line in rows[1:n+1]:
    command = line.split()
    if command[0] == "PUT":
        data[command[1]] = command[2]
    elif command[0] == "GET":
        output.append(data.get(command[1], "NOT_FOUND"))
print("\\n".join(output))
""",
    "javascript": """const fs = require('fs');
const lines = fs.readFileSync(0, 'utf8').trim().split(/\\r?\\n/);
const n = Number(lines[0]);
const data = new Map();
const output = [];
for (const line of lines.slice(1, n + 1)) {
  const parts = line.trim().split(/\\s+/);
  if (parts[0] === 'PUT') data.set(parts[1], parts[2]);
  else if (parts[0] === 'GET') output.push(data.has(parts[1]) ? data.get(parts[1]) : 'NOT_FOUND');
}
console.log(output.join('\\n'));
""",
    "java": """import java.util.*;
public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        int n = sc.nextInt();
        Map<String, String> data = new HashMap<>();
        List<String> output = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            String op = sc.next();
            if (op.equals("PUT")) {
                data.put(sc.next(), sc.next());
            } else if (op.equals("GET")) {
                String key = sc.next();
                output.add(data.getOrDefault(key, "NOT_FOUND"));
            }
        }
        System.out.println(String.join("\\n", output));
    }
}
""",
}


@pytest.mark.parametrize("language", ["python", "javascript", "java"])
def test_real_stage11_project_milestone_in_docker(language):
    from app.local_lab import LocalLab
    from app.unified import UnifiedEvidence

    lab = LocalLab()
    unified = UnifiedEvidence(lab)
    assert unified.projects.runner.available(language)
    output = unified.projects.submit_milestone(
        "key-value-store", "lookup", language, PROJECT_KV_SOLUTIONS[language]
    )
    assert output["all_passed"], output
    assert output["tests_passed"] == output["tests_total"] == 3
    assert output["source"] == "prepezy-docker-project-milestone"
    assert unified.projects.state("key-value-store")["milestones"][1]["unlocked"]
    skill = next(x for x in unified.skillgraph()["skills"] if x["id"] == "project-build")
    assert skill["first_try_correct_unassisted"] == 1
    assert unified.skillgraph()["sources"]["project_milestones"] == 1


def test_real_stage11_project_defense_tracks_checked_choice_not_written_rationale():
    from app.local_lab import LocalLab
    from app.unified import UnifiedEvidence
    lab = LocalLab()
    unified = UnifiedEvidence(lab)
    result = unified.projects.submit_milestone(
        "key-value-store", "lookup", "python", PROJECT_KV_SOLUTIONS["python"]
    )
    assert result["all_passed"]
    defense = unified.projects.defend(
        "key-value-store", "overwrite", "b",
        "Replacing the existing value leaves the set of distinct keys unchanged."
    )
    assert defense["correct"]
    assert defense["rationale_reviewed"] is False
    report = unified.skillgraph()
    assert report["sources"]["project_defense_choices"] == 1
    assert report["sources"]["project_milestones"] == 1


@pytest.mark.parametrize("language,source", [
    ("python", 'print("READY")\n'),
    ("javascript", 'console.log("READY");\n'),
    ("java", 'public class Main { public static void main(String[] args) { System.out.println("READY"); } }\n'),
])
def test_real_stage12_pinned_github_blob_approved_smoke_in_docker(language, source):
    """Actual Docker execution, with a fake GitHub REST transport for stable CI."""
    import asyncio
    import base64
    import hashlib
    import httpx
    from app.local_lab import LocalLab
    from app.repo_review import GitHubProjectReview

    payload = source.encode("utf-8")
    blob = hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload).hexdigest()
    commit, tree = "a" * 40, "b" * 40
    path = {"python": "main.py", "javascript": "main.js", "java": "Main.java"}[language]

    def fake_github(request):
        assert request.method == "GET"
        assert request.url.host == "api.github.com"
        route = request.url.path
        if route == "/repos/sample-user/standalone-hello":
            return httpx.Response(200, json={"private": False, "default_branch": "main"})
        if route.endswith("/commits/main"):
            return httpx.Response(200, json={"sha": commit, "commit": {"tree": {"sha": tree}}})
        if route.endswith("/git/trees/" + tree):
            return httpx.Response(200, json={"truncated": False, "tree": [
                {"path": path, "type": "blob", "size": len(payload), "sha": blob}
            ]})
        if route.endswith("/git/blobs/" + blob):
            return httpx.Response(200, json={
                "encoding": "base64", "content": base64.b64encode(payload).decode()
            })
        return httpx.Response(404, json={"detail": "not found"})

    lab = LocalLab()
    reviewer = GitHubProjectReview(
        lab.db, lab.lock, transport=httpx.MockTransport(fake_github), runner=DockerRunner()
    )
    snapshot = asyncio.run(reviewer.inspect("https://github.com/sample-user/standalone-hello"))
    assert snapshot["commit_sha"] == commit
    assert reviewer.runner.available(language), "CI must pre-pull language images"
    result = asyncio.run(reviewer.smoke_check(
        snapshot["id"], path, language, [{"stdin": "", "expected_stdout": "READY"}], True
    ))
    assert result["verdict"] == "matched-user-expected-output", result
    assert result["tests_passed"] == result["tests_total"] == 1
    assert result["graded_skillgraph"] is False
    assert result["expectation_origin"] == "learner-supplied-not-independently-verified"
