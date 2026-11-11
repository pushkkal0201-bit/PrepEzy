"""Real PDF/DOCX/text extraction, provenance, truthful role alignment, local-only API."""
from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
import httpx
import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.career import CareerEngine
from app.core import DemoEngine
from app.local_lab import LocalLab, SQL_TASKS
from app.main import create_app
from app.resume import MAX_BYTES, ResumeIntelligence, _parse

TEXT = (
    "Resume\nEducation\nB.Tech Computer Science\n"
    "Projects\nCreated a FastAPI service with Python and SQL queries.\n"
    "Used Docker to run local tests for backend work.\n"
    "Experience\nBuilt an API and maintained SQL database tables.\n"
    "Technical Skills\nPython, SQL, Git, FastAPI\n"
    "Contact: student@example.org\nGitHub: github.com/example\n"
)


def pdf_document(line: str) -> bytes:
    """A valid, single-page PDF containing genuine selectable text."""
    escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = ("BT /F1 11 Tf 72 720 Td (" + escaped + ") Tj ET").encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    result = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(str(number).encode() + b" 0 obj\n" + obj + b"\nendobj\n")
    start = len(result)
    result.extend(f"xref\n0 {len(offsets)}\n".encode())
    result.extend(b"0000000000 65535 f \n")
    for position in offsets[1:]:
        result.extend(f"{position:010d} 00000 n \n".encode())
    result.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
                  f"startxref\n{start}\n%%EOF\n".encode())
    return bytes(result)


def docx_document() -> bytes:
    doc = Document()
    for line in TEXT.splitlines():
        doc.add_paragraph(line)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def upstream(request: httpx.Request) -> httpx.Response:
    assert request.method == "GET"
    assert request.url.host == "boards-api.greenhouse.io"
    return httpx.Response(200, json={"jobs": [{
        "id": 2099, "title": "Junior Backend Engineer",
        "location": {"name": "India"},
        "absolute_url": "https://boards.greenhouse.io/company/jobs/2099",
        "content": "<p>Python SQL Docker Kubernetes FastAPI</p>",
    }]})


def clients(tmp_path=None):
    local = LocalLab(tmp_path / "resume.sqlite" if tmp_path else ":memory:")
    cv = ResumeIntelligence(local.db, local.lock)
    career = CareerEngine(local.db, local.lock, transport=httpx.MockTransport(upstream))
    client = TestClient(create_app(DemoEngine(), local_lab=local,
                                   career_client=career, resume_client=cv))
    return client, local, cv


def add_job(client):
    assert client.post("/api/local/careers/boards", json={
        "provider": "greenhouse", "token": "company", "company": "Real Employer"
    }).status_code == 200
    assert client.post("/api/local/careers/refresh").json()["saved"] == 1
    return "greenhouse:company:2099"


def test_real_pdf_extraction_with_page_reference():
    data = pdf_document("Python SQL FastAPI projects and Docker testing for backend role")
    lines, count, kind = _parse("resume.pdf", data)
    assert kind == "pdf" and count == 1
    assert any("Python SQL FastAPI" in x["text"] for x in lines)
    assert all(x["locator"] == "page 1" for x in lines)


def test_real_docx_paragraph_extraction():
    data = docx_document()
    lines, count, kind = _parse("resume.docx", data)
    assert count == 1 and kind == "docx"
    assert any(x["text"] == "Technical Skills" for x in lines)
    assert any("Docker" in x["text"] for x in lines)


def test_utf8_plaintext_and_markdown_extraction():
    for name in ("resume.txt", "resume.md"):
        lines, pages, kind = _parse(name, TEXT.encode("utf-8"))
        assert pages == 1
        assert kind == name.rsplit(".", 1)[-1]
        assert any("FastAPI" in x["text"] for x in lines)


def test_reject_corrupt_pdf_encrypted_style_and_scanned_images():
    with pytest.raises(ValueError):
        _parse("resume.pdf", b"%PDF-bad file that's not a complete PDF")
    with pytest.raises(ValueError, match="Too little selectable text"):
        _parse("resume.pdf", pdf_document(""))


def test_reject_binary_text_unsupported_and_too_big():
    for filename, payload in [
        ("resume.txt", b"\x00" + TEXT.encode()),
        ("resume.exe", TEXT.encode()),
        ("resume.pdf", TEXT.encode()),
        ("resume.txt", b"X" * (MAX_BYTES + 1)),
        ("resume.txt", b"hi"),
    ]:
        with pytest.raises(ValueError):
            _parse(filename, payload)


def test_reject_docx_zip_bomb_before_parsing():
    out = BytesIO()
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", "X" * (13 * 1024 * 1024))
    with pytest.raises(ValueError, match="expands beyond"):
        _parse("resume.docx", out.getvalue())


def test_api_import_and_inspection_no_fake_verification():
    c, _, _ = clients()
    assert c.get("/api/local/resume/status").json()["uploaded"] is False
    imported = c.post("/api/local/resume/upload", files={
        "file": ("actual-resume.txt", TEXT.encode(), "text/plain")
    })
    assert imported.status_code == 200, imported.text
    state = imported.json()
    assert state["uploaded"] is True
    assert len(state["sha256"]) == 64
    assert "independently verified" in state["notice"]
    inspected = c.get("/api/local/resume/inspection").json()
    assert inspected["sections"]["projects"]["detected"] is True
    assert inspected["sections"]["skills"]["detected"] is True
    assert "python" in inspected["mentioned_skills"]
    assert "sql" in inspected["mentioned_skills"]
    assert "ATS score" in inspected["notice"]
    assert inspected["mentioned_skills"]["sql"][0]["locator"] == "document"


