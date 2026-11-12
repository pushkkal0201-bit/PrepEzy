"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_PREPEZY_API_URL || "http://localhost:8000";

type Focus = "balanced" | "coding" | "project";
type Probe = "edge_cases" | "tradeoffs" | "verification";
type Evidence = {
  type: string; ref: string; verified_test_result: boolean;
  source_url?: string; commit_sha?: string; repository?: string;
};
type Question = {
  id: string; kind: string; question: string; evidence: Evidence[];
  is_followup?: boolean; parent_id?: string; probe?: string;
  priority_skill?: string; graded: false;
  response?: { answer: string; probe: string; created_at: string } | null;
};
type Session = {
  id: string; focus: Focus; status: "active" | "completed" | "stopped";
  target_role: string; created_at: string; answered: number; total: number;
  next_question: Question | null; questions: Question[];
  report: { answered: number; total: number; completion: string;
    next_practice: { area: string; activity: string }[]; assessment: string } | null;
  notice: string;
};
type History = { sessions: {
  id: string; focus: Focus; status: string; target_role: string; created_at: string;
}[] };
type RepoHistory = { snapshots: {
  id: number; repository: string; commit_sha: string; created_at: string;
}[] };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(API + path, init);
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : "Interview API HTTP " + r.status);
  }
  return r.json() as Promise<T>;
}

const headers = { "Content-Type": "application/json" };

