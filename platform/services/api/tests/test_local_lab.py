"""Real SQL execution and Core CS assessment contracts. No remote services required."""
import sqlite3

from fastapi.testclient import TestClient
from app.core import DemoEngine
from app.main import create_app
from app.local_lab import LocalLab, SQL_TASKS, _dataset, _execute_safe


def client(lab=None):
    return TestClient(create_app(DemoEngine(), local_lab=lab or LocalLab()))


def test_reference_sql_passes_both_real_fixtures():
    lab = LocalLab()
    for key, challenge in SQL_TASKS.items():
        result = lab.grade_sql(key, challenge["reference"])
        assert result["passed"], (key, result)
        assert result["tests_total"] == 2


def test_wrong_sql_is_not_falsely_passed():
    lab = LocalLab()
    result = lab.grade_sql("joins", "SELECT name AS employee, name AS department FROM employees")
    assert not result["passed"]
    assert result["tests_passed"] == 0


def test_sql_rejects_mutations_schema_access_and_extension_functions():
    lab = LocalLab()
    for query in [
        "DELETE FROM employees WHERE id=1",
        "SELECT * FROM sqlite_master",
        "SELECT load_extension('bad')",
        "WITH x AS (DELETE FROM employees RETURNING *) SELECT * FROM x",
        "PRAGMA database_list",
    ]:
        assert not lab.grade_sql("joins", query)["passed"], query


def test_rejects_multi_statement_and_recursive_resource_exhaustion():
    lab = LocalLab()
    for query in [
        "SELECT * FROM employees; DELETE FROM departments",
        "WITH RECURSIVE x(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM x) SELECT * FROM x",
    ]:
        assert not lab.grade_sql("joins", query)["passed"]


def test_catalog_does_not_expose_reference_queries_or_answer_keys():
    assert len(LocalLab.viva_catalog()["questions"]) == 12
    assert all("answer" not in q and "explanation" not in q for q in LocalLab.viva_catalog()["questions"])
    catalog = LocalLab.sql_catalog()
    assert len(catalog["challenges"]) == 5
    assert all("reference" not in challenge for challenge in catalog["challenges"])


def test_viva_is_checked_and_evidence_saved():
    lab = LocalLab()
    assert lab.grade_viva("dbms-atomicity", "b")["correct"]
    assert not lab.grade_viva("dbms-index", "b")["correct"]
    assert len(lab.evidence()["core"]) == 2
    assert lab.overview()["recorded_viva_attempts"] == 2


def test_real_local_profile_changes_study_plan():
    lab = LocalLab()
    assert lab.overview()["recommendation"]["topic"] == "sql"
    lab.update_profile("ml", "Python", 30)
    assert lab.profile()["target_role"] == "ML Engineer"
    assert sum(task["minutes"] for task in lab.overview()["roadmap"]) <= 30


def test_invalid_profile_is_not_accepted():
    lab = LocalLab()
    for role, lang, time in [
        ("invalid", "Java", 45), ("backend", "C++", 45), ("backend", "Java", 150)
    ]:
        try:
            lab.update_profile(role, lang, time)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid profile was accepted")


def test_first_attempt_evidence_persists_and_retries_do_not_inflate(tmp_path):
    path = tmp_path / "local.sqlite"
    a = LocalLab(path)
    a.grade_sql("joins", "SELECT name, name FROM employees")
    a.grade_sql("joins", SQL_TASKS["joins"]["reference"])
    b = LocalLab(path)
    track = next(x for x in b.overview()["tracks"] if x["id"] == "sql")
    assert track["assessed"] == 1
    assert track["correct_first_try"] == 0
    assert b.overview()["recorded_sql_attempts"] == 2
    b.reset()
    assert b.overview()["recorded_sql_attempts"] == 0


def test_sqlite_grader_blocks_system_table_access():
    conn = _dataset([])
    try:
        try:
            _execute_safe(conn, "SELECT * FROM sqlite_master")
        except sqlite3.DatabaseError:
            pass
        else:
            raise AssertionError("System metadata access allowed")
    finally:
        conn.close()


def test_real_api_grades_sql_and_changes_roadmap():
    c = client()
    assert c.get("/api/local/overview").json()["recorded_sql_attempts"] == 0
    r = c.post("/api/local/sql/attempts", json={
        "challenge_id": "joins", "query": SQL_TASKS["joins"]["reference"]
    })
    assert r.status_code == 200 and r.json()["result"]["passed"]
    state = c.get("/api/local/overview").json()
    assert state["recorded_sql_attempts"] == 1
    assert next(x for x in state["tracks"] if x["id"] == "sql")["assessed"] == 1


def test_profile_and_preferences_api_persist():
    c = client()
    r = c.put("/api/local/profile", json={"role": "data", "language": "Python", "daily_minutes": 30})
    assert r.status_code == 200 and r.json()["target_role"] == "Data Analyst"
    assert c.get("/api/local/overview").json()["profile"]["daily_minutes"] == 30


def test_origin_rejected_and_sql_mutations_not_executed():
    c = client()
    r = c.post("/api/local/sql/attempts", json={
        "challenge_id": "joins", "query": "DELETE FROM employees WHERE id=1"
    })
    assert r.status_code == 200 and not r.json()["result"]["passed"]
    assert c.delete("/api/local/data", headers={"Origin": "https://hostile.example"}).status_code == 403


def test_viva_http_and_local_delete_are_functional():
    c = client()
    question = c.get("/api/local/viva/questions").json()["questions"][0]
    assert "answer" not in question
    response = c.post("/api/local/viva/attempts", json={
        "question_id": "dbms-atomicity", "choice_id": "b"
    })
    assert response.status_code == 200 and response.json()["result"]["correct"]
    assert len(c.get("/api/local/evidence").json()["core"]) == 1
    assert c.delete("/api/local/data").json()["cleared"]
    assert c.get("/api/local/overview").json()["recorded_viva_attempts"] == 0


def test_no_auth_but_nonlocal_origin_denied():
    c = client()
    assert c.get("/api/local/profile", headers={"Origin": "http://localhost:3000"}).status_code == 200
    assert c.put("/api/local/profile", headers={"Origin": "https://evil.example"}, json={
        "role": "data", "language": "Java", "daily_minutes": 45
    }).status_code == 403
