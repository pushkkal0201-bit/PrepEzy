"""Stage 13: persisted mock-interview orchestration and evidence boundaries."""
import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core import DemoEngine
from app.local_lab import LocalLab
from app.main import create_app


def setup(path=":memory:"):
    local = LocalLab(path)
    return TestClient(create_app(DemoEngine(), local_lab=local)), local


def begin(api, **options):
    result = api.post("/api/local/mock-interviews", json=options)
    assert result.status_code == 200, result.text
    return result.json()


def respond(api, sid, question_id, probe="verification"):
    result = api.post(
        "/api/local/mock-interviews/" + sid + "/responses",
        json={"question_id": question_id, "probe": probe,
              "response": "I would reproduce the issue with controlled fixtures and explain the alternative approach."},
    )
    assert result.status_code == 200, result.text
    return result.json()


def test_real_workflow_uses_skillgraph_priority_but_does_not_fabricate_grades():
    api, local = setup()
    original = api.get("/api/local/skillgraph").json()
    created = begin(api)
    assert created["focus"] == "balanced"
    assert created["next_question"]["id"] == "coding"
    assert len(created["questions"]) == 4
    assert not created["next_question"]["evidence"]
    assert "No verified local coding-arena attempt" in created["next_question"]["question"]
    assert all(q["graded"] is False for q in created["questions"])
    assert created["report"] is None

    sid = created["id"]
    first = respond(api, sid, "coding", "edge_cases")
    assert first["next_question"]["id"] == "coding-followup"
    assert "boundary case" in first["next_question"]["question"]
    assert first["total"] == 5
    assert first["answered"] == 1

    assert api.post("/api/local/mock-interviews/" + sid + "/responses", json={
        "question_id": "coding", "response": "This answer is long enough to pass input validation.",
        "probe": "tradeoffs",
    }).status_code == 422

    follow = respond(api, sid, "coding-followup")
    assert follow["next_question"]["id"] == "technical"
    assert follow["total"] == 5
    assert follow["questions"][0]["response"]["answer"].startswith("I would reproduce")

    while follow["status"] == "active":
        follow = respond(api, sid, follow["next_question"]["id"], "verification")
    assert follow["status"] == "completed"
    assert follow["answered"] == follow["total"] == 7
    assert follow["report"]["completion"] == "all_questions_answered"
    assert len(follow["report"]["next_practice"]) == 4
    assert "Ungraded" in follow["report"]["assessment"]
    after = api.get("/api/local/skillgraph").json()
    assert after == original
    assert api.get("/api/local/mock-interviews").json()["sessions"][0]["id"] == sid


def test_checked_coding_provenance_is_real_attempt_not_derived_interview_score():
    api, local = setup()
    with local.lock:
        local.db.execute("""INSERT INTO arena_attempts(
            session_id,problem,language,passed,total,verdict,source_sha256,created_at
        ) VALUES (?,?,?,?,?,?,?,?)""",
                         ("fixture", "balanced-brackets", "java", 3, 5,
                          "wrong_answer", "0" * 64, 1794500000))
        local.db.commit()
    before = api.get("/api/local/skillgraph").json()
    item = begin(api, focus="coding")
    coding = item["next_question"]
    assert "balanced-brackets" in coding["question"]
    assert "3/5" in coding["question"]
    assert "wrong_answer" in coding["question"]
    assert coding["evidence"][0]["type"] == "checked_coding_attempt"
    assert coding["evidence"][0]["ref"].startswith("coding:")
    assert coding["evidence"][0]["verified_test_result"] is True
    assert api.get("/api/local/skillgraph").json() == before


def test_pinned_github_source_marker_remains_ungraded_and_is_not_ownership_proof():
    api, local = setup()
    findings = [{
        "id": "f" * 20, "kind": "database", "path": "app/store.py",
        "line": 9, "question": "Which failure would you test?",
        "source_url": "https://github.com/sample/checkout/blob/" + "a" * 40 + "/app/store.py#L9",
    }]
    with local.lock:
        cursor = local.db.execute(
            """INSERT INTO github_review_snapshots(
                repo,repo_url,commit_sha,tree_sha,created_at,files_json,findings_json,inventory_json
            ) VALUES (?,?,?,?,?,?,?,?)""",
            ("sample/checkout", "https://github.com/sample/checkout",
             "a" * 40, "b" * 40, "2026-11-12", "[]", json.dumps(findings), "{}"),
        )
        local.db.commit()
    sid = cursor.lastrowid
    response = begin(api, focus="project", snapshot_id=sid)
    project = response["next_question"]
    assert project["id"] == "project"
    assert "app/store.py" in project["question"]
    evidence = project["evidence"][0]
    assert evidence["type"] == "unscored_github_marker"
    assert evidence["source_url"].endswith("/app/store.py#L9")
    assert evidence["commit_sha"] == "a" * 40
    assert evidence["verified_test_result"] is False
    assert project["graded"] is False
    assert begin(api, focus="balanced")["questions"][2]["id"] == "project"
    invalid = api.post("/api/local/mock-interviews", json={
        "focus": "project", "snapshot_id": sid + 100,
    })
    assert invalid.status_code == 422


def test_session_persists_over_restart_and_deletion_purges_answers(tmp_path):
    filename = tmp_path / "stage13.sqlite"
    api, local = setup(filename)
    new = begin(api, focus="project")
    sid = new["id"]
    one = respond(api, sid, "project", "tradeoffs")
    assert one["next_question"]["id"] == "project-followup"
    reopened, local2 = setup(filename)
    record = reopened.get("/api/local/mock-interviews/" + sid)
    assert record.status_code == 200
    assert record.json()["next_question"]["probe"] == "tradeoffs"
    assert record.json()["questions"][0]["response"]["answer"]
    finished = reopened.post("/api/local/mock-interviews/" + sid + "/finish")
    assert finished.status_code == 200
    assert finished.json()["status"] == "stopped"
    assert finished.json()["report"]["completion"] == "ended_early"
    assert reopened.post("/api/local/mock-interviews/" + sid + "/responses", json={
        "question_id": "project-followup",
        "response": "I would check the expected outputs in several tests.",
        "probe": "verification",
    }).status_code == 422
    assert reopened.delete("/api/local/mock-interviews").json()["cleared"] is True
    assert reopened.get("/api/local/mock-interviews/" + sid).status_code == 404
    assert not reopened.get("/api/local/mock-interviews").json()["sessions"]


def test_global_local_reset_clears_mock_transcripts_without_touching_demo():
    api, local = setup()
    sid = begin(api)["id"]
    respond(api, sid, "coding")
    result = api.delete("/api/local/data")
    assert result.status_code == 200
    assert "mock_interviews" in result.json()["sources"]
    assert api.get("/api/local/mock-interviews/" + sid).status_code == 404
    assert api.get("/api/local/skillgraph").json()["event_count"] == 0


def test_validation_sequence_and_local_only_boundary():
    api, local = setup()
    assert api.post("/api/local/mock-interviews", json={"focus": "invalid"}).status_code == 422
    assert api.post("/api/local/mock-interviews", json={"snapshot_id": -1}).status_code == 422
    sid = begin(api)["id"]
    bad = api.post("/api/local/mock-interviews/" + sid + "/responses", json={
        "question_id": "technical",
        "response": "A thirty-plus-character response for testing.",
        "probe": "edge_cases",
    })
    assert bad.status_code == 422
    assert api.get("/api/local/mock-interviews/not-a-valid-id").status_code == 404
    blocked = api.post("/api/local/mock-interviews", headers={
        "origin": "https://example.com"
    }, json={})
    assert blocked.status_code == 403
