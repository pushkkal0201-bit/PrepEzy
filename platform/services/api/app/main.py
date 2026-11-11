"""PrepEzy local demo API. Not suitable for deployment with real accounts."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .core import DemoEngine


class Attempt(BaseModel):
    learner_id: str
    question_id: str
    choice_id: str


def create_app(engine: DemoEngine | None = None) -> FastAPI:
    if os.getenv("PREPEZY_ENV", "development") != "development":
        raise RuntimeError("This synthetic demo API is not production-ready")
    instance = engine or DemoEngine(os.getenv("PREPEZY_DEMO_DB", ":memory:"))
    app = FastAPI(title="PrepEzy Adaptive Foundation", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @app.get("/api/health")
    def health():
        return {"status": "ok", "mode": "synthetic-demo"}

    @app.get("/api/demo/questions")
    def questions():
        return DemoEngine.public_questions()

    @app.get("/api/demo/learners/{learner_id}")
    def learner(learner_id: str):
        try:
            return instance.snapshot(learner_id)
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    @app.post("/api/demo/attempts")
    def attempts(body: Attempt):
        try:
            return instance.submit(body.learner_id, body.question_id, body.choice_id)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/api/skills/cracked")
    def cracked_skills():
        """Discovery only: read existing SKILL.md metadata, never execute instructions."""
        root = Path(__file__).resolve().parents[4] / "skills"
        result = []
        for file in sorted(root.glob("*/*/SKILL.md")):
            result.append({"category": file.parent.parent.name, "name": file.parent.name, "status": "catalogued-not-integrated"})
        return result

    return app


app = create_app()
