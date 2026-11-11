from app.core import DemoEngine
from app.learning import make_roadmap, skill_graph
from fastapi.testclient import TestClient
from app.main import create_app


def test_skillgraph_has_valid_prerequisite_references():
    graph = skill_graph()
    keys = {node["id"] for node in graph["nodes"]}
    assert len(keys) == len(graph["nodes"])
    assert all(edge["from"] in keys and edge["to"] in keys for edge in graph["edges"])


def test_roadmap_is_target_specific_and_prerequisite_aware():
    engine = DemoEngine()
    backend = engine.roadmap("demo-backend")
    ml = engine.roadmap("demo-ml")
    assert backend["activities"][0]["skill"] == "dsa"
    assert ml["activities"][0]["skill"] == "python"
    assert "prerequisite" in ml["activities"][0]["why"].lower()


def test_roadmap_respects_time_budget_and_is_explainable():
    plan = DemoEngine().roadmap("demo-backend", minutes=30)
    assert sum(activity["minutes"] for activity in plan["activities"]) <= 30
    assert all(activity["why"] and activity["content_status"] == "local-curated-demo" for activity in plan["activities"])


def test_roadmap_rejects_bad_budget():
    for value in [0, 10, 121, "45", True]:
        try:
            make_roadmap(DemoEngine().snapshot("demo-ml"), minutes=value)
        except ValueError:
            pass
        else:
            raise AssertionError("Accepted an invalid planning budget")


def test_evidence_is_server_recorded_and_separated():
    engine = DemoEngine()
    engine.submit("demo-backend", "dsa-1", "a")
    events = engine.evidence("demo-backend")
    assert len(events) == 1
    assert events[0]["correct"] is False
    assert events[0]["source"] == "prepezy-server-graded-demo"
    assert engine.evidence("demo-ml") == []


def test_next_question_prefers_unattempted_from_priority_topic():
    engine = DemoEngine()
    assert engine.next_question("demo-backend")["question"]["id"] == "dsa-1"
    engine.submit("demo-backend", "dsa-1", "a")
    next_ = engine.next_question("demo-backend")
    assert next_["question"]["id"] == "dsa-2"
    assert "answer" not in next_["question"]


def test_api_roadmap_and_evidence_are_both_real():
    client = TestClient(create_app(DemoEngine()))
    assert client.get("/api/demo/skillgraph").status_code == 200
    data = client.get("/api/demo/learners/demo-ml/roadmap").json()
    assert data["activities"][0]["skill"] == "python"
    assert client.get("/api/demo/learners/demo-ml/evidence").json()["events"] == []
    assert client.get("/api/demo/learners/demo-ml/next-question").json()["question"]["skill"] == "python"


def test_api_rejects_non_demo_account_and_invalid_planning_minutes():
    client = TestClient(create_app(DemoEngine()))
    assert client.get("/api/demo/learners/unverified/roadmap").status_code == 404
    assert client.get("/api/demo/learners/demo-ml/roadmap?minutes=500").status_code == 422


def test_high_accuracy_still_requests_more_evidence_from_small_sample():
    engine = DemoEngine()
    engine.submit("demo-backend", "dsa-1", "b")
    activity = next(x for x in engine.roadmap("demo-backend")["activities"] if x["skill"] == "dsa")
    assert activity["type"] == "reinforcement"


def test_progress_can_change_recommendation():
    engine = DemoEngine()
    original = engine.snapshot("demo-backend")["recommendation"]["skill"]
    engine.submit("demo-backend", "dsa-1", "b")
    engine.submit("demo-backend", "dsa-2", "a")
    changed = engine.snapshot("demo-backend")["recommendation"]["skill"]
    assert original == "dsa" and changed != original
