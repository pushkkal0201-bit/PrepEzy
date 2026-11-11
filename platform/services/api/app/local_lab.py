"""PrepEzy local-first, authentication-free practical assessment engine.

Real, server-executed read-only SQL + independent CS knowledge checks.
One local workspace only. No public hosting, no arbitrary Python execution.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path
from threading import RLock

ROLES = {
    "backend": {"label": "Backend Engineer", "weights": {"sql": 1.0, "dbms": 0.95, "os": 0.7, "cn": 0.8, "oop": 0.75}},
    "data": {"label": "Data Analyst", "weights": {"sql": 1.0, "dbms": 0.8, "os": 0.2, "cn": 0.2, "oop": 0.35}},
    "ml": {"label": "ML Engineer", "weights": {"sql": 0.75, "dbms": 0.65, "os": 0.55, "cn": 0.4, "oop": 0.55}},
    "fullstack": {"label": "Full-stack Engineer", "weights": {"sql": 0.95, "dbms": 0.85, "os": 0.45, "cn": 0.85, "oop": 0.8}},
}

DEPARTMENTS = [(1, "Engineering"), (2, "Sales"), (3, "Support"), (4, "Research"), (5, "Design")]
FIXTURES = (
    [(1, "Anya", 1, 110000, 1), (2, "Dev", 1, 85000, 1), (3, "Ira", 1, 65000, 1),
     (4, "Om", 2, 78000, 1), (5, "Zara", 2, 56000, 1), (6, "Noor", 2, 30000, 0),
     (7, "Mira", 3, 54000, 1), (8, "Aarav", 4, 100000, 0)],
    [(11, "Kiran", 1, 75000, 1), (12, "Ravi", 1, 75000, 1), (13, "Meera", 1, 54000, 1),
     (14, "Asha", 2, 105000, 1), (15, "Kabir", 3, 49000, 1), (16, "Sana", 3, 51000, 1),
     (17, "Tara", 4, 90000, 1), (18, "Dia", 5, 43000, 0)],
)

SQL_TASKS = {
    "joins": {
        "title": "Join employees with departments", "topic": "JOIN",
        "prompt": "For active employees, return two columns named employee and department with the employee's name and department name.",
        "reference": "SELECT e.name AS employee, d.name AS department FROM employees e JOIN departments d ON d.id=e.department_id WHERE e.active=1",
    },
    "groups": {
        "title": "Count active employees by department", "topic": "GROUP BY + HAVING",
        "prompt": "Return department and headcount for departments that have at least two active employees.",
        "reference": "SELECT d.name AS department, COUNT(*) AS headcount FROM departments d JOIN employees e ON e.department_id=d.id WHERE e.active=1 GROUP BY d.id HAVING COUNT(*)>=2",
    },
    "anti-join": {
        "title": "Departments with no active employees", "topic": "LEFT JOIN",
        "prompt": "Return a single column department containing departments with zero active employees. Inactive employees do not count.",
        "reference": "SELECT d.name AS department FROM departments d LEFT JOIN employees e ON e.department_id=d.id AND e.active=1 WHERE e.id IS NULL",
    },
    "subquery": {
        "title": "Earners above their department average", "topic": "Correlated query",
        "prompt": "Among active employees, return employee and salary for employees earning strictly more than the average active salary in their own department.",
        "reference": "SELECT e.name AS employee, e.salary AS salary FROM employees e WHERE e.active=1 AND e.salary > (SELECT AVG(x.salary) FROM employees x WHERE x.department_id=e.department_id AND x.active=1)",
    },
    "window": {
        "title": "Rank active salaries within departments", "topic": "Window function",
        "prompt": "Return employee, department and salary_rank for active employees; salary_rank must be DENSE_RANK by salary descending within each department.",
        "reference": "SELECT e.name AS employee, d.name AS department, DENSE_RANK() OVER (PARTITION BY e.department_id ORDER BY e.salary DESC) AS salary_rank FROM employees e JOIN departments d ON d.id=e.department_id WHERE e.active=1",
    },
}

VIVA = {
    "dbms-atomicity": ("dbms", "Which ACID property means a transaction happens fully or not at all?", {"a": "Consistency", "b": "Atomicity", "c": "Isolation"}, "b", "Atomicity gives all-or-nothing transaction semantics."),
    "dbms-index": ("dbms", "Which is a common trade-off of adding an index?", {"a": "Slower writes and extra storage", "b": "No storage cost", "c": "Guaranteed faster queries of every kind"}, "a", "Indexes usually cost storage and maintenance during writes."),
    "dbms-fk": ("dbms", "What does a foreign key primarily enforce?", {"a": "Uniqueness of any text", "b": "Encryption", "c": "Referential integrity"}, "c", "Foreign keys link referencing values to existing referenced rows."),
    "os-context": ("os", "What does a CPU context switch do?", {"a": "Saves/restores execution context between tasks", "b": "Increases physical RAM", "c": "Compiles a program"}, "a", "Context switches let the CPU resume a different thread or process."),
    "os-deadlock": ("os", "Which is one of the necessary Coffman conditions for deadlock?", {"a": "Fixed process priority", "b": "Circular wait", "c": "Virtual memory"}, "b", "Circular wait is one of the four necessary deadlock conditions."),
    "os-memory": ("os", "Virtual memory primarily allows which abstraction?", {"a": "Every process directly owns all physical RAM", "b": "Networks without routers", "c": "A virtual address space mapped to memory/storage"}, "c", "The operating system and hardware translate virtual addresses to physical pages."),
    "cn-tcp": ("cn", "Which property does TCP provide to an application?", {"a": "Reliable ordered byte stream", "b": "Guaranteed packet boundaries", "c": "Unreliable independent datagrams"}, "a", "TCP gives a reliable ordered byte stream, not message boundaries."),
    "cn-dns": ("cn", "What is a primary use of DNS?", {"a": "Compile CSS", "b": "Resolve domain names to DNS records", "c": "Encrypt all web traffic"}, "b", "DNS resolves domain names to records such as A and AAAA."),
    "cn-http": ("cn", "What usually does HTTP 404 indicate?", {"a": "Internal server error", "b": "A successful POST", "c": "The requested resource was not found"}, "c", "404 indicates the target resource was not found."),
    "oop-encapsulation": ("oop", "What does encapsulation emphasize?", {"a": "Keeping object state and operations together with controlled access", "b": "Forcing all classes to inherit", "c": "Removing object methods"}, "a", "Encapsulation groups state and behavior and controls external access."),
    "oop-polymorphism": ("oop", "What best illustrates runtime polymorphism?", {"a": "A fixed numeric literal", "b": "An overridden method dispatched using the runtime object's type", "c": "Adding two integers"}, "b", "Dynamic dispatch selects the implementation for the runtime object."),
    "oop-composition": ("oop", "What does composition express?", {"a": "A subclass is always the superclass", "b": "A program must use global variables", "c": "An object is built using other objects"}, "c", "Composition represents has-a relationships and can reduce inheritance coupling."),
}

ALLOWED_FUNCTIONS = {"count", "sum", "avg", "min", "max", "round", "coalesce", "ifnull", "nullif", "lower", "upper", "length", "abs", "dense_rank", "rank", "row_number", "like"}
_ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}


def _dataset(rows):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE departments(id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    db.execute("CREATE TABLE employees(id INTEGER PRIMARY KEY, name TEXT NOT NULL, department_id INTEGER, salary INTEGER, active INTEGER)")
    db.executemany("INSERT INTO departments VALUES (?,?)", DEPARTMENTS)
    db.executemany("INSERT INTO employees VALUES (?,?,?,?,?)", rows)
    db.commit()
    return db


def _rows_key(rows):
    return sorted(json.dumps(list(row), ensure_ascii=True, separators=(",", ":")) for row in rows)


def _execute_safe(db, query):
    if not isinstance(query, str) or not 12 <= len(query) <= 1500 or not re.match(r"^\s*(SELECT|WITH)\b", query, re.I):
        raise ValueError("Write one SELECT or WITH query (12–1500 characters).")
    def authorize(action, arg1, arg2, database, source):
        if action not in _ALLOWED_ACTIONS:
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_READ and arg1 not in {"employees", "departments"}:
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() not in ALLOWED_FUNCTIONS:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    began = time.monotonic()
    db.set_authorizer(authorize)
    db.set_progress_handler(lambda: 1 if time.monotonic() - began > 0.2 else 0, 500)
    try:
        cursor = db.execute(query)
        if len(cursor.description or []) > 6:
            raise ValueError("Queries may return at most six columns.")
        rows = cursor.fetchmany(121)
        if len(rows) > 120:
            raise ValueError("Queries may return at most 120 rows.")
        if any(any(len(str(v)) > 160 for v in row) for row in rows):
            raise ValueError("Query results are too large.")
        return [tuple(r) for r in rows]
    finally:
        db.set_authorizer(None)
        db.set_progress_handler(None, 0)


class LocalLab:
    """A single-device study workspace, explicitly unauthenticated and not multi-user."""
    def __init__(self, path: str | Path = ":memory:"):
        self.lock = RLock()
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        with self.lock:
            self.db.execute("CREATE TABLE IF NOT EXISTS settings(singleton INTEGER PRIMARY KEY CHECK(singleton=1), role TEXT NOT NULL, language TEXT NOT NULL, minutes INTEGER NOT NULL)")
            self.db.execute("INSERT OR IGNORE INTO settings VALUES (1,'backend','Java',45)")
            self.db.execute("CREATE TABLE IF NOT EXISTS sql_attempts(id INTEGER PRIMARY KEY, challenge TEXT NOT NULL, passed INTEGER NOT NULL, tests_passed INTEGER NOT NULL, tests_total INTEGER NOT NULL, sql_sha256 TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            self.db.execute("CREATE TABLE IF NOT EXISTS viva_attempts(id INTEGER PRIMARY KEY, question TEXT NOT NULL, correct INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            self.db.commit()

    def profile(self):
        with self.lock:
            role, language, minutes = self.db.execute("SELECT role, language, minutes FROM settings WHERE singleton=1").fetchone()
        return {"role": role, "target_role": ROLES[role]["label"], "language": language, "daily_minutes": minutes, "mode": "local-single-workspace-no-auth"}

    def update_profile(self, role, language, minutes):
        if role not in ROLES or language not in {"Java", "Python", "JavaScript"} or type(minutes) is not int or not 15 <= minutes <= 120:
            raise ValueError("Invalid local learning preferences")
        with self.lock:
            self.db.execute("UPDATE settings SET role=?, language=?, minutes=? WHERE singleton=1", (role, language, minutes))
            self.db.commit()
        return self.profile()

    @staticmethod
    def sql_catalog():
        return {"schema": ["departments(id INTEGER, name TEXT)", "employees(id INTEGER, name TEXT, department_id INTEGER, salary INTEGER, active INTEGER)"],
                "active_definition": "active=1 means currently active; active=0 means inactive",
                "sample_departments": [list(d) for d in DEPARTMENTS],
                "sample_employees": [list(d) for d in FIXTURES[0][:5]],
                "challenges": [{k: v[k] for k in ("title", "topic", "prompt")} | {"id": cid} for cid, v in SQL_TASKS.items()],
                "grader": "Actual SQLite SELECT evaluation against two independent fixture datasets; expected results computed from reference queries."}

    def grade_sql(self, challenge, query):
        if challenge not in SQL_TASKS:
            raise ValueError("Unknown SQL challenge")
        if not isinstance(query, str) or not 12 <= len(query) <= 1500:
            raise ValueError("SQL query must contain 12–1500 characters")
        checks = []
        for i, fixture in enumerate(FIXTURES, 1):
            db = _dataset(fixture)
            try:
                expected = [tuple(r) for r in db.execute(SQL_TASKS[challenge]["reference"]).fetchall()]
                try:
                    actual = _execute_safe(db, query)
                    passed = _rows_key(actual) == _rows_key(expected)
                    checks.append({"fixture": i, "passed": passed, "rows_returned": len(actual),
                                   "actual_preview": [list(r) for r in actual[:4]],
                                   "expected_preview": [list(r) for r in expected[:4]] if not passed else []})
                except (sqlite3.Error, ValueError) as exc:
                    checks.append({"fixture": i, "passed": False, "error": "SQL query rejected or failed: " + str(exc)[:170]})
            finally:
                db.close()
        passed_count = sum(x["passed"] for x in checks)
        with self.lock:
            self.db.execute("INSERT INTO sql_attempts(challenge,passed,tests_passed,tests_total,sql_sha256) VALUES(?,?,?,?,?)",
                            (challenge, int(passed_count == len(checks)), passed_count, len(checks), hashlib.sha256(query.encode()).hexdigest()))
            self.db.commit()
        return {"challenge_id": challenge, "passed": passed_count == len(checks), "tests_passed": passed_count,
                "tests_total": len(checks), "checks": checks,
                "verified_source": "local-sqlite-select-grader", "notice": "Executed against fixture tables; not a full database administration assessment."}

    @staticmethod
    def viva_catalog():
        return {"topics": [{"id": t, "title": title} for t, title in [("dbms", "Databases"), ("os", "Operating Systems"), ("cn", "Computer Networks"), ("oop", "Object-oriented Programming")]],
                "questions": [{"id": qid, "topic": entry[0], "prompt": entry[1], "options": entry[2]} for qid, entry in VIVA.items()]}

    def grade_viva(self, question, choice):
        if question not in VIVA:
            raise ValueError("Unknown core CS question")
        topic, prompt, options, key, explanation = VIVA[question]
        if choice not in options:
            raise ValueError("Invalid answer option")
        correct = choice == key
        with self.lock:
            self.db.execute("INSERT INTO viva_attempts(question,correct) VALUES(?,?)", (question, int(correct)))
            self.db.commit()
        return {"question_id": question, "topic": topic, "correct": correct, "explanation": explanation,
                "source": "prepezy-original-server-checked-core-viva"}

    def evidence(self):
        with self.lock:
            sql = self.db.execute("SELECT id,challenge,passed,tests_passed,tests_total,sql_sha256,created_at FROM sql_attempts ORDER BY id DESC LIMIT 100").fetchall()
            viva = self.db.execute("SELECT id,question,correct,created_at FROM viva_attempts ORDER BY id DESC LIMIT 100").fetchall()
        return {"sql": [{"id": r[0], "challenge_id": r[1], "passed": bool(r[2]), "tests_passed": r[3], "tests_total": r[4], "query_sha256": r[5], "created_at": r[6], "source": "local-sqlite-select-grader"} for r in sql],
                "core": [{"id": r[0], "question_id": r[1], "topic": VIVA[r[1]][0], "correct": bool(r[2]), "created_at": r[3], "source": "prepezy-server-checked-viva"} for r in viva]}

    def overview(self):
        profile = self.profile()
        history = self.evidence()
        stats = {x: {"attempted": 0, "passed": 0, "total": 5 if x == "sql" else 3} for x in ("sql", "dbms", "os", "cn", "oop")}
        # Treat first submitted answer per item as independent baseline evidence;
        # repeated attempts are progression data, not new independent questions.
        independent = {}
        for item in reversed(history["sql"]):
            independent.setdefault(("sql", item["challenge_id"]), item["passed"])
        for item in reversed(history["core"]):
            independent.setdefault((item["topic"], item["question_id"]), item["correct"])
        for (topic, _), correct in independent.items():
            stats[topic]["attempted"] += 1
            stats[topic]["passed"] += int(correct)
        weights = ROLES[profile["role"]]["weights"]
        tracks = []
        for topic, item in stats.items():
            attempts, successes = item["attempted"], item["passed"]
            gap = 1 if not attempts else max(0.25, 1 - successes / attempts)
            priority = round(weights[topic] * (gap + 0.15 * (1 - attempts / item["total"])), 3)
            tracks.append({"id": topic, "assessed": attempts, "correct_first_try": successes, "available": item["total"],
                           "assessment_coverage": round(attempts / item["total"], 3), "priority": priority})
        tracks.sort(key=lambda item: (-item["priority"], item["id"]))
        top = tracks[0]
        activities = []
        minutes_remaining = profile["daily_minutes"]
        for track in tracks:
            minutes = 20 if track["id"] == "sql" else 10
            if minutes > minutes_remaining or len(activities) >= 4:
                continue
            activities.append({"type": "sql-practice" if track["id"] == "sql" else "core-cs-viva",
                               "topic": track["id"], "minutes": minutes,
                               "why": (f"Target role relevance and only {track['assessed']}/{track['available']} distinct tasks assessed; "
                                       f"{track['correct_first_try']} correct on first attempt.")})
            minutes_remaining -= minutes
        return {"profile": profile, "tracks": tracks, "recommendation": {"topic": top["id"], "type": "sql-practice" if top["id"] == "sql" else "core-cs-viva",
                "reason": "Ranked by target-role relevance, missing evidence and first-attempt results."},
                "roadmap": activities, "recorded_sql_attempts": len(history["sql"]), "recorded_viva_attempts": len(history["core"]),
                "evidence_note": "These are actual assessed exercises, not a validated overall skill mastery score. Other learning modules remain separately integrated."}

    def reset(self):
        with self.lock:
            self.db.execute("DELETE FROM sql_attempts")
            self.db.execute("DELETE FROM viva_attempts")
            self.db.execute("UPDATE settings SET role='backend', language='Java', minutes=45 WHERE singleton=1")
            self.db.commit()
        return {"cleared": True}
