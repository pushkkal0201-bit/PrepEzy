"""Unified, source-aware evidence for one *local* PrepEzy workspace.

No account, demo-profile scores, fake interviews or client supplied grades.
Only the server's SQL grader, Core CS grader, Cracked-derived guided assessment,
and validated Auralis restricted-AST runner may create observations.
"""
from __future__ import annotations

import sqlite3
from threading import RLock

from .cracked import PATTERNS, PatternCoach
from .local_lab import LocalLab, ROLES, SQL_TASKS, VIVA

LOCAL_NAMESPACE = "local-device-only"
SKILL_NAMES = {
    "sql": "SQL practical",
    "dbms": "Database fundamentals",
    "os": "Operating systems",
    "cn": "Computer networks",
    "oop": "Object-oriented programming",
    "dsa": "DSA pattern recognition",
    "python": "Restricted Python practical",
}
AVAILABLE = {"sql": len(SQL_TASKS), "dbms": 3, "os": 3, "cn": 3, "oop": 3,
             "dsa": len(PATTERNS), "python": 5}
ACTIONS = {"sql": "sql-practice", "dbms": "core-viva", "os": "core-viva",
           "cn": "core-viva", "oop": "core-viva",
           "dsa": "pattern-coach", "python": "restricted-python"}
ROLE_EXTRA = {
    "backend": {"dsa": 0.85, "python": 0.45},
    "data": {"dsa": 0.4, "python": 0.7},
    "ml": {"dsa": 0.8, "python": 1.0},
    "fullstack": {"dsa": 0.85, "python": 0.8},
}
CHALLENGES = {"sum_numbers", "reverse_text", "palindrome", "range_span", "clamp"}