export default function MockInterviewStudio() {
  const [focus, setFocus] = useState<Focus>("balanced");
  const [snapshotId, setSnapshotId] = useState<string>("");
  const [repos, setRepos] = useState<RepoHistory>({ snapshots: [] });
  const [history, setHistory] = useState<History>({ sessions: [] });
  const [session, setSession] = useState<Session | null>(null);
  const [answer, setAnswer] = useState("");
  const [probe, setProbe] = useState<Probe>("edge_cases");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function refresh() {
    const list = await request<History>("/api/local/mock-interviews");
    setHistory(list);
    return list;
  }

  useEffect(() => {
    let active = true;
    Promise.all([
      request<History>("/api/local/mock-interviews"),
      request<RepoHistory>("/api/local/repositories/history"),
    ]).then(async ([saved, snapshots]) => {
      if (!active) return;
      setHistory(saved); setRepos(snapshots);
      if (saved.sessions.length) {
        const current = await request<Session>("/api/local/mock-interviews/" + saved.sessions[0].id);
        if (active) setSession(current);
      }
    }).catch(e => { if (active) setError(String(e)); });
    return () => { active = false; };
  }, []);

  async function run(task: () => Promise<void>) {
    setBusy(true); setError(""); setNotice("");
    try { await task(); }
    catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  async function start() {
    await run(async () => {
      const payload: { focus: Focus; snapshot_id?: number } = { focus };
      if (snapshotId) payload.snapshot_id = Number(snapshotId);
      const created = await request<Session>("/api/local/mock-interviews", {
        method: "POST", headers, body: JSON.stringify(payload),
      });
      setSession(created); setAnswer(""); setProbe("edge_cases");
      await refresh();
      setNotice("Local mock interview created. The questions are not auto-graded.");
    });
  }

  async function submit() {
    const next = session?.next_question;
    if (!session || !next || answer.trim().length < 30) return;
    await run(async () => {
      const updated = await request<Session>(
        "/api/local/mock-interviews/" + session.id + "/responses",
        { method: "POST", headers, body: JSON.stringify({
          question_id: next.id, response: answer.trim(), probe,
        }) },
      );
      setSession(updated); setAnswer(""); setProbe("edge_cases");
      await refresh();
      if (updated.status === "completed")
        setNotice("Interview completed. Review your transcript and practice suggestions below.");
    });
  }

  async function finish() {
    if (!session) return;
    await run(async () => {
      const updated = await request<Session>("/api/local/mock-interviews/" + session.id + "/finish", {
        method: "POST",
      });
      setSession(updated);
      await refresh();
      setNotice("Session saved as " + updated.status + ".");
    });
  }

  async function reopen(id: string) {
    await run(async () => {
      setSession(await request<Session>("/api/local/mock-interviews/" + id));
      setAnswer("");
    });
  }

  async function clear() {
    if (!window.confirm("Delete all saved local mock interview prompts and answers?")) return;
    await run(async () => {
      await request("/api/local/mock-interviews", { method: "DELETE" });
      setSession(null); setHistory({ sessions: [] }); setAnswer("");
      setNotice("Local mock interview transcripts deleted.");
    });
  }

  return <section className="panel mock-studio">
    <p className="eyebrow">STAGE 13 · ADAPTIVE MOCK INTERVIEW ORCHESTRATOR</p>
    <h2>Interview rehearsal grounded in your work</h2>
    <p className="sub">Practice coding explanations, a SkillGraph priority, project-defense reasoning
      and a role scenario in one persistent session. Follow-up topics are your choice; no LLM
      grades responses or makes hiring predictions.</p>

    <div className="mock-setup">
      <label htmlFor="mock-focus">Interview focus</label>
      <select id="mock-focus" value={focus} onChange={e => setFocus(e.target.value as Focus)}>
        <option value="balanced">Balanced technical mock</option>
        <option value="coding">Coding and problem solving first</option>
        <option value="project">Project defense first</option>
      </select>
      <label htmlFor="mock-repo-snapshot">Pinned GitHub snapshot (optional)</label>
      <select id="mock-repo-snapshot" value={snapshotId} onChange={e => setSnapshotId(e.target.value)}>
        <option value="">Most recent inspection, if available</option>
        {repos.snapshots.map(s => <option key={s.id} value={String(s.id)}>
          {s.repository} · {s.commit_sha.slice(0, 9)}
        </option>)}
      </select>
      <button type="button" onClick={start} disabled={busy}>Start new interview</button>
    </div>

    {error && <p className="error" role="alert">{error}</p>}
    {notice && <p className="feedback" role="status">{notice}</p>}

    {session && <div className="mock-session">
      <div className="mock-progress">
        <strong>{session.target_role} · {session.status.replaceAll("_", " ")}</strong>
        <span>{session.answered}/{session.total} responses saved</span>
      </div>
      <div className="track" role="progressbar" aria-label="Interview progress"
        aria-valuemin={0} aria-valuemax={session.total} aria-valuenow={session.answered}>
        <div className="fill" style={{ width: (100 * session.answered / Math.max(1, session.total)) + "%" }} />
      </div>

      {session.next_question && <div className="mock-current">
        <p className="eyebrow">{session.next_question.kind.toUpperCase()}
          {session.next_question.is_followup ? " · FOLLOW-UP" : " · PRIMARY QUESTION"}</p>
        <h3>{session.next_question.question}</h3>
        {session.next_question.evidence.map((ev, i) => <div key={i} className="mock-evidence">
          <strong>{ev.type.replaceAll("_", " ")}</strong>
          <small>{ev.ref} · {ev.verified_test_result ? "Checked source result" : "Context only; not scored"}</small>
          {ev.source_url && <a href={ev.source_url} target="_blank" rel="noopener noreferrer">
            Open commit-pinned source
          </a>}
        </div>)}
        {!session.next_question.evidence.length && <p className="fineprint">
          No verified underlying result is linked to this question.
        </p>}
        <label htmlFor="mock-answer">Your reasoning (30–2000 characters)</label>
        <textarea id="mock-answer" rows={6} maxLength={2000} value={answer}
          onChange={e => setAnswer(e.target.value)}
          placeholder="Explain your assumptions, alternatives, and what evidence would support your conclusion." />
        {!session.next_question.is_followup && session.next_question.kind !== "reflection" && <>
          <label htmlFor="mock-probe">Choose what the interviewer asks next</label>
          <select id="mock-probe" value={probe} onChange={e => setProbe(e.target.value as Probe)}>
            <option value="edge_cases">Boundary cases and failure modes</option>
            <option value="tradeoffs">Alternatives and trade-offs</option>
            <option value="verification">Evidence and verification</option>
          </select>
        </>}
        <div className="interview-actions">
          <button type="button" disabled={busy || answer.trim().length < 30} onClick={submit}>
            Save answer and continue
          </button>
          <button type="button" className="secondary-button" disabled={busy} onClick={finish}>
            End interview early
          </button>
        </div>
      </div>}

      {session.report && <div className="mock-report">
        <h3>Interview reflection</h3>
        <p><strong>{session.report.answered}/{session.report.total}</strong> questions answered ·
          {session.report.completion === "all_questions_answered" ? " Complete" : " Stopped early"}</p>
        <p className="fineprint">{session.report.assessment}</p>
        <h4>Suggested next practice</h4>
        {session.report.next_practice.map(x =>
          <p key={x.area}><strong>{x.area}:</strong> {x.activity}</p>)}
      </div>}
      <details className="mock-transcript">
        <summary>Saved questions and answers ({session.answered})</summary>
        {session.questions.map(q => <div key={q.id}>
          <strong>{q.kind} · {q.id}</strong>
          <p>{q.question}</p>
          <p className="mock-saved-answer">{q.response?.answer || "Not answered"}</p>
        </div>)}
      </details>
      <p className="fineprint">{session.notice}</p>
    </div>}

    {!!history.sessions.length && <div className="mock-history">
      <h3>Saved interviews</h3>
      {history.sessions.map(s => <div key={s.id}>
        <span>{s.focus} · {s.target_role} · {s.status} · {s.created_at}</span>
        <button type="button" className="secondary-button" disabled={busy}
          onClick={() => reopen(s.id)}>Open</button>
      </div>)}
      <button type="button" className="secondary-button" disabled={busy} onClick={clear}>
        Delete all local interviews
      </button>
    </div>}
  </section>;
}
