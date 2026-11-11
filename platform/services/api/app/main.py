"""PrepEzy local demo API. Not suitable for deployment with real accounts."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .core import DemoEngine
from .auralis import AuralisClient, AuralisGatewayError, public_session
from .cracked import public_catalog
from .local_lab import LocalLab


class LocalProfileUpdate(BaseModel):
    role: Literal["backend", "data", "ml", "fullstack"]
    language: Literal["Java", "Python", "JavaScript"]
    daily_minutes: int = Field(ge=15, le=120)


class SqlAttempt(BaseModel):
    challenge_id: str = Field(min_length=1, max_length=30)
    query: str = Field(min_length=12, max_length=1500)


class VivaAttempt(BaseModel):
    question_id: str = Field(min_length=3, max_length=48)
    choice_id: str = Field(min_length=1, max_length=4)


class CodingAttempt(BaseModel):
    challenge_id: str = Field(min_length=1, max_length=48)
    code: str = Field(min_length=8, max_length=2500)


class InterviewAnswer(BaseModel):
    question_id: str = Field(min_length=3, max_length=80)
    text: str = Field(min_length=1, max_length=8000)


class PatternAnswer(BaseModel):
    step_id: str = Field(min_length=2, max_length=24)
    choice_id: str = Field(min_length=1, max_length=4)


class Attempt(BaseModel):
    learner_id: str
    question_id: str
    choice_id: str


def create_app(engine: DemoEngine | None = None, auralis_client: AuralisClient | None = None, local_lab: LocalLab | None = None) -> FastAPI:
    if os.getenv("PREPEZY_ENV", "development") != "development":
        raise RuntimeError("This synthetic demo API is not production-ready")
    instance = engine or DemoEngine(os.getenv("PREPEZY_DEMO_DB", ":memory:"))
    # Explicit opt-in. No other hosts may be used, and no login/account is created.
    auralis = auralis_client
    if auralis is None and os.getenv("PREPEZY_AURALIS_ENABLED") == "1":
        auralis = AuralisClient(os.getenv("PREPEZY_AURALIS_URL", "http://127.0.0.1:8001"))
    app = FastAPI(title="PrepEzy Adaptive Foundation", version="0.5.0")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type"])
    local = local_lab if local_lab is not None else LocalLab(
        ":memory:" if engine is not None else os.getenv("PREPEZY_LOCAL_DB", "prepezy_local.sqlite")
    )

    @app.middleware("http")
    async def local_network_gate(request: Request, call_next):
        # No authentication: fail closed for remote peers and untrusted browser origins.
        # This does NOT protect against other local programs or replace real auth.
        peer = request.client.host if request.client else ""
        origin = request.headers.get("origin")
        if peer not in {"127.0.0.1", "::1", "testclient"} or (
            origin and origin not in {"http://localhost:3000", "http://127.0.0.1:3000"}
        ):
            return JSONResponse({"detail": "Local-only development access"}, status_code=403)
        return await call_next(request)


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

    # A real local-first study workspace, with no sign-in and no synthetic user IDs.
    # This API is for one trusted local device; never expose it on a public interface.
    @app.get("/api/local/profile")
    def local_profile():
        return local.profile()

    @app.put("/api/local/profile")
    def local_update_profile(body: LocalProfileUpdate):
        try:
            return local.update_profile(body.role, body.language, body.daily_minutes)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/api/local/overview")
    def local_overview():
        return local.overview()

    @app.get("/api/local/sql/challenges")
    def local_sql_catalog():
        return local.sql_catalog()

    @app.post("/api/local/sql/attempts")
    def local_sql_attempt(body: SqlAttempt):
        try:
            return {"result": local.grade_sql(body.challenge_id, body.query),
                    "overview": local.overview()}
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/api/local/viva/questions")
    def local_viva_catalog():
        return local.viva_catalog()

    @app.post("/api/local/viva/attempts")
    def local_viva_attempt(body: VivaAttempt):
        try:
            return {"result": local.grade_viva(body.question_id, body.choice_id),
                    "overview": local.overview()}
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/api/local/evidence")
    def local_evidence():
        return local.evidence()

    @app.delete("/api/local/data")
    def local_delete_data():
        return local.reset()

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

    @app.get("/api/demo/cracked/patterns")
    def cracked_patterns():
        return public_catalog()

    @app.get("/api/demo/learners/{learner_id}/cracked/recommendation")
    def cracked_recommendation(learner_id: str):
        try:
            instance.validate_learner(learner_id)
            return instance.coach.recommendation(learner_id)
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    @app.get("/api/demo/learners/{learner_id}/cracked/evidence")
    def cracked_evidence(learner_id: str):
        try:
            instance.validate_learner(learner_id)
            return {"learner_id": learner_id, "results": instance.coach.evidence(learner_id),
                    "transfer_grades": instance.coach.independent_transfer_grades(learner_id)}
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    @app.get("/api/demo/learners/{learner_id}/cracked/patterns/{pattern_id}")
    def cracked_pattern_state(learner_id: str, pattern_id: str):
        try:
            instance.validate_learner(learner_id)
            return instance.coach.state(learner_id, pattern_id)
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    @app.post("/api/demo/learners/{learner_id}/cracked/patterns/{pattern_id}/hint")
    def cracked_pattern_hint(learner_id: str, pattern_id: str):
        try:
            instance.validate_learner(learner_id)
            return instance.coach.hint(learner_id, pattern_id)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.post("/api/demo/learners/{learner_id}/cracked/patterns/{pattern_id}/answers")
    def cracked_pattern_answer(learner_id: str, pattern_id: str, body: PatternAnswer):
        try:
            instance.validate_learner(learner_id)
            result = instance.coach.submit(learner_id, pattern_id, body.step_id, body.choice_id)
            return {"result": result, "learner": instance.snapshot(learner_id),
                    "roadmap": instance.roadmap(learner_id)}
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
