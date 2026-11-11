"""Local-first JobSearch-inspired career workflows.

Live published jobs come ONLY from explicit employer Greenhouse / Lever boards.
JobSearch's Claude Code agent skills are not executed as a web service. This is
a separately authored, deterministic adaptation of its discover -> rank ->
draft -> review -> outcome progression. Zero application submissions occur.
"""
from __future__ import annotations

import html
import ipaddress
import json
import re
import sqlite3
from datetime import datetime, timezone
from html.parser import HTMLParser
from threading import RLock
from urllib.parse import urlsplit

import httpx

TOKEN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,59}$")
SAFE_JOB_ID = re.compile(r"^[a-zA-Z0-9_-]{1,120}$")
ALLOWED_PROVIDERS = ("greenhouse", "lever")
ALLOWED_STATES = ("saved", "applied", "interviewing", "offer", "rejected", "withdrawn")
KEYWORDS = {
    "python": ("python",),
    "java": ("java",),
    "javascript": ("javascript", "node.js", "nodejs"),
    "typescript": ("typescript",),
    "sql": ("sql",),
    "postgresql": ("postgresql", "postgres"),
    "database": ("dbms", "database", "databases"),
    "docker": ("docker",),
    "kubernetes": ("kubernetes",),
    "aws": ("aws", "amazon web services"),
    "linux": ("linux",),
    "git": ("git",),
    "react": ("react.js", "reactjs", "react"),
    "nextjs": ("next.js", "nextjs"),
    "fastapi": ("fastapi",),
    "machine-learning": ("machine learning",),
    "pytorch": ("pytorch",),
    "tensorflow": ("tensorflow",),
    "data-structures": ("data structures",),
    "algorithms": ("algorithms", "algorithm"),
    "computer-networks": ("computer networks", "network protocols"),
    "oop": ("object oriented", "object-oriented", "oop"),
}
EVIDENCE_SKILLS = {
    "sql": "sql", "database": "dbms",
    "computer-networks": "cn", "oop": "oop",
    "algorithms": "coding", "data-structures": "coding",
    "python": "python",
}
ROLE_WORDS = {
    "backend": ("backend", "back-end", "server", "software engineer", "api"),
    "ml": ("machine learning", "ml engineer", "artificial intelligence", "ai engineer", "data scientist"),
    "data": ("data analyst", "analytics", "business intelligence", "data engineer"),
    "fullstack": ("fullstack", "full stack", "full-stack", "frontend", "front-end", "software engineer"),
}
INSTRUCTION_ALERT = re.compile(
    r"(?:ignore\s+(?:all\s+)?(?:previous|prior|system)\s+instructions|"
    r"you\s+are\s+(?:now\s+)?(?:an?\s+)?(?:ai|assistant|language\s+model)|"
    r"send\s+(?:your\s+)?(?:private|secret|api\s+key|credentials))",
    re.I,
)
INVISIBLE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff\U000e0000-\U000e007f]")
MAX_POSTING_BYTES = 3_000_000


class CareerProviderError(RuntimeError):
    pass


