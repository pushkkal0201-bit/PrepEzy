"use client";

import { useEffect, useMemo, useState } from "react";

const API = process.env.NEXT_PUBLIC_PREPEZY_API_URL || "http://localhost:8000";
type FileEntry = { path: string; language: "python" | "javascript" | "java" | null; size: number; sha: string };
type Finding = {
  id: string; kind: string; path: string; line: number; marker: string;
  excerpt: string; source_url: string; question: string; interpretation: string;
};
type Snapshot = {
  id: number; repository: string; url: string; commit_sha: string; tree_sha: string; created_at: string;
  candidate_files: FileEntry[]; findings: Finding[]; question_count: number;
  inventory: { candidate_files: number; inspected_count: number; inspected_paths: string[];
    failed_paths: { path: string; error: string }[]; test_file_paths: string[];
    files_omitted: number; scope: string };
  assessment: string; notice: string;
};
type History = { snapshots: { id: number; repository: string; commit_sha: string; created_at: string }[] };
type Evidence = {
  smoke_checks: { id: number; path: string; language: string; cases_total: number; cases_passed: number;
    verdict: string; blob_sha: string; graded_skillgraph: boolean }[];
  answers: { id: number; finding_id: string; response: string; graded: boolean; created_at: string }[];
  notice: string;
};
type Smoke = {
  file_path: string; language: string; tests_passed: number; tests_total: number; verdict: string;
  expectation_origin: string; graded_skillgraph: boolean; notice: string;
  checks: { case: number; status: string; feedback?: string }[];
};

async function request(path: string, init?: RequestInit) {
  const r = await fetch(API + path, init);
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    throw Error(typeof data.detail === "string" ? data.detail : "GitHub review API returned HTTP " + r.status);
  }
  return r.json();
}
const jsonHeaders = { "Content-Type": "application/json" };

