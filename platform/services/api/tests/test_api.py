from fastapi.testclient import TestClient
from app.core import DemoEngine
from app.main import create_app


def test_health_and_questions():
    client = TestClient(create_app(DemoEngine()))
    assert client.get("/api/health").json()["mode"] == "synthetic-demo"
    assert len(client.get("/api/demo/questions").json()) == 5


def test_submission_updates_recommendations():
    client = TestClient(create_app(DemoEngine()))
    response = client.post("/api/demo/attempts", json={"learner_id": "demo-backend", "question_id": "dsa-1", "choice_id": "a"})
    assert response.status_code == 200
    assert response.json()["correct"] is False
    assert client.get("/api/demo/learners/demo-backend").json()["total_attempts"] == 1


def test_missing_demo_learner_is_not_exposed():
    client = TestClient(create_app(DemoEngine()))
    assert client.get("/api/demo/learners/private-user").status_code == 404
