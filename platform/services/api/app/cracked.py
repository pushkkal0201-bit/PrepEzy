"""Local, deterministic adaptation of Cracked's pattern-coach learning workflow.

Cracked's skills/interview/pattern-coach/SKILL.md describes Socratic phases.
The *content and grader here are PrepEzy-authored*, not executions of Claude
Code skills, online assessments, or arbitrary student programs.

Only synthetic demo learners are supported. Never use for real-student records.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import RLock

PATTERNS = {
    "two-pointers": {
        "name": "Two pointers",
        "signal": "Sorted data and relationships between a left and a right endpoint.",
        "card": {"signal": "Sorted arrays; pair sums or pair differences.",
                 "invariant": "Every discarded pair cannot be the required answer.",
                 "pitfalls": ["Moving both pointers without justification", "Skipping duplicates incorrectly"]},
        "steps": [
            {"id": "brute", "phase": "brute-force", "prompt": "Given a sorted array, what simple baseline finds whether any pair sums to a target?",
             "options": {"a": "Check every distinct pair", "b": "Always check the two endpoints only", "c": "Reverse the array"},
             "answer": "a", "hint": "What would you do before trying to exploit that the array is sorted?",
             "why": "Trying every pair is a valid O(n²) baseline."},
            {"id": "signal", "phase": "find-the-waste", "prompt": "In sorted data, a current pair sums too high. Which move can reduce the sum without discarding a better candidate?",
             "options": {"a": "Move the left pointer right", "b": "Move the right pointer left", "c": "Move both pointers right"},
             "answer": "b", "hint": "Which end contains the larger value?",
             "why": "Moving the right pointer left decreases or maintains the sum in sorted ascending data."},
            {"id": "transfer", "phase": "transfer-check", "prompt": "For a sorted array with duplicates, which condition should stop the standard pair-search loop?",
             "options": {"a": "left <= right", "b": "left < right", "c": "left == 0"},
             "answer": "b", "hint": "A pair must use two distinct positions.",
             "why": "For a distinct-index pair, stop when the pointers meet."},
        ],
    },
    "sliding-window": {
        "name": "Sliding window",
        "signal": "Contiguous segments that can be updated as endpoints move.",
        "card": {"signal": "Subarrays or substrings; contiguous ranges.",
                 "invariant": "The maintained window satisfies its stated constraint.",
                 "pitfalls": ["Off-by-one window length", "Using a shrinking window where negative values break monotonicity"]},
        "steps": [
            {"id": "brute", "phase": "brute-force", "prompt": "How could you brute-force the maximum sum of any contiguous segment of exactly k elements?",
             "options": {"a": "Check each k-length segment and sum it", "b": "Sort the array first", "c": "Use only the first segment"},
             "answer": "a", "hint": "Enumerate the legal segments, even if this repeats work.",
             "why": "Computing every fixed-size segment independently is a correct baseline."},
            {"id": "signal", "phase": "find-the-waste", "prompt": "When a size-k window moves one step right, which values change in its sum?",
             "options": {"a": "All k values", "b": "Only its maximum value", "c": "Remove the old left, add the new right"},
             "answer": "c", "hint": "Compare the old and new windows to find their shared elements.",
             "why": "Overlapping windows differ at exactly two endpoints."},
            {"id": "transfer", "phase": "transfer-check", "prompt": "With k=3 and array [2, 1, 5, 1, 3], what is the greatest fixed-window sum?",
             "options": {"a": "7", "b": "9", "c": "10"},
             "answer": "b", "hint": "Calculate the sums of windows [2,1,5], [1,5,1], and [5,1,3].",
             "why": "The windows sum to 8, 7 and 9, so the best is 9."},
        ],
    },
    "binary-search-answer": {
        "name": "Binary search on the answer",
        "signal": "A monotonic feasibility test on a numerical answer range.",
        "card": {"signal": "Find minimum feasible limit or maximum feasible value.",
                 "invariant": "The true answer stays inside the current search interval.",
                 "pitfalls": ["Using a non-monotonic predicate", "Infinite loops from incorrect boundary updates"]},
        "steps": [
            {"id": "brute", "phase": "brute-force", "prompt": "To find the smallest feasible capacity from 1 to N, what is the simplest baseline?",
             "options": {"a": "Try each capacity in increasing order", "b": "Always return N/2", "c": "Sort the feasibility answers"},
             "answer": "a", "hint": "Assume you can call feasible(capacity) for any candidate.",
             "why": "Testing capacities in order establishes a correct baseline when feasibility can be checked."},
            {"id": "signal", "phase": "find-the-waste", "prompt": "If capacity 15 is feasible and higher capacities are also feasible, what can you conclude?",
             "options": {"a": "All lower capacities are feasible", "b": "No capacity below 15 can be feasible", "c": "The minimum feasible capacity is at most 15"},
             "answer": "c", "hint": "Finding one feasible answer gives an upper bound on the minimum.",
             "why": "A feasible value provides an upper bound; smaller values may or may not work."},
            {"id": "transfer", "phase": "transfer-check", "prompt": "You seek the smallest feasible integer and feasible(mid) is true. Which inclusive interval update keeps mid eligible?",
             "options": {"a": "high = mid", "b": "low = mid + 1", "c": "low = high + 1"},
             "answer": "a", "hint": "The midpoint could itself be the minimum feasible answer.",
             "why": "Keep mid when it is feasible and search the lower half for an even smaller answer."},
        ],
    },
    "bfs": {
        "name": "Breadth-first search",
        "signal": "Shortest path by number of edges in an unweighted graph.",
        "card": {"signal": "Unweighted graph; nearest reachable state; minimum moves.",
                 "invariant": "The queue processes nodes by non-decreasing distance from the start.",
                 "pitfalls": ["Marking visited too late", "Treating weighted edges as equal without justification"]},
        "steps": [
            {"id": "brute", "phase": "brute-force", "prompt": "For an unweighted graph, which direct exploration method visits the start and then all its neighbors?",
             "options": {"a": "Depth-first search only", "b": "Breadth-first search", "c": "Sorting node IDs"},
             "answer": "b", "hint": "Think of exploring nodes in layers of distance.",
             "why": "BFS visits nodes in non-decreasing distance layers."},
            {"id": "signal", "phase": "find-the-waste", "prompt": "In an unweighted BFS, when should a newly discovered node be marked visited?",
             "options": {"a": "When enqueuing it", "b": "Only after the entire search", "c": "When enqueuing it for the third time"},
             "answer": "a", "hint": "Avoid adding the same node repeatedly from different neighbors.",
             "why": "Marking on enqueue prevents repeated queue entries and preserves a shortest first discovery."},
            {"id": "transfer", "phase": "transfer-check", "prompt": "In an unweighted graph, BFS first reaches a node using 4 edges. Can another shorter path be discovered later in that BFS?",
             "options": {"a": "Yes, always", "b": "No, if BFS started from the same source and used ordinary FIFO exploration", "c": "Only if the graph is directed"},
             "answer": "b", "hint": "BFS's queue visits distance-3 states before distance-4 states.",
             "why": "In unweighted graphs, the first BFS discovery gives the minimum edge count."},
        ],
    },
}

SOURCE_PATH = "skills/interview/pattern-coach/SKILL.md"
SOURCE_REPO = "https://github.com/nishant-Tiwari24/cracked"
STEPS = ("brute", "signal", "transfer")


def public_catalog() -> dict:
    """Return curated exercises without private solution keys."""
    return {
        "source": SOURCE_REPO,
        "source_skill": SOURCE_PATH,
        "adaptation": "PrepEzy-authored deterministic implementation of Cracked's Socratic pattern-coach workflow",
        "execution": "No Claude skill execution and no arbitrary code execution",
        "patterns": [
            {"id": key, "name": item["name"], "signal": item["signal"], "stages": 3}
            for key, item in PATTERNS.items()
        ],
    }


class PatternCoach:
    def __init__(self, db: sqlite3.Connection, lock: RLock):
        self.db, self.lock = db, lock
        with self.lock:
            self.db.execute("""CREATE TABLE IF NOT EXISTS cracked_pattern_attempts(
                id INTEGER PRIMARY KEY,
                learner TEXT NOT NULL,
                pattern TEXT NOT NULL,
                step TEXT NOT NULL,
                choice TEXT NOT NULL,
                correct INTEGER NOT NULL,
                hint_used INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            self.db.execute("""CREATE TABLE IF NOT EXISTS cracked_pattern_hints(
                learner TEXT NOT NULL,
                pattern TEXT NOT NULL,
                step TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(learner,pattern,step)
            )""")
            self.db.commit()

    @staticmethod
    def _require_pattern(pattern: str) -> dict:
        if pattern not in PATTERNS:
            raise ValueError("Unknown pattern")
        return PATTERNS[pattern]

    def state(self, learner: str, pattern: str) -> dict:
        data = self._require_pattern(pattern)
        with self.lock:
            attempts = self.db.execute(
                "SELECT step,correct FROM cracked_pattern_attempts WHERE learner=? AND pattern=? ORDER BY id",
                (learner, pattern),
            ).fetchall()
            hints = {r[0] for r in self.db.execute(
                "SELECT step FROM cracked_pattern_hints WHERE learner=? AND pattern=?",
                (learner, pattern),
            ).fetchall()}
        passed = {step for step, correct in attempts if correct}
        step = next((s for s in data["steps"] if s["id"] not in passed), None)
        if step is None:
            return {"pattern_id": pattern, "name": data["name"], "completed": True,
                    "completed_steps": len(passed), "total_steps": 3, "step": None,
                    "pattern_card": data["card"],
                    "notice": "Conceptual reasoning practice only; no coding solution was executed."}
        public_step = {k: step[k] for k in ("id", "phase", "prompt", "options")}
        prior = sum(1 for step_id, _ in attempts if step_id == step["id"])
        return {"pattern_id": pattern, "name": data["name"], "completed": False,
                "completed_steps": len(passed), "total_steps": 3, "step": public_step,
                "attempts_on_step": prior, "hint_used": step["id"] in hints,
                "hint_available": True,
                "notice": "Questions and answers are locally authored and server-checked; this is not Cracked's live agent or an OA."}

    def hint(self, learner: str, pattern: str) -> dict:
        state = self.state(learner, pattern)
        if state["completed"]:
            raise ValueError("Pattern is already completed")
        step_id = state["step"]["id"]
        with self.lock:
            self.db.execute(
                "INSERT OR IGNORE INTO cracked_pattern_hints(learner,pattern,step) VALUES (?,?,?)",
                (learner, pattern, step_id),
            )
            self.db.commit()
        step = next(x for x in PATTERNS[pattern]["steps"] if x["id"] == step_id)
        return {"pattern_id": pattern, "step_id": step_id, "hint": step["hint"],
                "counts_as_assistance": True}

    def submit(self, learner: str, pattern: str, step_id: str, choice: str) -> dict:
        state = self.state(learner, pattern)
        if state["completed"]:
            raise ValueError("Pattern is already completed")
        step = next(x for x in PATTERNS[pattern]["steps"] if x["id"] == state["step"]["id"])
        if step_id != step["id"]:
            raise ValueError("Complete the current guided stage before moving ahead")
        if choice not in step["options"]:
            raise ValueError("Unknown answer choice")
        with self.lock:
            hint_used = bool(self.db.execute(
                "SELECT 1 FROM cracked_pattern_hints WHERE learner=? AND pattern=? AND step=?",
                (learner, pattern, step_id),
            ).fetchone())
            correct = choice == step["answer"]
            self.db.execute(
                "INSERT INTO cracked_pattern_attempts(learner,pattern,step,choice,correct,hint_used) VALUES (?,?,?,?,?,?)",
                (learner, pattern, step_id, choice, int(correct), int(hint_used)),
            )
            self.db.commit()
        return {
            "correct": correct,
            "feedback": step["why"] if correct else "Not quite. Reconsider the constraints and try again.",
            "hint_used": hint_used,
            "pattern": self.state(learner, pattern),
        }

    def evidence(self, learner: str) -> list[dict]:
        with self.lock:
            rows = self.db.execute(
                """SELECT id,pattern,step,correct,hint_used,created_at
                   FROM cracked_pattern_attempts WHERE learner=? ORDER BY id DESC LIMIT 100""",
                (learner,),
            ).fetchall()
        return [{"id": rid, "pattern": pattern, "step": step, "correct": bool(correct),
                 "hint_used": bool(hint), "source": "prepezy-curated-cracked-pattern-coach",
                 "created_at": created}
                for rid, pattern, step, correct, hint, created in rows]

    def independent_transfer_grades(self, learner: str) -> list[dict]:
        """First try of each distinct transfer step; assisted correct is not unassisted mastery."""
        with self.lock:
            rows = self.db.execute(
                """SELECT pattern,correct,hint_used FROM cracked_pattern_attempts
                   WHERE learner=? AND step='transfer' ORDER BY id""", (learner,),
            ).fetchall()
        first = {}
        for pattern, correct, assisted in rows:
            first.setdefault(pattern, {"pattern": pattern, "correct": bool(correct and not assisted),
                                       "assisted": bool(assisted)})
        return list(first.values())

    def recommendation(self, learner: str) -> dict:
        """Prefer an in-progress guided pattern; otherwise an unseen pattern."""
        scores = []
        for i, pattern in enumerate(PATTERNS):
            state = self.state(learner, pattern)
            scores.append((state["completed"], -state["completed_steps"], i, pattern, state))
        _, _, _, pattern, state = min(scores)
        return {"pattern_id": pattern, "name": PATTERNS[pattern]["name"],
                "reason": ("Continue your unfinished guided stages." if not state["completed"] and state["completed_steps"]
                           else "Start with brute force, spot the pattern, then pass a transfer check."
                           if not state["completed"] else "All curated patterns were attempted; revisit earlier evidence."),
                "completed": state["completed"], "source_skill": SOURCE_PATH}
