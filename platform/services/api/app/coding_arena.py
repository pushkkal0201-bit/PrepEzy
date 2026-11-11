"""Local Docker-only coding judge. Never runs user code on the host.

Not a hosted, adversarially hardened sandbox. Use on a trusted developer
machine only. DO NOT expose an unauthenticated Docker-backed service publicly.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone

IMAGES = {
    "python": "python:3.11-alpine",
    "javascript": "node:22-alpine",
    "java": "eclipse-temurin:21-jdk-alpine",
}
FILENAMES = {"python": "main.py", "javascript": "main.js", "java": "Main.java"}
# These are fixed, trusted shell scripts. User code is only placed in a file.
COMMANDS = {
    "python": "ulimit -f 32; python3 -B /workspace/main.py > /tmp/answer.out 2>/tmp/answer.err; rc=$?; cat /tmp/answer.out; cat /tmp/answer.err >&2; exit $rc",
    "javascript": "ulimit -f 32; node /workspace/main.js > /tmp/answer.out 2>/tmp/answer.err; rc=$?; cat /tmp/answer.out; cat /tmp/answer.err >&2; exit $rc",
    "java": "ulimit -f 32; javac -encoding UTF-8 -d /tmp /workspace/Main.java 2>/tmp/answer.err || { cat /tmp/answer.err >&2; exit 120; }; java -cp /tmp Main > /tmp/answer.out 2>/tmp/answer.err; rc=$?; cat /tmp/answer.out; cat /tmp/answer.err >&2; exit $rc",
}

# Original PrepEzy assessment tasks; inputs and outputs are deterministic.
# The browser only receives public examples and metadata, not hidden cases.
PROBLEMS = {
    "sum-pair": {
        "title": "Sum two integers", "topic": "Input/output", "difficulty": "easy",
        "statement": "Read two signed integers a and b; print their sum.",
        "cases": [("3 8\n", "11"), ("-7 14\n", "7"), ("0 0\n", "0"), ("1000000000 1000000000\n", "2000000000")],
        "public": 1,
    },
    "distinct-values": {
        "title": "Count distinct values", "topic": "Hashing", "difficulty": "easy",
        "statement": "Read n and then n integers. Print how many different integer values occur.",
        "cases": [("6\n2 1 2 3 1 4\n", "4"), ("1\n99\n", "1"), ("8\n-1 -1 0 0 1 1 2 2\n", "4"),
                  ("10\n5 4 3 2 1 5 4 3 2 1\n", "5")],
        "public": 1,
    },
    "positive-streak": {
        "title": "Longest positive streak", "topic": "Arrays", "difficulty": "easy",
        "statement": "Read n and n integers. Print the length of the longest consecutive run of values strictly greater than zero.",
        "cases": [("8\n1 2 -3 4 5 6 0 7\n", "3"), ("4\n-1 0 -2 -7\n", "0"), ("5\n1 2 3 4 5\n", "5"),
                  ("9\n1 -1 1 1 0 2 2 2 2\n", "4")],
        "public": 1,
    },
    "balanced-brackets": {
        "title": "Balanced parentheses", "topic": "Stacks", "difficulty": "medium",
        "statement": "Read one nonempty string containing only '(' and ')'. Print YES if it is balanced; otherwise NO.",
        "cases": [("(())()\n", "YES"), ("())(\n", "NO"), ("((((()))))\n", "YES"),
                  ("(()\n", "NO"), (")(\n", "NO")],
        "public": 1,
    },
}
STARTERS = {
    "python": "import sys\n\ndef main():\n    tokens = sys.stdin.read().split()\n    # TODO: compute and print the answer\n\nif __name__ == '__main__':\n    main()\n",
    "javascript": "const fs = require('fs');\nconst tokens = fs.readFileSync(0, 'utf8').trim().split(/\\s+/);\n// TODO: compute and print the answer\n",
    "java": "import java.util.*;\npublic class Main {\n    public static void main(String[] args) {\n        Scanner sc = new Scanner(System.in);\n        // TODO: compute and print the answer\n    }\n}\n",
}

class JudgeUnavailable(RuntimeError):
    pass


def _normalise(output: str) -> list[str]:
    return output.split()


def public_problems() -> dict:
    return {
        "problems": [
            {"id": key, "title": val["title"], "topic": val["topic"],
             "difficulty": val["difficulty"], "statement": val["statement"],
             "public_examples": [{"input": x, "output": y} for x, y in val["cases"][:val["public"]]],
             "test_count": len(val["cases"])}
            for key, val in PROBLEMS.items()
        ],
        "languages": sorted(IMAGES),
        "starters": STARTERS,
        "limitations": "Local-only Docker execution with predefined deterministic tests. This is not a remote contest or proof of interview readiness.",
    }


class DockerRunner:
    """One ephemeral, network-disabled container per test case; no host fallback."""
    def available(self, language: str) -> bool:
        if language not in IMAGES or shutil.which("docker") is None:
            return False
        try:
            check = subprocess.run(
                ["docker", "image", "inspect", IMAGES[language]],
                capture_output=True, timeout=4, check=False,
            )
            return check.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def run(self, language: str, source: str, cases: list[tuple[str, str]]) -> list[dict]:
        if language not in IMAGES:
            raise ValueError("Unsupported language")
        if not self.available(language):
            raise JudgeUnavailable("Docker or the selected language image is unavailable. See setup instructions.")
        results = []
        with tempfile.TemporaryDirectory(prefix="prepezy-judge-") as folder:
            root = Path(folder).resolve()
            src = root / FILENAMES[language]
            src.write_text(source, encoding="utf-8")
            try:
                os.chmod(root, 0o755)
                os.chmod(src, 0o644)
            except OSError:
                pass
            for index, (stdin, expected) in enumerate(cases):
                name = "prepezy-judge-" + uuid.uuid4().hex[:20]
                cmd = [
                    "docker", "run", "--rm", "--interactive", "--name", name,
                    "--network=none", "--read-only", "--cap-drop=ALL",
                    "--security-opt=no-new-privileges", "--pids-limit=64",
                    "--cpus=1", "--memory=" + ("384m" if language == "java" else "192m"),
                    "--memory-swap=" + ("384m" if language == "java" else "192m"),
                    "--tmpfs=/tmp:rw,exec,nosuid,nodev,size=96m",
                    "--mount=type=bind,source=" + str(root) + ",target=/workspace,readonly",
                    "--workdir=/tmp", "--user=65534:65534",
                    "--entrypoint=/bin/sh", IMAGES[language], "-c", COMMANDS[language],
                ]
                try:
                    result = subprocess.run(cmd, input=stdin.encode("utf-8"),
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            timeout=16 if language == "java" else 8, check=False)
                except subprocess.TimeoutExpired:
                    # A killed docker CLI does not necessarily terminate the container.
                    # Explicitly remove the named container; never leave timed-out code running.
                    try:
                        subprocess.run(["docker", "rm", "--force", name],
                                       capture_output=True, timeout=4, check=False)
                    except (OSError, subprocess.TimeoutExpired):
                        pass
                    results.append({"case": index + 1, "status": "time_limit"})
                    continue
                except OSError as error:
                    raise JudgeUnavailable("Docker CLI failed to start") from error
                stdout = result.stdout.decode("utf-8", errors="replace")[:16000]
                stderr = result.stderr.decode("utf-8", errors="replace")[:1600]
                if result.returncode == 120 and language == "java":
                    status = "compile_error"
                elif result.returncode != 0:
                    status = "runtime_error"
                else:
                    status = "accepted" if _normalise(stdout) == _normalise(expected) else "wrong_answer"
                # Never return hidden test input/output. Short compiler errors are fine.
                item = {"case": index + 1, "status": status}
                if index == 0 and status != "accepted":
                    item["feedback"] = stderr[:280] if status in ("compile_error", "runtime_error") else "Output did not match the public example."
                results.append(item)
                if status in ("compile_error", "time_limit"):
                    # Repeating a failed compile on every private test adds no value.
                    break
        return results


class CodingArena:
    def __init__(self, db: sqlite3.Connection, lock: threading.RLock,
                 runner=None, clock=None):
        self.db, self.lock = db, lock
        self.runner = runner if runner is not None else DockerRunner()
        self.clock = clock if clock is not None else time.time
        self.capacity = threading.BoundedSemaphore(value=1)
        with self.lock:
            self.db.execute("""CREATE TABLE IF NOT EXISTS arena_sessions(
                id TEXT PRIMARY KEY, mode TEXT NOT NULL, created_at INTEGER NOT NULL,
                deadline INTEGER NOT NULL, ended_at INTEGER
            )""")
            self.db.execute("""CREATE TABLE IF NOT EXISTS arena_attempts(
                id INTEGER PRIMARY KEY, session_id TEXT NOT NULL,
                problem TEXT NOT NULL, language TEXT NOT NULL, passed INTEGER NOT NULL,
                total INTEGER NOT NULL, verdict TEXT NOT NULL, source_sha256 TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )""")
            self.db.commit()

    def availability(self) -> dict:
        return {"ready": {lang: bool(self.runner.available(lang)) for lang in IMAGES},
                "requires": "Docker Desktop in Linux-container mode, with pre-pulled language images",
                "execution": "Docker only; never run submissions on the host"}

    def current_session(self) -> dict | None:
        with self.lock:
            row = self.db.execute("""SELECT id,mode,created_at,deadline,ended_at
                FROM arena_sessions ORDER BY created_at DESC, rowid DESC LIMIT 1""").fetchone()
        if not row:
            return None
        sid, mode, created, deadline, ended = row
        now = int(self.clock())
        status = "finished" if ended is not None else "expired" if now >= deadline else "active"
        return {"id": sid, "mode": mode, "created_at": created,
                "deadline": deadline, "seconds_remaining": max(0, deadline - now),
                "status": status}

    def start(self, mode: str, duration_minutes: int) -> dict:
        if mode not in ("practice", "timed"):
            raise ValueError("Choose practice or timed")
        if type(duration_minutes) is not int or duration_minutes not in (15, 30, 45, 60):
            raise ValueError("Choose 15, 30, 45 or 60 minutes")
        if not any(self.runner.available(lang) for lang in IMAGES):
            raise JudgeUnavailable("Docker and at least one language image must be ready before starting.")
        active = self.current_session()
        if active and active["status"] == "active":
            return active
        now = int(self.clock())
        session_id = uuid.uuid4().hex
        limit = 4 * 60 * 60 if mode == "practice" else duration_minutes * 60
        with self.lock:
            self.db.execute(
                "INSERT INTO arena_sessions(id,mode,created_at,deadline) VALUES (?,?,?,?)",
                (session_id, mode, now, now + limit),
            )
            self.db.commit()
        return self.current_session()

    def finish(self, session_id: str) -> dict:
        active = self.current_session()
        if active is None or active["id"] != session_id or active["status"] != "active":
            raise ValueError("No active matching session")
        with self.lock:
            self.db.execute("UPDATE arena_sessions SET ended_at=? WHERE id=?",
                            (int(self.clock()), session_id))
            self.db.commit()
        return self.current_session()

    def submit(self, session_id: str, problem: str, language: str, source: str) -> dict:
        active = self.current_session()
        if active is None or active["id"] != session_id or active["status"] != "active":
            raise ValueError("Start an active local coding session first")
        if problem not in PROBLEMS or language not in IMAGES:
            raise ValueError("Unknown coding problem or language")
        if not isinstance(source, str) or not 12 <= len(source.encode("utf-8")) <= 12000:
            raise ValueError("Source must be 12–12000 UTF-8 bytes")
        with self.lock:
            attempts = self.db.execute(
                "SELECT COUNT(*) FROM arena_attempts WHERE session_id=?", (session_id,)
            ).fetchone()[0]
        if attempts >= 30:
            raise ValueError("This session reached its 30 submission limit")
        if not self.capacity.acquire(blocking=False):
            raise JudgeUnavailable("Local judge is busy processing another submission")
        try:
            cases = PROBLEMS[problem]["cases"]
            checked = self.runner.run(language, source, cases)
            passed = sum(x["status"] == "accepted" for x in checked)
            full = passed == len(cases) and len(checked) == len(cases)
            if full:
                verdict = "accepted"
            else:
                verdict = next(
                    (x["status"] for x in checked if x["status"] != "accepted"),
                    "wrong_answer",
                )
            now = int(self.clock())
            digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
            with self.lock:
                cur = self.db.execute(
                    """INSERT INTO arena_attempts(
                         session_id,problem,language,passed,total,verdict,source_sha256,created_at
                       ) VALUES (?,?,?,?,?,?,?,?)""",
                    (session_id, problem, language, passed, len(cases), verdict, digest, now),
                )
                self.db.commit()
                number = cur.lastrowid
            return {"id": number, "session_id": session_id, "problem_id": problem,
                    "language": language, "tests_passed": passed,
                    "tests_total": len(cases), "verdict": verdict,
                    "all_passed": full, "checks": checked,
                    "source": "prepezy-docker-isolated-code-runner",
                    "notice": "Actual predefined test execution, not an AI-inferred score. Private inputs and outputs remain hidden."}
        finally:
            self.capacity.release()

    def evidence(self) -> list[dict]:
        with self.lock:
            rows = self.db.execute("""SELECT id,session_id,problem,language,passed,total,
                verdict,source_sha256,created_at
                FROM arena_attempts ORDER BY id DESC LIMIT 120""").fetchall()
        return [{
            "id": rid, "session_id": sid, "problem_id": problem,
            "language": lang, "tests_passed": passed, "tests_total": total,
            "verdict": verdict, "correct": verdict == "accepted",
            "source_sha256": sha,
            "source": "prepezy-docker-isolated-code-runner",
            "created_at": datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        } for rid, sid, problem, lang, passed, total, verdict, sha, ts in rows]

    def reset(self) -> None:
        with self.lock:
            self.db.execute("DELETE FROM arena_attempts")
            self.db.execute("DELETE FROM arena_sessions")
            self.db.commit()
