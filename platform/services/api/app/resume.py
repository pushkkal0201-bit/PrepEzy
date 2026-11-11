"""Stage 10 — local, evidence-aware resume inspection and role preparation.

This is document *inspection*, not independent verification of career claims.
No LLM, fabricated qualifications, ATS score or employer-side application.
Bytes and extracted text remain in the local single-device workspace; uploaded
binary bytes are never persisted. Untrusted PDF/DOCX parsing requires caution.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import re
import sqlite3
from threading import RLock
from zipfile import BadZipFile, ZipFile

from docx import Document
from pypdf import PdfReader

from .career import KEYWORDS, EVIDENCE_SKILLS, _matches

MAX_BYTES = 2 * 1024 * 1024
MAX_TEXT = 80_000
MAX_PAGES = 8
MAX_DOCX_UNCOMPRESSED = 12 * 1024 * 1024
SUPPORTED = {".pdf", ".docx", ".txt", ".md"}
HEADINGS = {
    "education": ("education", "academic background", "academics"),
    "experience": ("experience", "employment", "work experience", "internships"),
    "projects": ("projects", "personal projects", "selected projects"),
    "skills": ("skills", "technical skills", "technologies", "tech stack"),
}
CONTACT_EMAIL = re.compile(r"(?<![^\s])[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}")
CONTACT_URL = re.compile(r"(?:https?://|github\.com/|linkedin\.com/)", re.I)


def _lines(pages: list[tuple[str, str]]) -> list[dict]:
    result = []
    for label, body in pages:
        for number, raw in enumerate(body.splitlines(), 1):
            value = " ".join(raw.strip().split())
            if value and len(result) < 650:
                result.append({"locator": label, "line": number, "text": value[:600]})
    return result


def _parse(filename: str, content: bytes) -> tuple[list[dict], int, str]:
    """Parse actual bytes, enforce size caps, explicitly decline scanned PDFs."""
    if not isinstance(content, bytes) or not 1 <= len(content) <= MAX_BYTES:
        raise ValueError("Document must contain 1 byte to 2 MiB")
    if not isinstance(filename, str) or len(filename) > 120:
        raise ValueError("Invalid document name")
    safe = filename.replace("\\", "/").split("/")[-1]
    if not safe or safe.startswith(".") or any(ord(c) < 32 for c in safe):
        raise ValueError("Invalid document name")
    suffix = ("." + safe.rsplit(".", 1)[-1]).lower() if "." in safe else ""
    if suffix not in SUPPORTED:
        raise ValueError("Choose a PDF, DOCX, TXT or Markdown file")
    pages: list[tuple[str, str]] = []
    if suffix == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise ValueError("File is not a valid PDF")
        try:
            reader = PdfReader(BytesIO(content), strict=False)
            if reader.is_encrypted:
                raise ValueError("Encrypted PDFs are not supported; provide an unencrypted copy")
            count = len(reader.pages)
            if not 1 <= count <= MAX_PAGES:
                raise ValueError("PDF must contain 1–8 pages")
            for i, page in enumerate(reader.pages, 1):
                pages.append((f"page {i}", page.extract_text() or ""))
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Could not safely extract text from this PDF") from exc
    elif suffix == ".docx":
        try:
            with ZipFile(BytesIO(content)) as archive:
                infos = archive.infolist()
                if len(infos) > 350 or sum(x.file_size for x in infos) > MAX_DOCX_UNCOMPRESSED:
                    raise ValueError("DOCX expands beyond supported limits")
                if not any(x.filename == "word/document.xml" for x in infos):
                    raise ValueError("Not a valid Word document")
            doc = Document(BytesIO(content))
            paragraphs = [p.text for p in doc.paragraphs]
            for table in doc.tables:
                for row in table.rows:
                    paragraphs.append(" | ".join(cell.text for cell in row.cells))
            pages = [("document", "\n".join(paragraphs))]
        except ValueError:
            raise
        except (BadZipFile, OSError, Exception) as exc:
            raise ValueError("Could not safely extract text from this DOCX") from exc
    else:
        if b"\x00" in content:
            raise ValueError("Binary content is not supported as text")
        try:
            pages = [("document", content.decode("utf-8-sig"))]
        except UnicodeDecodeError as exc:
            raise ValueError("TXT and Markdown documents must be UTF-8") from exc

    total = sum(len(text) for _, text in pages)
    if total > MAX_TEXT:
        raise ValueError("Extracted document text exceeds 80,000 characters")
    if total < 25 or len(" ".join(text for _, text in pages).split()) < 5:
        raise ValueError(
            "Too little selectable text was found. Scanned/image-only documents need OCR; "
            "this version does not run OCR or invent missing content."
        )
    content_lines = _lines(pages)
    if not content_lines:
        raise ValueError("No usable text lines were found")
    return content_lines, len(pages), suffix.lstrip(".")


def _sections(lines: list[dict]) -> dict:
    present = {}
    for section, alternatives in HEADINGS.items():
        matches = [x for x in lines if x["text"].casefold().strip(" :|-") in alternatives]
        present[section] = [{"locator": x["locator"], "line": x["line"]} for x in matches[:3]]
    return present


def _extract_signals(lines: list[dict]) -> dict:
    labels = {}
    for skill, patterns in KEYWORDS.items():
        evidence = [x for x in lines if _matches(x["text"], patterns)]
        if evidence:
            labels[skill] = [
                {"locator": x["locator"], "line": x["line"], "quote": x["text"][:300]}
                for x in evidence[:3]
            ]
    return labels


class ResumeIntelligence:
    def __init__(self, db: sqlite3.Connection, lock: RLock):
        self.db, self.lock = db, lock
        with lock:
            db.execute("""CREATE TABLE IF NOT EXISTS local_resume(
                id INTEGER PRIMARY KEY CHECK(id=1),
                filename TEXT NOT NULL,
                file_format TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                page_count INTEGER NOT NULL,
                lines_json TEXT NOT NULL,
                imported_at TEXT NOT NULL
            )""")
            db.commit()

    def upload(self, filename: str, content: bytes) -> dict:
        lines, page_count, file_format = _parse(filename, content)
        digest = sha256(content).hexdigest()
        imported = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.lock:
            self.db.execute("""INSERT INTO local_resume
                (id,filename,file_format,sha256,page_count,lines_json,imported_at)
                VALUES (1,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    filename=excluded.filename,file_format=excluded.file_format,
                    sha256=excluded.sha256,page_count=excluded.page_count,
                    lines_json=excluded.lines_json,imported_at=excluded.imported_at""",
                (filename.replace("\\", "/").split("/")[-1], file_format,
                 digest, page_count, json.dumps(lines), imported))
            self.db.commit()
        return self.status()

    def status(self) -> dict:
        with self.lock:
            row = self.db.execute(
                "SELECT filename,file_format,sha256,page_count,lines_json,imported_at FROM local_resume WHERE id=1"
            ).fetchone()
        if not row:
            return {"uploaded": False, "notice": "No resume imported. No candidate details inferred."}
        name, format_, checksum, pages, serialized, imported = row
        return {"uploaded": True, "filename": name, "format": format_,
                "sha256": checksum, "pages": pages,
                "extracted_lines": len(json.loads(serialized)),
                "imported_at": imported,
                "notice": ("Selectable text was extracted from the supplied file. "
                           "Resume statements are self-reported, not independently verified.")}

    def _content(self) -> list[dict]:
        with self.lock:
            row = self.db.execute("SELECT lines_json FROM local_resume WHERE id=1").fetchone()
        if not row:
            raise ValueError("Import a resume first")
        return json.loads(row[0])

    def inspect(self) -> dict:
        lines = self._content()
        sections = _sections(lines)
        skills = _extract_signals(lines)
        entire_text = "\n".join(x["text"] for x in lines)
        issues = []
        for section, refs in sections.items():
            if not refs:
                issues.append({
                    "type": "structure",
                    "message": f"No obvious '{section}' heading was detected. Check the extracted text; layouts vary."
                })
        if not CONTACT_EMAIL.search(entire_text):
            issues.append({"type": "contact", "message": "No email address detected in extracted text."})
        if not CONTACT_URL.search(entire_text):
            issues.append({"type": "portfolio", "message": "No recognizable GitHub, LinkedIn or URL reference detected."})
        return {
            "document": self.status(),
            "sections": {name: {"detected": bool(refs), "references": refs}
                         for name, refs in sections.items()},
            "mentioned_skills": skills,
            "skill_mention_count": len(skills),
            "checks": issues,
            "sample_lines": lines[:18],
            "notice": ("This checks extracted structure and literal keywords only. "
                       "Skill mentions and resume claims are not verified competence. "
                       "No invented ATS score, employer feedback or qualifications."),
        }

    def for_job(self, job: dict, graph: dict) -> dict:
        lines = self._content()
        detected = _extract_signals(lines)
        mentioned, unmentioned = [], []
        for tag in job.get("requested_skills", []):
            refs = detected.get(tag, [])
            if refs:
                mentioned.append({"requirement": tag, "mentions": refs})
            else:
                unmentioned.append(tag)
        skills = {x["id"]: x for x in graph["skills"]}
        evidence = []
        for tag in job.get("requested_skills", []):
            sid = EVIDENCE_SKILLS.get(tag)
            if not sid or sid not in skills:
                continue
            state = skills[sid]
            if state["distinct_assessments"]:
                evidence.append({
                    "requirement": tag, "skillgraph_skill": sid,
                    "independent_checks": state["distinct_assessments"],
                    "first_try_correct_unassisted": state["first_try_correct_unassisted"],
                    "interpretation": "Small verified assessment sample; not proof of workplace expertise.",
                })
        actions = []
        for tag in unmentioned[:5]:
            actions.append({
                "priority": "review-requirement",
                "skill": tag,
                "task": f"Check whether you genuinely have experience with {tag}. "
                        "Only add a resume statement if you can substantiate it.",
                "reason": "This requirement was found in the employer posting but not in extracted resume text.",
            })
        for tag in [x for x in job.get("requested_skills", []) if x not in unmentioned][:5]:
            sid = EVIDENCE_SKILLS.get(tag)
            if sid in skills and not skills[sid]["distinct_assessments"]:
                actions.append({
                    "priority": "practice-and-document",
                    "skill": tag,
                    "task": f"Complete a relevant assessment/project for {tag}; record the actual outcome.",
                    "reason": "The resume mentions this skill but PrepEzy has no independent assessment evidence.",
                })
        for step in graph.get("roadmap", []):
            if len(actions) >= 8:
                break
            actions.append({
                "priority": "preploop",
                "skill": step["skill"],
                "task": f"Practice {step['activity'].replace('-', ' ')} for {step['minutes']} minutes.",
                "reason": step["why"],
            })
        brief = []
        for item in mentioned:
            for ref in item["mentions"][:1]:
                if len(brief) >= 6:
                    break
                brief.append({"requirement": item["requirement"], **ref})
        return {
            "job": {"id": job["id"], "company": job["company"], "title": job["title"],
                    "provider": job["provider"], "url": job["url"],
                    "fetched_at": job["fetched_at"]},
            "resume": self.status(),
            "requirements_count": len(job.get("requested_skills", [])),
            "mentioned_requirements": mentioned,
            "unmentioned_requirements": unmentioned,
            "separate_assessment_evidence": evidence,
            "preparation_actions": actions[:8],
            "exact_resume_excerpts": brief,
            "interpretation": (
                "Literal resume mentions are unverified self-reported text; "
                "SkillGraph evidence is separate and limited. "
                "Missing keyword text does not imply missing competence. "
                "No ATS ranking or hiring prediction is calculated."
            ),
        }

    def clear(self) -> dict:
        with self.lock:
            self.db.execute("DELETE FROM local_resume")
            self.db.commit()
        return {"deleted": True, "notice": "Extracted resume text and metadata deleted from the local database."}