export default function GitHubReviewStudio() {
  const [url, setUrl] = useState("");
  const [history, setHistory] = useState<History>({ snapshots: [] });
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [findingId, setFindingId] = useState("");
  const [reasoning, setReasoning] = useState("");
  const [filePath, setFilePath] = useState("");
  const [stdin, setStdin] = useState("");
  const [expected, setExpected] = useState("");
  const [approved, setApproved] = useState(false);
  const [smoke, setSmoke] = useState<Smoke | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function loadHistory() {
    const data: History = await request("/api/local/repositories/history");
    setHistory(data);
    return data;
  }

  async function openSnapshot(id: number) {
    const [snap, ev]: [Snapshot, Evidence] = await Promise.all([
      request("/api/local/repositories/" + id),
      request("/api/local/repositories/" + id + "/evidence"),
    ]);
    setSnapshot(snap); setEvidence(ev);
    setFindingId(snap.findings[0]?.id || "");
    setFilePath(snap.candidate_files.find(x => x.language && snap.inventory.inspected_paths.includes(x.path))?.path || "");
    setApproved(false); setSmoke(null); setReasoning(""); setNotice("");
    return snap;
  }

  useEffect(() => {
    let active = true;
    request("/api/local/repositories/history").then(async (data: History) => {
      if (!active) return;
      setHistory(data);
      const last = data.snapshots[0]?.id;
      if (last) {
        const [snap, ev] = await Promise.all([
          request("/api/local/repositories/" + last),
          request("/api/local/repositories/" + last + "/evidence"),
        ]);
        if (!active) return;
        setSnapshot(snap); setEvidence(ev);
        setFindingId(snap.findings[0]?.id || "");
        setFilePath(snap.candidate_files.find((x: FileEntry) => x.language &&
          snap.inventory.inspected_paths.includes(x.path))?.path || "");
      }
    }).catch(e => { if (active) setError(String(e)); });
    return () => { active = false; };
  }, []);

  async function execute(operation: string, work: () => Promise<void>) {
    setBusy(operation); setError(""); setNotice("");
    try { await work(); } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  async function inspect() {
    await execute("inspect", async () => {
      const result: Snapshot = await request("/api/local/repositories/inspect", {
        method: "POST", headers: jsonHeaders, body: JSON.stringify({ repo_url: url.trim() }),
      });
      await loadHistory();
      await openSnapshot(result.id);
      setNotice("Read-only inspection saved at commit " + result.commit_sha.slice(0, 12) +
        ". Only a bounded source sample was examined.");
    });
  }

  async function submitReasoning() {
    if (!snapshot || !findingId || reasoning.trim().length < 30) return;
    await execute("defense", async () => {
      const result = await request("/api/local/repositories/" + snapshot.id + "/defense", {
        method: "POST", headers: jsonHeaders,
        body: JSON.stringify({ finding_id: findingId, response: reasoning }),
      });
      setEvidence(await request("/api/local/repositories/" + snapshot.id + "/evidence"));
      setReasoning("");
      setNotice(result.notice);
    });
  }

  async function runSmoke() {
    if (!snapshot || !approved || !selectedFile?.language) return;
    await execute("smoke", async () => {
      const result: Smoke = await request("/api/local/repositories/" + snapshot.id + "/smoke", {
        method: "POST", headers: jsonHeaders,
        body: JSON.stringify({
          file_path: filePath, language: selectedFile.language,
          cases: [{ stdin, expected_stdout: expected }], approved,
        }),
      });
      setSmoke(result);
      setApproved(false);
      setEvidence(await request("/api/local/repositories/" + snapshot.id + "/evidence"));
    });
  }

  async function clear() {
    if (!window.confirm("Delete all local GitHub inspection snapshots, defense explanations and smoke-check records?")) return;
    await execute("delete", async () => {
      await request("/api/local/repositories/data", { method: "DELETE" });
      setSnapshot(null); setEvidence(null); setSmoke(null); setFindingId("");
      setFilePath(""); setApproved(false); setReasoning(""); setHistory({ snapshots: [] });
      setNotice("Locally saved GitHub review data deleted.");
    });
  }

  const activeFinding = useMemo(
    () => snapshot?.findings.find(x => x.id === findingId),
    [snapshot, findingId],
  );
  const selectedFile = useMemo(
    () => snapshot?.candidate_files.find(x => x.path === filePath),
    [snapshot, filePath],
  );
  const executable = snapshot?.candidate_files.filter(
    x => x.language && snapshot.inventory.inspected_paths.includes(x.path)
  ) || [];

  return <section className="panel repo-review" aria-label="GitHub evidence and project defense">
    <p className="eyebrow">STAGE 12 · PINNED GITHUB EVIDENCE · REVIEW-ONLY DEFENSE</p>
    <h2>GitHub Project Evidence</h2>
    <p className="sub">Inspect a public repository that you choose. PrepEzy reads small source files at an exact commit, cites actual code lines, and asks technical-defense questions based on what was found. This does not verify ownership or assess full project quality.</p>

    <div className="repo-box">
      <h3>1. Inspect a public GitHub repository</h3>
      <p className="fineprint">Only public GitHub root links are accepted. GitHub's REST API is used read-only. No git clone, arbitrary URLs, web crawling, or repository commands.</p>
      <label htmlFor="repo-link">Public GitHub repository URL</label>
      <div className="repo-inspect-row">
        <input id="repo-link" placeholder="https://github.com/owner/repository"
          value={url} maxLength={250} onChange={e => setUrl(e.target.value)}/>
        <button disabled={Boolean(busy) || !url.startsWith("https://github.com/")}
          onClick={inspect}>{busy === "inspect" ? "Reading pinned source…" : "Inspect source"}</button>
      </div>
      {history.snapshots.length > 0 && <label htmlFor="repo-history">Previously inspected snapshots
        <select id="repo-history" value={snapshot?.id || ""} onChange={e => {
          if (e.target.value) openSnapshot(Number(e.target.value)).catch(err => setError(String(err)));
        }}>
          <option value="">Select a snapshot</option>
          {history.snapshots.map(h => <option value={h.id} key={h.id}>
            {h.repository} · {h.commit_sha.slice(0, 10)} · {h.created_at}
          </option>)}
        </select>
      </label>}
      {error && <p className="error" role="alert">{error}</p>}
      {notice && <p className="feedback" role="status">{notice}</p>}
    </div>

    {snapshot && <>
      <div className="repo-summary">
        <div><strong>{snapshot.repository}</strong><small>Public GitHub source · pinned commit</small></div>
        <div><strong>{snapshot.commit_sha.slice(0, 12)}</strong><small>Commit SHA</small></div>
        <div><strong>{snapshot.inventory.inspected_count}</strong><small>Small source files inspected</small></div>
        <div><strong>{snapshot.findings.length}</strong><small>Static code observations</small></div>
      </div>
      <p className="fineprint">The repository contains {snapshot.inventory.candidate_files} eligible files; only {snapshot.inventory.inspected_count} small UTF-8 files were inspected. {snapshot.inventory.files_omitted} eligible files were not inspected. No absence-of-feature claim is drawn from this subset.</p>
      <div className="repo-grid">
        <div className="repo-box">
          <h3>2. Source-linked technical-defense questions</h3>
          <p className="fineprint">Each question is based on a real observed source marker, not an invented project description. Answer quality requires human review; there is no AI-generated defense score.</p>
          {snapshot.findings.length === 0 && <p className="fineprint">No recognized source patterns were found in the limited sample.</p>}
          <label htmlFor="repo-defense-select">Observed source marker</label>
          <select id="repo-defense-select" value={findingId} onChange={e => {
            setFindingId(e.target.value); setReasoning("");
          }}>
            <option value="">Choose a source finding</option>
            {snapshot.findings.map(f => <option key={f.id} value={f.id}>
              {f.kind} · {f.path}:{f.line}
            </option>)}
          </select>
          {activeFinding && <div className="repo-finding">
            <p className="eyebrow">{activeFinding.kind.toUpperCase()} · ACTUAL SOURCE</p>
            <a href={activeFinding.source_url} target="_blank" rel="noopener noreferrer">
              {activeFinding.path} · line {activeFinding.line}
            </a>
            <code>{activeFinding.excerpt}</code>
            <p className="fineprint">{activeFinding.interpretation}</p>
            <p className="repo-prompt">{activeFinding.question}</p>
            <label htmlFor="repo-defense-answer">Your design explanation (ungraded)</label>
            <textarea id="repo-defense-answer" rows={6} maxLength={2000}
              placeholder="Explain the tradeoff and reference what the actual code does. This will not be automatically graded."
              value={reasoning} onChange={e => setReasoning(e.target.value)}/>
            <button disabled={Boolean(busy) || reasoning.trim().length < 30}
              onClick={submitReasoning}>Save reasoning for review</button>
          </div>}
          <div className="repo-evidence-list">
            <h4>Saved explanations</h4>
            {evidence?.answers.length === 0 && <p className="fineprint">No project-defense explanations recorded.</p>}
            {evidence?.answers.slice(0, 5).map(a => <div key={a.id}>
              <strong>Source question {a.finding_id.slice(0, 7)} · ungraded</strong>
              <p>{a.response}</p>
            </div>)}
          </div>
        </div>

        <div className="repo-box">
          <h3>3. Explicitly approved, single-file Docker smoke check</h3>
          <p className="fineprint">This is an optional execution of a pinned standalone file inside the existing local restricted Docker judge. It does NOT run \`pytest\`, \`npm test\`, build scripts or arbitrary repository commands. Only Python, JavaScript and Java single files are supported.</p>
          {executable.length === 0 && <p className="fineprint">No inspected standalone language files eligible for smoke checks.</p>}
          <label htmlFor="repo-source-file">Pinned source file</label>
          <select id="repo-source-file" value={filePath} onChange={e => {
            setFilePath(e.target.value); setApproved(false); setSmoke(null);
          }}>
            <option value="">Choose a source file</option>
            {executable.map(f => <option key={f.path} value={f.path}>{f.path} · {f.language} · {f.size} bytes</option>)}
          </select>
          <label htmlFor="repo-smoke-input">Test input (stdin, max 2,000 characters)</label>
          <textarea id="repo-smoke-input" rows={3} maxLength={2000} spellCheck={false}
            value={stdin} onChange={e => { setStdin(e.target.value); setApproved(false); }}/>
          <label htmlFor="repo-smoke-expected">Expected program output (your own expectation)</label>
          <textarea id="repo-smoke-expected" rows={3} maxLength={2000} spellCheck={false}
            value={expected} onChange={e => { setExpected(e.target.value); setApproved(false); }}/>
          <p className="fineprint">Passing means actual output matched <strong>your declared expectation</strong>, not that the project passed independently designed tests or deserves SkillGraph credit. Programs requiring packages, imported files, network access or custom compilation may not run in this restricted standalone environment.</p>
          <label className="repo-approval">
            <input type="checkbox" checked={approved} onChange={e => setApproved(e.target.checked)}/>
            I explicitly approve running this pinned source file in the local restricted Docker container against the input and expected output I entered.
          </label>
          <button disabled={Boolean(busy) || !approved || !selectedFile?.language}
            onClick={runSmoke}>{busy === "smoke" ? "Executing approved Docker check…" : "Run approved smoke check"}</button>
          {smoke && <div className="repo-smoke-result" role="status">
            <strong>{smoke.verdict.replaceAll("-", " ")} · {smoke.tests_passed}/{smoke.tests_total} checks</strong>
            <p>{smoke.notice}</p>
            {smoke.checks.map(c => <p key={c.case}>Case {c.case}: {c.status.replaceAll("_", " ")}</p>)}
          </div>}
          <div className="repo-evidence-list">
            <h4>Recorded user-defined smoke checks</h4>
            {evidence?.smoke_checks.length === 0 && <p className="fineprint">No execution evidence recorded.</p>}
            {evidence?.smoke_checks.slice(0, 5).map(x => <div key={x.id}>
              <strong>{x.path} · {x.verdict.replaceAll("-", " ")}</strong>
              <p>{x.cases_passed}/{x.cases_total} cases · not graded in SkillGraph</p>
            </div>)}
          </div>
        </div>
      </div>
      <div className="repo-box">
        <h3>4. Files and tests detected in the limited source snapshot</h3>
        <p className="fineprint">These are repository path observations, not claims that any test ran, passed, or covered a particular behavior.</p>
        {snapshot.inventory.test_file_paths.length === 0 && <p className="fineprint">No familiar test filename was found within the eligible file list.</p>}
        <div className="repo-file-list">
          {snapshot.inventory.test_file_paths.slice(0, 16).map(path => <code key={path}>{path}</code>)}
        </div>
        {snapshot.inventory.failed_paths.length > 0 && <p className="fineprint">{snapshot.inventory.failed_paths.length} eligible files could not be decoded and were not inspected.</p>}
      </div>
    </>}
    <div className="repo-footer">
      <p className="fineprint">Read-only GitHub access requires a public repository and available GitHub API quota. Results can be incomplete for large, binary, private or unsupported repositories. All saved observations remain on the local device.</p>
      <button className="secondary-button" disabled={Boolean(busy)} onClick={clear}>
        Delete all local GitHub-review data
      </button>
    </div>
  </section>;
}
