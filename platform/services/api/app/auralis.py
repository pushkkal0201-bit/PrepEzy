"""Local-only Auralis HTTP adapter using upstream session APIs.

No authentication or public network access is added. The token is a *synthetic*
local namespace key accepted by Auralis local mode, NOT an identity guarantee.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from urllib.parse import urlsplit

import httpx

from .core import LEARNERS

SESSION_ID = re.compile(r"^session_[0-9a-f]{32}$")
DEMO_PROFILES = {
    "demo-backend": {
        "role": "Backend Engineer",
        "cv": "Taylor Demo built a booking API using Python and SQL. Created automated concurrency tests and reviewed transaction failure cases.",
        "jd": "Backend developer role requiring SQL, API design, concurrency, debugging, testing, database transactions and technical communication.",
    },
    "demo-ml": {
        "role": "Machine Learning Engineer",
        "cv": "Jordan Demo created Python machine learning experiments with train and held-out test splits, data checks and repeatable evaluations.",
        "jd": "Machine learning engineer role requiring Python, data analysis, model evaluation, deployment thinking, testing and technical communication.",
    },
}


class AuralisGatewayError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


class AuralisClient:
    def __init__(self, url: str = "http://127.0.0.1:8001", transport: httpx.AsyncBaseTransport | None = None):
        parts = urlsplit(url)
        # Prevent SSRF and accidental forwarding of synthetic demo data to remote hosts.
        if (parts.scheme != "http" or parts.hostname not in {"127.0.0.1", "localhost", "::1"}
                or not parts.port or parts.username or parts.password or parts.path not in ("", "/")
                or parts.query or parts.fragment):
            raise ValueError("Auralis must be a loopback-only HTTP service with an explicit port.")
        self.url = url.rstrip("/")
        self.transport = transport

    @staticmethod
    def _token(learner: str) -> str:
        if learner not in LEARNERS:
            raise ValueError("Unknown synthetic demo learner")
        # Deterministic *demo namespace*, not a secret. Never use for real users.
        return hashlib.sha256(("PREPEZY-INSECURE-DEMO-ONLY::" + learner).encode()).hexdigest()

    async def call(self, learner: str, method: str, path: str, payload: dict | None = None) -> dict:
        if not path.startswith("/api/") or "//" in path or method not in ("GET", "POST"):
            raise ValueError("Invalid Auralis API request")
        headers = {"X-Owner-Token": self._token(learner)}
        try:
            async with httpx.AsyncClient(base_url=self.url, transport=self.transport, timeout=12.0,
                                         follow_redirects=False, trust_env=False) as client:
                response = await client.request(method, path, json=payload, headers=headers)
        except httpx.RequestError as exc:
            raise AuralisGatewayError("Local Auralis is unreachable on its configured loopback port.", 503) from exc
        if response.status_code >= 400:
            # Never silently interpret an upstream error as a successful assessment.
            raise AuralisGatewayError("Auralis returned HTTP " + str(response.status_code) + " for " + path, 502)
        try:
            content = response.json()
        except ValueError as exc:
            raise AuralisGatewayError("Auralis returned invalid JSON.", 502) from exc
        if not isinstance(content, dict):
            raise AuralisGatewayError("Auralis response must be a JSON object.", 502)
        return content

    async def health(self) -> dict:
        return await self.call("demo-backend", "GET", "/api/health")

    async def coding_catalog(self, learner: str) -> dict:
        response = await self.call(learner, "GET", "/api/practical/catalog")
        if not str(response.get("execution_policy", "")).startswith("Restricted AST"):
            raise AuralisGatewayError("Auralis did not advertise restricted AST evaluation.")
        challenges = response.get("challenges") or []
        if not isinstance(challenges, list):
            raise AuralisGatewayError("Auralis challenge catalog was malformed.")
        return {
            "execution_policy": response["execution_policy"],
            "challenges": [
                {
                    "id": str(x.get("id", ""))[:48],
                    "title": str(x.get("title", ""))[:120],
                    "description": str(x.get("description", ""))[:500],
                    "starter": str(x.get("starter", ""))[:2500],
                    "hint": str(x.get("hint", ""))[:400],
                }
                for x in challenges[:20] if isinstance(x, dict)
            ],
            "source": "real-local-auralis-practical-catalog",
        }

    async def grade_code(self, learner: str, challenge_id: str, code: str) -> dict:
        if challenge_id not in {"sum_numbers", "reverse_text", "palindrome", "range_span", "clamp"}:
            raise ValueError("Unknown Auralis restricted coding challenge")
        if not 8 <= len(code) <= 2500:
            raise ValueError("Code must contain 8 to 2500 characters")
        response = await self.call(learner, "POST", "/api/practical/code", {
            "challenge_id": challenge_id,
            "code": code,
        })
        passed, total = response.get("passed"), response.get("total")
        if (response.get("source") != "restricted_ast_test_runner" or
                response.get("challenge_id") != challenge_id or
                type(passed) is not int or type(total) is not int or
                not 1 <= total <= 30 or not 0 <= passed <= total or
                response.get("all_passed") is not (passed == total)):
            raise AuralisGatewayError("Auralis returned an invalid coding assessment.")
        rows = response.get("tests") or []
        if not isinstance(rows, list) or len(rows) != total:
            raise AuralisGatewayError("Auralis returned incomplete test evidence.")
        tests = []
        for item in rows:
            if not isinstance(item, dict) or item.get("status") not in ("pass", "fail", "error"):
                raise AuralisGatewayError("Invalid Auralis test case status.")
            test = {"test": item.get("test"), "status": item["status"], "public": item.get("public") is True}
            if test["public"]:
                test.update({"input": item.get("input"), "expected": item.get("expected"), "actual": item.get("actual")})
            tests.append(test)
        return {
            "challenge_id": challenge_id,
            "passed": passed, "total": total,
            "all_passed": passed == total,
            "source": "restricted_ast_test_runner",
            "tests": tests,
            "limitations": "Restricted expression-only Python practice; tests are not proof of general Python proficiency.",
        }

    async def create_and_start(self, learner: str) -> dict:
        profile = DEMO_PROFILES.get(learner)
        if profile is None:
            raise ValueError("Unknown synthetic demo learner")
        setup = {
            **profile,
            "mode": "interview",
            "interview_track": "technical",
            "language": "en",
            "duration_minutes": 10,
            "adaptive_difficulty": True,
            "provider": "demo",
            "synthetic_data": True,
            "consent": False,
        }
        session = await self.call(learner, "POST", "/api/sessions", setup)
        sid = session.get("id")
        if not isinstance(sid, str) or not SESSION_ID.fullmatch(sid):
            raise AuralisGatewayError("Auralis returned an invalid session identifier.")
        started = await self.call(learner, "POST", f"/api/sessions/{sid}/start", {})
        return started

    async def get(self, learner: str, sid: str) -> dict:
        self._validate_sid(sid)
        return await self.call(learner, "GET", f"/api/sessions/{sid}")

    async def answer(self, learner: str, sid: str, question_id: str, text: str) -> dict:
        self._validate_sid(sid)
        if not re.fullmatch(r"q_[0-9a-f]{32}", question_id):
            raise ValueError("Invalid Auralis question ID")
        if not text.strip() or len(text) > 8000:
            raise ValueError("Answer must contain 1 to 8000 characters")
        return await self.call(learner, "POST", f"/api/sessions/{sid}/actions", {
            "text": text.strip(),
            "kind": "answer",
            "request_id": uuid.uuid4().hex,
            "expected_question_id": question_id,
        })

    async def finish(self, learner: str, sid: str) -> dict:
        self._validate_sid(sid)
        return await self.call(learner, "POST", f"/api/sessions/{sid}/finish", {})

    @staticmethod
    def _validate_sid(sid: str) -> None:
        if not SESSION_ID.fullmatch(sid):
            raise ValueError("Invalid Auralis session ID")


def public_session(session: dict) -> dict:
    """Return bounded interview data, omitting CV/JD and upstream internals."""
    sid = session.get("id")
    if not isinstance(sid, str) or not SESSION_ID.fullmatch(sid):
        raise AuralisGatewayError("Auralis returned an invalid session.")
    setup = session.get("setup") or {}
    if setup.get("provider") != "demo" or not setup.get("synthetic_data"):
        raise AuralisGatewayError("This integration only supports scripted, synthetic Auralis interviews.")
    current = session.get("current") or {}
    turns = session.get("turns") or []
    answers = [t for t in turns if t.get("kind") == "answer"]
    report = session.get("report")
    safe_report = None
    if report:
        if report.get("demo") is not True:
            raise AuralisGatewayError("Unexpected non-demo Auralis report.")
        safe_report = {
            "summary": str(report.get("summary", ""))[:1200],
            "demo": True,
            "scored": False,
            "limitations": [str(x)[:300] for x in (report.get("limitations") or [])[:5]],
            "items": [
                {
                    "name": str(x.get("name", x.get("competency_id", "")))[:100],
                    "status": str(x.get("status", "not_assessed"))[:70],
                    "score": None,  # Scripted demo must never be treated as graded.
                    "evidence_count": len(x.get("evidence_ids") or []),
                    "feedback": str(x.get("feedback", ""))[:600],
                }
                for x in (report.get("items") or [])[:6]
            ],
        }
    return {
        "id": sid,
        "status": str(session.get("status", ""))[:60],
        "provider": "scripted-demo",
        "role": str((session.get("plan") or {}).get("role", ""))[:100],
        "current": {
            "id": current.get("id"),
            "text": str(current.get("text", ""))[:900],
            "competency_id": current.get("competency_id"),
            "difficulty": current.get("difficulty"),
            "source": current.get("source"),
        } if current else None,
        "answer_count": len(answers),
        "answers": [
            {
                "id": t.get("id"),
                "question": str((t.get("question") or {}).get("text", ""))[:500],
                "text": str(t.get("text", ""))[:1000],
            }
            for t in answers[-6:]
        ],
        "report": safe_report,
        "notice": "Auralis scripted interview: genuine session and saved answers, but no AI grading or proficiency score.",
    }
