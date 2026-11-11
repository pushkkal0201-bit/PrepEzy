"""Contract tests exercise real adapter requests through an HTTP transport spy.

No claim is made that these tests execute the upstream Auralis application.
The separate live integration check does that when configured.
"""
from __future__ import annotations

import asyncio
import httpx
import pytest
from fastapi.testclient import TestClient

from app.auralis import AuralisClient, AuralisGatewayError, public_session
from app.core import DemoEngine
from app.main import create_app

SID = "session_" + "a" * 32
QID = "q_" + "b" * 32


def fake_session(status="active", answers=0, report=None):
    return {
        "id": SID,
        "setup": {"provider": "demo", "synthetic_data": True, "cv": "A" * 45, "jd": "B" * 45},
        "plan": {"role": "Backend Engineer"},
        "status": status,
        "current": {"id": QID, "text": "How would you test your implementation?", "competency_id": "c1", "difficulty": "applied", "source": "scripted_demo"},
        "turns": [
            {"id": f"turn_{i}", "kind": "answer", "text": "I would test errors.", "question": {"text": "Test?"}}
            for i in range(answers)
        ],
        "report": report,
    }


def make_transport(calls):
    def handler(request):
        calls.append((request.method, request.url.path, request.headers.get("X-Owner-Token")))
        assert request.url.host == "127.0.0.1"
        assert request.headers.get("X-Owner-Token") and len(request.headers["X-Owner-Token"]) == 64
        p = request.url.path
        if p == "/api/practical/catalog":
            return httpx.Response(200, json={
                "execution_policy": "Restricted AST expression interpretation; no arbitrary Python execution",
                "challenges": [{"id": "sum_numbers", "title": "Sum a list", "description": "Return total", "starter": "def solve(nums):\n    return 0", "hint": "Use sum."}],
            })
        if p == "/api/practical/code":
            return httpx.Response(200, json={
                "challenge_id": "sum_numbers", "passed": 5, "total": 5,
                "all_passed": True, "source": "restricted_ast_test_runner",
                "tests": [{"test": i + 1, "status": "pass", "public": i < 2} for i in range(5)],
            })
        if p == "/api/health":
            return httpx.Response(200, json={"status": "ok", "demo_available": True})
        if p == "/api/sessions" and request.method == "POST":
            return httpx.Response(200, json=fake_session(status="ready"))
        if p.endswith("/start"):
            return httpx.Response(200, json=fake_session())
        if p.endswith("/actions"):
            return httpx.Response(200, json=fake_session(answers=1))
        if p.endswith("/finish"):
            report = {"demo": True, "summary": "Scripted, no AI grade.", "items": [{"name": "Testing", "score": None, "status": "insufficient_evidence", "evidence_ids": ["turn_0"], "feedback": "Review your answer."}], "limitations": ["Not graded"]}
            return httpx.Response(200, json=fake_session(status="completed", answers=1, report=report))
        if p == f"/api/sessions/{SID}":
            return httpx.Response(200, json=fake_session())
        return httpx.Response(404, json={"detail": "not found"})
    return httpx.MockTransport(handler)


def test_url_guard_refuses_remote_hosts():
    for url in ("https://127.0.0.1:8001", "http://external.example:8001", "http://127.0.0.1:8001/path", "http://localhost:8001?x=1", "http://user:pass@localhost:8001"):
        with pytest.raises(ValueError):
            AuralisClient(url)


def test_unconfigured_service_does_not_claim_connection():
    client = TestClient(create_app(DemoEngine(), auralis_client=None))
    res = client.get("/api/demo/integrations/auralis")
    assert res.json()["enabled"] is False
    assert client.post("/api/demo/learners/demo-backend/interviews").status_code == 503


def test_real_http_contract_and_synthetic_owner_separation():
    calls = []
    adapter = AuralisClient(transport=make_transport(calls))
    left = asyncio.run(adapter.create_and_start("demo-backend"))
    right = asyncio.run(adapter.create_and_start("demo-ml"))
    assert left["status"] == right["status"] == "active"
    assert calls[0][2] != calls[2][2]
    assert all(host for _, _, host in calls)


