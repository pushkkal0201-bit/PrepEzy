"""PrepEzy local demo API. Not suitable for deployment with real accounts."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request, File, UploadFile
from pydantic import Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .core import DemoEngine
from .auralis import AuralisClient, AuralisGatewayError, public_session
from .cracked import public_catalog
from .local_lab import LocalLab
from .unified import UnifiedEvidence, LOCAL_NAMESPACE
from .coding_arena import JudgeUnavailable, public_problems
from .knowledge import NotesFolder, ServietteGateway, ServietteUnavailable, suggest_from_skillgraph
from .career import CareerEngine
from .resume import ResumeIntelligence, MAX_BYTES as RESUME_MAX_BYTES
from .project_lab import PROJECTS
from .repo_review import GitHubProjectReview, GitHubReviewUnavailable
from .mock_interview import MockInterviews


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


class CareerBoardInput(BaseModel):
    provider: Literal["greenhouse", "lever"]
    token: str = Field(min_length=1, max_length=60)
    company: str = Field(min_length=2, max_length=120)


class CareerProfileInput(BaseModel):
    facts: str = Field(max_length=6000)
    preferred_location: str = Field(default="", max_length=100)


class CareerStageInput(BaseModel):
    stage: Literal["saved", "applied", "interviewing", "offer", "rejected", "withdrawn"]
    notes: str = Field(default="", max_length=1500)


class KnowledgeNoteRequest(BaseModel):
    filename: str = Field(min_length=4, max_length=70)
    content: str = Field(min_length=1, max_length=50000)


class KnowledgeQueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=800)
    mode: Literal["retrieve", "answer"] = "retrieve"
    k: int = Field(default=5, ge=1, le=8)


class ArenaSessionRequest(BaseModel):
    mode: Literal["practice", "timed"] = "timed"
    duration_minutes: Literal[15, 30, 45, 60] = 30


class ArenaSubmission(BaseModel):
    session_id: str = Field(min_length=32, max_length=32)
    problem_id: str = Field(min_length=3, max_length=64)
    language: Literal["python", "java", "javascript"]
    source: str = Field(min_length=12, max_length=12000)


class ProjectMilestoneSubmission(BaseModel):
    language: Literal["python", "java", "javascript"]
    code: str = Field(min_length=12, max_length=12000)


class ProjectDefenseSubmission(BaseModel):
    choice_id: Literal["a", "b", "c"]
    rationale: str = Field(min_length=20, max_length=1200)


class ProjectArtifactSubmission(BaseModel):
    repo_url: str = Field(min_length=20, max_length=220)
    notes: str = Field(default="", max_length=1800)


class RepositoryInspectRequest(BaseModel):
    repo_url: str = Field(min_length=24, max_length=250)


class RepositoryDefenseRequest(BaseModel):
    finding_id: str = Field(min_length=20, max_length=20)
    response: str = Field(min_length=30, max_length=2000)


class RepositorySmokeCase(BaseModel):
    stdin: str = Field(max_length=2000)
    expected_stdout: str = Field(max_length=2000)


class RepositorySmokeRequest(BaseModel):
    file_path: str = Field(min_length=3, max_length=240)
    language: Literal["python", "javascript", "java"]
    cases: list[RepositorySmokeCase] = Field(min_length=1, max_length=3)
    approved: bool


class MockInterviewStart(BaseModel):
    focus: Literal["balanced", "coding", "project"] = "balanced"
    snapshot_id: int | None = Field(default=None, ge=1)


class MockInterviewResponse(BaseModel):
    question_id: str = Field(min_length=3, max_length=80)
    response: str = Field(min_length=30, max_length=2000)
    probe: Literal["edge_cases", "tradeoffs", "verification"] = "edge_cases"


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


def create_app(engine: DemoEngine | None = None, auralis_client: AuralisClient | None = None, local_lab: LocalLab | None = None, knowledge_client: ServietteGateway | None = None, notes_folder: NotesFolder | None = None, career_client: CareerEngine | None = None, resume_client: ResumeIntelligence | None = None, repo_review_client: GitHubProjectReview | None = None) -> FastAPI:
    if os.getenv("PREPEZY_ENV", "development") != "development":
        raise RuntimeError("This synthetic demo API is not production-ready")
    instance = engine or DemoEngine(os.getenv("PREPEZY_DEMO_DB", ":memory:"))
    # Explicit opt-in. No other hosts may be used, and no login/account is created.
    auralis = auralis_client
    if auralis is None and os.getenv("PREPEZY_AURALIS_ENABLED") == "1":
        auralis = AuralisClient(os.getenv("PREPEZY_AURALIS_URL", "http://127.0.0.1:8001"))
    app = FastAPI(title="PrepEzy Adaptive Foundation", version="0.13.0")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type"])
    local = local_lab if local_lab is not None else LocalLab(
        ":memory:" if engine is not None else os.getenv("PREPEZY_LOCAL_DB", "prepezy_local.sqlite")
    )
    unified = UnifiedEvidence(local)
    knowledge = knowledge_client if knowledge_client is not None else ServietteGateway(
        url=os.getenv("PREPEZY_SERVIETTE_URL", "http://127.0.0.1:8989"),
        enabled=os.getenv("PREPEZY_SERVIETTE_ENABLED", "0") == "1",
    )
    notes = notes_folder if notes_folder is not None else NotesFolder(
        os.getenv("PREPEZY_KNOWLEDGE_DIR", "prepezy-knowledge")
    )
    career = career_client if career_client is not None else CareerEngine(local.db, local.lock)
    resumes = resume_client if resume_client is not None else ResumeIntelligence(local.db, local.lock)
    repo_review = repo_review_client if repo_review_client is not None else GitHubProjectReview(local.db, local.lock, runner=unified.arena.runner, gate=unified.arena.capacity)
    mocks = MockInterviews(local.db, local.lock, unified, repo_review)

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

    # One local device is one workspace. No client-submitted evidence scores.
    # JobSearch-inspired real published-board discovery and review-only drafts.
    # All ATS requests use fixed public read-only Greenhouse/Lever hosts.
    # Real document extraction and role review. No outbound resume uploads.
    # Curated, educational Build Your Own X links; original Docker-checked milestones.
    # Public GitHub REST inspection, commit-pinned source evidence and user-
    # approved single-file Docker smoke checks. No arbitrary clone/test commands.
    # Stage 13: persisted interview flow with evidence-based question selection.
    # Oral answers are saved but never treated as verified SkillGraph marks.
    @app.get("/api/local/mock-interviews")
    def mock_interview_history():
        return mocks.history()

    @app.post("/api/local/mock-interviews")
    def mock_interview_start(body: MockInterviewStart):
        try:
            return mocks.start(body.focus, body.snapshot_id)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/api/local/mock-interviews/{session_id}")
    def mock_interview_session(session_id: str):
        try:
            return mocks.session(session_id)
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    @app.post("/api/local/mock-interviews/{session_id}/responses")
    def mock_interview_response(session_id: str, body: MockInterviewResponse):
        try:
            return mocks.respond(session_id, body.question_id, body.response, body.probe)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.post("/api/local/mock-interviews/{session_id}/finish")
    def mock_interview_finish(session_id: str):
        try:
            return mocks.finish(session_id)
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    @app.delete("/api/local/mock-interviews")
    def mock_interview_delete():
        return mocks.clear()

    @app.get("/api/local/repositories/history")
    def repo_review_history():
        return repo_review.history()

    @app.post("/api/local/repositories/inspect")
    async def repo_review_inspect(body: RepositoryInspectRequest):
        try:
            return await repo_review.inspect(body.repo_url)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except GitHubReviewUnavailable as error:
            raise HTTPException(503, str(error)) from error

    @app.get("/api/local/repositories/{snapshot_id}")
    def repo_review_snapshot(snapshot_id: int):
        try:
            return repo_review.snapshot(snapshot_id)
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    @app.post("/api/local/repositories/{snapshot_id}/defense")
    def repo_review_answer(snapshot_id: int, body: RepositoryDefenseRequest):
        try:
            return repo_review.answer(snapshot_id, body.finding_id, body.response)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/api/local/repositories/{snapshot_id}/evidence")
    def repo_review_evidence(snapshot_id: int):
        try:
            return repo_review.evidence(snapshot_id)
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    @app.post("/api/local/repositories/{snapshot_id}/smoke")
    async def repo_review_smoke(snapshot_id: int, body: RepositorySmokeRequest):
        try:
            return await repo_review.smoke_check(
                snapshot_id, body.file_path, body.language,
                [case.model_dump() for case in body.cases], body.approved
            )
        except JudgeUnavailable as error:
            raise HTTPException(503, str(error)) from error
        except GitHubReviewUnavailable as error:
            raise HTTPException(503, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.delete("/api/local/repositories/data")
    def repo_review_delete():
        return repo_review.clear()

    @app.get("/api/local/projects/catalog")
    def project_catalog():
        return unified.projects.catalog(local.profile()["role"])

    @app.get("/api/local/projects/{project_id}")
    def project_detail(project_id: str):
        try:
            return unified.projects.state(project_id)
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    @app.post("/api/local/projects/{project_id}/milestones/{milestone_id}/submit")
    def project_submit(project_id: str, milestone_id: str, body: ProjectMilestoneSubmission):
        try:
            result = unified.projects.submit_milestone(
                project_id, milestone_id, body.language, body.code
            )
            return {"result": result, "project": unified.projects.state(project_id),
                    "skillgraph": unified.skillgraph()}
        except JudgeUnavailable as error:
            raise HTTPException(503, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.post("/api/local/projects/{project_id}/defense/{question_id}/submit")
    def project_defense(project_id: str, question_id: str, body: ProjectDefenseSubmission):
        try:
            result = unified.projects.defend(
                project_id, question_id, body.choice_id, body.rationale
            )
            return {"result": result, "project": unified.projects.state(project_id),
                    "skillgraph": unified.skillgraph()}
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.put("/api/local/projects/{project_id}/artifact")
    def project_artifact(project_id: str, body: ProjectArtifactSubmission):
        try:
            return unified.projects.save_artifact(project_id, body.repo_url, body.notes)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/api/local/projects/evidence/all")
    def project_evidence_all():
        return {"milestones": unified.projects.milestone_evidence(),
                "defense": unified.projects.defense_evidence(),
                "notice": "Only Docker test verdicts and checked defense choices are graded; rationales and repository links remain unverified."}

    @app.get("/api/local/resume/status")
    def resume_status():
        return resumes.status()

    @app.post("/api/local/resume/upload")
    async def resume_upload(file: UploadFile = File(...)):
        name = file.filename or ""
        try:
            raw = await file.read(RESUME_MAX_BYTES + 1)
            return resumes.upload(name, raw)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        finally:
            await file.close()

    @app.get("/api/local/resume/inspection")
    def resume_inspection():
        try:
            return resumes.inspect()
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    @app.get("/api/local/resume/jobs/{job_id}/analysis")
    def resume_job_analysis(job_id: str):
        try:
            job = career.get(job_id)
            return resumes.for_job(job, unified.skillgraph())
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    @app.delete("/api/local/resume")
    def resume_clear():
        return resumes.clear()

    @app.get("/api/local/careers/boards")
    def career_boards():
        return {"boards": career.boards()}

    @app.post("/api/local/careers/boards")
    def career_add_board(body: CareerBoardInput):
        try:
            return career.add_board(body.provider, body.token, body.company)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.delete("/api/local/careers/boards/{provider}/{token}")
    def career_remove_board(provider: str, token: str):
        try:
            return career.remove_board(provider, token)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.post("/api/local/careers/refresh")
    async def career_refresh():
        return await career.refresh()

    @app.get("/api/local/careers/profile")
    def career_profile():
        return career.profile()

    @app.put("/api/local/careers/profile")
    def career_update_profile(body: CareerProfileInput):
        try:
            return career.update_profile(body.facts, body.preferred_location)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/api/local/careers/jobs")
    def career_jobs(q: str = Query(default="", max_length=100),
                    location: str = Query(default="", max_length=100),
                    limit: int = Query(default=30, ge=1, le=100)):
        try:
            return career.jobs(unified.skillgraph(), search=q, location=location, limit=limit)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/api/local/careers/jobs/{job_id}")
    def career_job(job_id: str):
        try:
            return {**career.get(job_id), "match": career.match(career.get(job_id), unified.skillgraph())}
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    @app.get("/api/local/careers/jobs/{job_id}/drafts")
    def career_drafts(job_id: str):
        try:
            return {"drafts": career.drafts(job_id)}
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    @app.post("/api/local/careers/jobs/{job_id}/drafts")
    def career_draft(job_id: str):
        try:
            return career.draft(job_id)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/api/local/careers/applications")
    def career_applications():
        return {"applications": career.applications(),
                "notice": "Statuses are manually recorded and are not confirmed by employers."}

    @app.put("/api/local/careers/applications/{job_id}")
    def career_update_application(job_id: str, body: CareerStageInput):
        try:
            return career.update_application(job_id, body.stage, body.notes)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.delete("/api/local/careers/data")
    def career_delete_data():
        return career.delete_local_career_data()

    @app.get("/api/local/knowledge/status")
    async def knowledge_status():
        upstream = await knowledge.status()
        return {"upstream": upstream, "saved_notes": len(notes.list()),
                "folder": str(notes.path),
                "note": "A saved file is not proof that Serviette indexed it."}

    @app.get("/api/local/knowledge/notes")
    def knowledge_notes():
        return {"notes": notes.list(),
                "notice": "Saved local notes, not necessarily Serviette-indexed documents."}

    @app.post("/api/local/knowledge/notes")
    def save_knowledge_note(body: KnowledgeNoteRequest):
        try:
            return notes.put(body.filename, body.content)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/api/local/knowledge/notes/{filename}")
    def read_knowledge_note(filename: str):
        try:
            return {"filename": filename, "content": notes.read(filename)}
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    @app.delete("/api/local/knowledge/notes/{filename}")
    def delete_knowledge_note(filename: str):
        try:
            return notes.delete(filename)
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    @app.get("/api/local/knowledge/documents")
    async def indexed_knowledge_documents(q: str = Query(default="", max_length=120),
                                           limit: int = Query(default=50, ge=1, le=100)):
        try:
            return await knowledge.documents(q, limit)
        except (ServietteUnavailable, ValueError) as error:
            raise HTTPException(503, str(error)) from error

    @app.get("/api/local/knowledge/recommendation")
    def knowledge_recommendation():
        return suggest_from_skillgraph(unified.skillgraph())

    @app.post("/api/local/knowledge/query")
    async def query_knowledge(body: KnowledgeQueryRequest):
        try:
            answer = await knowledge.retrieve(body.question, body.k,
                                              body.mode == "answer")
            return {**answer,
                    "student_context": {
                        "target_role": local.profile()["target_role"],
                        "personalization": "Question explicitly chosen by learner; recommendations remain separate from retrieval."
                    }}
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except ServietteUnavailable as error:
            raise HTTPException(503, str(error)) from error

    @app.get("/api/local/arena/problems")
    def arena_problems():
        return public_problems()

    @app.get("/api/local/arena/status")
    def arena_status():
        return {"availability": unified.arena.availability(),
                "session": unified.arena.current_session()}

    @app.get("/api/local/arena/evidence")
    def arena_evidence():
        return {"attempts": unified.arena.evidence()}

    @app.post("/api/local/arena/sessions")
    def arena_start(body: ArenaSessionRequest):
        try:
            return unified.arena.start(body.mode, body.duration_minutes)
        except JudgeUnavailable as error:
            raise HTTPException(503, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.post("/api/local/arena/sessions/{session_id}/finish")
    def arena_finish(session_id: str):
        try:
            return unified.arena.finish(session_id)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.post("/api/local/arena/submissions")
    def arena_submit(body: ArenaSubmission):
        try:
            result = unified.arena.submit(body.session_id, body.problem_id,
                                          body.language, body.source)
            return {"result": result, "skillgraph": unified.skillgraph()}
        except JudgeUnavailable as error:
            raise HTTPException(503, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/api/local/skillgraph")
    def local_skillgraph():
        graph = unified.skillgraph()
        graph["github_review_context"] = repo_review.context()
        return graph

    @app.get("/api/local/unified-evidence")
    def local_unified_evidence():
        return unified.evidence()

    @app.get("/api/local/cracked/patterns")
    def local_patterns():
        return public_catalog()

    @app.get("/api/local/cracked/patterns/{pattern_id}")
    def local_pattern_state(pattern_id: str):
        try:
            return unified.patterns.state(LOCAL_NAMESPACE, pattern_id)
        except ValueError as error:
            raise HTTPException(404, str(error)) from error

    @app.post("/api/local/cracked/patterns/{pattern_id}/hint")
    def local_pattern_hint(pattern_id: str):
        try:
            return unified.patterns.hint(LOCAL_NAMESPACE, pattern_id)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.post("/api/local/cracked/patterns/{pattern_id}/answers")
    def local_pattern_answer(pattern_id: str, body: PatternAnswer):
        try:
            outcome = unified.patterns.submit(LOCAL_NAMESPACE, pattern_id, body.step_id, body.choice_id)
            return {"result": outcome, "skillgraph": unified.skillgraph()}
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/api/local/auralis/challenges")
    async def local_auralis_challenges():
        try:
            # The upstream local instance uses a fixed *non-secret* namespace
            # only to separate its internal restricted coding records.
            return await local_auralis().coding_catalog("demo-backend")
        except AuralisGatewayError as error:
            raise HTTPException(error.status, str(error)) from error

    @app.post("/api/local/auralis/code")
    async def local_auralis_coding(body: CodingAttempt):
        try:
            result = await local_auralis().grade_code("demo-backend", body.challenge_id, body.code)
            unified.record_auralis(result)
            return {"result": result, "skillgraph": unified.skillgraph()}
        except AuralisGatewayError as error:
            raise HTTPException(error.status, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/api/local/auralis/evidence")
    def local_auralis_evidence():
        return {"results": unified.code_evidence()}

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
        local.reset()
        unified.clear()
        career.delete_local_career_data()
        resumes.clear()
        repo_review.clear()
        mocks.clear()
        return {"cleared": True, "sources": ["sql", "core_viva", "cracked_pattern", "auralis_restricted_code", "coding_arena", "career_data", "resume_data", "project_lab", "github_review_context", "mock_interviews"]}

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
