"""Real, local-only Serviette REST adapter and watched-folder notes.

Serviette independently watches PREPEZY_KNOWLEDGE_DIR and indexes documents.
PrepEzy never pretends a saved note has already been indexed. Actual retrieval
and generated answers always come from the upstream Serviette REST API.
"""
from __future__ import annotations

import math
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import httpx

ALLOWED_SUFFIXES = {".md", ".txt"}
NOTE_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,60}\.(?:md|txt)$")
KNOWLEDGE_SUGGESTIONS = {
    "sql": "SQL joins GROUP BY HAVING query optimization",
    "dbms": "database normalization indexes and transactions",
    "os": "operating system processes threads synchronization deadlocks",
    "cn": "computer networking TCP IP DNS HTTP routing",
    "oop": "object oriented programming encapsulation inheritance polymorphism",
    "dsa": "algorithm patterns two pointers binary search graphs BFS",
    "coding": "coding interview problem solving testing and time complexity",
    "python": "Python functions loops lists dictionaries and testing",
}


class ServietteUnavailable(RuntimeError):
    """Upstream was not ready or refused the real request."""


class NotesFolder:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.mkdir(parents=True, exist_ok=True)

    def _file(self, filename: str) -> Path:
        if not NOTE_NAME.fullmatch(filename):
            raise ValueError("Use a safe .md or .txt filename (letters, numbers, - or _).")
        return self.path / filename

    def list(self) -> list[dict]:
        records = []
        for item in sorted(self.path.iterdir()):
            if item.is_symlink() or not item.is_file() or not NOTE_NAME.fullmatch(item.name):
                continue
            stat = item.stat()
            records.append({"name": item.name, "bytes": stat.st_size,
                            "status": "saved-locally-not-necessarily-indexed"})
        return records[:200]

    def put(self, filename: str, body: str) -> dict:
        target = self._file(filename)
        if target.is_symlink():
            raise ValueError("Refusing to overwrite a symbolic link")
        raw = body.encode("utf-8")
        if not body.strip() or len(raw) > 50_000:
            raise ValueError("Notes must contain 1–50,000 UTF-8 bytes")
        with tempfile.NamedTemporaryFile(mode="wb", dir=str(self.path),
                                         prefix=".prepezy-", delete=False) as handle:
            tmp = Path(handle.name)
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            tmp.replace(target)
        finally:
            tmp.unlink(missing_ok=True)
        return {"filename": filename, "bytes": len(raw),
                "status": "saved-awaiting-serviette-indexing",
                "detail": "Serviette's watcher will index this file when configured and running; verify with the indexed documents endpoint."}

    def read(self, filename: str) -> str:
        target = self._file(filename)
        if target.is_symlink() or not target.is_file() or target.stat().st_size > 50_000:
            raise ValueError("Note not found or exceeds read limit")
        return target.read_text(encoding="utf-8")

    def delete(self, filename: str) -> dict:
        target = self._file(filename)
        if target.is_symlink() or not target.is_file():
            raise ValueError("Note not found")
        target.unlink()
        return {"filename": filename, "status": "deleted-locally-index-update-pending"}


