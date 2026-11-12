"use client";

import { useEffect, useMemo, useState } from "react";

const API = process.env.NEXT_PUBLIC_PREPEZY_API_URL || "http://localhost:8000";
type Language = "python" | "java" | "javascript";
type Problem = {
  id: string; title: string; topic: string; difficulty: string; statement: string;
  public_examples: { input: string; output: string }[]; test_count: number;
};
type Catalogue = { problems: Problem[]; languages: Language[]; starters: Record<Language, string>; limitations: string };
type Session = { id: string; mode: string; status: string; deadline: number; seconds_remaining: number; created_at: number };
type Status = { availability: { ready: Record<Language, boolean>; requires: string; execution: string }; session: Session | null };
type Check = { case: number; status: string; feedback?: string };
type Verdict = {
  problem_id: string; language: string; verdict: string; tests_passed: number; tests_total: number;
  checks: Check[]; notice: string;
};
type History = { id: number; problem_id: string; language: string; verdict: string; created_at: string }[];

async function request(url: string, options?: RequestInit) {
  const response = await fetch(API + url, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : "The coding judge returned status " + response.status);
  }
  return response.json();
}

export default function CodingArena({ onEvidence }: { onEvidence: () => void }) {
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [history, setHistory] = useState<History>([]);
  const [mode, setMode] = useState<"timed" | "practice">("timed");
  const [minutes, setMinutes] = useState(30);
  const [problemId, setProblemId] = useState("sum-pair");
  const [language, setLanguage] = useState<Language>("python");
  const [source, setSource] = useState("");
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);

  async function refresh() {
    const [s, h]: [Status, { attempts: History }] = await Promise.all([
      request("/api/local/arena/status"),
      request("/api/local/arena/evidence"),
    ]);
    setStatus(s);
    setHistory(h.attempts);
  }

  useEffect(() => {
    let active = true;
    Promise.all([
      request("/api/local/arena/problems"),
      request("/api/local/arena/status"),
      request("/api/local/arena/evidence"),
    ]).then(([c, s, h]) => {
      if (!active) return;
      setCatalogue(c);
      setSource(c.starters.python);
      setStatus(s);
      setHistory(h.attempts);
      setLoaded(true);
    }).catch(e => { if (active) { setError(String(e)); setLoaded(true); } });
    return () => { active = false; };
  }, []);

  const session = status?.session;
  useEffect(() => {
    function update() {
      setSecondsLeft(session?.status === "active" ?
        Math.max(0, session.deadline - Math.floor(Date.now() / 1000)) : 0);
    }
    update();
    const interval = window.setInterval(update, 1000);
    return () => window.clearInterval(interval);
  }, [session?.deadline, session?.status]);

  const languages = catalogue?.languages || [];
  const selected = useMemo(() => catalogue?.problems.find(p => p.id === problemId), [catalogue, problemId]);
  const enabled = Boolean(status?.availability.ready[language]);
  const anyReady = Boolean(status && Object.values(status.availability.ready).some(Boolean));
  const isActive = Boolean(session?.status === "active" && secondsLeft > 0);
  const remaining = String(Math.floor(secondsLeft / 60)).padStart(2, "0") +
    ":" + String(secondsLeft % 60).padStart(2, "0");

  function chooseLanguage(value: Language) {
    setLanguage(value);
    setSource(catalogue?.starters[value] || "");
    setVerdict(null);
  }

  async function start() {
    setBusy("start"); setError("");
    try {
      await request("/api/local/arena/sessions", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode, duration_minutes: minutes }),
      });
      await refresh();
    } catch (e) { setError(String(e)); } finally { setBusy(""); }
  }

  async function finish() {
    if (!session) return;
    setBusy("finish"); setError("");
    try {
      await request("/api/local/arena/sessions/" + session.id + "/finish", { method: "POST" });
      await refresh();
    } catch (e) { setError(String(e)); } finally { setBusy(""); }
  }

  async function submit() {
    if (!isActive || !session || !enabled) return;
    setBusy("submit"); setVerdict(null); setError("");
    try {
      const data = await request("/api/local/arena/submissions", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: session.id, problem_id: problemId, language, source }),
      });
      setVerdict(data.result);
      await refresh();
      onEvidence();
    } catch (e) { setError(String(e)); } finally { setBusy(""); }
  }

  return <section className="panel coding-arena" aria-label="Docker coding assessment">
    <p className="eyebrow">STAGE 7 · REAL JAVA / PYTHON / JAVASCRIPT EXECUTION</p>
    <h2>Coding Arena</h2>
    <p className="sub">Write, compile and test complete programs using an isolated Docker container. Choose a timed assessment or a longer practice session. Tests are deterministic and results are recorded in the same local SkillGraph.</p>
    {!loaded && <p role="status">Checking the local Docker judge…</p>}
    {status && <div className="judge-status" aria-label="Available language images">
      {languages.map(name => <span className={"judge-pill " + (status.availability.ready[name] ? "ready" : "missing")} key={name}>
        {name}: {status.availability.ready[name] ? "ready" : "image missing"}
      </span>)}
    </div>}
    {!anyReady && loaded && <div className="judge-setup">
      <strong>Docker setup required</strong>
      <p>Install and start Docker Desktop in Linux-container mode, then pull the Python, JavaScript and Java images shown in the project documentation. The runner never falls back to running submissions on your host.</p>
      <code>docker pull python:3.11-alpine</code>
      <code>docker pull node:22-alpine</code>
      <code>docker pull eclipse-temurin:21-jdk-alpine</code>
      <button className="secondary-button" disabled={Boolean(busy)} onClick={() => refresh().catch(e => setError(String(e)))}>Recheck Docker</button>
    </div>}

    <div className="arena-session">
      {session?.status === "active" ? <>
        <div><strong>{session.mode === "timed" ? "Timed assessment" : "Practice session"} active</strong>
          <p className="sub">Time remaining: <span className="arena-timer">{remaining}</span></p>
        </div>
        <button className="secondary-button" disabled={Boolean(busy)} onClick={finish}>Finish session</button>
      </> : <>
        <label>Mode<select value={mode} onChange={e => setMode(e.target.value as "timed" | "practice")}>
          <option value="timed">Timed assessment</option><option value="practice">Long-form practice (up to 4 hours)</option>
        </select></label>
        {mode === "timed" && <label>Duration<select value={minutes} onChange={e => setMinutes(Number(e.target.value))}>
          {[15,30,45,60].map(n => <option key={n} value={n}>{n} minutes</option>)}
        </select></label>}
        <button disabled={!anyReady || Boolean(busy)} onClick={start}>{busy === "start" ? "Starting…" : "Start coding session"}</button>
      </>}
    </div>

    <div className="arena-grid">
      <div>
        <label htmlFor="arena-problem">Coding problem</label>
        <select id="arena-problem" value={problemId} onChange={e => { setProblemId(e.target.value); setVerdict(null); }}>
          {catalogue?.problems.map(p => <option key={p.id} value={p.id}>{p.title} ({p.difficulty})</option>)}
        </select>
        <p className="prompt">{selected?.statement}</p>
        <details className="local-schema"><summary>Public examples · {selected?.test_count ?? 0} total tests</summary>
          {selected?.public_examples.map((item, i) => <div key={i}>
            <p><strong>Input:</strong> <code>{item.input}</code></p>
            <p><strong>Expected:</strong> <code>{item.output}</code></p>
          </div>)}
        </details>
        <label htmlFor="arena-language">Programming language</label>
        <select id="arena-language" value={language} onChange={e => chooseLanguage(e.target.value as Language)}>
          {languages.map(l => <option key={l} value={l}>{l === "javascript" ? "JavaScript" : l === "java" ? "Java" : "Python"} {status?.availability.ready[l] ? "· available" : "· Docker image needed"}</option>)}
        </select>
        <p className="fineprint">Use stdin to read input and stdout to print the result. Java requires a public class named Main.</p>
      </div>
      <div>
        <label htmlFor="arena-editor">Your solution</label>
        <textarea id="arena-editor" className="arena-editor" rows={14} spellCheck={false}
          value={source} maxLength={12000} onChange={e => setSource(e.target.value)} />
        <button disabled={!isActive || !enabled || Boolean(busy) || source.trim().length < 12} onClick={submit}>
          {busy === "submit" ? "Executing isolated tests…" : "Run & submit"}
        </button>
        {!isActive && <p className="fineprint">Start a session above to unlock submissions.</p>}
        {error && <p className="error" role="alert">{error}</p>}
        {verdict && <div className="local-result" role="status">
          <h4>{verdict.verdict.replaceAll("_", " ").toUpperCase()} · {verdict.tests_passed}/{verdict.tests_total} tests passed</h4>
          <div className="judge-results">{verdict.checks.map(c => <span key={c.case} className={"judge-pill " + (c.status === "accepted" ? "ready" : "missing")}>
            Case {c.case}: {c.status.replaceAll("_", " ")}
          </span>)}</div>
          {verdict.checks.map(c => c.feedback && <p key={c.case} className="fineprint">Case {c.case}: {c.feedback}</p>)}
          <p className="fineprint">{verdict.notice}</p>
        </div>}
      </div>
    </div>
    <div className="arena-history">
      <h3>Recent locally graded submissions</h3>
      {history.length === 0 && <p className="sub">No coding submissions yet.</p>}
      {history.slice(0, 8).map(a => <div key={a.id} className="arena-history-row">
        <strong>{a.problem_id}</strong><span>{a.language}</span><span>{a.verdict.replaceAll("_", " ")}</span>
        <small>{a.created_at}</small>
      </div>)}
    </div>
    <p className="fineprint">This is a Docker-contained educational runner, not a certified secure multi-tenant sandbox. Keep the unauthenticated API bound to 127.0.0.1; never expose Docker-backed code execution to the internet.</p>
  </section>;
}
