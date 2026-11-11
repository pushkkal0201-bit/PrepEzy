"""Serviette API contract, local file ingestion, source provenance and truthful fallbacks."""
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.core import DemoEngine
from app.knowledge import NotesFolder, ServietteGateway, ServietteUnavailable, suggest_from_skillgraph, serviette_url
from app.local_lab import LocalLab, SQL_TASKS
from app.main import create_app


def transport(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/api/v1/health":
        return httpx.Response(200, json={"status": "ok"})
    if path == "/api/v1/stats":
        return httpx.Response(200, json={"backend": "duckdb", "documents": 2, "chunks": 8})
    if path == "/api/v1/documents":
        return httpx.Response(200, json={"total": 2, "matched": 1, "truncated": False,
            "documents": [{"id": "/docs/binary-search.md", "name": "binary-search.md",
                           "chunks": 4, "metadata": {"path": "/docs/binary-search.md"}}]})
    if path == "/api/v1/retrieve":
        body = __import__("json").loads(request.content)
        assert body["query"] and 1 <= body["k"] <= 8
        return httpx.Response(200, json={"results": [
            {"text": "Binary search halves the interval.", "score": 0.91,
             "metadata": {"path": "/docs/binary-search.md", "page": 1}}
        ]})
    if path == "/api/v1/rag":
        return httpx.Response(200, json={"answer": "Binary search takes O(log n) steps.",
            "sources": [{"text": "The interval is halved.", "score": 0.94,
                         "metadata": {"path": "/docs/binary-search.md"}}],
            "mode": "search", "documents": [], "notice": None})
    return httpx.Response(404, json={"detail": "not found"})


def make(tmp_path, handler=transport, enabled=True):
    client = ServietteGateway("http://127.0.0.1:8989", enabled,
                             transport=httpx.MockTransport(handler))
    api = create_app(DemoEngine(), local_lab=LocalLab(),
                     knowledge_client=client, notes_folder=NotesFolder(tmp_path / "notes"))
    return TestClient(api)


def test_knowledge_health_and_server_reported_stats(tmp_path):
    client = make(tmp_path)
    state = client.get("/api/local/knowledge/status").json()
    assert state["upstream"]["connected"] is True
    assert state["upstream"]["backend"] == "duckdb"
    assert state["upstream"]["indexed_documents"] == 2
    assert state["saved_notes"] == 0


def test_real_upstream_retrieval_provenance_preserved(tmp_path):
    client = make(tmp_path)
    result = client.post("/api/local/knowledge/query",
                         json={"question": "Explain binary search", "mode": "retrieve"}).json()
    assert result["answer"] is None
    assert result["mode"] == "retrieval-only"
    assert result["grounded"] is True
    assert result["sources"][0]["source"] == "/docs/binary-search.md"
    assert result["sources"][0]["text"] == "Binary search halves the interval."
    assert result["provider"] == "serviette-rest-api-v1"


def test_rag_generated_answer_requires_upstream_model_and_sources(tmp_path):
    client = make(tmp_path)
    value = client.post("/api/local/knowledge/query", json={
        "question": "Explain binary search", "mode": "answer"
    }).json()
    assert value["mode"] == "source-grounded-answer"
    assert value["answer"] == "Binary search takes O(log n) steps."
    assert value["sources"][0]["source"].endswith("binary-search.md")


def test_rag_without_llm_does_retrieval_only_not_fake_answer(tmp_path):
    def handler(request):
        if request.url.path == "/api/v1/rag":
            return httpx.Response(501, json={"detail": "LLM not configured"})
        return transport(request)
    client = make(tmp_path, handler)
    result = client.post("/api/local/knowledge/query", json={
        "question": "Explain binary search", "mode": "answer"
    }).json()
    assert result["mode"] == "retrieval-only"
    assert result["answer"] is None
    assert "without its configured answer model" in result["notice"]


def test_note_save_read_list_delete_and_not_claim_indexed(tmp_path):
    c = make(tmp_path)
    saved = c.post("/api/local/knowledge/notes",
                   json={"filename": "binary-search.md", "content": "# Binary search\nHalve intervals."})
    assert saved.status_code == 200
    assert saved.json()["status"] == "saved-awaiting-serviette-indexing"
    entries = c.get("/api/local/knowledge/notes").json()["notes"]
    assert len(entries) == 1
    assert entries[0]["status"] == "saved-locally-not-necessarily-indexed"
    assert c.get("/api/local/knowledge/notes/binary-search.md").json()["content"].startswith("#")
    assert c.delete("/api/local/knowledge/notes/binary-search.md").status_code == 200
    assert c.get("/api/local/knowledge/notes").json()["notes"] == []


def test_malicious_note_names_and_empty_content_rejected(tmp_path):
    c = make(tmp_path)
    for name in ("../outside.md", "../../secret.txt", "bad.exe", ".env", "a/b.txt", "SPACE NAME.md"):
        assert c.post("/api/local/knowledge/notes",
                      json={"filename": name, "content": "valid text"}).status_code in (422,)
    assert c.post("/api/local/knowledge/notes",
                  json={"filename": "valid.txt", "content": "   "}).status_code == 422
    assert list(tmp_path.iterdir()) == [tmp_path / "notes"]


def test_no_ssrf_untrusted_service_url():
    for url in ("https://127.0.0.1:8989", "http://evil.com:8989", "http://169.254.169.254:80",
                "http://127.0.0.1:8989/api/v1", "http://user:password@127.0.0.1:8989",
                "http://127.0.0.1:8989?target=evil"):
        try:
            serviette_url(url)
        except ValueError:
            pass
        else:
            raise AssertionError("Accepted untrusted endpoint " + url)


def test_disabled_upstream_must_not_claim_success(tmp_path):
    c = make(tmp_path, enabled=False)
    info = c.get("/api/local/knowledge/status").json()
    assert info["upstream"]["connected"] is False
    assert c.post("/api/local/knowledge/query",
                  json={"question": "What is indexing?"}).status_code == 503
    assert c.get("/api/local/knowledge/documents").status_code == 503


def test_backend_unavailable_is_a_real_error(tmp_path):
    def handler(request):
        return httpx.Response(503, json={"detail": "index not ready"})
    c = make(tmp_path, handler)
    assert c.post("/api/local/knowledge/query", json={
        "question": "Any learning context?"}).status_code == 503


def test_indexed_documents_are_from_serviette_not_notes(tmp_path):
    c = make(tmp_path)
    c.post("/api/local/knowledge/notes", json={"filename": "new-note.md", "content": "New note not indexed yet"})
    docs = c.get("/api/local/knowledge/documents?q=binary").json()
    assert docs["supported"] is True
    assert docs["documents"][0]["name"] == "binary-search.md"
    assert "new-note.md" not in str(docs)


def test_recommendation_uses_real_local_skillgraph_not_generated_claim(tmp_path):
    lab = LocalLab()
    client = ServietteGateway(enabled=False)
    c = TestClient(create_app(DemoEngine(), local_lab=lab, knowledge_client=client,
                              notes_folder=NotesFolder(tmp_path / "notes")))
    prior = c.get("/api/local/knowledge/recommendation").json()
    assert prior["based_on"] == "local-preploop-evidence"
    assert prior["skill"] in ("sql", "coding")
    c.put("/api/local/profile", json={"role": "ml", "language": "Python", "daily_minutes": 30})
    later = c.get("/api/local/knowledge/recommendation").json()
    assert later["skill"] in ("python", "coding")
    assert later["query"]


def test_reject_blank_or_large_question(tmp_path):
    c = make(tmp_path)
    for value in ("", "a" * 900):
        assert c.post("/api/local/knowledge/query", json={"question": value}).status_code == 422


def test_no_citations_means_answer_unverified(tmp_path):
    def handler(request):
        if request.url.path == "/api/v1/rag":
            return httpx.Response(200, json={"answer": "Unverified response", "sources": []})
        return transport(request)
    c = make(tmp_path, handler)
    answer = c.post("/api/local/knowledge/query", json={
        "question": "Do I have supporting evidence?", "mode": "answer"
    }).json()
    assert answer["grounded"] is False
    assert "unverified" in answer["notice"]


def test_source_document_catalog_unsupported_is_explicit(tmp_path):
    def handler(request):
        if request.url.path == "/api/v1/documents":
            return httpx.Response(501, json={"detail": "unsupported backend"})
        return transport(request)
    c = make(tmp_path, handler)
    result = c.get("/api/local/knowledge/documents").json()
    assert result["supported"] is False
