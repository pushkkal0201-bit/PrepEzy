"""Deterministic, server-scored adaptation for *synthetic* demo learners only.

No LLM scores, real accounts, user-supplied grades, or arbitrary code execution.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import RLock

SKILLS = {
    "dsa": "Data Structures & Algorithms",
    "sql": "SQL & Databases",
    "systems": "System Design",
    "python": "Python Fundamentals",
    "ml": "Machine Learning",
}
LEARNERS = {
    "demo-backend": {"role": "Backend Engineer", "weights": {"dsa": 1.0, "sql": 0.95, "systems": 0.85, "python": 0.35, "ml": 0.15}},
    "demo-ml": {"role": "ML Engineer", "weights": {"ml": 1.0, "python": 0.95, "dsa": 0.7, "sql": 0.4, "systems": 0.35}},
}
QUESTIONS = {
    "dsa-1": {"skill": "dsa", "prompt": "What is binary search's worst-case time complexity on a sorted array?", "options": {"a": "O(n)", "b": "O(log n)", "c": "O(n²)"}, "answer": "b", "explanation": "The search interval is halved on each step."},
    "sql-1": {"skill": "sql", "prompt": "Which SQL clause filters groups after aggregation?", "options": {"a": "WHERE", "b": "HAVING", "c": "ORDER BY"}, "answer": "b", "explanation": "HAVING filters groups after GROUP BY; WHERE filters rows before grouping."},
    "systems-1": {"skill": "systems", "prompt": "What is the primary purpose of a cache?", "options": {"a": "Reduce repeated expensive reads", "b": "Guarantee strong consistency", "c": "Replace all persistent storage"}, "answer": "a", "explanation": "Caches can reduce access latency but require consistency strategies."},
    "python-1": {"skill": "python", "prompt": "Which Python type is immutable?", "options": {"a": "list", "b": "dict", "c": "tuple"}, "answer": "c", "explanation": "Tuples cannot be modified in place."},
    "ml-1": {"skill": "ml", "prompt": "Which evaluation split is used for final unbiased reporting?", "options": {"a": "Training", "b": "Validation", "c": "Held-out test"}, "answer": "c", "explanation": "A held-out test split measures performance after model selection."},
    "dsa-2": {"skill": "dsa", "prompt": "Which data structure typically supports O(1) average-time lookup by key?", "options": {"a": "Hash map", "b": "Unsorted array", "c": "Linked list"}, "answer": "a", "explanation": "Hash maps offer average constant-time key lookups with suitable hashing."},
    "sql-2": {"skill": "sql", "prompt": "Which JOIN keeps every row from the left table, even if unmatched?", "options": {"a": "INNER JOIN", "b": "LEFT JOIN", "c": "CROSS JOIN"}, "answer": "b", "explanation": "LEFT JOIN keeps left-side rows and fills unmatched right-side columns with NULL."},
    "systems-2": {"skill": "systems", "prompt": "Which approach can reduce the impact of a temporarily unavailable dependency?", "options": {"a": "Retry forever without delay", "b": "Remove monitoring", "c": "Use timeouts and circuit breakers"}, "answer": "c", "explanation": "Timeouts and circuit breakers help prevent cascading failures."},
    "python-2": {"skill": "python", "prompt": "What does a Python dictionary map?", "options": {"a": "Indices to arrays only", "b": "Hashable keys to values", "c": "Only strings to strings"}, "answer": "b", "explanation": "Dictionary keys must be hashable and can map to arbitrary values."},
    "ml-2": {"skill": "ml", "prompt": "Which method helps detect model overfitting?", "options": {"a": "Evaluate on unseen validation data", "b": "Train on the test set", "c": "Remove all features"}, "answer": "a", "explanation": "Validation performance compared to training performance helps reveal overfitting."},
}


class DemoEngine:
    """A local-only prototype with persisted, independently graded quiz evidence."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._lock = RLock()
        self.db = sqlite3.connect(str(db_path), check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY, learner TEXT NOT NULL, question TEXT NOT NULL, choice TEXT NOT NULL, correct INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS auralis_interviews (
                 session_id TEXT PRIMARY KEY, learner TEXT NOT NULL, provider TEXT NOT NULL,
                 status TEXT NOT NULL, answer_count INTEGER NOT NULL DEFAULT 0,
                 scored INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
               )"""
        )
        self.db.commit()

    @staticmethod
    def validate_learner(learner: str) -> None:
        if learner not in LEARNERS:
            raise ValueError("Unknown synthetic demo learner")

    @staticmethod
    def public_questions() -> list[dict]:
        return [{"id": key, "skill": val["skill"], "prompt": val["prompt"], "options": val["options"]} for key, val in QUESTIONS.items()]

    def submit(self, learner: str, question: str, choice: str) -> dict:
        self.validate_learner(learner)
        if question not in QUESTIONS:
            raise ValueError("Unknown question")
        q = QUESTIONS[question]
        if choice not in q["options"]:
            raise ValueError("Unknown answer choice")
        correct = choice == q["answer"]
        with self._lock:
            self.db.execute("INSERT INTO attempts (learner, question, choice, correct) VALUES (?, ?, ?, ?)", (learner, question, choice, int(correct)))
            self.db.commit()
        return {"correct": correct, "explanation": q["explanation"], "learner": self.snapshot(learner)}

    def register_interview(self, learner: str, sid: str, status: str, answer_count: int = 0) -> None:
        """Link only real upstream sessions to our synthetic learner namespace."""
        self.validate_learner(learner)
        if not sid.startswith("session_") or not isinstance(answer_count, int) or answer_count < 0:
            raise ValueError("Invalid local Auralis link")
        with self._lock:
            existing = self.db.execute(
                "SELECT learner FROM auralis_interviews WHERE session_id=?", (sid,)
            ).fetchone()
            if existing and existing[0] != learner:
                raise ValueError("Auralis session belongs to a different synthetic learner")
            self.db.execute(
                """INSERT INTO auralis_interviews(session_id, learner, provider, status, answer_count, scored)
                   VALUES (?, ?, 'scripted-demo', ?, ?, 0)
                   ON CONFLICT(session_id) DO UPDATE SET
                     status=excluded.status, answer_count=excluded.answer_count,
                     updated_at=CURRENT_TIMESTAMP""",
                (sid, learner, status, answer_count),
            )
            self.db.commit()

    def owns_interview(self, learner: str, sid: str) -> bool:
        self.validate_learner(learner)
        with self._lock:
            row = self.db.execute(
                "SELECT 1 FROM auralis_interviews WHERE session_id=? AND learner=?",
                (sid, learner),
            ).fetchone()
        return bool(row)

    def interview_history(self, learner: str) -> list[dict]:
        self.validate_learner(learner)
        with self._lock:
            rows = self.db.execute(
                """SELECT session_id, provider, status, answer_count, scored, updated_at
                   FROM auralis_interviews WHERE learner=?
                   ORDER BY updated_at DESC, rowid DESC LIMIT 30""",
                (learner,),
            ).fetchall()
        return [
            {"id": sid, "provider": provider, "status": status,
             "answer_count": count, "scored": bool(scored), "updated_at": updated}
            for sid, provider, status, count, scored, updated in rows
        ]

    def evidence(self, learner: str, limit: int = 30) -> list[dict]:
        """Server-verified quiz evidence for a synthetic demo learner, latest first."""
        self.validate_learner(learner)
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        with self._lock:
            rows = self.db.execute(
                "SELECT id, question, correct, created_at FROM attempts WHERE learner=? ORDER BY id DESC LIMIT ?",
                (learner, limit),
            ).fetchall()
        return [
            {
                "id": row_id, "question_id": question, "skill": QUESTIONS[question]["skill"],
                "correct": bool(correct), "created_at": recorded, "source": "prepezy-server-graded-demo",
            }
            for row_id, question, correct, recorded in rows
        ]

    def roadmap(self, learner: str, minutes: int = 45) -> dict:
        """Build a transparent, goal-specific roadmap from recorded quiz evidence."""
        from .learning import make_roadmap
        return make_roadmap(self.snapshot(learner), minutes=minutes)

    def next_question(self, learner: str) -> dict:
        """Prefer not-yet-attempted questions for the highest-priority roadmap skill."""
        self.validate_learner(learner)
        plan = self.roadmap(learner)
        target = plan["activities"][0]["skill"]
        with self._lock:
            rows = self.db.execute(
                "SELECT question, COUNT(*) FROM attempts WHERE learner=? GROUP BY question", (learner,)
            ).fetchall()
        counts = dict(rows)
        candidates = [qid for qid, item in QUESTIONS.items() if item["skill"] == target]
        chosen = min(candidates, key=lambda question: (counts.get(question, 0), question))
        question = next(q for q in self.public_questions() if q["id"] == chosen)
        return {
            "question": question,
            "skill": target,
            "reason": plan["activities"][0]["why"],
            "previous_attempts": counts.get(chosen, 0),
            "limitations": "Suggested from a small local question bank, not a validated adaptive exam.",
        }

    def snapshot(self, learner: str) -> dict:
        self.validate_learner(learner)
        with self._lock:
            rows = self.db.execute("SELECT question, correct FROM attempts WHERE learner=? ORDER BY id", (learner,)).fetchall()
        # A retry of the same question is useful feedback, but it is not
        # independent evidence of proficiency. Only the latest result for
        # each *distinct* question contributes to the competency estimate.
        latest_by_question = {}
        for question, correct in rows:
            latest_by_question[question] = int(correct)
        stats = {skill: {"attempts": 0, "correct": 0} for skill in SKILLS}
        for question, correct in latest_by_question.items():
            skill = QUESTIONS[question]["skill"]
            stats[skill]["attempts"] += 1
            stats[skill]["correct"] += correct
        weights = LEARNERS[learner]["weights"]
        competencies = []
        for skill, item in stats.items():
            attempts = item["attempts"]
            accuracy = item["correct"] / attempts if attempts else None
            mastery = round((item["correct"] + 1) / (attempts + 2), 3) if attempts else None
            priority = weights[skill] * (1.5 * (1 - accuracy) if attempts else 0.7)
            competencies.append({"id": skill, "name": SKILLS[skill], "attempts": attempts, "correct": item["correct"], "practice_accuracy": round(accuracy, 3) if accuracy is not None else None, "mastery_estimate": mastery, "confidence": round(min(1.0, attempts / 5.0), 3), "priority": round(priority, 3), "status": "unassessed" if not attempts else "review" if accuracy < 0.7 else "practice-more"})
        competencies.sort(key=lambda c: (-c["priority"], c["id"]))
        top = competencies[0]
        reason = ("No assessment recorded yet; establish a baseline for this role." if top["attempts"] == 0 else "Recent server-graded answers suggest this topic needs further practice.")
        return {"id": learner, "synthetic_demo": True, "target_role": LEARNERS[learner]["role"], "total_attempts": len(rows), "distinct_questions": len(latest_by_question), "interview_history": self.interview_history(learner), "competencies": competencies, "recommendation": {"skill": top["id"], "action": "baseline-assessment" if top["attempts"] == 0 else "guided-practice", "reason": reason}, "limitations": "Practice-only estimate from a small quiz; not a certification or hiring prediction."}
