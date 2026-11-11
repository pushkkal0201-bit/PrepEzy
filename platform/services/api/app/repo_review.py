"""Stage 12: explicit, pinned PUBLIC GitHub repo inspection and approved smoke checks.

No OAuth, no repo cloning, no arbitrary hosts/commands, no claims of authorship.
GitHub REST reads fixed endpoints. Static source markers are NOT graded skills.
Single-file checks run in the existing Docker-only judge after explicit approval
and compare to *user-supplied* expectations, NOT independently verified tests.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from threading import RLock
from urllib.parse import quote, urlsplit

import httpx

from .coding_arena import DockerRunner, IMAGES, JudgeUnavailable

OWNER_RE = re.compile(r"^[A-Za-z0-9-]{1,39}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
SHA_RE = re.compile(r"^[a-f0-9]{40}$")
SAFE_CODE_EXTS = {".py": "python", ".js": "javascript", ".java": "java"}
READ_EXTS = {".py", ".js", ".ts", ".tsx", ".java", ".md", ".json", ".toml", ".yaml", ".yml"}
MAX_TREE_BYTES = 2_500_000
MAX_BLOB_BYTES = 24_000
MAX_FILES = 250
MAX_INSPECT = 14
MAX_TEXT_LINES = 450
FINDING_PATTERNS = (
    ("fastapi", re.compile(r"\bFastAPI\s*\(|@\w+\.(?:get|post|put|delete|patch)\s*\(", re.I),
     "This source mentions an HTTP route or FastAPI application. Explain validation, permissions and failure handling for this code."),
    ("database", re.compile(r"\bsqlite3\.connect\s*\(|\bSELECT\b|\bINSERT INTO\b|\bCREATE TABLE\b", re.I),
     "This source references database operations. How would you prevent incorrect or conflicting changes and test persistence?"),
    ("tests", re.compile(r"\bdef test_[A-Za-z0-9_]+\s*\(|\bdescribe\s*\(|\bit\s*\(|@Test\b", re.I),
     "This source appears to define a test. Which behavior is covered, and what edge cases remain untested?"),
    ("frontend", re.compile(r"\buseState\s*\(|\buseEffect\s*\(|\bfunction\s+[A-Z][A-Za-z0-9_]*\s*\(", re.I),
     "This source suggests a UI component or state management. How are loading, errors and stale data handled?"),
    ("network", re.compile(r"\bfetch\s*\(|\bhttpx\.(?:get|post)\s*\(|\brequests\.(?:get|post)\s*\(", re.I),
     "This source mentions a network request. How would you manage timeouts, credentials and untrusted responses?"),
    ("algorithms", re.compile(r"\bclass\s+(?:Solution|Main)\b|\bdef\s+(?:search|solve|binary_search)\b", re.I),
     "This source contains a possible algorithm entry point. Explain complexity and a boundary-case test."),
)
SENSITIVE = re.compile(r"(?i)\b(api[_-]?key|secret|password|token|private[_-]?key)\b")
HIGH_RISK_PATH = re.compile(r"(^|/)(?:\.env[^/]*|id_rsa|id_ed25519|\.git|node_modules|vendor|dist|build|__pycache__)(/|$)", re.I)


class GitHubReviewUnavailable(RuntimeError):
    pass


def repo_parts(value: str) -> tuple[str, str]:
    if not isinstance(value, str) or len(value) > 250:
        raise ValueError("Use a public GitHub repository URL")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or parsed.netloc.lower() != "github.com"
        or parsed.query or parsed.fragment or parsed.username or parsed.password):
        raise ValueError("Only HTTPS github.com/owner/repository links are allowed")
    pieces = [p for p in parsed.path.split("/") if p]
    if (len(pieces) != 2 or not OWNER_RE.fullmatch(pieces[0])
        or not REPO_RE.fullmatch(pieces[1]) or pieces[1].startswith(".")):
        raise ValueError("Use a repository root URL, not a file, issue, PR or arbitrary path")
    name = pieces[1][:-4] if pieces[1].endswith(".git") else pieces[1]
    if not REPO_RE.fullmatch(name):
        raise ValueError("Invalid GitHub repository name")
    return pieces[0], name


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _file_ok(path: str, size: int) -> bool:
    if (not isinstance(path, str) or len(path) > 240
        or HIGH_RISK_PATH.search("/" + path) or size > MAX_BLOB_BYTES or size < 0):
        return False
    return any(path.lower().endswith(ext) for ext in READ_EXTS)


def _safe_line(line: str) -> str:
    """Never echo whole source lines that might contain credentials."""
    if SENSITIVE.search(line):
        return "[possible credential-related line hidden]"
    return line.strip()[:150]


def _findings(path: str, text: str, sha: str, owner: str, name: str, commit: str) -> list[dict]:
    found = []
    for line_no, line in enumerate(text.splitlines()[:MAX_TEXT_LINES], 1):
        for kind, pattern, prompt in FINDING_PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            found.append({
                "id": hashlib.sha256(f"{path}:{line_no}:{kind}".encode()).hexdigest()[:20],
                "kind": kind, "path": path, "line": line_no,
                "marker": match.group(0)[:45],
                "excerpt": _safe_line(line),
                "blob_sha": sha,
                "source_url": (
                    f"https://github.com/{owner}/{name}/blob/{commit}/"
                    + quote(path, safe="/") + f"#L{line_no}"
                ),
                "question": prompt,
                "interpretation": "Static source pattern, not proof the feature works or the code is safe.",
            })
            break
        if len(found) >= 30:
            break
    return found


class GitHubProjectReview:
    def __init__(self, db: sqlite3.Connection, lock: RLock,
                 transport: httpx.AsyncBaseTransport | None = None,
                 runner: DockerRunner | None = None):
        self.db, self.lock = db, lock
        self.transport = transport
        self.runner = runner or DockerRunner()
        with lock:
            db.execute("""CREATE TABLE IF NOT EXISTS github_review_snapshots(
                id INTEGER PRIMARY KEY, repo TEXT NOT NULL, repo_url TEXT NOT NULL,
                commit_sha TEXT NOT NULL, tree_sha TEXT NOT NULL,
                created_at TEXT NOT NULL, files_json TEXT NOT NULL,
                findings_json TEXT NOT NULL, inventory_json TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS github_review_answers(
                id INTEGER PRIMARY KEY, snapshot_id INTEGER NOT NULL,
                finding_id TEXT NOT NULL, response TEXT NOT NULL,
                created_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS github_review_smoke(
                id INTEGER PRIMARY KEY, snapshot_id INTEGER NOT NULL,
                file_path TEXT NOT NULL, blob_sha TEXT NOT NULL,
                language TEXT NOT NULL, cases_total INTEGER NOT NULL,
                cases_passed INTEGER NOT NULL, verdict TEXT NOT NULL,
                created_at TEXT NOT NULL)""")
            db.commit()

    async def _api(self, path: str) -> dict:
        # path only constructed internally from validated owner/repo and hashes.
        try:
            async with httpx.AsyncClient(
                base_url="https://api.github.com",
                timeout=httpx.Timeout(15.0, connect=4.0),
                follow_redirects=False, trust_env=False, transport=self.transport,
                headers={"Accept": "application/vnd.github+json",
                         "User-Agent": "PrepEzy-local-review/1.0"},
            ) as client:
                response = await client.get(path)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise GitHubReviewUnavailable("GitHub API is unreachable") from exc
        if response.status_code in (403, 429):
            raise GitHubReviewUnavailable(
                "GitHub API denied or rate-limited the read-only request; retry manually later"
            )
        if response.status_code != 200:
            raise GitHubReviewUnavailable(f"GitHub API returned HTTP {response.status_code}")
        if len(response.content) > MAX_TREE_BYTES:
            raise GitHubReviewUnavailable("GitHub response exceeded the allowed size")
        try:
            data = response.json()
        except ValueError as exc:
            raise GitHubReviewUnavailable("GitHub returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise GitHubReviewUnavailable("Unexpected GitHub API response")
        return data

    async def _blob(self, owner: str, name: str, sha: str) -> str:
        if not SHA_RE.fullmatch(sha):
            raise ValueError("Invalid immutable blob SHA")
        response = await self._api(f"/repos/{owner}/{name}/git/blobs/{sha}")
        if response.get("encoding") != "base64":
            raise GitHubReviewUnavailable("Unsupported GitHub blob encoding")
        try:
            raw = base64.b64decode(response["content"], validate=False)
            if len(raw) > MAX_BLOB_BYTES:
                raise GitHubReviewUnavailable("Source file exceeds inspection size cap")
            return raw.decode("utf-8")
        except (ValueError, UnicodeDecodeError, TypeError, KeyError) as exc:
            raise GitHubReviewUnavailable("Blob is not a small UTF-8 source file") from exc

    async def inspect(self, repo_url: str) -> dict:
        owner, name = repo_parts(repo_url)
        base = f"/repos/{owner}/{name}"
        metadata = await self._api(base)
        if metadata.get("private") is not False:
            raise GitHubReviewUnavailable("Only publicly accessible GitHub repositories are supported")
        default = metadata.get("default_branch")
        if not isinstance(default, str) or not 1 <= len(default) <= 100:
            raise GitHubReviewUnavailable("GitHub did not return a usable default branch")
        commit = await self._api(f"{base}/commits/{quote(default, safe='')}")
        sha = str(commit.get("sha", ""))
        tree_sha = str((commit.get("commit") or {}).get("tree", {}).get("sha", ""))
        if not SHA_RE.fullmatch(sha) or not SHA_RE.fullmatch(tree_sha):
            raise GitHubReviewUnavailable("GitHub returned invalid commit/tree provenance")
        tree = await self._api(f"{base}/git/trees/{tree_sha}?recursive=1")
        listing = tree.get("tree")
        if not isinstance(listing, list) or tree.get("truncated") or len(listing) > 3000:
            raise GitHubReviewUnavailable("Repository tree was truncated or too large; no partial inspection is claimed")
        candidates = []
        for obj in listing:
            if not isinstance(obj, dict) or obj.get("type") != "blob":
                continue
            path, blob = obj.get("path"), obj.get("sha")
            size = obj.get("size")
            if not isinstance(size, int) or not isinstance(blob, str) or not SHA_RE.fullmatch(blob):
                continue
            if _file_ok(path, size):
                candidates.append({"path": path, "sha": blob, "size": size})
        candidates.sort(key=lambda x: (
            0 if re.search(r"(^|/)(?:main|app|server|index)\.(?:py|js|java|ts)$", x["path"], re.I) else
            1 if re.search(r"(^|/)(?:test_|.*\.test\.|.*\.spec\.)", x["path"], re.I) else
            2 if x["path"].lower().endswith((".py", ".js", ".ts", ".java")) else 3,
            x["path"],
        ))
        chosen = candidates[:MAX_INSPECT]
        findings: list[dict] = []
        inspected = []
        failures = []
        for file in chosen:
            try:
                text = await self._blob(owner, name, file["sha"])
            except GitHubReviewUnavailable as exc:
                failures.append({"path": file["path"], "error": str(exc)})
                continue
            inspected.append(file["path"])
            findings.extend(_findings(file["path"], text, file["sha"], owner, name, sha))
        # No inference from absence of findings in a bounded file subset.
        tests = [x["path"] for x in candidates if re.search(
            r"(^|/)(test_[^/]*\.py|[^/]*\.(?:test|spec)\.[jt]sx?|tests?/)", x["path"], re.I
        )][:40]
        inventory = {
            "candidate_files": len(candidates), "inspected_count": len(inspected),
            "inspected_paths": inspected, "failed_paths": failures,
            "test_file_paths": tests,
            "files_omitted": max(0, len(candidates) - len(inspected)),
            "scope": "bounded-read-only-static-sample",
        }
        if not inspected:
            raise GitHubReviewUnavailable("No eligible small UTF-8 source files could be inspected")
        with self.lock:
            cur = self.db.execute("""INSERT INTO github_review_snapshots(
                repo,repo_url,commit_sha,tree_sha,created_at,files_json,
                findings_json,inventory_json) VALUES (?,?,?,?,?,?,?,?)""",
                (f"{owner}/{name}", f"https://github.com/{owner}/{name}", sha,
                 tree_sha, _now(), json.dumps(candidates[:MAX_FILES]),
                 json.dumps(findings[:100]), json.dumps(inventory)),
            )
            self.db.commit()
            snapshot_id = cur.lastrowid
        return self.snapshot(snapshot_id)

    def snapshot(self, snapshot_id: int) -> dict:
        with self.lock:
            row = self.db.execute("""SELECT id,repo,repo_url,commit_sha,tree_sha,created_at,
                files_json,findings_json,inventory_json FROM github_review_snapshots
                WHERE id=?""", (snapshot_id,)).fetchone()
        if not row:
            raise ValueError("No saved GitHub review snapshot")
        sid, repo, url, commit, tree, created, file_json, finding_json, inventory = row
        files = json.loads(file_json)
        findings = json.loads(finding_json)
        return {
            "id": sid, "repository": repo, "url": url, "commit_sha": commit,
            "tree_sha": tree, "created_at": created,
            "candidate_files": [{"path": x["path"], "language": next(
                (v for ext, v in SAFE_CODE_EXTS.items() if x["path"].endswith(ext)), None),
                "size": x["size"], "sha": x["sha"]} for x in files],
            "findings": findings,
            "inventory": json.loads(inventory),
            "question_count": len(findings),
            "assessment": "not-scored-static-inspection",
            "notice": ("Read-only snapshot of a limited subset of public GitHub files pinned to a commit. "
                       "Markers are not verified functionality, ownership, code quality or SkillGraph mastery."),
        }

    def history(self) -> dict:
        with self.lock:
            rows = self.db.execute("""SELECT id,repo,commit_sha,created_at
                FROM github_review_snapshots ORDER BY id DESC LIMIT 15""").fetchall()
        return {"snapshots": [{"id": x[0], "repository": x[1], "commit_sha": x[2],
                               "created_at": x[3]} for x in rows]}

    def answer(self, snapshot_id: int, finding_id: str, response: str) -> dict:
        snapshot = self.snapshot(snapshot_id)
        if finding_id not in {x["id"] for x in snapshot["findings"]}:
            raise ValueError("Unknown source-linked technical-defense question")
        if not isinstance(response, str) or not 30 <= len(response.strip()) <= 2000:
            raise ValueError("Write 30–2000 characters explaining design and tradeoffs")
        with self.lock:
            number = self.db.execute(
                "SELECT COUNT(*) FROM github_review_answers WHERE snapshot_id=?", (snapshot_id,)
            ).fetchone()[0]
            if number >= 30:
                raise ValueError("Maximum 30 explanations per snapshot")
            cur = self.db.execute("""INSERT INTO github_review_answers(
                snapshot_id,finding_id,response,created_at) VALUES (?,?,?,?)""",
                (snapshot_id, finding_id, response.strip(), _now()))
            self.db.commit()
        return {"id": cur.lastrowid, "saved": True, "graded": False,
                "notice": "Free-form defense reasoning saved for self/mentor review, not graded by AI."}

    def answers(self, snapshot_id: int) -> dict:
        self.snapshot(snapshot_id)
        with self.lock:
            rows = self.db.execute("""SELECT id,finding_id,response,created_at
                FROM github_review_answers WHERE snapshot_id=? ORDER BY id DESC LIMIT 30""",
                (snapshot_id,)).fetchall()
        return {"answers": [{"id": r[0], "finding_id": r[1], "response": r[2],
                             "created_at": r[3], "graded": False} for r in rows]}

    async def smoke_check(self, snapshot_id: int, file_path: str, language: str,
                          cases: list[dict], approved: bool) -> dict:
        if approved is not True:
            raise ValueError("Explicit approval is required before executing any repository source")
        snapshot = self.snapshot(snapshot_id)
        file = next((x for x in snapshot["candidate_files"]
                     if x["path"] == file_path and x["language"] == language), None)
        if file is None or language not in IMAGES:
            raise ValueError("Select a previously snapshotted, supported Python/JavaScript/Java file")
        if not isinstance(cases, list) or not 1 <= len(cases) <= 3:
            raise ValueError("Provide one to three user-specified stdin/expected-stdout cases")
        pairs = []
        for case in cases:
            if (not isinstance(case, dict)
                or not isinstance(case.get("stdin"), str)
                or not isinstance(case.get("expected_stdout"), str)
                or len(case["stdin"]) > 2000 or len(case["expected_stdout"]) > 2000):
                raise ValueError("Each case needs bounded stdin and expected stdout strings")
            pairs.append((case["stdin"], case["expected_stdout"]))
        with self.lock:
            count = self.db.execute(
                "SELECT COUNT(*) FROM github_review_smoke WHERE snapshot_id=?", (snapshot_id,)
            ).fetchone()[0]
        if count >= 12:
            raise ValueError("Maximum twelve local smoke checks per snapshot")
        owner, name = snapshot["repository"].split("/")
        src = await self._blob(owner, name, file["sha"])
        if not 12 <= len(src.encode("utf-8")) <= 12000:
            raise ValueError("Only standalone source files of 12–12,000 bytes can be smoke-tested")
        # DockerRunner runs each test with no network and strict resource limits.
        checks = self.runner.run(language, src, pairs)
        passed = sum(x["status"] == "accepted" for x in checks)
        success = len(checks) == len(pairs) and passed == len(pairs)
        verdict = "matched-user-expected-output" if success else next(
            (x["status"] for x in checks if x["status"] != "accepted"), "wrong_answer",
        )
        with self.lock:
            cur = self.db.execute("""INSERT INTO github_review_smoke(
                snapshot_id,file_path,blob_sha,language,cases_total,cases_passed,
                verdict,created_at) VALUES (?,?,?,?,?,?,?,?)""",
                (snapshot_id, file_path, file["sha"], language, len(pairs),
                 passed, verdict, _now()))
            self.db.commit()
        return {
            "id": cur.lastrowid, "snapshot_id": snapshot_id,
            "file_path": file_path, "blob_sha": file["sha"],
            "commit_sha": snapshot["commit_sha"],
            "language": language, "tests_passed": passed, "tests_total": len(pairs),
            "verdict": verdict, "checks": checks,
            "expectation_origin": "learner-supplied-not-independently-verified",
            "graded_skillgraph": False,
            "notice": ("Actual Docker execution of a pinned public GitHub file against user-supplied expectations. "
                       "No arbitrary repo command or network access. Passing is NOT independent "
                       "verification of the project, qualifications or a SkillGraph assessment."),
        }

    def evidence(self, snapshot_id: int) -> dict:
        self.snapshot(snapshot_id)
        with self.lock:
            rows = self.db.execute("""SELECT id,file_path,blob_sha,language,cases_total,
                cases_passed,verdict,created_at FROM github_review_smoke
                WHERE snapshot_id=? ORDER BY id DESC""", (snapshot_id,)).fetchall()
        return {
            "smoke_checks": [{
                "id": r[0], "path": r[1], "blob_sha": r[2],
                "language": r[3], "tests_total": r[4], "tests_passed": r[5],
                "verdict": r[6], "created_at": r[7], "graded_skillgraph": False,
            } for r in rows],
            "answers": self.answers(snapshot_id)["answers"],
            "notice": ("Smoke checks use learner-specified expectations. Static findings and "
                       "free-form explanations are ungraded and do not alter SkillGraph."),
        }

    def clear(self) -> dict:
        with self.lock:
            self.db.execute("DELETE FROM github_review_answers")
            self.db.execute("DELETE FROM github_review_smoke")
            self.db.execute("DELETE FROM github_review_snapshots")
            self.db.commit()
        return {"deleted": True, "notice": "GitHub repository inspection snapshots and local technical-defense responses deleted."}
