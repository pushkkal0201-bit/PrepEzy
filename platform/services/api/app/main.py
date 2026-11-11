"""PrepEzy local demo API. Not suitable for deployment with real accounts."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from pydantic import Field
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .core import DemoEngine
from .auralis import AuralisClient, AuralisGatewayError, public_session


class CodingAttempt(BaseModel):
    challenge_id: str = Field(min_length=1, max_length=48)
    code: str = Field(min_length=8, max_length=2500)


class InterviewAnswer(BaseModel):
    question_id: str = Field(min_length=3, max_length=80)
    text: str = Field(min_length=1, max_length=8000)


class Attempt(BaseModel):
    learner_id: str
    question_id: str
    choice_id: str


def create_app(engine: DemoEngine | None = None, auralis_client: AuralisClient | None = None) -> FastAPI:
    if os.getenv("PREPEZY_ENV", "development") != "development":
        raise RuntimeError("This synthetic demo API is not production-ready")
    instance = engine or DemoEngine(os.getenv("PREPEZY_DEMO_DB", ":memory:"))
    # Explicit opt-in. No other hosts may be used, and no login/account is created.
    auralis = auralis_client
    if auralis is None and os.getenv("PREPEZY_AURALIS_ENABLED") == "1":
        auralis = AuralisClient(os.getenv("PREPEZY_AURALIS_URL", "http://127.0.0.1:8001"))
    app = FastAPI(title="PrepEzy Adaptive Foundation", version="0.3.0")
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

    @app.get("/api/demo/skillgraph")
    def skillgraph():
        from .learning import skill_graph
        return skill_graph()

    @app.get("/api/demo/learners/{learner_id}/roadmap")
    def roadmap(learner_id: str, minutes: int = Query(default=45, ge=15, le=120)):
        try:
            return instance.roadmap(learner_id, minutes=minutes)
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    @app.get("/api/demo/learners/{learner_id}/evidence")
    def evidence(learner_id: str):
        try:
            return {"learner_id": learner_id, "events": instance.evidence(learner_id)}
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    @app.get("/api/demo/learners/{learner_id}/next-question")
    def next_question(learner_id: str):
        try:
            return instance.next_question(learner_id)
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    def local_auralis() -> AuralisClient:
        if auralis is None:
            raise HTTPException(503, "Auralis is not connected. Start local Auralis on port 8001 and enable PREPEZY_AURALIS_ENABLED=1.")
        return auralis

    @app.get("/api/demo/integrations/auralis")
    async def auralis_status():
        if auralis is None:
            return {"enabled": False, "connected": False, "mode": "local-scripted-demo"}
        try:
            health = await auralis.health()
            connected = health.get("status") == "ok" and health.get("demo_available") is True
            return {"enabled": True, "connected": connected, "mode": "local-scripted-demo",
                    "upstream_version": health.get("version"), "message": (
                        "Actual local Auralis scripted engine responding." if connected
                        else "Local Auralis does not advertise scripted-demo mode."
                    )}
        except AuralisGatewayError as error:
            return {"enabled": True, "connected": False, "mode": "local-scripted-demo", "message": str(error)}

    @app.get("/api/demo/integrations/auralis/challenges")
    async def auralis_challenges(learner_id: str = "demo-backend"):
        try:
            instance.validate_learner(learner_id)
            return await local_auralis().coding_catalog(learner_id)
        except AuralisGatewayError as error:
            raise HTTPException(error.status, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.post("/api/demo/learners/{learner_id}/code")
    async def auralis_coding_attempt(learner_id: str, body: CodingAttempt):
        try:
            instance.validate_learner(learner_id)
            result = await local_auralis().grade_code(learner_id, body.challenge_id, body.code)
            instance.record_auralis_code(learner_id, result)
            return {"result": result, "learner": instance.snapshot(learner_id)}
        except AuralisGatewayError as error:
            raise HTTPException(error.status, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/api/demo/learners/{learner_id}/code/evidence")
    def auralis_code_evidence(learner_id: str):
        try:
            return {"learner_id": learner_id, "results": instance.code_history(learner_id)}
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    @app.get("/api/demo/learners/{learner_id}/interviews")
    def interview_history(learner_id: str):
        try:
            return {"learner_id": learner_id, "interviews": instance.interview_history(learner_id)}
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    @app.post("/api/demo/learners/{learner_id}/interviews")
    async def start_interview(learner_id: str):
        try:
            instance.validate_learner(learner_id)
            client = local_auralis()
            health = await client.health()
            if health.get("status") != "ok" or health.get("demo_available") is not True:
                raise HTTPException(503, "Auralis scripted local mode is unavailable.")
            upstream = public_session(await client.create_and_start(learner_id))
            instance.register_interview(learner_id, upstream["id"], upstream["status"], upstream["answer_count"])
            return upstream
        except AuralisGatewayError as error:
            raise HTTPException(error.status, str(error)) from error
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    def require_link(learner_id: str, sid: str) -> AuralisClient:
        try:
            linked = instance.owns_interview(learner_id, sid)
        except ValueError as error:
            raise HTTPException(404, str(error)) from error
        if not linked:
            raise HTTPException(404, "Interview not linked to that synthetic demo learner.")
        return local_auralis()

    @app.get("/api/demo/learners/{learner_id}/interviews/{sid}")
    async def get_interview(learner_id: str, sid: str):
        client = require_link(learner_id, sid)
        try:
            return public_session(await client.get(learner_id, sid))
        except AuralisGatewayError as error:
            raise HTTPException(error.status, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.post("/api/demo/learners/{learner_id}/interviews/{sid}/answer")
    async def answer_interview(learner_id: str, sid: str, body: InterviewAnswer):
        client = require_link(learner_id, sid)
        try:
            upstream = public_session(await client.answer(learner_id, sid, body.question_id, body.text))
            instance.register_interview(learner_id, sid, upstream["status"], upstream["answer_count"])
            return upstream
        except AuralisGatewayError as error:
            raise HTTPException(error.status, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.post("/api/demo/learners/{learner_id}/interviews/{sid}/finish")
    async def finish_interview(learner_id: str, sid: str):
        client = require_link(learner_id, sid)
        try:
            upstream = public_session(await client.finish(learner_id, sid))
            if upstream["status"] != "completed" or not upstream["report"]:
                raise HTTPException(502, "Auralis did not return a completed report.")
            instance.register_interview(learner_id, sid, upstream["status"], upstream["answer_count"])
            return upstream
        except AuralisGatewayError as error:
            raise HTTPException(error.status, str(error)) from error
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
