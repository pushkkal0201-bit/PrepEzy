"""Stage 13: local, evidence-grounded mock interview orchestration.

These conversations are NOT automated technical grading. Verified coding
results remain attributed to their original judges; GitHub inspection is
unscored context. Answers and learner-selected follow-ups are local only.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from threading import RLock

from .unified import UnifiedEvidence
from .repo_review import GitHubProjectReview

FOCUSES = {"balanced", "coding", "project"}
PROBES = {
    "edge_cases": "Give one concrete failure or boundary case. How would you detect it and demonstrate the fix?",
    "tradeoffs": "What alternative design could you use? Describe the cost you would accept and why.",
    "verification": "What independent evidence or repeatable test would validate your explanation?",
}
TOPIC_QUESTIONS = {
    "sql": "Explain one SQL query you would use for this role, its correctness conditions, and how you would check the execution plan.",
    "dbms": "Describe a database consistency failure and how a transaction or constraint would prevent it.",
    "os": "Explain a concurrency or resource-lifetime bug you might encounter and how you would reproduce it.",
    "cn": "Describe a failure mode for a client/server request, including timeouts, retries, and idempotency.",
    "oop": "Compare composition and inheritance for a feature you have actually implemented.",
    "dsa": "Choose a data structure for a real task and derive time and space complexity, including a worst-case input.",
    "python": "Describe how you test Python code for edge cases and prevent a passing example from masking a bug.",
    "coding": "Explain the algorithm and edge cases of a coding problem, including how you would verify complexity.",
    "project-build": "Walk through the test boundary of one built component and what an independent test would check.",
    "project-defense": "Describe a design choice you would defend, one plausible alternative, and evidence you would collect.",
}
ROLE_SCENARIOS = {
    "backend": "A service begins returning duplicate records after retries. How would you investigate and fix it?",
    "data": "Two dashboards disagree on a metric. How would you trace the disagreement to input data and transformations?",
    "ml": "A model performs well offline but poorly after release. What evidence would you inspect first?",
    "fullstack": "A user action succeeds in the API but the interface shows stale state. How would you debug it?",
}
SUGGESTIONS = {
    "coding": "Revisit the coding arena and run independent predefined test cases; explain an edge case aloud.",
    "technical": "Practice the highest-priority SkillGraph concept using its existing checked exercise.",
    "project": "Use the pinned GitHub source link to discuss design, tests, and limitations with a human reviewer.",
    "reflection": "Write a concise, evidence-backed retrospective with a concrete next practice step.",
}


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class MockInterviews:
    def __init__(self, db: sqlite3.Connection, lock: RLock,
                 unified: UnifiedEvidence, reviews: GitHubProjectReview):
        self.db, self.lock, self.unified, self.reviews = db, lock, unified, reviews
        with self.lock:
            self.db.execute("""CREATE TABLE IF NOT EXISTS local_mock_interviews(
                id TEXT PRIMARY KEY, focus TEXT NOT NULL, status TEXT NOT NULL,
                target_role TEXT NOT NULL, plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL, ended_at TEXT
            )""")
            self.db.execute("""CREATE TABLE IF NOT EXISTS local_mock_responses(
                session_id TEXT NOT NULL, question_id TEXT NOT NULL,
                answer TEXT NOT NULL, probe TEXT NOT NULL, created_at TEXT NOT NULL,
                PRIMARY KEY(session_id, question_id)
            )""")
            self.db.commit()

    def _plan(self, focus: str, snapshot_id: int | None) -> tuple[list[dict], str]:
        graph = self.unified.skillgraph()
        events = self.unified.evidence()["events"]
        profile = graph["profile"]
        skill = graph["skills"][0]
        relevant = [e for e in events if e["kind"] == "docker_code_execution"]
        latest = relevant[0] if relevant else None
        if latest:
            d = latest["details"]
            coding_prompt = (
                "Your last Docker-checked coding attempt for " + latest["assessment_id"]
                + " (" + d["language"] + ") returned " + d["verdict"]
                + " with " + str(d["tests_passed"]) + "/" + str(d["tests_total"])
                + " test cases passing. Explain your approach, its complexity, "
                  "and what the checks do or do not establish."
            )
            coding_evidence = [{"type": "checked_coding_attempt", "ref": latest["id"],
                                "source": latest["source"], "verified_test_result": True}]
        else:
            coding_prompt = (
                "No verified local coding-arena attempt was found. Explain how you "
                "would design, test, and analyze a solution to a new coding problem."
            )
            coding_evidence = []

        snapshot = None
        if snapshot_id is not None:
            snapshot = self.reviews.snapshot(snapshot_id)
        else:
            history = self.reviews.history()["snapshots"]
            if history:
                snapshot = self.reviews.snapshot(history[0]["id"])
        finding = snapshot["findings"][0] if snapshot and snapshot["findings"] else None
        if finding:
            project_prompt = (
                "In the sampled public repository " + snapshot["repository"] + ", "
                + finding["path"] + " contains a " + finding["kind"]
                + " marker. " + finding["question"]
            )
            project_evidence = [{
                "type": "unscored_github_marker", "ref": "github:" + str(snapshot["id"])
                + ":" + finding["id"], "repository": snapshot["repository"],
                "commit_sha": snapshot["commit_sha"],
                "source_url": finding["source_url"],
                "verified_test_result": False,
            }]
        else:
            project_prompt = (
                "No source-grounded GitHub question is available. Describe the "
                "architecture of one project, its boundaries, and how you would "
                "gather independent evidence for its behavior."
            )
            project_evidence = []

        technical_prompt = (
            "SkillGraph currently prioritizes " + skill["name"] + " ("
            + str(skill["distinct_assessments"]) + "/"
            + str(skill["available"]) + " distinct checks). "
            + TOPIC_QUESTIONS[skill["id"]]
        )
        questions = {
            "coding": {
                "id": "coding", "kind": "coding", "question": coding_prompt,
                "evidence": coding_evidence, "graded": False,
            },
            "technical": {
                "id": "technical", "kind": "technical", "question": technical_prompt,
                "evidence": [{"type": "skillgraph_priority", "ref": x,
                              "verified_test_result": True}
                             for x in skill["evidence_refs"]],
                "priority_skill": skill["id"], "graded": False,
            },
            "project": {
                "id": "project", "kind": "project", "question": project_prompt,
                "evidence": project_evidence, "graded": False,
            },
            "reflection": {
                "id": "reflection", "kind": "reflection",
                "question": ROLE_SCENARIOS[profile["role"]]
                + " Describe what you would check first, what would change your mind, and how you would communicate uncertainty.",
                "evidence": [], "graded": False,
            },
        }
        order = {
            "balanced": ["coding", "technical", "project", "reflection"],
            "coding": ["coding", "technical", "reflection", "project"],
            "project": ["project", "technical", "coding", "reflection"],
        }[focus]
        return [questions[k] for k in order], profile["target_role"]

    def start(self, focus: str = "balanced", snapshot_id: int | None = None) -> dict:
        if focus not in FOCUSES or (snapshot_id is not None and
                                    (type(snapshot_id) is not int or snapshot_id < 1)):
            raise ValueError("Choose a supported focus and a saved snapshot ID")
        plan, role = self._plan(focus, snapshot_id)
        with self.lock:
            count = self.db.execute("SELECT COUNT(*) FROM local_mock_interviews").fetchone()[0]
            if count >= 40:
                raise ValueError("Maximum 40 saved mock interviews; clear old local sessions first")
            sid = uuid.uuid4().hex
            self.db.execute(
                """INSERT INTO local_mock_interviews(
                    id,focus,status,target_role,plan_json,created_at)
                    VALUES (?,?,'active',?,?,?)""",
                (sid, focus, role, json.dumps(plan), _stamp()),
            )
            self.db.commit()
        return self.session(sid)

    def _record(self, sid: str):
        if not isinstance(sid, str) or len(sid) != 32:
            raise ValueError("Unknown interview session")
        with self.lock:
            row = self.db.execute(
                """SELECT focus,status,target_role,plan_json,created_at,ended_at
                   FROM local_mock_interviews WHERE id=?""", (sid,)
            ).fetchone()
            records = self.db.execute(
                """SELECT question_id,answer,probe,created_at
                   FROM local_mock_responses WHERE session_id=? ORDER BY rowid""",
                (sid,),
            ).fetchall() if row else []
        if not row:
            raise ValueError("Unknown interview session")
        answers = {r[0]: {"answer": r[1], "probe": r[2], "created_at": r[3]} for r in records}
        return row, answers

    def session(self, sid: str) -> dict:
        row, answers = self._record(sid)
        focus, status, role, plan_json, created, ended = row
        plan = json.loads(plan_json)
        pending = next((q for q in plan if q["id"] not in answers), None)
        report = None
        if status != "active":
            report = {
                "answered": len(answers), "total": len(plan),
                "completion": "all_questions_answered" if not pending else "ended_early",
                "next_practice": [{"area": q["kind"], "activity": SUGGESTIONS[q["kind"]]}
                                  for q in plan if not q.get("is_followup")],
                "assessment": "Ungraded reflection: no AI mark, hiring prediction or SkillGraph update.",
            }
        return {
            "id": sid, "focus": focus, "status": status,
            "target_role": role, "created_at": created, "ended_at": ended,
            "answered": len(answers), "total": len(plan),
            "next_question": pending if status == "active" else None,
            "questions": [{**q, "response": answers.get(q["id"])} for q in plan],
            "report": report,
            "notice": (
                "Adaptive ordering uses verified SkillGraph evidence and the learner's "
                "selected follow-up topic, not automatic grading of explanations. "
                "Public GitHub markers and learner-defined smoke checks are unscored. "
                "Answers are stored locally until deleted."
            ),
        }

    def respond(self, sid: str, question_id: str, answer: str, probe: str) -> dict:
        if not isinstance(answer, str) or not 30 <= len(answer.strip()) <= 2000:
            raise ValueError("Answer must be 30–2000 characters")
        if probe not in PROBES:
            raise ValueError("Select edge_cases, tradeoffs or verification")
        if not isinstance(question_id, str):
            raise ValueError("Invalid question")
        with self.lock:
            row, answers = self._record(sid)
            focus, status, role, plan_json, created, ended = row
            if status != "active":
                raise ValueError("Interview already ended")
            plan = json.loads(plan_json)
            first_index = next((i for i, q in enumerate(plan)
                                if q["id"] not in answers), None)
            if first_index is None or plan[first_index]["id"] != question_id:
                raise ValueError("Answer the next unanswered question in order")
            item = plan[first_index]
            self.db.execute(
                """INSERT INTO local_mock_responses(
                    session_id,question_id,answer,probe,created_at)
                    VALUES (?,?,?,?,?)""",
                (sid, question_id, answer.strip(), probe, _stamp()),
            )
            if not item.get("is_followup") and item["kind"] != "reflection":
                followup = {
                    "id": item["id"] + "-followup", "kind": item["kind"],
                    "is_followup": True, "parent_id": item["id"],
                    "question": PROBES[probe], "evidence": item["evidence"],
                    "graded": False, "probe": probe,
                }
                plan.insert(first_index + 1, followup)
                self.db.execute(
                    "UPDATE local_mock_interviews SET plan_json=? WHERE id=?",
                    (json.dumps(plan), sid),
                )
            if len(answers) + 1 == len(plan):
                self.db.execute(
                    """UPDATE local_mock_interviews
                       SET status='completed', ended_at=? WHERE id=?""",
                    (_stamp(), sid),
                )
            self.db.commit()
        return self.session(sid)

    def finish(self, sid: str) -> dict:
        with self.lock:
            row, answers = self._record(sid)
            if row[1] == "active":
                plan = json.loads(row[3])
                status = "completed" if len(answers) == len(plan) else "stopped"
                self.db.execute(
                    "UPDATE local_mock_interviews SET status=?, ended_at=? WHERE id=?",
                    (status, _stamp(), sid),
                )
                self.db.commit()
        return self.session(sid)

    def history(self) -> dict:
        with self.lock:
            rows = self.db.execute(
                """SELECT id,focus,status,target_role,created_at,ended_at
                   FROM local_mock_interviews ORDER BY created_at DESC, rowid DESC LIMIT 40"""
            ).fetchall()
        return {"sessions": [{
            "id": r[0], "focus": r[1], "status": r[2], "target_role": r[3],
            "created_at": r[4], "ended_at": r[5],
        } for r in rows]}

    def clear(self) -> dict:
        with self.lock:
            self.db.execute("DELETE FROM local_mock_responses")
            self.db.execute("DELETE FROM local_mock_interviews")
            self.db.commit()
        return {"cleared": True, "source": "local_mock_interviews",
                "notice": "Mock interview prompts, answers and local reports deleted."}
