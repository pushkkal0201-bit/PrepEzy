"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_PREPEZY_API_URL || "http://localhost:8000";
type Question = { id: string; skill: string; prompt: string; options: Record<string, string> };
type Competency = { id: string; name: string; attempts: number; correct: number; practice_accuracy: number | null; mastery_estimate: number | null; priority: number; status: string };
type Snapshot = { id: string; target_role: string; synthetic_demo: boolean; total_attempts: number; competencies: Competency[]; recommendation: { skill: string; action: string; reason: string }; limitations: string };

export default function Home() {
  const [learner, setLearner] = useState("demo-backend");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [questionId, setQuestionId] = useState("dsa-1");
  const [choice, setChoice] = useState("");
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    setError("");
    Promise.all([
      fetch(API + "/api/demo/questions").then(r => { if (!r.ok) throw Error("Cannot load questions"); return r.json(); }),
      fetch(API + "/api/demo/learners/" + learner).then(r => { if (!r.ok) throw Error("Cannot load learner"); return r.json(); })
    ]).then(([q, s]) => { if (active) { setQuestions(q); setSnapshot(s); } }).catch(e => { if (active) setError(String(e)); });
    return () => { active = false; };
  }, [learner]);
  const current = questions.find(q => q.id === questionId);
  async function submit() {
    if (!choice || !current) return;
    setBusy(true); setError("");
    try {
      const response = await fetch(API + "/api/demo/attempts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ learner_id: learner, question_id: current.id, choice_id: choice }) });
      if (!response.ok) throw Error("Submission rejected: " + response.status);
      const data = await response.json();
      setSnapshot(data.learner);
      setFeedback((data.correct ? "Correct. " : "Not correct. ") + data.explanation);
      setChoice("");
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  const top = snapshot?.competencies.find(c => c.id === snapshot.recommendation.skill);
  return <main className="shell">
    <header className="top"><div className="brand">Prep<span>Ezy</span></div><span className="tag">Adaptive foundation · synthetic demo</span></header>
    <section className="hero"><p className="eyebrow">LEARN · PRACTICE · PROVE</p><h1>A different preparation journey for every student.</h1><p>These practice questions are graded by the API. Recommendations change when evidence changes—no AI-generated scores and no claims about hiring readiness.</p></section>
    <section className="layout">
      <div className="panel"><h2>1. Choose a demo learner</h2><label htmlFor="learner">Role-specific learning goals</label><select id="learner" value={learner} onChange={e => { setLearner(e.target.value); setFeedback(""); }}><option value="demo-backend">Demo A · Backend Engineer</option><option value="demo-ml">Demo B · ML Engineer</option></select>
        <h2>2. Complete a knowledge check</h2><label htmlFor="question">Choose a question</label><select id="question" value={questionId} onChange={e => { setQuestionId(e.target.value); setChoice(""); setFeedback(""); }}>{questions.map(q => <option key={q.id} value={q.id}>{q.skill.toUpperCase()} · {q.id}</option>)}</select><p className="prompt">{current?.prompt || "Loading questions..."}</p><fieldset><legend>Answer</legend>{current && Object.entries(current.options).map(([id, name]) => <label className="option" key={id}><input type="radio" name="answer" value={id} checked={choice === id} onChange={() => setChoice(id)}/>{name}</label>)}</fieldset><button disabled={!choice || busy} onClick={submit}>{busy ? "Checking..." : "Submit answer"}</button>{feedback && <p className="feedback" role="status">{feedback}</p>}{error && <p className="error" role="alert">{error}. Start the local API on port 8000.</p>}</div>
      <div className="panel"><h2>Live SkillGraph</h2><p className="sub">{snapshot?.target_role || "Loading..."} · {snapshot?.total_attempts ?? 0} server-graded attempts</p><div className="skills">{snapshot?.competencies.map(s => <div className="skill" key={s.id}><div className="skill-line"><strong>{s.name}</strong><span>{s.attempts ? String(Math.round((s.practice_accuracy || 0) * 100)) + "% practice accuracy" : "Unassessed"}</span></div><div className="track"><div className="fill" style={{ width: (s.practice_accuracy || 0) * 100 + "%" }}/></div></div>)}</div><div className="recommend"><span className="eyebrow">PREPLOOP RECOMMENDS</span><h3>{top?.name || "Loading..."}</h3><p>{snapshot?.recommendation.reason}</p><small>{snapshot?.recommendation.action}</small></div><p className="fineprint">{snapshot?.limitations}</p></div>
    </section><footer>Local prototype only · No real accounts, job applications or upstream AI execution are connected yet.</footer>
  </main>;
}
