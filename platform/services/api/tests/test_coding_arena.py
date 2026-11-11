"""Coding Arena API tests; injected runner never executes host code."""
import pytest
from fastapi.testclient import TestClient

from app.coding_arena import CodingArena, DockerRunner, JudgeUnavailable, PROBLEMS, public_problems
from app.core import DemoEngine
from app.local_lab import LocalLab
from app.main import create_app
from app.unified import UnifiedEvidence


class FakeDocker:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.runs = []

    def available(self, language):
        return self.enabled and language in ("java", "python", "javascript")

    def run(self, language, source, cases):
        self.runs.append((language, source, len(cases)))
        return [{"case": i + 1, "status": "accepted" if source == "VALID CODE SAMPLE" else "wrong_answer"}
                for i in range(len(cases))]


def make(clock=None, available=True):
    local = LocalLab()
    graph = UnifiedEvidence(local)
    graph.arena.runner = FakeDocker(available)
    graph.arena.clock = clock or (lambda: 1700000000)
    return local, graph


def test_public_catalog_has_no_hidden_tests():
    catalog = public_problems()
    assert len(catalog["problems"]) == 4
    assert set(catalog["languages"]) == {"python", "javascript", "java"}
    assert all("cases" not in p for p in catalog["problems"])
    assert all(len(p["public_examples"]) == 1 for p in catalog["problems"])
    assert all("source" not in p for p in catalog["problems"])


def test_runner_requires_docker_and_no_host_fallback(monkeypatch):
    import app.coding_arena as module
    monkeypatch.setattr(module.shutil, "which", lambda _: None)
    judge = DockerRunner()
    assert judge.available("python") is False
    with pytest.raises(JudgeUnavailable):
        judge.run("python", "print('hello world')", [("", "hello world")])


def test_timed_and_practice_session_persist():
    local, graph = make()
    session = graph.arena.start("timed", 15)
    assert session["deadline"] - session["created_at"] == 15 * 60
    assert graph.arena.start("timed", 60)["id"] == session["id"]
    assert graph.arena.current_session()["status"] == "active"
    graph.arena.finish(session["id"])
    assert graph.arena.current_session()["status"] == "finished"
    other = CodingArena(local.db, local.lock, runner=FakeDocker(), clock=lambda: 1700000000)
    new = other.start("practice", 30)
    assert new["id"] != session["id"]
    assert new["deadline"] - new["created_at"] == 4 * 60 * 60


def test_time_expiry_prevents_submission():
    current = [1000]
    _, graph = make(clock=lambda: current[0])
    session = graph.arena.start("timed", 15)
    current[0] = 2000
    assert graph.arena.current_session()["status"] == "expired"
    with pytest.raises(ValueError):
        graph.arena.submit(session["id"], "sum-pair", "python", "VALID CODE SAMPLE")
    assert graph.arena.evidence() == []


def test_success_and_first_attempt_skillgraph():
    _, graph = make()
    session = graph.arena.start("timed", 30)
    result = graph.arena.submit(session["id"], "sum-pair", "python", "VALID CODE SAMPLE")
    assert result["verdict"] == "accepted"
    assert result["tests_passed"] == len(PROBLEMS["sum-pair"]["cases"])
    assert len(result["checks"]) == result["tests_total"]
    graph_state = graph.skillgraph()
    coding = next(s for s in graph_state["skills"] if s["id"] == "coding")
    assert coding["distinct_assessments"] == 1
    assert coding["first_try_correct_unassisted"] == 1
    assert graph_state["sources"]["coding_arena"] == 1


def test_retry_keeps_original_wrong_first_try():
    _, graph = make()
    sid = graph.arena.start("practice", 30)["id"]
    graph.arena.submit(sid, "sum-pair", "java", "INCORRECT SAMPLE")
    graph.arena.submit(sid, "sum-pair", "python", "VALID CODE SAMPLE")
    score = next(x for x in graph.skillgraph()["skills"] if x["id"] == "coding")
    assert score["distinct_assessments"] == 1
    assert score["first_try_correct_unassisted"] == 0
    assert graph.skillgraph()["sources"]["coding_arena"] == 2


def test_no_untrusted_grade_could_be_supplied():
    _, graph = make()
    sid = graph.arena.start("timed", 30)["id"]
    with pytest.raises(ValueError):
        graph.arena.submit(sid, "secret-problem", "python", "VALID CODE SAMPLE")
    with pytest.raises(ValueError):
        graph.arena.submit(sid, "sum-pair", "haskell", "VALID CODE SAMPLE")
    with pytest.raises(ValueError):
        graph.arena.submit(sid, "sum-pair", "python", "x")
    assert graph.arena.evidence() == []


def test_no_runtime_when_image_not_ready():
    _, graph = make(available=False)
    with pytest.raises(JudgeUnavailable):
        graph.arena.start("timed", 15)
    assert graph.arena.current_session() is None


def test_history_contains_hash_not_source():
    _, graph = make()
    sid = graph.arena.start("timed", 30)["id"]
    graph.arena.submit(sid, "sum-pair", "java", "VALID CODE SAMPLE")
    evidence = graph.arena.evidence()[0]
    assert len(evidence["source_sha256"]) == 64
    assert "VALID CODE SAMPLE" not in str(evidence)
    events = graph.evidence()["events"]
    assert events[0]["kind"] == "docker_code_execution"
    assert events[0]["details"]["verdict"] == "accepted"


def test_reset_removes_sessions_and_arena_evidence():
    _, graph = make()
    sid = graph.arena.start("timed", 30)["id"]
    graph.arena.submit(sid, "sum-pair", "python", "VALID CODE SAMPLE")
    graph.clear()
    assert graph.arena.current_session() is None
    assert graph.arena.evidence() == []
    assert graph.skillgraph()["event_count"] == 0


def test_api_end_to_end_with_fake_runner():
    lab = LocalLab()
    app = create_app(DemoEngine(), local_lab=lab)
    from app.coding_arena import CodingArena
    # The API's UnifiedEvidence owns the runner. Swap it through its known
    # instance only for tests, never via a public endpoint.
    # Patch DockerRunner globally here to make the test independent of Docker.
    client = TestClient(app)
    catalog = client.get("/api/local/arena/problems")
    assert catalog.status_code == 200
    assert len(catalog.json()["problems"]) == 4
    assert client.get("/api/local/arena/status").status_code == 200
    bad = client.post("/api/local/arena/submissions", json={
        "session_id": "0" * 32, "problem_id": "sum-pair",
        "language": "python", "source": "VALID CODE SAMPLE",
        "passed": True
    })
    assert bad.status_code == 422
    assert client.get("/api/local/arena/evidence").json()["attempts"] == []


def test_only_expected_duration_accepted():
    _, graph = make()
    for duration in [0, 3, 17, 120]:
        with pytest.raises(ValueError):
            graph.arena.start("timed", duration)
    assert graph.arena.start("timed", 30)["status"] == "active"
