"""Stage 11: original, executable project milestones and checked project-defense decisions.

Build Your Own X is a *link index*, not imported executable code. Curated
external resources remain linked; milestone specs, tests and questions below
are authored for PrepEzy. Submitted programs execute only inside the existing
local DockerRunner. Explanatory reasoning is stored but NOT AI-graded.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
import threading
from datetime import datetime, timezone
from urllib.parse import urlsplit

from .coding_arena import DockerRunner, IMAGES, JudgeUnavailable

def _spec(title, statement, cases):
    return {"title": title, "statement": statement,
            "cases": cases, "public_examples": 1}

PROJECTS = {
    "key-value-store": {
        "title": "Build a Small Key–Value Store",
        "category": "Database",
        "roles": ("backend", "data", "fullstack"),
        "description": "Implement a command-driven, in-memory store from scratch. Test overwrites, misses, deletion and store size.",
        "resources": [
            {"label": "Build Your Own Database from Scratch (Go)",
             "url": "https://build-your-own.org/database/",
             "via": "Build Your Own X database section"},
            {"label": "Let's Build a Simple Database (C)",
             "url": "https://cstack.github.io/db_tutorial/",
             "via": "Build Your Own X database section"},
        ],
        "milestones": {
            "lookup": _spec(
                "Implement PUT and GET",
                "Input: first line n (command count). Next n lines are PUT key value or GET key, "
                "with single-word case-sensitive ASCII keys/values. PUT stores or replaces a value "
                "without output. GET prints the stored value or NOT_FOUND on its own line. "
                "Print output only for GET, in command order.",
                [
                    ("6\nPUT apple 7\nGET apple\nPUT apple 9\nGET apple\nGET pear\nGET APPLE\n",
                     "7\n9\nNOT_FOUND\nNOT_FOUND"),
                    ("4\nGET x\nPUT x zero\nGET x\nGET y\n",
                     "NOT_FOUND\nzero\nNOT_FOUND"),
                    ("5\nPUT a 1\nPUT b 2\nGET a\nGET b\nGET c\n",
                     "1\n2\nNOT_FOUND"),
                ],
            ),
            "mutations": _spec(
                "Add DELETE and SIZE",
                "Keep PUT and GET behavior from the previous milestone. Also support DELETE key: "
                "remove the key and print DELETED if it existed, otherwise MISSING. "
                "SIZE prints the number of distinct keys currently stored. A PUT overwrite "
                "does not increase the size. First line n, followed by n commands, "
                "one command per line.",
                [
                    ("9\nSIZE\nPUT a 1\nPUT a 2\nSIZE\nGET a\nDELETE a\nSIZE\nDELETE a\nGET a\n",
                     "0\n1\n2\nDELETED\n0\nMISSING\nNOT_FOUND"),
                    ("8\nPUT x red\nPUT y blue\nDELETE z\nSIZE\nDELETE y\nGET y\nGET x\nSIZE\n",
                     "MISSING\n2\nDELETED\nNOT_FOUND\nred\n1"),
                    ("7\nPUT Q a\nPUT q b\nSIZE\nDELETE Q\nSIZE\nPUT q c\nGET q\n",
                     "2\nDELETED\n1\nc"),
                ],
            ),
        },
        "defense": {
            "overwrite": {
                "prompt": "The store replaces an existing key. Which invariant should hold for SIZE?",
                "options": {"a": "Increase by one for every PUT",
                            "b": "The number of distinct currently stored keys remains unchanged",
                            "c": "Always reset the store"},
                "correct": "b",
                "explanation": "SIZE counts unique keys, so replacing a value never creates a new key.",
            },
            "complexity": {
                "prompt": "For typical average-case O(1) key lookup in memory, which choice is most appropriate?",
                "options": {"a": "Hash map", "b": "Unsorted array scanned for every query",
                            "c": "Linear scan of all previous commands"},
                "correct": "a",
                "explanation": "Hash maps offer average constant-time lookup, subject to hashing and collision behavior.",
            },
        },
    },
    "inverted-index": {
        "title": "Build a Tiny Search Index",
        "category": "Search Engine",
        "roles": ("data", "ml", "backend"),
        "description": "Index document terms and execute deterministic AND queries. This is the foundation of an inverted index, not a full search engine.",
        "resources": [
            {"label": "Finding Important Words Using TF-IDF",
             "url": "https://stevenloria.com/tf-idf/",
             "via": "Build Your Own X search engine section"},
            {"label": "Build a Vector Space Indexing Engine (Python)",
             "url": "https://boyter.org/2010/08/build-vector-space-search-engine-python/",
             "via": "Build Your Own X search engine section"},
        ],
        "milestones": {
            "term-search": _spec(
                "Index and query single terms",
                "Read n, then n document lines: integer doc_id followed by lowercase space-separated "
                "ASCII terms. IDs are unique but may appear in any order. Read q, then q single-term "
                "query lines. For each query, print unique matching document IDs sorted numerically "
                "ascending with spaces, or NONE if no document contains that term.",
                [
                    ("3\n1 apple banana\n2 banana carrot\n3 apple\n3\napple\nbanana\npear\n",
                     "1 3\n1 2\nNONE"),
                    ("4\n10 kiwi kiwi\n2 mango kiwi\n7 mango\n4 grape\n3\nkiwi\nmango\ngrape\n",
                     "2 10\n2 7\n4"),
                    ("2\n5 x y\n1 y z\n2\nz\nnone\n", "1\nNONE"),
                ],
            ),
            "and-query": _spec(
                "Intersect postings for two terms",
                "Use the same document format. Each of q query lines now contains exactly two lowercase "
                "terms. Print numerically sorted document IDs containing BOTH terms, separated by spaces, "
                "or NONE. Repeated terms within a document must not duplicate its ID in the result.",
                [
                    ("3\n1 red blue\n2 blue green\n3 red green\n3\nred blue\nblue green\nred purple\n",
                     "1\n2\nNONE"),
                    ("4\n10 x y x\n2 x y\n7 y\n4 x z\n3\nx y\nx x\nz y\n",
                     "2 10\n2 4 10\nNONE"),
                    ("2\n7 a b\n3 b c\n2\nb c\na b\n", "3\n7"),
                ],
            ),
        },
        "defense": {
            "index-map": {
                "prompt": "Which mapping best describes an inverted search index?",
                "options": {"a": "Term to the document IDs containing that term",
                            "b": "Document ID to screen color",
                            "c": "Query to an unrelated random document"},
                "correct": "a",
                "explanation": "A postings list associates each term with the documents in which it occurs.",
            },
            "intersection": {
                "prompt": "For an AND query, what result is needed?",
                "options": {"a": "All documents containing either term",
                            "b": "Documents appearing in both terms' postings lists",
                            "c": "All indexed documents regardless of terms"},
                "correct": "b",
                "explanation": "An AND query computes the intersection, rather than union, of postings lists.",
            },
        },
    },
    "expression-interpreter": {
        "title": "Build a Tiny Expression Interpreter",
        "category": "Programming Language",
        "roles": ("backend", "fullstack", "ml"),
        "description": "Parse arithmetic tokens and evaluate expressions with increasing grammar complexity.",
        "resources": [
            {"label": "Let's Build A Simple Interpreter (Python)",
             "url": "https://ruslanspivak.com/lsbasi-part1/",
             "via": "Build Your Own X programming-language section"},
            {"label": "Build Your Own Lisp",
             "url": "http://www.buildyourownlisp.com/",
             "via": "Build Your Own X programming-language section"},
        ],
        "milestones": {
            "left-to-right": _spec(
                "Evaluate + and - from left to right",
                "Read n then n arithmetic expression lines. Each line contains nonnegative integers and "
                "+ or - operators, with a single space between every token. Evaluate strictly "
                "from left to right, then print one signed integer per line. "
                "Example: 4 + 5 - 2 evaluates to 7.",
                [
                    ("3\n4 + 5 - 2\n10 - 4 - 3\n0 + 8 + 2\n", "7\n3\n10"),
                    ("3\n1 - 9 + 2\n99\n10 - 1 + 2 - 4\n", "-6\n99\n7"),
                    ("2\n100 - 200 + 10\n6 + 7 - 2 + 1\n", "-90\n12"),
                ],
            ),
            "precedence": _spec(
                "Add multiplication precedence",
                "Read n and n space-delimited expressions. Supported operators are +, - and *. "
                "Multiplication binds more tightly than addition and subtraction; all are left-associative "
                "within their precedence level. No parentheses or unary sign tokens are required. "
                "Print one signed integer result per expression.",
                [
                    ("3\n2 + 3 * 4\n10 - 2 * 3\n2 * 3 + 5 * 2\n", "14\n4\n16"),
                    ("3\n8 * 2 - 3 * 4\n5 + 6 * 0\n9 - 1 - 2 * 2\n", "4\n5\n4"),
                    ("3\n100\n5 * 4 * 3 + 2\n6 - 2 * 4 + 10\n", "100\n62\n8"),
                ],
            ),
        },
        "defense": {
            "precedence": {
                "prompt": "Why must an evaluator distinguish * from + in the advanced milestone?",
                "options": {"a": "All operators always run left to right",
                            "b": "Multiplication has higher precedence and must be grouped first",
                            "c": "The order never affects arithmetic results"},
                "correct": "b",
                "explanation": "Operator precedence determines evaluation order; blindly scanning left to right produces wrong answers.",
            },
            "parser": {
                "prompt": "Why separate tokenization/parsing from evaluation as an interpreter grows?",
                "options": {"a": "It helps represent grammar structure and report syntax errors",
                            "b": "It makes every expression constant-time",
                            "c": "It guarantees all programs are secure"},
                "correct": "a",
                "explanation": "Separating parsing from evaluation clarifies structure and error handling; it is not a performance or security guarantee.",
            },
        },
    },
}
PROJECT_ORDER = tuple(PROJECTS)
MILESTONE_COUNT = sum(len(p["milestones"]) for p in PROJECTS.values())
DEFENSE_COUNT = sum(len(p["defense"]) for p in PROJECTS.values())
GITHUB_REPO = re.compile(r"^https://github\.com/[a-zA-Z0-9-]{1,39}/[a-zA-Z0-9_.-]{1,100}/?$")


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _project(project_id: str) -> dict:
    if project_id not in PROJECTS:
        raise ValueError("Unknown curated project")
    return PROJECTS[project_id]


def public_project(project_id: str) -> dict:
    project = _project(project_id)
    return {
        "id": project_id,
        "title": project["title"],
        "category": project["category"],
        "roles": list(project["roles"]),
        "description": project["description"],
        "resources": project["resources"],
        "milestones": [
            {"id": milestone_id, "title": milestone["title"],
             "statement": milestone["statement"],
             "test_count": len(milestone["cases"]),
             "public_examples": [{"input": i, "output": o}
                                 for i, o in milestone["cases"][:milestone["public_examples"]]]}
            for milestone_id, milestone in project["milestones"].items()
        ],
        "defense_questions": [
            {"id": qid, "prompt": question["prompt"], "options": question["options"]}
            for qid, question in project["defense"].items()
        ],
        "note": ("These are original PrepEzy educational mini-milestones, not full implementations "
                 "of the external tutorials. Tutorials are linked, not copied or executed."),
    }


class ProjectLab:
    def __init__(self, db: sqlite3.Connection, lock: threading.RLock,
                 runner: DockerRunner | None = None, gate: threading.BoundedSemaphore | None = None):
        self.db, self.lock = db, lock
        self.runner = runner if runner is not None else DockerRunner()
        self.gate = gate if gate is not None else threading.BoundedSemaphore(1)
        with self.lock:
            db.execute("""CREATE TABLE IF NOT EXISTS project_milestone_attempts(
                id INTEGER PRIMARY KEY, project_id TEXT NOT NULL, milestone TEXT NOT NULL,
                language TEXT NOT NULL, verdict TEXT NOT NULL,
                passed INTEGER NOT NULL, total INTEGER NOT NULL,
                source_sha256 TEXT NOT NULL, created_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS project_defense_attempts(
                id INTEGER PRIMARY KEY, project_id TEXT NOT NULL, question TEXT NOT NULL,
                choice TEXT NOT NULL, correct INTEGER NOT NULL, rationale TEXT NOT NULL,
                created_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS project_artifacts(
                project_id TEXT PRIMARY KEY, repo_url TEXT NOT NULL, notes TEXT NOT NULL,
                updated_at TEXT NOT NULL)""")
            db.commit()

    def recommend(self, role: str, project_id: str | None = None) -> dict | None:
        eligible = PROJECT_ORDER if project_id is None else (project_id,)
        if project_id is not None:
            _project(project_id)
        found = []
        for pid in eligible:
            state = self.state(pid)
            if state["all_milestones_passed"]:
                continue
            next_step = next((step for step in state["milestones"] if step["status"] != "passed"), None)
            if not next_step:
                continue
            score = (
                (1 if role in PROJECTS[pid]["roles"] else 0) * 100
                + (20 if next_step["status"] == "not-started" else 30)
                + (10 if state["milestones"][0]["status"] == "passed" else 0)
            )
            found.append((score, pid, next_step["id"]))
        if not found:
            return None
        _, pid, mid = sorted(found, key=lambda item: (-item[0], PROJECT_ORDER.index(item[1])))[0]
        return {
            "project_id": pid, "milestone_id": mid,
            "reason": f"Suggested from target role '{role}' and real milestone progress. "
                      "This is a deterministic planning rule, not a model-estimated skill level.",
        }

    def catalog(self, role: str) -> dict:
        return {
            "projects": [
                {"id": pid, "title": item["title"], "category": item["category"],
                 "description": item["description"], "role_relevant": role in item["roles"],
                 "progress": self.state(pid)["progress"]}
                for pid, item in PROJECTS.items()
            ],
            "recommendation": self.recommend(role),
            "languages": sorted(IMAGES),
            "runner_status": {lang: bool(self.runner.available(lang)) for lang in IMAGES},
            "source_index": "https://github.com/codecrafters-io/build-your-own-x",
            "notice": "Curated original milestones linked to external tutorials; no copied tutorial content or fabricated project completions.",
        }

    def milestone_evidence(self) -> list[dict]:
        with self.lock:
            rows = self.db.execute("""SELECT id,project_id,milestone,language,verdict,passed,total,
                   source_sha256,created_at FROM project_milestone_attempts
                   ORDER BY id DESC LIMIT 300""").fetchall()
        return [{
            "id": rid, "project_id": pid, "milestone_id": mid, "language": lang,
            "verdict": verdict, "tests_passed": passed, "tests_total": total,
            "source_sha256": digest, "correct": verdict == "accepted",
            "source": "prepezy-docker-project-milestone",
            "created_at": stamp,
        } for rid, pid, mid, lang, verdict, passed, total, digest, stamp in rows]

    def defense_evidence(self) -> list[dict]:
        with self.lock:
            rows = self.db.execute("""SELECT id,project_id,question,choice,correct,rationale,created_at
                   FROM project_defense_attempts ORDER BY id DESC LIMIT 300""").fetchall()
        return [{
            "id": rid, "project_id": pid, "question_id": qid,
            "choice_id": choice, "correct": bool(correct),
            "rationale": rationale, "rationale_reviewed": False,
            "source": "prepezy-server-checked-project-defense-choice",
            "created_at": stamp,
        } for rid, pid, qid, choice, correct, rationale, stamp in rows]

    def _progress(self, pid: str) -> dict:
        rows = [x for x in self.milestone_evidence() if x["project_id"] == pid]
        first = {}
        for x in reversed(rows):
            first.setdefault(x["milestone_id"], x)
        passed = {x["milestone_id"] for x in rows if x["correct"]}
        return {"attempts": rows, "first": first, "passed": passed}

    def state(self, project_id: str) -> dict:
        project = public_project(project_id)
        progress = self._progress(project_id)
        milestones = []
        unlocked = True
        for step in project["milestones"]:
            attempted = [x for x in progress["attempts"] if x["milestone_id"] == step["id"]]
            passed = step["id"] in progress["passed"]
            milestones.append({
                **step, "status": "passed" if passed else "attempted" if attempted else "not-started",
                "unlocked": unlocked,
                "attempt_count": len(attempted),
                "first_try_passed": progress["first"].get(step["id"], {}).get("correct", False),
                "latest_verdict": attempted[0]["verdict"] if attempted else None,
            })
            unlocked = passed
        defense = self.defense_evidence()
        questions = []
        for item in project["defense_questions"]:
            attempts = [x for x in defense if x["project_id"] == project_id and x["question_id"] == item["id"]]
            questions.append({
                **item,
                "attempted": bool(attempts),
                "attempt_count": len(attempts),
                "latest_choice_correct": attempts[0]["correct"] if attempts else None,
                "first_try_correct": attempts[-1]["correct"] if attempts else None,
                "feedback": PROJECTS[project_id]["defense"][item["id"]]["explanation"]
                    if attempts else None,
                "rationale_reviewed": False if attempts else None,
            })
        passed_count = sum(x["status"] == "passed" for x in milestones)
        with self.lock:
            artifact = self.db.execute(
                "SELECT repo_url,notes,updated_at FROM project_artifacts WHERE project_id=?",
                (project_id,),
            ).fetchone()
        return {
            **project, "milestones": milestones,
            "defense_questions": questions,
            "defense_unlocked": passed_count >= 1,
            "all_milestones_passed": passed_count == len(milestones),
            "progress": {"passed_milestones": passed_count,
                         "total_milestones": len(milestones),
                         "checked_defense_questions": sum(x["attempted"] for x in questions)},
            "artifact": {"url": artifact[0], "notes": artifact[1], "updated_at": artifact[2],
                         "verification": "self-reported-link-not-reviewed"} if artifact else None,
            "notice": "Milestones use real Docker tests. Defense choices are checked; written rationale is saved but not graded or verified.",
        }

    def submit_milestone(self, project_id: str, milestone_id: str, language: str, code: str) -> dict:
        project = _project(project_id)
        if milestone_id not in project["milestones"] or language not in IMAGES:
            raise ValueError("Unknown milestone or language")
        if not isinstance(code, str) or not 12 <= len(code.encode("utf-8")) <= 12_000:
            raise ValueError("Source must contain 12–12,000 UTF-8 bytes")
        state = self.state(project_id)
        current = next(x for x in state["milestones"] if x["id"] == milestone_id)
        if not current["unlocked"]:
            raise ValueError("Complete the preceding milestone before submitting this one")
        with self.lock:
            attempts = self.db.execute(
                "SELECT COUNT(*) FROM project_milestone_attempts WHERE project_id=?", (project_id,),
            ).fetchone()[0]
        if attempts >= 50:
            raise ValueError("This project has reached its 50-attempt local cap")
        if not self.gate.acquire(blocking=False):
            raise JudgeUnavailable("The local Docker judge is processing another submission")
        try:
            cases = project["milestones"][milestone_id]["cases"]
            checks = self.runner.run(language, code, cases)
            passed = sum(row["status"] == "accepted" for row in checks)
            success = len(checks) == len(cases) and passed == len(cases)
            verdict = "accepted" if success else next(
                (x["status"] for x in checks if x["status"] != "accepted"),
                "wrong_answer",
            )
            digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
            with self.lock:
                cur = self.db.execute("""INSERT INTO project_milestone_attempts
                    (project_id,milestone,language,verdict,passed,total,source_sha256,created_at)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (project_id, milestone_id, language, verdict, passed, len(cases), digest, _stamp()),
                )
                self.db.commit()
            return {
                "id": cur.lastrowid, "project_id": project_id,
                "milestone_id": milestone_id, "language": language,
                "verdict": verdict, "tests_passed": passed, "tests_total": len(cases),
                "all_passed": success, "checks": checks,
                "source": "prepezy-docker-project-milestone",
                "source_sha256": digest,
                "notice": "Only code run inside Docker is graded. Hidden test inputs and outputs are not exposed.",
            }
        finally:
            self.gate.release()

    def defend(self, project_id: str, question_id: str, choice_id: str, rationale: str) -> dict:
        project = _project(project_id)
        if question_id not in project["defense"]:
            raise ValueError("Unknown defense question")
        if not self.state(project_id)["defense_unlocked"]:
            raise ValueError("Pass at least one executable project milestone before defending it")
        if not isinstance(rationale, str) or not 20 <= len(rationale.strip()) <= 1200:
            raise ValueError("Write 20–1200 characters of technical reasoning")
        item = project["defense"][question_id]
        if choice_id not in item["options"]:
            raise ValueError("Invalid defense choice")
        with self.lock:
            count = self.db.execute(
                "SELECT COUNT(*) FROM project_defense_attempts WHERE project_id=? AND question=?",
                (project_id, question_id),
            ).fetchone()[0]
            if count >= 10:
                raise ValueError("Ten submissions maximum per defense question")
            correct = choice_id == item["correct"]
            cursor = self.db.execute("""INSERT INTO project_defense_attempts
                (project_id,question,choice,correct,rationale,created_at)
                VALUES (?,?,?,?,?,?)""",
                (project_id, question_id, choice_id, int(correct), rationale.strip(), _stamp()),
            )
            self.db.commit()
        return {
            "id": cursor.lastrowid, "project_id": project_id,
            "question_id": question_id, "correct": correct,
            "explanation": item["explanation"], "rationale_reviewed": False,
            "source": "prepezy-server-checked-project-defense-choice",
            "notice": "The selected answer is checked. Your written technical reasoning is stored for self/mentor review, NOT independently graded.",
        }

    def save_artifact(self, project_id: str, repo_url: str, notes: str) -> dict:
        _project(project_id)
        if not isinstance(repo_url, str) or not GITHUB_REPO.fullmatch(repo_url):
            raise ValueError("Use an HTTPS GitHub repository URL: https://github.com/owner/repository")
        if not isinstance(notes, str) or len(notes) > 1800:
            raise ValueError("Artifact notes must be 1,800 characters or fewer")
        with self.lock:
            self.db.execute("""INSERT INTO project_artifacts(project_id,repo_url,notes,updated_at)
                VALUES (?,?,?,?) ON CONFLICT(project_id) DO UPDATE SET
                repo_url=excluded.repo_url,notes=excluded.notes,updated_at=excluded.updated_at""",
                (project_id, repo_url.rstrip("/"), notes.strip(), _stamp()),
            )
            self.db.commit()
        return {
            "project_id": project_id, "url": repo_url.rstrip("/"),
            "notes": notes.strip(), "verification": "self-reported-link-not-reviewed",
            "notice": "Saved as an unverified learner-supplied project link. No clone, fetch, execution or repository analysis occurs.",
        }

    def clear(self) -> None:
        with self.lock:
            self.db.execute("DELETE FROM project_milestone_attempts")
            self.db.execute("DELETE FROM project_defense_attempts")
            self.db.execute("DELETE FROM project_artifacts")
            self.db.commit()
