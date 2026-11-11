"""Stage 6: a single local evidence graph across verified assessment engines."""
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auralis import AuralisClient
from app.core import DemoEngine
from app.local_lab import LocalLab, SQL_TASKS
from app.main import create_app
from app.unified import LOCAL_NAMESPACE, UnifiedEvidence


def passed_code():
    return {
        "challenge_id": "sum_numbers", "passed": 2, "total": 2,
        "all_passed": True, "source": "restricted_ast_test_runner",
        "tests": [{"test": 1, "status": "pass", "public": True},
                  {"test": 2, "status": "pass", "public": False}],
    }


def make():
    local = LocalLab()
    unified = UnifiedEvidence(local)
    return local, unified


def test_empty_graph_uses_real_evidence_categories_and_marks_unassessed():
    _, graph = make()
    snapshot = graph.skillgraph()
    assert len(snapshot["skills"]) == 7
    assert snapshot["event_count"] == 0
    assert all(skill["status"] == "unassessed" for skill in snapshot["skills"])
    assert snapshot["recommendation"]["skill"] == "sql"
    assert "No single percentage" in snapshot["interpretation"]


def test_sql_and_core_viva_evidence_links_to_graph():
    local, unified = make()
    assert local.grade_sql("joins", SQL_TASKS["joins"]["reference"])["passed"]
    assert local.grade_viva("dbms-atomicity", "b")["correct"]
    result = unified.skillgraph()
    sql = next(s for s in result["skills"] if s["id"] == "sql")
    dbms = next(s for s in result["skills"] if s["id"] == "dbms")
    assert sql["distinct_assessments"] == 1
    assert sql["first_try_correct_unassisted"] == 1
    assert dbms["distinct_assessments"] == 1
    assert result["sources"]["sql"] == 1
    assert result["sources"]["core_viva"] == 1
    assert any(e["kind"] == "sql_execution" for e in unified.evidence()["events"])


def test_sql_retries_not_double_counted_and_first_wrong_remains_wrong():
    local, unified = make()
    assert not local.grade_sql("joins", "SELECT name AS employee, name AS department FROM employees")["passed"]
    assert local.grade_sql("joins", SQL_TASKS["joins"]["reference"])["passed"]
    s = next(s for s in unified.skillgraph()["skills"] if s["id"] == "sql")
    assert s["distinct_assessments"] == 1
    assert s["first_try_correct_unassisted"] == 0
    assert unified.evidence()["sources"]["sql"] == 2


def test_pattern_only_transfer_check_contributes_one_dsa_observation():
    _, unified = make()
    c = unified.patterns
    assert c.submit(LOCAL_NAMESPACE, "two-pointers", "brute", "a")["correct"]
    assert c.submit(LOCAL_NAMESPACE, "two-pointers", "signal", "b")["correct"]
    assert c.submit(LOCAL_NAMESPACE, "two-pointers", "transfer", "b")["correct"]
    dsa = next(s for s in unified.skillgraph()["skills"] if s["id"] == "dsa")
    assert dsa["distinct_assessments"] == 1
    assert dsa["first_try_correct_unassisted"] == 1
    assert unified.evidence()["sources"]["cracked_pattern"] == 3


def test_hint_assisted_pattern_transfer_is_not_independent_success():
    _, unified = make()
    c = unified.patterns
    c.submit(LOCAL_NAMESPACE, "bfs", "brute", "b")
    c.submit(LOCAL_NAMESPACE, "bfs", "signal", "a")
    assert c.hint(LOCAL_NAMESPACE, "bfs")["counts_as_assistance"]
    c.submit(LOCAL_NAMESPACE, "bfs", "transfer", "b")
    dsa = next(s for s in unified.skillgraph()["skills"] if s["id"] == "dsa")
    assert dsa["distinct_assessments"] == 1
    assert dsa["first_try_correct_unassisted"] == 0


def test_real_auralis_validated_runner_evidence_updates_python():
    _, unified = make()
    unified.record_auralis(passed_code())
    py = next(s for s in unified.skillgraph()["skills"] if s["id"] == "python")
    assert py["kind"] == "restricted_execution"
    assert py["distinct_assessments"] == 1
    assert py["first_try_correct_unassisted"] == 1
    assert unified.evidence()["sources"]["auralis_restricted_code"] == 1


def test_reject_inconsistent_auralis_grade_and_unverified_source():
    _, unified = make()
    for payload in [
        {**passed_code(), "source": "user-submitted"},
        {**passed_code(), "passed": 1},
        {**passed_code(), "challenge_id": "untrusted_python"},
        {**passed_code(), "tests": []},
    ]:
        with pytest.raises(ValueError):
            unified.record_auralis(payload)
    assert unified.skillgraph()["sources"]["auralis_restricted_code"] == 0


def test_changing_real_local_role_changes_roadmap_without_erasing_history():
    local, unified = make()
    old = unified.skillgraph()
    assert old["recommendation"]["skill"] == "sql"
    local.update_profile("ml", "Python", 30)
    new = unified.skillgraph()
    assert new["recommendation"]["skill"] == "python"
    assert sum(step["minutes"] for step in new["roadmap"]) <= 30
    assert new["profile"]["language"] == "Python"


