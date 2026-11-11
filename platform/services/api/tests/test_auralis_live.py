"""Runs against actual Auralis upstream when explicitly enabled in CI/local.

This is not executed by the default unit suite; it requires PREPEZY_RUN_AURALIS_LIVE=1
and a separately running, pinned Auralis local server on port 8001.
"""
from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

from app.auralis import AuralisClient
from app.core import DemoEngine
from app.main import create_app


@pytest.mark.skipif(os.getenv("PREPEZY_RUN_AURALIS_LIVE") != "1", reason="Requires real local Auralis server")
def test_real_upstream_auralis_interview_start_answer_finish():
    client = TestClient(create_app(DemoEngine(), auralis_client=AuralisClient()))
    health = client.get("/api/demo/integrations/auralis")
    assert health.status_code == 200 and health.json()["connected"] is True, health.text
    started = client.post("/api/demo/learners/demo-backend/interviews")
    assert started.status_code == 200, started.text
    session = started.json()
    assert session["provider"] == "scripted-demo" and session["status"] == "active"
    assert session["current"]["text"]
    answered = client.post(
        "/api/demo/learners/demo-backend/interviews/" + session["id"] + "/answer",
        json={"question_id": session["current"]["id"], "text": "I would test concurrent requests and database transactions."},
    )
    assert answered.status_code == 200, answered.text
    assert answered.json()["answer_count"] == 1
    finished = client.post("/api/demo/learners/demo-backend/interviews/" + session["id"] + "/finish")
    assert finished.status_code == 200, finished.text
    result = finished.json()
    assert result["status"] == "completed"
    assert result["report"]["demo"] is True and result["report"]["scored"] is False
    assert all(item["score"] is None for item in result["report"]["items"])
    roadmap = client.get("/api/demo/learners/demo-backend/roadmap").json()
    assert roadmap["activities"][0]["type"] == "interview-reflection"
    catalog = client.get("/api/demo/integrations/auralis/challenges")
    assert catalog.status_code == 200 and catalog.json()["challenges"]
    graded = client.post("/api/demo/learners/demo-backend/code", json={
        "challenge_id": "sum_numbers",
        "code": "def solve(nums):\\n    return sum(nums)",
    })
    assert graded.status_code == 200, graded.text
    result = graded.json()["result"]
    assert result["source"] == "restricted_ast_test_runner"
    assert result["passed"] == result["total"] == 5
    python = next(c for c in graded.json()["learner"]["competencies"] if c["id"] == "python")
    assert python["attempts"] == 1 and python["correct"] == 1
