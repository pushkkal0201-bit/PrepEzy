from pathlib import Path

from fastapi.testclient import TestClient

from app.core import DemoEngine
from app.cracked import PATTERNS, public_catalog
from app.main import create_app


def solve(coach, learner, pattern, answers=("a", "b", "b")):
    """Follow a real guided session using the server's current stage IDs."""
    for step, choice in zip(PATTERNS[pattern]["steps"], answers):
        assert coach.state(learner, pattern)["step"]["id"] == step["id"]
        result = coach.submit(learner, pattern, step["id"], choice)
        assert result["correct"] is True
    assert coach.state(learner, pattern)["completed"]


def test_catalog_never_exposes_answer_keys():
    items = public_catalog()
    assert items["adaptation"].startswith("PrepEzy-authored")
    assert items["source_skill"].endswith("pattern-coach/SKILL.md")
    assert len(items["patterns"]) == 4
    assert all("answer" not in str(item).lower() for item in items["patterns"])
    state = DemoEngine().coach.state("demo-backend", "two-pointers")
    assert "answer" not in state["step"]
    assert "why" not in state["step"]


def test_socratic_stages_are_enforced():
    coach = DemoEngine().coach
    assert coach.state("demo-backend", "two-pointers")["step"]["id"] == "brute"
    try:
        coach.submit("demo-backend", "two-pointers", "transfer", "b")
    except ValueError:
        pass
    else:
        raise AssertionError("Skipped a Socratic stage")
    wrong = coach.submit("demo-backend", "two-pointers", "brute", "b")
    assert wrong["correct"] is False
    assert coach.state("demo-backend", "two-pointers")["step"]["id"] == "brute"
    assert coach.submit("demo-backend", "two-pointers", "brute", "a")["correct"]
    assert coach.state("demo-backend", "two-pointers")["step"]["id"] == "signal"


def test_completed_pattern_produces_one_dsa_transfer_observation():
    engine = DemoEngine()
    before = next(x for x in engine.snapshot("demo-backend")["competencies"] if x["id"] == "dsa")
    solve(engine.coach, "demo-backend", "two-pointers", ("a", "b", "b"))
    after = next(x for x in engine.snapshot("demo-backend")["competencies"] if x["id"] == "dsa")
    assert after["attempts"] == before["attempts"] + 1
    assert after["correct"] == before["correct"] + 1
    assert len(engine.coach.independent_transfer_grades("demo-backend")) == 1


def test_assisted_transfer_is_not_unassisted_proficiency():
    engine = DemoEngine()
    coach = engine.coach
    coach.submit("demo-ml", "bfs", "brute", "b")
    coach.submit("demo-ml", "bfs", "signal", "a")
    hint = coach.hint("demo-ml", "bfs")
    assert hint["counts_as_assistance"] is True
    assert hint["step_id"] == "transfer"
    coach.submit("demo-ml", "bfs", "transfer", "b")
    grade = coach.independent_transfer_grades("demo-ml")[0]
    assert grade["assisted"] is True
    assert grade["correct"] is False
    assert coach.state("demo-ml", "bfs")["completed"] is True


def test_wrong_first_transfer_cannot_be_rewritten_as_first_try_success():
    engine = DemoEngine()
    coach = engine.coach
    coach.submit("demo-backend", "sliding-window", "brute", "a")
    coach.submit("demo-backend", "sliding-window", "signal", "c")
    assert coach.submit("demo-backend", "sliding-window", "transfer", "a")["correct"] is False
    assert coach.submit("demo-backend", "sliding-window", "transfer", "b")["correct"] is True
    assert coach.independent_transfer_grades("demo-backend")[0]["correct"] is False
    assert coach.state("demo-backend", "sliding-window")["completed"] is True


def test_patterns_and_evidence_are_separated_for_synthetic_demo_accounts():
    engine = DemoEngine()
    engine.coach.submit("demo-backend", "two-pointers", "brute", "a")
    assert engine.coach.evidence("demo-ml") == []
    assert engine.coach.state("demo-ml", "two-pointers")["completed_steps"] == 0
    assert len(engine.coach.evidence("demo-backend")) == 1


def test_pattern_progress_survives_local_sqlite_restart(tmp_path):
    path = tmp_path / "coach.sqlite"
    first = DemoEngine(path)
    first.coach.submit("demo-ml", "binary-search-answer", "brute", "a")
    assert DemoEngine(path).coach.state("demo-ml", "binary-search-answer")["step"]["id"] == "signal"


def test_roadmap_identifies_curated_dsa_pattern():
    engine = DemoEngine()
    plan = engine.roadmap("demo-backend")
    dsa = next(x for x in plan["activities"] if x["skill"] == "dsa")
    assert dsa["suggested_pattern"]["source_skill"].endswith("pattern-coach/SKILL.md")
    assert dsa["suggested_pattern"]["pattern_id"] == "two-pointers"


def test_api_pattern_coach_is_functional_and_server_checked():
    client = TestClient(create_app(DemoEngine()))
    catalog = client.get("/api/demo/cracked/patterns").json()
    assert len(catalog["patterns"]) == 4
    u = "/api/demo/learners/demo-backend/cracked/patterns/two-pointers"
    state = client.get(u).json()
    assert state["step"]["id"] == "brute"
    hint = client.post(u + "/hint").json()
    assert hint["counts_as_assistance"]
    rejected = client.post(u + "/answers", json={"step_id": "transfer", "choice_id": "b"})
    assert rejected.status_code == 422
    result = client.post(u + "/answers", json={"step_id": "brute", "choice_id": "a"})
    assert result.status_code == 200
    assert result.json()["result"]["correct"] is True
    assert client.get(u).json()["step"]["id"] == "signal"
    assert client.get("/api/demo/learners/demo-backend/cracked/evidence").json()["results"]


def test_bad_user_pattern_and_choice_are_rejected():
    client = TestClient(create_app(DemoEngine()))
    base = "/api/demo/learners/"
    assert client.get(base + "not-real/cracked/patterns/two-pointers").status_code == 404
    assert client.get(base + "demo-backend/cracked/patterns/not-a-pattern").status_code == 404
    r = client.post(base + "demo-backend/cracked/patterns/two-pointers/answers",
                    json={"step_id": "brute", "choice_id": "invalid"})
    assert r.status_code == 422


def test_core_learning_history_reflects_real_pattern_evidence():
    engine = DemoEngine()
    engine.coach.submit("demo-backend", "two-pointers", "brute", "a")
    snap = engine.snapshot("demo-backend")
    assert len(snap["cracked_pattern_evidence"]) == 1
    assert snap["cracked_recommendation"]["pattern_id"] == "two-pointers"
    assert snap["cracked_pattern_evidence"][0]["source"] == "prepezy-curated-cracked-pattern-coach"