def test_gateway_full_interview_flow_records_actual_upstream_results():
    calls = []
    gateway = TestClient(create_app(DemoEngine(), auralis_client=AuralisClient(transport=make_transport(calls))))
    assert gateway.get("/api/demo/integrations/auralis").json()["connected"] is True
    initial = gateway.post("/api/demo/learners/demo-backend/interviews")
    assert initial.status_code == 200, initial.text
    created = initial.json()
    assert created["id"] == SID and created["current"]["id"] == QID
    assert "cv" not in created
    blocked = gateway.get(f"/api/demo/learners/demo-ml/interviews/{SID}")
    assert blocked.status_code == 404
    answered = gateway.post(f"/api/demo/learners/demo-backend/interviews/{SID}/answer", json={"question_id": QID, "text": "I would cover edge cases."})
    assert answered.status_code == 200, answered.text
    finished = gateway.post(f"/api/demo/learners/demo-backend/interviews/{SID}/finish")
    assert finished.status_code == 200, finished.text
    report = finished.json()["report"]
    assert report["demo"] is True and report["scored"] is False
    assert report["items"][0]["score"] is None
    roadmap = gateway.get("/api/demo/learners/demo-backend/roadmap").json()
    assert roadmap["activities"][0]["type"] == "interview-reflection"
    assert "unscored" in roadmap["activities"][0]["why"].lower()
    evidence = gateway.get(f"/api/demo/learners/demo-backend/interviews")
    assert evidence.status_code == 200 and evidence.json()["interviews"][0]["answer_count"] == 1


def test_bad_auralis_session_and_fake_scores_are_never_trusted():
    with pytest.raises(AuralisGatewayError):
        public_session({"id": SID, "setup": {"provider": "groq", "synthetic_data": True}})
    report = {"demo": True, "summary": "Synthetic", "items": [{"score": 4, "name": "Testing"}]}
    result = public_session(fake_session(status="completed", report=report))
    assert result["report"]["items"][0]["score"] is None


def test_auralis_unavailable_is_explicit():
    adapter = AuralisClient(transport=httpx.MockTransport(lambda req: httpx.Response(503, json={"detail": "offline"})))
    result = TestClient(create_app(DemoEngine(), auralis_client=adapter)).get("/api/demo/integrations/auralis")
    assert result.status_code == 200
    assert result.json()["connected"] is False


def test_restricted_ast_grades_update_skillgraph_without_retry_inflation():
    adapter = AuralisClient(transport=make_transport([]))
    client = TestClient(create_app(DemoEngine(), auralis_client=adapter))
    catalog = client.get("/api/demo/integrations/auralis/challenges")
    assert catalog.status_code == 200
    assert catalog.json()["challenges"][0]["id"] == "sum_numbers"
    before = client.get("/api/demo/learners/demo-backend").json()
    payload = {"challenge_id": "sum_numbers", "code": "def solve(nums):\n    return sum(nums)"}
    response = client.post("/api/demo/learners/demo-backend/code", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["result"]["source"] == "restricted_ast_test_runner"
    after = response.json()["learner"]
    python = next(c for c in after["competencies"] if c["id"] == "python")
    assert python["attempts"] == 1 and python["correct"] == 1
    assert client.post("/api/demo/learners/demo-backend/code", json=payload).status_code == 200
    again = client.get("/api/demo/learners/demo-backend").json()
    python = next(c for c in again["competencies"] if c["id"] == "python")
    assert python["attempts"] == 1
    assert len(client.get("/api/demo/learners/demo-backend/code/evidence").json()["results"]) == 2
    assert client.get("/api/demo/learners/demo-ml/code/evidence").json()["results"] == []
    assert before["total_attempts"] == after["total_attempts"] == 0


def test_unverified_auralis_scores_are_rejected():
    engine = DemoEngine()
    with pytest.raises(ValueError):
        engine.record_auralis_code("demo-ml", {
            "challenge_id": "sum_numbers", "passed": 5, "total": 5,
            "all_passed": True, "source": "fictional_provider",
        })
    assert engine.code_history("demo-ml") == []
