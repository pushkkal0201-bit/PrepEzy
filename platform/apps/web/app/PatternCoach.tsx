"use client";

import { useCallback, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_PREPEZY_API_URL || "http://localhost:8000";
type PatternMeta = { id: string; name: string; signal: string; stages: number };
type Step = { id: string; phase: string; prompt: string; options: Record<string, string> };
type PatternState = {
  pattern_id: string; name: string; completed: boolean; completed_steps: number;
  total_steps: number; step: Step | null; attempts_on_step?: number; hint_used?: boolean;
  notice: string; pattern_card?: { signal: string; invariant: string; pitfalls: string[] };
};
type AnswerResponse = {
  result: { correct: boolean; feedback: string; hint_used: boolean; pattern: PatternState };
};

export default function PatternCoach({ learner, onEvidence, local = false }: { learner: string; onEvidence: () => void; local?: boolean }) {
  const route = local ? "/api/local/cracked" : "/api/demo/learners/" + learner + "/cracked";
  const [catalog, setCatalog] = useState<PatternMeta[]>([]);
  const [selected, setSelected] = useState("two-pointers");
  const [session, setSession] = useState<PatternState | null>(null);
  const [choice, setChoice] = useState("");
  const [hint, setHint] = useState("");
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    fetch(API + (local ? "/api/local/cracked/patterns" : "/api/demo/cracked/patterns"))
      .then(r => { if (!r.ok) throw Error("Pattern catalog unavailable"); return r.json(); })
      .then(data => setCatalog(data.patterns ?? []))
      .catch(e => setError(String(e)));
  }, [local]);

  const reload = useCallback(async () => {
    const res = await fetch(API + route + "/patterns/" + selected);
    if (!res.ok) throw Error("Could not load guided practice");
    setSession(await res.json());
  }, [route, selected]);

  useEffect(() => {
    let active = true;
    setSession(null); setChoice(""); setHint(""); setFeedback(""); setError("");
    reload().catch(e => { if (active) setError(String(e)); });
    return () => { active = false; };
  }, [reload, refresh]);

  async function requestHint() {
    if (!session?.step) return;
    setBusy(true); setError("");
    try {
      const res = await fetch(API + route + "/patterns/" + selected + "/hint", { method: "POST" });
      if (!res.ok) throw Error("Could not retrieve guided hint");
      const data = await res.json();
      setHint(data.hint);
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  async function answer() {
    if (!session?.step || !choice) return;
    setBusy(true); setError("");
    try {
      const res = await fetch(API + route + "/patterns/" + selected + "/answers", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ step_id: session.step.id, choice_id: choice }),
      });
      if (!res.ok) throw Error("The API rejected this answer (" + res.status + ")");
      const data: AnswerResponse = await res.json();
      setSession(data.result.pattern);
      setFeedback((data.result.correct ? "Correct. " : "Try again. ") + data.result.feedback);
      setChoice(""); setHint("");
      onEvidence();
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  return <section className="panel coach-panel">
    <p className="eyebrow">{local ? "LOCAL EVIDENCE · " : "SYNTHETIC DEMO · "}CRACKED PATTERN COACH</p>
    <h2>Learn the pattern, not the answer</h2>
    <p className="sub">Three guided checkpoints: establish a brute-force baseline, spot the wasted work and transfer the insight. Server-graded concept checks update {local ? "your local DSA evidence graph" : "the synthetic demo SkillGraph"}. No student code is executed.</p>
    <label htmlFor="pattern-topic">Choose DSA pattern</label>
    <select id="pattern-topic" value={selected} onChange={e => setSelected(e.target.value)}>
      {catalog.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
    </select>
    {session && <div className="coach-content">
      <p className="eyebrow">{session.completed ? "PATTERN COMPLETED" : "STEP " + (session.completed_steps + 1) + " OF " + session.total_steps + " · " + (session.step?.phase || "").replaceAll("-", " ").toUpperCase()}</p>
      {session.step && <>
        <h3>{session.step.prompt}</h3>
        <fieldset><legend>Choose your reasoning</legend>
          {Object.entries(session.step.options).map(([id, value]) => <label key={id} className="option">
            <input name="pattern-answer" type="radio" checked={choice === id} onChange={() => setChoice(id)}/>{value}
          </label>)}
        </fieldset>
        <div className="interview-actions">
          <button disabled={!choice || busy} onClick={answer}>{busy ? "Checking..." : "Check reasoning"}</button>
          <button className="secondary-button" disabled={busy} onClick={requestHint}>Request a hint</button>
        </div>
        {hint && <p className="coach-hint">Hint (recorded as assistance): {hint}</p>}
      </>}
      {session.pattern_card && <div className="recommend">
        <p className="eyebrow">YOUR PATTERN CARD</p>
        <h3>{session.name}</h3>
        <p><strong>When to use it:</strong> {session.pattern_card.signal}</p>
        <p><strong>Invariant:</strong> {session.pattern_card.invariant}</p>
        <p><strong>Pitfalls:</strong> {session.pattern_card.pitfalls.join("; ")}</p>
      </div>}
      {feedback && <p className="feedback" role="status">{feedback}</p>}
      <p className="fineprint">{session.notice}</p>
    </div>}
    {error && <p className="error" role="alert">{error}</p>}
  </section>;
}