class _DescriptionText(HTMLParser):
    """Strip executable and hidden DOM content even when it contains nested tags."""
    _BLOCKS = {"p", "div", "li", "br", "h1", "h2", "h3", "section", "article"}
    _VOID = {"br", "hr", "img", "input", "meta", "link", "source", "wbr", "area"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.stack: list[tuple[str, bool]] = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        style = str(values.get("style") or "").replace(" ", "").lower()
        parent_hidden = self.stack[-1][1] if self.stack else False
        hidden = parent_hidden or tag in {"script", "style", "noscript", "template", "svg"} or (
            "hidden" in values or str(values.get("aria-hidden") or "").lower() == "true" or
            "display:none" in style or "visibility:hidden" in style
        )
        if tag in self._BLOCKS and not hidden:
            self.parts.append("\n")
        if tag not in self._VOID:
            self.stack.append((tag, hidden))

    def handle_endtag(self, tag):
        match = next((i for i in range(len(self.stack) - 1, -1, -1)
                      if self.stack[i][0] == tag), None)
        if match is None:
            return
        was_hidden = self.stack[match][1]
        del self.stack[match:]
        if tag in self._BLOCKS and not was_hidden:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.stack or not self.stack[-1][1]:
            self.parts.append(data)


def posting_text(markup: str) -> tuple[str, list[str]]:
    raw = str(markup or "")[:100_000]
    parser = _DescriptionText()
    try:
        parser.feed(raw)
        cleaned = " ".join(" ".join(parser.parts).split())
    except (ValueError, AssertionError):
        cleaned = html.unescape(re.sub(r"<[^>]*>", " ", raw))
    alerts = []
    if INVISIBLE.search(cleaned):
        alerts.append("Invisible formatting characters were removed")
    cleaned = INVISIBLE.sub("", cleaned)[:12_000]
    if INSTRUCTION_ALERT.search(cleaned):
        alerts.append("Posting contains instruction-like text; treat as untrusted data")
    return cleaned, alerts


def safe_application_url(value: str) -> str | None:
    """Only expose HTTPS public links; never follow posting-provided URLs server-side."""
    if not isinstance(value, str) or len(value) > 1600:
        return None
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    try:
        if not parsed.hostname.count("."):
            return None
        addr = ipaddress.ip_address(parsed.hostname)
        if not addr.is_global:
            return None
    except ValueError:
        if parsed.hostname in ("localhost",) or parsed.hostname.endswith(".local"):
            return None
    return value


def _matches(body: str, options: tuple[str, ...]) -> bool:
    text = body.casefold()
    return any(re.search(r"(?<![a-z0-9])" + re.escape(w.casefold()) + r"(?![a-z0-9])", text) for w in options)


def _skills(description: str) -> list[str]:
    return [key for key, words in KEYWORDS.items() if _matches(description, words)]


def _validated(provider: str, token: str) -> None:
    if provider not in ALLOWED_PROVIDERS or not TOKEN.fullmatch(token):
        raise ValueError("Use a valid Greenhouse/Lever board and its public token.")


def _normalise(provider: str, token: str, label: str, item: dict) -> dict | None:
    raw_id = str(item.get("id", ""))
    if not SAFE_JOB_ID.fullmatch(raw_id):
        return None
    if provider == "greenhouse":
        title = str(item.get("title") or "")
        location = str((item.get("location") or {}).get("name") or "")
        link = safe_application_url(item.get("absolute_url", ""))
        body, alerts = posting_text(item.get("content", ""))
        updated = str(item.get("updated_at") or "")
    else:
        title = str(item.get("text") or "")
        categories = item.get("categories") if isinstance(item.get("categories"), dict) else {}
        location = str(categories.get("location") or "")
        link = safe_application_url(item.get("hostedUrl") or item.get("applyUrl") or "")
        raw = str(item.get("descriptionPlain") or "")
        if not raw:
            raw = str(item.get("description") or "")
        lists = item.get("lists")
        if isinstance(lists, list):
            raw += "\n" + "\n".join(str(x.get("text", "")) + " " + str(x.get("content", "")) for x in lists if isinstance(x, dict))
        body, alerts = posting_text(raw)
        updated = ""
    if not title.strip() or not link:
        return None
    return {
        "id": f"{provider}:{token}:{raw_id}",
        "provider": provider, "board": token, "company": label[:120],
        "title": title.strip()[:240], "location": location[:200],
        "url": link, "description": body[:12_000],
        "updated_at": updated[:100], "integrity_alerts": alerts,
        "requested_skills": _skills(body + " " + title),
    }


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class CareerEngine:
    def __init__(self, db: sqlite3.Connection, lock: RLock,
                 transport: httpx.AsyncBaseTransport | None = None):
        self.db = db
        self.lock = lock
        self.transport = transport
        with lock:
            db.execute("""CREATE TABLE IF NOT EXISTS career_boards(
                provider TEXT NOT NULL, token TEXT NOT NULL, company TEXT NOT NULL,
                PRIMARY KEY(provider,token))""")
            db.execute("""CREATE TABLE IF NOT EXISTS career_jobs(
                id TEXT PRIMARY KEY, provider TEXT NOT NULL, board TEXT NOT NULL,
                company TEXT NOT NULL, title TEXT NOT NULL, location TEXT NOT NULL,
                url TEXT NOT NULL, description TEXT NOT NULL, metadata TEXT NOT NULL,
                fetched_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS career_profile(
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                facts TEXT NOT NULL DEFAULT '', preferred_location TEXT NOT NULL DEFAULT '')""")
            db.execute("INSERT OR IGNORE INTO career_profile(singleton) VALUES (1)")
            db.execute("""CREATE TABLE IF NOT EXISTS career_applications(
                job_id TEXT PRIMARY KEY, stage TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL, FOREIGN KEY(job_id) REFERENCES career_jobs(id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS career_drafts(
                id INTEGER PRIMARY KEY, job_id TEXT NOT NULL, content TEXT NOT NULL,
                created_at TEXT NOT NULL, FOREIGN KEY(job_id) REFERENCES career_jobs(id))""")
            db.commit()

    def boards(self) -> list[dict]:
        with self.lock:
            rows = self.db.execute(
                "SELECT provider,token,company FROM career_boards ORDER BY company,provider"
            ).fetchall()
        return [{"provider": p, "token": t, "company": c} for p, t, c in rows]

    def add_board(self, provider: str, token: str, company: str) -> dict:
        _validated(provider, token)
        if not isinstance(company, str) or not 2 <= len(company.strip()) <= 120:
            raise ValueError("Enter a company label of 2–120 characters.")
        with self.lock:
            count = self.db.execute("SELECT COUNT(*) FROM career_boards").fetchone()[0]
            exists = self.db.execute("SELECT 1 FROM career_boards WHERE provider=? AND token=?",
                                     (provider, token)).fetchone()
            if count >= 12 and not exists:
                raise ValueError("Maximum twelve configured employer boards.")
            self.db.execute(
                "INSERT INTO career_boards(provider,token,company) VALUES (?,?,?) "
                "ON CONFLICT(provider,token) DO UPDATE SET company=excluded.company",
                (provider, token, company.strip()),
            )
            self.db.commit()
        return {"provider": provider, "token": token, "company": company.strip(),
                "notice": "Board saved. No jobs are claimed until a real API refresh succeeds."}

    def remove_board(self, provider: str, token: str) -> dict:
        _validated(provider, token)
        with self.lock:
            cur = self.db.execute("DELETE FROM career_boards WHERE provider=? AND token=?",
                                  (provider, token))
            self.db.commit()
        if not cur.rowcount:
            raise ValueError("Board not found")
        return {"deleted": True, "notice": "Previously fetched job snapshots and application history remain for review."}

    async def _fetch(self, provider: str, token: str) -> list[dict]:
        _validated(provider, token)
        if provider == "greenhouse":
            url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
            params = {"content": "true"}
        else:
            url = f"https://api.lever.co/v0/postings/{token}"
            params = {"mode": "json", "limit": 100}
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=httpx.Timeout(12, connect=3),
                                         follow_redirects=False, trust_env=False) as client:
                response = await client.get(url, params=params, headers={"Accept": "application/json"})
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise CareerProviderError(f"{provider} board {token} is unreachable") from exc
        if response.status_code != 200:
            raise CareerProviderError(f"{provider} board {token} returned HTTP {response.status_code}")
        if len(response.content) > MAX_POSTING_BYTES:
            raise CareerProviderError(f"{provider} board response exceeded the size cap")
        try:
            parsed = response.json()
        except ValueError as exc:
            raise CareerProviderError(f"{provider} returned invalid JSON") from exc
        if provider == "greenhouse":
            if not isinstance(parsed, dict) or not isinstance(parsed.get("jobs"), list):
                raise CareerProviderError("Unexpected Greenhouse jobs schema")
            return parsed["jobs"][:100]
        if not isinstance(parsed, list):
            raise CareerProviderError("Unexpected Lever postings schema")
        return parsed[:100]

    async def refresh(self) -> dict:
        sources = self.boards()
        if not sources:
            return {"sources": [], "saved": 0,
                    "notice": "Add an employer's actual Greenhouse or Lever board token to fetch published jobs."}
        outcomes, saved = [], 0
        for source in sources:
            try:
                listing = await self._fetch(source["provider"], source["token"])
                posts = [_normalise(source["provider"], source["token"], source["company"], x)
                         for x in listing if isinstance(x, dict)]
                posts = [x for x in posts if x]
                with self.lock:
                    for job in posts:
                        details = json.dumps({"updated_at": job["updated_at"],
                                              "integrity_alerts": job["integrity_alerts"],
                                              "requested_skills": job["requested_skills"]})
                        self.db.execute("""INSERT INTO career_jobs
                          (id,provider,board,company,title,location,url,description,metadata,fetched_at)
                          VALUES (?,?,?,?,?,?,?,?,?,?)
                          ON CONFLICT(id) DO UPDATE SET
                           company=excluded.company,title=excluded.title,location=excluded.location,
                           url=excluded.url,description=excluded.description,
                           metadata=excluded.metadata,fetched_at=excluded.fetched_at""",
                          (job["id"], job["provider"], job["board"], job["company"], job["title"],
                           job["location"], job["url"], job["description"], details, _utc()))
                    self.db.commit()
                saved += len(posts)
                outcomes.append({**source, "result": "fetched", "saved": len(posts)})
            except (CareerProviderError, ValueError) as exc:
                outcomes.append({**source, "result": "error", "message": str(exc), "saved": 0})
        return {"sources": outcomes, "saved": saved,
                "notice": "Real public ATS GET results; saved snapshots may become stale. Verify each posting on the employer website."}

    def get(self, job_id: str) -> dict:
        with self.lock:
            row = self.db.execute(
                """SELECT id,provider,board,company,title,location,url,description,metadata,fetched_at
                   FROM career_jobs WHERE id=?""", (job_id,),
            ).fetchone()
        if not row:
            raise ValueError("Job not found; refresh an employer's board first.")
        id_, provider, board, company, title, location, url, description, details, stamp = row
        data = json.loads(details)
        return {"id": id_, "provider": provider, "board": board, "company": company,
                "title": title, "location": location, "url": url,
                "description": description, "fetched_at": stamp,
                "requested_skills": data.get("requested_skills", []),
                "integrity_alerts": data.get("integrity_alerts", []),
                "updated_at": data.get("updated_at", ""),
                "notice": "Published posting snapshot, not confirmation this vacancy remains open."}

    def profile(self) -> dict:
        with self.lock:
            facts, preferred = self.db.execute(
                "SELECT facts,preferred_location FROM career_profile WHERE singleton=1"
            ).fetchone()
        return {"facts": facts, "preferred_location": preferred,
                "notice": "Self-reported facts, not verified by PrepEzy. Stored in local SQLite only."}

    def update_profile(self, facts: str, preferred_location: str) -> dict:
        if not isinstance(facts, str) or len(facts) > 6000 or not isinstance(preferred_location, str) or len(preferred_location) > 100:
            raise ValueError("Facts must be <=6000 characters and location <=100.")
        if len([x for x in facts.splitlines() if x.strip()]) > 35:
            raise ValueError("Use at most 35 factual lines for your application profile.")
        with self.lock:
            self.db.execute("UPDATE career_profile SET facts=?,preferred_location=? WHERE singleton=1",
                            (facts.strip(), preferred_location.strip()))
            self.db.commit()
        return self.profile()

    def match(self, job: dict, graph: dict) -> dict:
        role = graph["profile"]["role"]
        role_signal = _matches(job["title"], ROLE_WORDS[role])
        skills = {s["id"]: s for s in graph["skills"]}
        verified, unassessed, limited = [], [], []
        for tag in job["requested_skills"]:
            target = EVIDENCE_SKILLS.get(tag)
            if not target:
                unassessed.append(tag)
                continue
            s = skills[target]
            if not s["distinct_assessments"]:
                unassessed.append(tag)
            elif s["first_try_correct_unassisted"] > 0:
                verified.append({"tag": tag, "skillgraph": target,
                                 "evidence": "limited positive first-attempt evidence"})
            else:
                limited.append({"tag": tag, "skillgraph": target,
                                "evidence": "assessed; no independent first-attempt success yet"})
        preferred = self.profile()["preferred_location"]
        location_signal = bool(preferred and preferred.casefold() in job["location"].casefold())
        return {"role_title_relevance": role_signal, "location_preference_match": location_signal,
                "observed_evidence": verified, "unassessed_requirements": unassessed,
                "practice_gaps": limited, "explanation": (
                    "Transparent matching signals only. Unassessed means unknown, not unqualified; "
                    "this is neither ATS score nor prediction of hiring."
                )}

    def jobs(self, graph: dict, search: str = "", location: str = "", limit: int = 30) -> dict:
        if len(search) > 100 or len(location) > 100 or not 1 <= limit <= 100:
            raise ValueError("Invalid job search filters")
        with self.lock:
            rows = self.db.execute(
                "SELECT id FROM career_jobs ORDER BY fetched_at DESC,id LIMIT 500"
            ).fetchall()
        listings = []
        for (key,) in rows:
            job = self.get(key)
            blob = f"{job['title']} {job['company']} {job['description']}"
            if search and search.casefold() not in blob.casefold():
                continue
            if location and location.casefold() not in job["location"].casefold():
                continue
            match = self.match(job, graph)
            listings.append({k: v for k, v in job.items() if k != "description"} |
                            {"description_preview": job["description"][:260], "match": match})
        listings.sort(key=lambda x: (-int(x["match"]["role_title_relevance"]),
                                     -len(x["match"]["observed_evidence"]),
                                     -int(x["match"]["location_preference_match"]),
                                     x["company"].casefold(), x["title"].casefold()))
        return {"jobs": listings[:limit], "matched": len(listings), "returned": min(len(listings), limit),
                "notice": "Results come only from employer boards you configured and successfully refreshed; availability may have changed."}

    def draft(self, job_id: str) -> dict:
        job = self.get(job_id)
        profile = self.profile()
        facts = [line.strip().lstrip("-* ").strip() for line in profile["facts"].splitlines() if line.strip()]
        if not facts:
            raise ValueError("Add your actual experience or skills to your private profile before creating a draft.")
        items = "\n".join("- " + line[:250] for line in facts[:8])
        content = (
            f"Dear Hiring Team,\n\n"
            f"I am interested in the {job['title']} opportunity at {job['company']}.\n\n"
            f"The following are the experience and skill statements I supplied for this draft:\n{items}\n\n"
            "I would welcome an opportunity to discuss which of these experiences are relevant to your role.\n\n"
            "Sincerely,\n[Your name]\n\n"
            "[Review this draft, verify every statement, and adapt it to the role before using it. "
            "No application has been submitted by PrepEzy.]"
        )
        with self.lock:
            cursor = self.db.execute(
                "INSERT INTO career_drafts(job_id,content,created_at) VALUES (?,?,?)",
                (job_id, content, _utc()),
            )
            self.db.commit()
        return {"id": cursor.lastrowid, "job_id": job_id, "content": content,
                "status": "draft-only-not-submitted",
                "notice": "Uses only learner-supplied facts; no AI-generated experience, contact details or achievements."}

    def drafts(self, job_id: str) -> list[dict]:
        self.get(job_id)
        with self.lock:
            rows = self.db.execute(
                "SELECT id,content,created_at FROM career_drafts WHERE job_id=? ORDER BY id DESC LIMIT 15",
                (job_id,),
            ).fetchall()
        return [{"id": x[0], "content": x[1], "created_at": x[2]} for x in rows]

    def update_application(self, job_id: str, stage: str, notes: str = "") -> dict:
        self.get(job_id)
        if stage not in ALLOWED_STATES or not isinstance(notes, str) or len(notes) > 1500:
            raise ValueError("Unsupported stage or notes too long")
        with self.lock:
            self.db.execute("""INSERT INTO career_applications(job_id,stage,notes,updated_at)
                VALUES (?,?,?,?) ON CONFLICT(job_id)
                DO UPDATE SET stage=excluded.stage,notes=excluded.notes,updated_at=excluded.updated_at""",
                (job_id, stage, notes, _utc()))
            self.db.commit()
        return {"job_id": job_id, "stage": stage, "notes": notes,
                "status": "manually-recorded-only",
                "notice": "PrepEzy never submits applications, sends outreach or verifies an employer response."}

    def applications(self) -> list[dict]:
        with self.lock:
            rows = self.db.execute(
                """SELECT a.job_id,a.stage,a.notes,a.updated_at,j.company,j.title,j.url
                   FROM career_applications a JOIN career_jobs j ON j.id=a.job_id
                   ORDER BY a.updated_at DESC,a.job_id LIMIT 200"""
            ).fetchall()
        return [{"job_id": r[0], "stage": r[1], "notes": r[2], "updated_at": r[3],
                 "company": r[4], "title": r[5], "url": r[6]} for r in rows]

    def delete_local_career_data(self) -> dict:
        with self.lock:
            self.db.execute("DELETE FROM career_applications")
            self.db.execute("DELETE FROM career_drafts")
            self.db.execute("DELETE FROM career_jobs")
            self.db.execute("DELETE FROM career_boards")
            self.db.execute("UPDATE career_profile SET facts='',preferred_location='' WHERE singleton=1")
            self.db.commit()
        return {"cleared": True}
