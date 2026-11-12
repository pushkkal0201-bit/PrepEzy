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