def test_document_replacement_and_local_resume_persistence(tmp_path):
    c, _, cv = clients(tmp_path)
    c.post("/api/local/resume/upload", files={"file": ("old.txt", TEXT.encode())})
    c.post("/api/local/resume/upload", files={"file": (
        "new.txt", ("Projects\nPython and SQL work completed in Java\n" * 3).encode()
    )})
    assert cv.status()["filename"] == "new.txt"
    reopened = ResumeIntelligence(LocalLab(tmp_path / "resume.sqlite").db, __import__("threading").RLock())
    assert reopened.status()["uploaded"] is True
    assert reopened.status()["filename"] == "new.txt"


def test_role_analysis_links_literal_resume_passages_and_assessment_evidence():
    c, _, _ = clients()
    job_id = add_job(c)
    c.post("/api/local/resume/upload", files={"file": ("resume.txt", TEXT.encode())})
    result = c.get("/api/local/resume/jobs/" + job_id + "/analysis").json()
    mentioned = {x["requirement"] for x in result["mentioned_requirements"]}
    assert {"python", "sql", "docker", "fastapi"} <= mentioned
    assert "kubernetes" in result["unmentioned_requirements"]
    assert any(x["requirement"] == "sql" for x in result["exact_resume_excerpts"])
    assert all("quote" in ref for x in result["mentioned_requirements"] for ref in x["mentions"])
    assert result["separate_assessment_evidence"] == []
    assert "no" not in result["interpretation"].lower() or "ATS" in result["interpretation"]


def test_sql_grade_updates_separate_evidence_without_modifying_resume_claim():
    c, _, _ = clients()
    job_id = add_job(c)
    c.post("/api/local/resume/upload", files={"file": ("resume.txt", TEXT.encode())})
    before = c.get("/api/local/resume/jobs/" + job_id + "/analysis").json()
    assert before["separate_assessment_evidence"] == []
    grade = c.post("/api/local/sql/attempts", json={
        "challenge_id": "joins", "query": SQL_TASKS["joins"]["reference"]
    })
    assert grade.status_code == 200 and grade.json()["result"]["passed"]
    after = c.get("/api/local/resume/jobs/" + job_id + "/analysis").json()
    assert any(x["requirement"] == "sql" and x["first_try_correct_unassisted"] == 1
               for x in after["separate_assessment_evidence"])
    assert after["mentioned_requirements"] == before["mentioned_requirements"]


def test_missing_resume_and_job_errors_are_explicit():
    c, _, _ = clients()
    assert c.get("/api/local/resume/inspection").status_code == 404
    assert c.get("/api/local/resume/jobs/nonexistent/analysis").status_code == 404
    job_id = add_job(c)
    assert c.get("/api/local/resume/jobs/" + job_id + "/analysis").status_code == 404


def test_resume_does_not_change_skillgraph_and_no_fictional_job():
    c, _, _ = clients()
    before = c.get("/api/local/skillgraph").json()
    c.post("/api/local/resume/upload", files={"file": ("resume.txt", TEXT.encode())})
    after = c.get("/api/local/skillgraph").json()
    assert before["event_count"] == after["event_count"] == 0
    assert c.get("/api/local/careers/jobs").json()["jobs"] == []


def test_explicit_resume_delete_and_full_reset():
    c, _, _ = clients()
    c.post("/api/local/resume/upload", files={"file": ("resume.txt", TEXT.encode())})
    assert c.delete("/api/local/resume").json()["deleted"] is True
    assert c.get("/api/local/resume/status").json()["uploaded"] is False
    c.post("/api/local/resume/upload", files={"file": ("resume.txt", TEXT.encode())})
    cleared = c.delete("/api/local/data").json()
    assert "resume_data" in cleared["sources"]
    assert c.get("/api/local/resume/status").json()["uploaded"] is False


def test_remote_origin_rejected_for_resume_upload():
    c, _, _ = clients()
    res = c.post("/api/local/resume/upload",
                 headers={"Origin": "https://unsafe.example"},
                 files={"file": ("resume.txt", TEXT.encode())})
    assert res.status_code == 403
    assert c.get("/api/local/resume/status").json()["uploaded"] is False


def test_truthful_role_preparation_proposes_review_not_fake_accomplishments():
    c, _, _ = clients()
    job_id = add_job(c)
    c.post("/api/local/resume/upload", files={"file": ("resume.txt", TEXT.encode())})
    analysis = c.get("/api/local/resume/jobs/" + job_id + "/analysis").json()
    assert any(x["skill"] == "kubernetes" and "Only add" in x["task"]
               for x in analysis["preparation_actions"])
    assert any(x["priority"] == "practice-and-document" for x in analysis["preparation_actions"])
    assert "hire" not in analysis["interpretation"].lower()


def test_upload_rejects_invalid_files_with_actual_http_422():
    c, _, _ = clients()
    for name, data in [
        ("fake.pdf", TEXT.encode()), ("resume.exe", TEXT.encode()),
        ("blank.txt", b"empty")
    ]:
        r = c.post("/api/local/resume/upload", files={"file": (name, data)})
        assert r.status_code == 422, (name, r.text)
    assert c.get("/api/local/resume/status").json()["uploaded"] is False