class UnifiedEvidence:
    def __init__(self, lab: LocalLab):
        self.lab = lab
        self.lock: RLock = lab.lock
        self.db: sqlite3.Connection = lab.db
        self.patterns = PatternCoach(self.db, self.lock)
        with self.lock:
            self.db.execute("""CREATE TABLE IF NOT EXISTS local_auralis_code(
                id INTEGER PRIMARY KEY,
                challenge TEXT NOT NULL,
                passed INTEGER NOT NULL,
                total INTEGER NOT NULL,
                score INTEGER NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            self.db.commit()

    def record_auralis(self, result: dict) -> None:
        """Caller MUST pass only AuralisClient.grade_code() verified output."""
        challenge = result.get("challenge_id")
        passed, total = result.get("passed"), result.get("total")
        tests = result.get("tests")
        if (challenge not in CHALLENGES or
                result.get("source") != "restricted_ast_test_runner" or
                type(passed) is not int or type(total) is not int or
                not 1 <= total <= 30 or not 0 <= passed <= total or
                result.get("all_passed") is not (passed == total) or
                not isinstance(tests, list) or len(tests) != total or
                any(not isinstance(x, dict) or x.get("status") not in ("pass", "fail", "error") for x in tests) or
                sum(x["status"] == "pass" for x in tests) != passed):
            raise ValueError("Unverified Auralis code result")
        with self.lock:
            self.db.execute(
                "INSERT INTO local_auralis_code(challenge,passed,total,score,source) VALUES (?,?,?,?,?)",
                (challenge, passed, total, int(passed == total), result["source"]),
            )
            self.db.commit()

    def code_evidence(self) -> list[dict]:
        with self.lock:
            rows = self.db.execute(
                """SELECT id,challenge,passed,total,score,source,created_at
                   FROM local_auralis_code ORDER BY id DESC LIMIT 100"""
            ).fetchall()
        return [
            {"id": rid, "challenge_id": challenge, "tests_passed": passed, "tests_total": total,
             "correct": bool(score), "source": source, "created_at": stamp}
            for rid, challenge, passed, total, score, source, stamp in rows
        ]

    def evidence(self) -> dict:
        """Typed, source-identifiable history, not a misleading global grade."""
        base = self.lab.evidence()
        coach = self.patterns.evidence(LOCAL_NAMESPACE)
        code = self.code_evidence()
        events: list[dict] = []
        for record in base["sql"]:
            events.append({
                "id": "sql:" + str(record["id"]), "skill": "sql", "kind": "sql_execution",
                "assessment_id": record["challenge_id"], "correct": record["passed"],
                "source": record["source"], "assisted": False, "created_at": record["created_at"],
                "details": {"tests_passed": record["tests_passed"], "tests_total": record["tests_total"]},
            })
        for record in base["core"]:
            events.append({
                "id": "viva:" + str(record["id"]), "skill": record["topic"], "kind": "core_cs_choice",
                "assessment_id": record["question_id"], "correct": record["correct"],
                "source": record["source"], "assisted": False, "created_at": record["created_at"],
            })
        for record in coach:
            events.append({
                "id": "pattern:" + str(record["id"]), "skill": "dsa", "kind": "pattern_reasoning",
                "assessment_id": record["pattern"] + ":" + record["step"],
                "correct": record["correct"], "assisted": record["hint_used"],
                "source": record["source"], "created_at": record["created_at"],
            })
        for record in code:
            events.append({
                "id": "auralis:" + str(record["id"]), "skill": "python",
                "kind": "restricted_python_execution", "assessment_id": record["challenge_id"],
                "correct": record["correct"], "assisted": False,
                "source": record["source"], "created_at": record["created_at"],
                "details": {"tests_passed": record["tests_passed"], "tests_total": record["tests_total"]},
            })
        events.sort(key=lambda e: (e["created_at"], e["id"]), reverse=True)
        return {
            "events": events, "event_count": len(events),
            "sources": {
                "sql": len(base["sql"]), "core_viva": len(base["core"]),
                "cracked_pattern": len(coach), "auralis_restricted_code": len(code),
            },
            "notice": "Only verified local assessment events. No interview scores, hiring predictions or inferred grades.",
        }

    def skillgraph(self) -> dict:
        """First independent attempt per assessment; never combine unlike tests into a global score."""
        profile = self.lab.profile()
        events = self.evidence()
        first: dict[tuple[str, str], dict] = {}
        # Query history is newest-first, so iterate oldest-first to record only
        # the original baseline attempt (not a later corrected retry).
        for item in reversed(events["events"]):
            if item["kind"] == "pattern_reasoning" and not item["assessment_id"].endswith(":transfer"):
                continue
            key = (item["skill"], item["assessment_id"])
            if key not in first:
                first[key] = item

        weights = {**ROLES[profile["role"]]["weights"], **ROLE_EXTRA[profile["role"]]}
        skills = []
        for sid in SKILL_NAMES:
            assessed = [x for (topic, _), x in first.items() if topic == sid]
            successes = sum(bool(x["correct"]) and not x["assisted"] for x in assessed)
            count = len(assessed)
            # Conservative priority heuristic: don't infer mastery from very
            # small samples. Missing evidence is a recommendation, not a failure.
            unanswered = 1 - count / AVAILABLE[sid]
            error = (count - successes) / count if count else 0
            priority = weights[sid] * (0.65 * unanswered + 0.65 * error + (0.2 if count == 0 else 0))
            skills.append({
                "id": sid, "name": SKILL_NAMES[sid], "kind": (
                    "practical_sql" if sid == "sql" else "restricted_execution" if sid == "python"
                    else "pattern_transfer" if sid == "dsa" else "core_knowledge"),
                "available": AVAILABLE[sid], "distinct_assessments": count,
                "first_try_correct_unassisted": successes, "coverage": round(count / AVAILABLE[sid], 3),
                "role_weight": weights[sid], "priority": round(priority, 3),
                "status": "unassessed" if count == 0 else "review-needed" if successes < count else "limited-positive-evidence",
                "evidence_refs": [x["id"] for x in assessed],
                "interpretation": (
                    "No assessed evidence yet." if count == 0
                    else f"{successes} of {count} distinct first attempts passed without assistance; this is not a mastery certificate."
                ),
            })
        skills.sort(key=lambda item: (-item["priority"], item["id"]))
        steps, remaining = [], profile["daily_minutes"]
        for skill in skills:
            if len(steps) == 4:
                break
            minutes = 20 if skill["id"] in ("sql", "python") else 15 if skill["id"] == "dsa" else 10
            if minutes > remaining:
                continue
            steps.append({
                "skill": skill["id"], "activity": ACTIONS[skill["id"]], "minutes": minutes,
                "why": (
                    f"{skill['name']} is relevant to {profile['target_role']}; "
                    f"{skill['distinct_assessments']}/{skill['available']} distinct assessments tried; "
                    f"{skill['first_try_correct_unassisted']} first-attempt unassisted successes."
                ),
            })
            remaining -= minutes
        return {
            "version": "local-evidence-v1",
            "profile": profile,
            "skills": skills,
            "recommendation": steps[0] if steps else None,
            "roadmap": steps,
            "sources": events["sources"],
            "event_count": events["event_count"],
            "interpretation": (
                "Evidence is grouped by assessment type and first attempt. "
                "No single percentage combines SQL, MCQs, pattern recognition and restricted code execution. "
                "Recommendations are a transparent heuristic, not proof of improved learning."
            ),
        }

    def clear(self) -> None:
        """Remove unified source data when the local workspace is deleted."""
        with self.lock:
            self.db.execute("DELETE FROM cracked_pattern_attempts WHERE learner=?", (LOCAL_NAMESPACE,))
            self.db.execute("DELETE FROM cracked_pattern_hints WHERE learner=?", (LOCAL_NAMESPACE,))
            self.db.execute("DELETE FROM local_auralis_code")
            self.db.commit()
