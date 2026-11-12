"""Stage 12: commit-pinned GitHub API contract and explicitly approved Docker checks."""
import base64
import hashlib
from io import BytesIO

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core import DemoEngine
from app.local_lab import LocalLab
from app.main import create_app
from app.repo_review import (GitHubProjectReview, GitHubReviewUnavailable,
                             _file_ok, repo_parts)

COMMIT = "a" * 40
TREE = "b" * 40
OWNER, REPO = "sample-user", "typed-demo"
PATH = "app/main.py"
SOURCE = (
    'from fastapi import FastAPI\n'
    'app = FastAPI()\n'
    '@app.get("/health")\n'
    'def health():\n'
    '    return {"ok": True}\n'
    'print("Ready")\n'
).encode("utf-8")
TEST_FILE = b"def test_health():\n    assert 1 + 1 == 2\n"
README = b"# A small open-source project\nWritten as example documentation.\n"


def sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


BLOBS = {sha(x): x for x in [SOURCE, TEST_FILE, README]}


def fixture(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    assert request.method == "GET"
    assert request.url.host == "api.github.com"
    if path == "/repos/sample-user/typed-demo":
        return httpx.Response(200, json={"private": False, "default_branch": "main"})
    if path == "/repos/sample-user/typed-demo/commits/main":
        return httpx.Response(200, json={
            "sha": COMMIT, "commit": {"tree": {"sha": TREE}}
        })
    if path == "/repos/sample-user/typed-demo/git/trees/" + TREE:
        assert request.url.params["recursive"] == "1"
        return httpx.Response(200, json={"truncated": False, "tree": [
            {"path": PATH, "type": "blob", "size": len(SOURCE), "sha": sha(SOURCE)},
            {"path": "tests/test_main.py", "type": "blob", "size": len(TEST_FILE), "sha": sha(TEST_FILE)},
            {"path": "README.md", "type": "blob", "size": len(README), "sha": sha(README)},
            {"path": ".env", "type": "blob", "size": 50, "sha": "c" * 40},
            {"path": "vendor/secret.py", "type": "blob", "size": 80, "sha": "d" * 40},
        ]})
    if path.startswith("/repos/sample-user/typed-demo/git/blobs/"):
        digest = path.split("/")[-1]
        data = BLOBS.get(digest)
        if data is None:
            return httpx.Response(404, json={"message": "not found"})
        return httpx.Response(200, json={
            "encoding": "base64", "content": base64.b64encode(data).decode(),
        })
    return httpx.Response(404, json={"message": "not found"})


class GuardedHTTP:
    def __init__(self, upstream=fixture):
        self.upstream = upstream
        self.calls = []
    def __call__(self, request):
        self.calls.append(str(request.url))
        return self.upstream(request)


class FakeDocker:
    def __init__(self, available=True):
        self.enabled = available
        self.runs = []

    def available(self, language):
        return self.enabled

    def run(self, language, source, cases):
        self.runs.append((language, source, list(cases)))
        if not self.enabled:
            raise RuntimeError("unavailable")
        good = 'print("Ready")' in source and cases == [("", "Ready")]
        return [{"case": 1, "status": "accepted" if good else "wrong_answer"}]


def setup(tmp_path=None, provider=None, runner=None):
    local = LocalLab(tmp_path / "repo.sqlite" if tmp_path else ":memory:")
    calls = provider or GuardedHTTP()
    docker = runner or FakeDocker()
    review = GitHubProjectReview(
        local.db, local.lock, transport=httpx.MockTransport(calls), runner=docker
    )
    api = TestClient(create_app(DemoEngine(), local_lab=local, repo_review_client=review))
    return api, review, calls, docker


def inspect(api):
    r = api.post("/api/local/repositories/inspect",
                 json={"repo_url": "https://github.com/sample-user/typed-demo"})
    assert r.status_code == 200, r.text
    return r.json()


def test_safe_repo_root_validation_rejects_other_domains_and_paths():
    for value in [
        "https://github.com/x/y/issues/1", "http://github.com/x/y",
        "https://raw.githubusercontent.com/x/y", "https://github.com/x/y?token=1",
        "https://github.com/x/y#commit", "https://github.com/x/../../etc",
        "https://github.com/x/.secret", "https://github.com@evil.com/a/b",
    ]:
        with pytest.raises(ValueError):
            repo_parts(value)
    assert repo_parts("https://github.com/sample-user/typed-demo.git") == (
        "sample-user", "typed-demo"
    )


def test_snapshot_uses_only_fixed_api_host_and_pinned_commit_and_exact_lines():
    c, review, provider, docker = setup()
    result = inspect(c)
    assert result["commit_sha"] == COMMIT and result["tree_sha"] == TREE
    assert result["inventory"]["inspected_count"] == 3
    assert not any(".env" in f["path"] for f in result["candidate_files"])
    assert result["inventory"]["test_file_paths"] == ["tests/test_main.py"]
    assert result["assessment"] == "not-scored-static-inspection"
    assert result["findings"]
    assert any(f["kind"] == "fastapi" and f["line"] == 2
               and f["source_url"] == f"https://github.com/sample-user/typed-demo/blob/{COMMIT}/app/main.py#L2"
               for f in result["findings"])
    assert all(url.startswith("https://api.github.com/") for url in provider.calls)
    assert docker.runs == []


def test_snapshot_does_not_automatically_award_skillgraph_grades():
    c, _, _, _ = setup()
    before = c.get("/api/local/skillgraph").json()
    assert before["event_count"] == 0
    result = inspect(c)
    after = c.get("/api/local/skillgraph").json()
    assert len(after["skills"]) == 10
    assert after["event_count"] == 0
    assert after["github_review_context"]["snapshots"] == 1
    assert after["github_review_context"]["counts_as_skill_assessment"] is False
    assert result["question_count"] >= 1


def test_ungraded_technical_defense_requires_actual_pinned_source_finding():
    c, _, _, _ = setup()
    snapshot = inspect(c)
    question = snapshot["findings"][0]
    response = c.post(f"/api/local/repositories/{snapshot['id']}/defense", json={
        "finding_id": question["id"],
        "response": "I would test the failure path and validate inputs before returning an API response.",
    })
    assert response.status_code == 200
    assert response.json()["graded"] is False
    reviews = c.get(f"/api/local/repositories/{snapshot['id']}/evidence").json()
    assert reviews["answers"][0]["graded"] is False
    assert "response" in reviews["answers"][0]
    assert c.get("/api/local/skillgraph").json()["event_count"] == 0
    wrong = c.post(f"/api/local/repositories/{snapshot['id']}/defense", json={
        "finding_id": "0" * 20, "response": "I would describe potential issues in the surrounding code.",
    })
    assert wrong.status_code == 422


def test_explicit_approval_is_required_and_no_automatic_code_execution():
    c, _, _, docker = setup()
    snapshot = inspect(c)
    body = {"file_path": PATH, "language": "python",
            "cases": [{"stdin": "", "expected_stdout": "Ready"}], "approved": False}
    denied = c.post(f"/api/local/repositories/{snapshot['id']}/smoke", json=body)
    assert denied.status_code == 422
    assert docker.runs == []
    body["approved"] = True
    result = c.post(f"/api/local/repositories/{snapshot['id']}/smoke", json=body)
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["verdict"] == "matched-user-expected-output"
    assert data["expectation_origin"] == "learner-supplied-not-independently-verified"
    assert data["graded_skillgraph"] is False
    assert len(docker.runs) == 1 and docker.runs[0][1] == SOURCE.decode()
    assert c.get("/api/local/skillgraph").json()["event_count"] == 0
    assert c.get("/api/local/skillgraph").json()["github_review_context"]["user_defined_smoke_checks"] == 1


def test_smoke_results_persist_without_storing_user_provided_stdin_or_expected():
    c, review, _, _ = setup()
    snap = inspect(c)
    result = c.post(f"/api/local/repositories/{snap['id']}/smoke", json={
        "file_path": PATH, "language": "python",
        "cases": [{"stdin": "", "expected_stdout": "Ready"}], "approved": True,
    })
    assert result.status_code == 200, result.text
    history = c.get(f"/api/local/repositories/{snap['id']}/evidence").json()
    assert len(history["smoke_checks"]) == 1
    assert "expected_stdout" not in str(history["smoke_checks"])
    assert len(history["smoke_checks"][0]["blob_sha"]) == 40


def test_fails_if_blob_content_does_not_match_pinned_sha():
    def corrupted(request):
        if "/git/blobs/" in request.url.path:
            return httpx.Response(200, json={
                "encoding": "base64", "content": base64.b64encode(b"wrong content").decode()
            })
        return fixture(request)
    c, _, _, _ = setup(provider=GuardedHTTP(corrupted))
    failed = c.post("/api/local/repositories/inspect",
                    json={"repo_url": "https://github.com/sample-user/typed-demo"})
    assert failed.status_code == 503
    assert "No eligible" in failed.json()["detail"]


def test_private_or_rate_limited_repositories_are_not_presented_as_inspected():
    def limited(request):
        if request.url.path == "/repos/sample-user/typed-demo":
            return httpx.Response(403, json={"message": "rate limit"})
        return fixture(request)
    c, _, _, _ = setup(provider=GuardedHTTP(limited))
    result = c.post("/api/local/repositories/inspect",
                    json={"repo_url": "https://github.com/sample-user/typed-demo"})
    assert result.status_code == 503
    assert c.get("/api/local/repositories/history").json()["snapshots"] == []


def test_truncated_tree_is_rejected_no_partial_inspection_claim():
    def truncated(request):
        if "/git/trees/" in request.url.path:
            return httpx.Response(200, json={"tree": [], "truncated": True})
        return fixture(request)
    c, _, _, _ = setup(provider=GuardedHTTP(truncated))
    res = c.post("/api/local/repositories/inspect",
                 json={"repo_url": "https://github.com/sample-user/typed-demo"})
    assert res.status_code == 503
    assert "truncated" in res.json()["detail"]


def test_no_unsafe_source_files_or_arbitrary_commands():
    assert not _file_ok(".env", 30)
    assert not _file_ok("vendor/private.py", 100)
    assert not _file_ok("node_modules/a.js", 100)
    assert not _file_ok("package-lock.json", 250_000)
    c, _, _, docker = setup()
    snap = inspect(c)
    invalid = c.post(f"/api/local/repositories/{snap['id']}/smoke", json={
        "file_path": "README.md", "language": "python",
        "approved": True, "cases": [{"stdin": "", "expected_stdout": "Ready"}],
    })
    assert invalid.status_code == 422
    assert docker.runs == []


def test_smoke_mismatch_remains_user_defined_not_credential_or_assessment():
    c, _, _, _ = setup()
    snap = inspect(c)
    out = c.post(f"/api/local/repositories/{snap['id']}/smoke", json={
        "file_path": PATH, "language": "python", "approved": True,
        "cases": [{"stdin": "ignored", "expected_stdout": "secret invented value"}],
    })
    assert out.status_code == 200
    assert out.json()["verdict"] == "wrong_answer"
    assert out.json()["graded_skillgraph"] is False


def test_defense_and_smoke_persist_across_restart_and_delete_reset(tmp_path):
    c, _, _, _ = setup(tmp_path)
    snap = inspect(c)
    question = snap["findings"][0]
    c.post(f"/api/local/repositories/{snap['id']}/defense", json={
        "finding_id": question["id"],
        "response": "I would verify the HTTP route, errors, and the API's authorization boundary.",
    })
    c.post(f"/api/local/repositories/{snap['id']}/smoke", json={
        "file_path": PATH, "language": "python", "approved": True,
        "cases": [{"stdin": "", "expected_stdout": "Ready"}],
    })
    c2, _, _, _ = setup(tmp_path)
    assert len(c2.get("/api/local/repositories/history").json()["snapshots"]) == 1
    assert len(c2.get(f"/api/local/repositories/{snap['id']}/evidence").json()["answers"]) == 1
    assert c2.delete("/api/local/data").status_code == 200
    assert c2.get("/api/local/repositories/history").json()["snapshots"] == []
    assert c2.get("/api/local/skillgraph").json()["github_review_context"]["snapshots"] == 0


def test_wrong_origin_blocked_before_github_api_or_docker():
    c, _, provider, docker = setup()
    resp = c.post("/api/local/repositories/inspect", headers={"Origin": "https://example.com"},
                  json={"repo_url": "https://github.com/sample-user/typed-demo"})
    assert resp.status_code == 403
    assert provider.calls == [] and docker.runs == []