def test_shared_local_records_persist_across_restart(tmp_path):
    db = tmp_path / "local.sqlite"
    first = LocalLab(db)
    bridge = UnifiedEvidence(first)
    first.grade_viva("dbms-atomicity", "b")
    bridge.patterns.submit(LOCAL_NAMESPACE, "two-pointers", "brute", "a")
    bridge.record_auralis(passed_code())
    reopened = UnifiedEvidence(LocalLab(db))
    sources = reopened.skillgraph()["sources"]
    assert sources["core_viva"] == 1
    assert sources["cracked_pattern"] == 1
    assert sources["auralis_restricted_code"] == 1


def test_delete_clears_all_verified_sources_including_pattern_hints():
    local, unified = make()
    local.grade_sql("joins", SQL_TASKS["joins"]["reference"])
    local.grade_viva("os-context", "a")
    unified.patterns.hint(LOCAL_NAMESPACE, "two-pointers")
    unified.patterns.submit(LOCAL_NAMESPACE, "two-pointers", "brute", "a")
    unified.record_auralis(passed_code())
    local.reset()
    unified.clear()
    assert unified.skillgraph()["event_count"] == 0
    assert unified.patterns.state(LOCAL_NAMESPACE, "two-pointers")["hint_used"] is False


def test_local_endpoint_unifies_sql_viva_cracked():
    app = create_app(DemoEngine(), local_lab=LocalLab())
    client = TestClient(app)
    base = client.get("/api/local/skillgraph").json()
    assert len(base["skills"]) == 7
    q = client.post("/api/local/sql/attempts", json={"challenge_id": "joins", "query": SQL_TASKS["joins"]["reference"]})
    assert q.status_code == 200 and q.json()["result"]["passed"]
    viva = client.post("/api/local/viva/attempts", json={"question_id": "dbms-atomicity", "choice_id": "b"})
    assert viva.status_code == 200 and viva.json()["result"]["correct"]
    url = "/api/local/cracked/patterns/two-pointers"
    assert client.get(url).json()["step"]["id"] == "brute"
    c = client.post(url + "/answers", json={"step_id": "brute", "choice_id": "a"})
    assert c.status_code == 200 and c.json()["result"]["correct"]
    sources = client.get("/api/local/skillgraph").json()["sources"]
    assert sources["sql"] == sources["core_viva"] == sources["cracked_pattern"] == 1
    assert client.get("/api/local/unified-evidence").json()["event_count"] == 3
    assert client.delete("/api/local/data").json()["cleared"]
    assert client.get("/api/local/unified-evidence").json()["event_count"] == 0


def test_synthetic_profile_is_not_implicitly_imported_into_local_graph():
    demo = DemoEngine()
    demo.submit("demo-ml", "dsa-1", "a")
    c = TestClient(create_app(demo, local_lab=LocalLab()))
    assert c.get("/api/local/skillgraph").json()["event_count"] == 0
    assert c.get("/api/demo/learners/demo-ml").json()["total_attempts"] == 1


def test_local_pattern_stage_skip_rejected():
    c = TestClient(create_app(DemoEngine(), local_lab=LocalLab()))
    u = "/api/local/cracked/patterns/bfs"
    r = c.post(u + "/answers", json={"step_id": "transfer", "choice_id": "b"})
    assert r.status_code == 422
    assert c.get(u).json()["step"]["id"] == "brute"


def test_local_auralis_unavailable_fails_openly_without_faking_result():
    c = TestClient(create_app(DemoEngine(), local_lab=LocalLab()))
    r = c.post("/api/local/auralis/code", json={
        "challenge_id": "sum_numbers", "code": "def solve(nums): return sum(nums)"
    })
    assert r.status_code == 503
    assert c.get("/api/local/skillgraph").json()["sources"]["auralis_restricted_code"] == 0


def test_local_auralis_http_contract_passes_only_verified_runner_output():
    def upstream(request):
        if request.url.path == "/api/practical/code":
            return httpx.Response(200, json=passed_code())
        return httpx.Response(404, json={"detail": "not found"})
    client = AuralisClient("http://127.0.0.1:8001", transport=httpx.MockTransport(upstream))
    api = TestClient(create_app(DemoEngine(), auralis_client=client, local_lab=LocalLab()))
    r = api.post("/api/local/auralis/code", json={
        "challenge_id": "sum_numbers",
        "code": "def solve(nums): return sum(nums)",
    })
    assert r.status_code == 200, r.text
    assert r.json()["result"]["source"] == "restricted_ast_test_runner"
    assert api.get("/api/local/skillgraph").json()["sources"]["auralis_restricted_code"] == 1


def test_many_retries_keep_original_first_attempt_not_lexicographic_order():
    local, unified = make()
    local.grade_viva("dbms-atomicity", "a")
    for _ in range(12):
        local.grade_viva("dbms-atomicity", "b")
    state = next(s for s in unified.skillgraph()["skills"] if s["id"] == "dbms")
    assert state["distinct_assessments"] == 1
    assert state["first_try_correct_unassisted"] == 0
