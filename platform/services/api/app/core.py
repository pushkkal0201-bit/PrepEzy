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
}


class DemoEngine:
    """A local-only prototype with persisted, independently graded quiz evidence."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._lock = RLock()
        self.db = sqlite3.connect(str(db_path), check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY, learner TEXT NOT NULL, question TEXT NOT NULL, choice TEXT NOT NULL, correct INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
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

    def snapshot(self, learner: str) -> dict:
        self.validate_learner(learner)
        with self._lock:
            rows = self.db.execute("SELECT question, correct FROM attempts WHERE learner=? ORDER BY id", (learner,)).fetchall()
        stats = {skill: {"attempts": 0, "correct": 0} for skill in SKILLS}
        for question, correct in rows:
            skill = QUESTIONS[question]["skill"]
            stats[skill]["attempts"] += 1
            stats[skill]["correct"] += int(correct)
        weights = LEARNERS[learner]["weights"]
        competencies = []
        for skill, item in stats.items():
            attempts = item["attempts"]
            accuracy = item["correct"] / attempts if attempts else None
            mastery = round((item["correct"] + 1) / (attempts + 2), 3) if attempts else None
            priority = weights[skill] * (1.5 * (1 - accuracy) if attempts else 0.7)
            competencies.append({"id": skill, "name": SKILLS[skill], "attempts": attempts, "correct": item["correct"], "practice_accuracy": round(accuracy, 3) if accuracy is not None else None, "mastery_estimate": mastery, "priority": round(priority, 3), "status": "unassessed" if not attempts else "review" if accuracy < 0.7 else "practice-more"})
        competencies.sort(key=lambda c: (-c["priority"], c["id"]))
        top = competencies[0]
        reason = ("No assessment recorded yet; establish a baseline for this role." if top["attempts"] == 0 else "Recent server-graded answers suggest this topic needs further practice.")
        return {"id": learner, "synthetic_demo": True, "target_role": LEARNERS[learner]["role"], "total_attempts": len(rows), "competencies": competencies, "recommendation": {"skill": top["id"], "action": "baseline-assessment" if top["attempts"] == 0 else "guided-practice", "reason": reason}, "limitations": "Practice-only estimate from a small quiz; not a certification or hiring prediction."}