def serviette_url(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"}
            or not parsed.port or parsed.username or parsed.password
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise ValueError("Serviette must use a local http://127.0.0.1:<port> endpoint")
    return f"http://127.0.0.1:{parsed.port}"


def suggest_from_skillgraph(skillgraph: dict) -> dict:
    recommendation = skillgraph.get("recommendation") or {}
    skill = recommendation.get("skill", "dsa")
    if skill not in KNOWLEDGE_SUGGESTIONS:
        skill = "dsa"
    return {
        "skill": skill,
        "query": KNOWLEDGE_SUGGESTIONS[skill],
        "reason": recommendation.get("why", "Find source-grounded learning materials for the selected skill."),
        "based_on": "local-preploop-evidence",
        "notice": "This is a suggested retrieval query, not a claim that Serviette found relevant content.",
    }


def _hit(item: dict) -> dict:
    if not isinstance(item, dict):
        raise ServietteUnavailable("Unexpected upstream retrieval result")
    metadata = item.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    text = item.get("text")
    if not isinstance(text, str):
        text = ""
    score = item.get("score")
    safe_score = round(float(score), 5) if isinstance(score, (float, int)) and math.isfinite(float(score)) else None
    path = metadata.get("path") or metadata.get("name") or metadata.get("source")
    return {
        "text": text[:3500],
        "score": safe_score,
        "source": str(path)[:500] if path is not None else "indexed-source-unidentified",
        "metadata": {str(k): str(v)[:300] for k, v in metadata.items()
                     if k in ("path", "name", "source", "modified_at", "page")},
    }


class ServietteGateway:
    def __init__(self, url: str = "http://127.0.0.1:8989",
                 enabled: bool = False, transport: httpx.AsyncBaseTransport | None = None):
        self.url = serviette_url(url)
        self.enabled = enabled
        self._transport = transport

    async def _request(self, method: str, route: str, **kwargs):
        if not self.enabled:
            raise ServietteUnavailable("Serviette is disabled; set PREPEZY_SERVIETTE_ENABLED=1 after starting its local service.")
        # Do not follow redirects; no arbitrary user-selected URL/SSRF.
        try:
            async with httpx.AsyncClient(base_url=self.url, transport=self._transport,
                                         timeout=httpx.Timeout(12.0, connect=2.0),
                                         follow_redirects=False) as client:
                response = await client.request(method, route, **kwargs)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise ServietteUnavailable("Local Serviette service is unreachable") from exc
        if response.status_code in (503, 502, 504):
            raise ServietteUnavailable("Serviette index or server not ready")
        if response.status_code >= 400:
            if response.status_code == 501:
                return {"upstream_not_implemented": True}
            raise ServietteUnavailable(f"Serviette returned HTTP {response.status_code}")
        try:
            obj = response.json()
        except ValueError as exc:
            raise ServietteUnavailable("Invalid JSON from Serviette") from exc
        if not isinstance(obj, dict):
            raise ServietteUnavailable("Unexpected response format from Serviette")
        return obj

    async def status(self) -> dict:
        if not self.enabled:
            return {"enabled": False, "connected": False, "status": "disabled",
                    "endpoint": self.url, "message": "Start Serviette and opt in with PREPEZY_SERVIETTE_ENABLED=1."}
        try:
            health = await self._request("GET", "/api/v1/health")
            connected = health.get("status") == "ok"
            stats = await self._request("GET", "/api/v1/stats") if connected else {}
            return {"enabled": True, "connected": connected,
                    "status": "ready" if connected else "not-ready",
                    "backend": stats.get("backend"),
                    "indexed_documents": stats.get("documents"),
                    "index_stats_available": stats.get("stats_available", True),
                    "endpoint": self.url,
                    "message": "Health only confirms the server. Check indexed documents before claiming ingestion completed."}
        except ServietteUnavailable as exc:
            return {"enabled": True, "connected": False, "status": "unavailable",
                    "endpoint": self.url, "message": str(exc)}

    async def documents(self, search: str = "", limit: int = 50) -> dict:
        if len(search) > 120 or not 1 <= limit <= 100:
            raise ValueError("Search must be <=120 characters and limit 1–100")
        data = await self._request("GET", "/api/v1/documents", params={"q": search, "limit": limit})
        if data.get("upstream_not_implemented"):
            return {"supported": False, "documents": [], "notice": "This vector DB cannot enumerate indexed documents."}
        docs = []
        for document in data.get("documents", []):
            if not isinstance(document, dict):
                continue
            docs.append({"id": str(document.get("id", ""))[:500],
                         "name": str(document.get("name", ""))[:300],
                         "chunks": int(document.get("chunks", 0))})
        return {"supported": True, "total": int(data.get("total", 0)),
                "matched": int(data.get("matched", 0)), "truncated": bool(data.get("truncated")),
                "documents": docs, "notice": "These documents are reported by the actual Serviette index, not by the local folder listing."}

    async def retrieve(self, query: str, k: int = 5, answer: bool = False) -> dict:
        if not 3 <= len(query.strip()) <= 800 or not 1 <= k <= 8:
            raise ValueError("Question must be 3–800 characters and k between 1 and 8")
        route = "/api/v1/rag" if answer else "/api/v1/retrieve"
        value = await self._request("POST", route, json={"query": query.strip(), "k": k})
        if answer and value.get("upstream_not_implemented"):
            # Explicit retrieval-only fallback, never invent a generated answer.
            return await self.retrieve(query, k, False)
        hits = value.get("sources" if answer else "results", [])
        if not isinstance(hits, list):
            raise ServietteUnavailable("Serviette response is missing a valid result list")
        citations = [_hit(x) for x in hits[:8]]
        is_answer = answer and isinstance(value.get("answer"), str)
        return {"question": query.strip(),
                "mode": "source-grounded-answer" if is_answer else "retrieval-only",
                "answer": value["answer"][:10000] if is_answer else None,
                "sources": citations,
                "source_count": len(citations),
                "grounded": bool(citations),
                "upstream_mode": value.get("mode", "search"),
                "notice": (
                    "Upstream returned an answer without supporting sources; treat as unverified."
                    if is_answer and not citations
                    else "Serviette /rag is unavailable without its configured answer model; showing retrieved passages only."
                    if answer and not is_answer
                    else value.get("notice") or "Citations are taken from Serviette retrieval metadata."
                ),
                "provider": "serviette-rest-api-v1"}
