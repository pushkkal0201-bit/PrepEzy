"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_PREPEZY_API_URL || "http://localhost:8000";
type Question = { id: string; skill: string; prompt: string; options: Record<string, string> };
type Competency = { id: string; name: string; attempts: number; correct: number; practice_accuracy: number | null; mastery_estimate: number | null; priority: number; status: string };
type Snapshot = { id: string; target_role: string; synthetic_demo: boolean; total_attempts: number; competencies: Competency[]; recommendation: { skill: string; action: string; reason: string }; limitations: string };

type AuralisInterview = {
  id: string;
  status: string;
  provider: string;
  role: string;
  current: { id: string; text: string; source?: string; difficulty?: string } | null;
  answer_count: number;
  answers: { id: string; question: string; text: string }[];
  report: { summary: string; scored: boolean; demo: boolean; limitations: string[]; items: { name: string; status: string; score: number | null; feedback: string; evidence_count: number }[] } | null;
  notice: string;
};
type AuralisChallenge = { id: string; title: string; description: string; starter: string; hint: string };
type CodeGrade = { challenge_id: string; passed: number; total: number; all_passed: boolean; source: string; limitations: string; tests: { test: number; public: boolean; status: string }[] };
type AuralisStatus = { enabled: boolean; connected: boolean; message?: string; upstream_version?: string };
type InterviewHistory = { id: string; status: string; answer_count: number }[];
type Roadmap = { minutes_budget: number; minutes_planned: number; activities: { skill: string; title: string; type: string; minutes: number; why: string }[]; limitations: string };

export default function Home() {
  const [learner, setLearner] = useState("demo-backend");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [questionId, setQuestionId] = useState("dsa-1");
  const [choice, setChoice] = useState("");
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [auralisStatus, setAuralisStatus] = useState<AuralisStatus | null>(null);
  const [interview, setInterview] = useState<AuralisInterview | null>(null);
  const [interviewHistory, setInterviewHistory] = useState<InterviewHistory>([]);
  const [interviewText, setInterviewText] = useState("");
  const [interviewError, setInterviewError] = useState("");
  const [interviewBusy, setInterviewBusy] = useState(false);
  const [challenges, setChallenges] = useState<AuralisChallenge[]>([]);
  const [selectedChallenge, setSelectedChallenge] = useState("");
  const [codeSource, setCodeSource] = useState("");
  const [codeGrade, setCodeGrade] = useState<CodeGrade | null>(null);
  const [codeBusy, setCodeBusy] = useState(false);
  const [codeError, setCodeError] = useState("");
  useEffect(() => {
    let active = true;
    setError("");
    Promise.all([
      fetch(API + "/api/demo/questions").then(r => { if (!r.ok) throw Error("Cannot load questions"); return r.json(); }),
      fetch(API + "/api/demo/learners/" + learner).then(r => { if (!r.ok) throw Error("Cannot load learner"); return r.json(); })
    ]).then(([q, s]) => { if (active) { setQuestions(q); setSnapshot(s); } }).catch(e => { if (active) setError(String(e)); });
    return () => { active = false; };
  }, [learner]);
  useEffect(() => {
    let active = true;
    fetch(API + "/api/demo/learners/" + learner + "/roadmap")
      .then(r => { if (!r.ok) throw Error("Cannot load roadmap"); return r.json(); })
      .then(r => { if (active) setRoadmap(r); })
      .catch(e => { if (active) setError(String(e)); });
    return () => { active = false; };
  }, [learner, snapshot?.total_attempts, refresh]);

  useEffect(() => {
    let active = true;
    setInterview(null);
    setInterviewText("");
    setInterviewError("");
    Promise.all([
      fetch(API + "/api/demo/integrations/auralis").then(r => r.json()),
      fetch(API + "/api/demo/learners/" + learner + "/interviews").then(r => r.json()),
    ]).then(([status, history]) => {
      if (active) {
        setAuralisStatus(status);
        setInterviewHistory(history.interviews || []);
      }
    }).catch(e => { if (active) setInterviewError(String(e)); });
    return () => { active = false; };
  }, [learner, refresh]);

  async function practiceNext() {
    setError("");
    try {
      const response = await fetch(API + "/api/demo/learners/" + learner + "/next-question");
      if (!response.ok) throw Error("Could not load a recommended question");
      const suggested = await response.json();
      setQuestionId(suggested.question.id);
      setChoice("");
      setFeedback("Selected because: " + suggested.reason);
    } catch (e) { setError(String(e)); }
  }
  useEffect(() => {
    let active = true;
    setCodeGrade(null);
    setCodeError("");
    if (!auralisStatus?.connected) {
      setChallenges([]);
      setSelectedChallenge("");
      setCodeSource("");
      return;
    }
    fetch(API + "/api/demo/integrations/auralis/challenges?learner_id=" + learner)
      .then(r => { if (!r.ok) throw Error("Auralis coding catalog unavailable"); return r.json(); })
      .then(data => {
        if (!active) return;
        const list: AuralisChallenge[] = data.challenges || [];
        setChallenges(list);
        setSelectedChallenge(list[0]?.id || "");
        setCodeSource(list[0]?.starter || "");
      }).catch(e => { if (active) setCodeError(String(e)); });
    return () => { active = false; };
  }, [auralisStatus?.connected, learner]);

  async function runAuralisCode() {
    if (!selectedChallenge || !codeSource.trim()) return;
    setCodeBusy(true);
    setCodeError("");
    try {
      const response = await fetch(API + "/api/demo/learners/" + learner + "/code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ challenge_id: selectedChallenge, code: codeSource }),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => null);
        throw Error(err?.detail || "Auralis rejected this restricted exercise");
      }
      const graded = await response.json();
      setCodeGrade(graded.result);
      setSnapshot(graded.learner);
      setRefresh(x => x + 1);
    } catch (e) {
      setCodeError(String(e));
    } finally { setCodeBusy(false); }
  }

  async function interviewAction(kind: "start" | "answer" | "finish" | "resume") {
    setInterviewBusy(true);
    setInterviewError("");
    try {
      const urlBase = API + "/api/demo/learners/" + learner + "/interviews";
      const url = kind === "start" ? urlBase
        : kind === "resume" ? urlBase + "/" + interviewHistory[0].id
        : urlBase + "/" + interview?.id + "/" + (kind === "finish" ? "finish" : "answer");
      const options: RequestInit = kind === "resume" ? {} : {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        ...(kind === "answer" ? { body: JSON.stringify({
          question_id: interview?.current?.id,
          text: interviewText,
        }) } : {}),
      };
      const response = await fetch(url, options);
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw Error(detail?.detail || "Auralis action failed (HTTP " + response.status + ")");
      }
      const data: AuralisInterview = await response.json();
      setInterview(data);
      setInterviewText("");
      if (kind === "finish") setRefresh(r => r + 1);
    } catch (e) {
      setInterviewError(String(e));
    } finally {
      setInterviewBusy(false);
    }
  }
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
        <h2>2. Complete a knowledge check</h2><button className="secondary-button" onClick={practiceNext}>Choose PrepLoop's next question</button><label htmlFor="question">Choose a question</label><select id="question" value={questionId} onChange={e => { setQuestionId(e.target.value); setChoice(""); setFeedback(""); }}>{questions.map(q => <option key={q.id} value={q.id}>{q.skill.toUpperCase()} · {q.id}</option>)}</select><p className="prompt">{current?.prompt || "Loading questions..."}</p><fieldset><legend>Answer</legend>{current && Object.entries(current.options).map(([id, name]) => <label className="option" key={id}><input type="radio" name="answer" value={id} checked={choice === id} onChange={() => setChoice(id)}/>{name}</label>)}</fieldset><button disabled={!choice || busy} onClick={submit}>{busy ? "Checking..." : "Submit answer"}</button>{feedback && <p className="feedback" role="status">{feedback}</p>}{error && <p className="error" role="alert">{error}. Start the local API on port 8000.</p>}</div>
      <div className="panel"><h2>Live SkillGraph</h2><p className="sub">{snapshot?.target_role || "Loading..."} · {snapshot?.total_attempts ?? 0} server-graded attempts</p><div className="skills">{snapshot?.competencies.map(s => <div className="skill" key={s.id}><div className="skill-line"><strong>{s.name}</strong><span>{s.attempts ? String(Math.round((s.practice_accuracy || 0) * 100)) + "% practice accuracy" : "Unassessed"}</span></div><div className="track"><div className="fill" style={{ width: (s.practice_accuracy || 0) * 100 + "%" }}/></div></div>)}</div><div className="recommend"><span className="eyebrow">PREPLOOP RECOMMENDS</span><h3>{top?.name || "Loading..."}</h3><p>{snapshot?.recommendation.reason}</p><small>{snapshot?.recommendation.action}</small></div><p className="fineprint">{snapshot?.limitations}</p></div>
    </section><section className="panel roadmap-panel"><h2>Your adaptive learning roadmap</h2><p className="sub">Prepared from server-graded evidence and role relevance. No account or authentication required for these synthetic profiles.</p><div className="roadmap-grid">{roadmap?.activities.map((activity, i) => <article className="roadmap-step" key={activity.skill}><span className="eyebrow">STEP {i + 1} · {activity.minutes} MIN · {activity.type.toUpperCase().replaceAll("-", " ")}</span><h3>{activity.title}</h3><p>{activity.why}</p></article>)}</div><p className="fineprint">Total: {roadmap?.minutes_planned ?? 0} / {roadmap?.minutes_budget ?? 45} minutes planned. {roadmap?.limitations}</p></section><section className="panel interview-panel">
      <div className="interview-heading"><div><p className="eyebrow">AURALIS · LIVE LOCAL CONNECTOR</p><h2>Interview practice</h2><p className="sub">Real Auralis session state and recorded answers, not generated placeholder questions. Its scripted demo does not score proficiency.</p></div>
      <span className={"status-pill " + (auralisStatus?.connected ? "connected" : "")}>{auralisStatus?.connected ? "Local Auralis connected" : "Not connected"}</span></div>
      {auralisStatus?.message && <p className="sub">{auralisStatus.message}</p>}
      {!auralisStatus?.connected && <p className="sub">Optional: start Auralis locally on port 8001 and set PREPEZY_AURALIS_ENABLED=1 for the PrepEzy API. No authentication is required for these synthetic demo profiles.</p>}
      <div className="interview-actions">
        <button disabled={!auralisStatus?.connected || interviewBusy} onClick={() => interviewAction("start")}>{interviewBusy ? "Working..." : "Start scripted Auralis interview"}</button>
        <button className="secondary-button" disabled={!auralisStatus?.connected || interviewBusy || interviewHistory.length === 0} onClick={() => interviewAction("resume")}>Open latest recorded interview</button>
      </div>
      {interview && <div className="interview-session">
        <p className="sub">Session {interview.id.slice(0, 16)}… · {interview.status} · {interview.answer_count} recorded answer(s)</p>
        {interview.status === "active" && interview.current && <>
          <p className="eyebrow">CURRENT AURALIS QUESTION · {interview.current.source || "source not specified"}</p>
          <h3>{interview.current.text}</h3>
          <label htmlFor="auralis-answer">Your answer (synthetic/local practice only)</label>
          <textarea id="auralis-answer" rows={5} maxLength={8000} value={interviewText} onChange={e => setInterviewText(e.target.value)} placeholder="Explain your approach, assumptions and how you would test it."/>
          <div className="interview-actions">
            <button disabled={interviewBusy || !interviewText.trim()} onClick={() => interviewAction("answer")}>Record answer and continue</button>
            <button className="secondary-button" disabled={interviewBusy} onClick={() => interviewAction("finish")}>Finish and view report</button>
          </div>
        </>}
        {interview.report && <div className="interview-report">
          <p className="eyebrow">UPSTREAM REPORT · {interview.report.scored ? "SCORED" : "UNSCORED"}</p>
          <h3>{interview.report.summary}</h3>
          {interview.report.items.map((item, index) => <div className="interview-report-item" key={index}>
            <strong>{item.name} · {item.status.replaceAll("_", " ")}</strong>
            <p>{item.feedback}</p>
          </div>)}
          <p className="fineprint">{interview.notice}</p>
        </div>}
      </div>}
      {interviewError && <p className="error" role="alert">{interviewError}</p>}
    </section><section className="panel practical-panel">
      <p className="eyebrow">REAL AURALIS RESTRICTED TEST RUNNER</p>
      <h2>Adaptive coding lab</h2>
      <p className="sub">When local Auralis is connected, it evaluates a constrained Python return expression against real public and hidden tests. Results become independent evidence for the Python skill, without executing arbitrary Python.</p>
      {!auralisStatus?.connected && <p className="sub">Start the optional local Auralis service to unlock verified coding exercises.</p>}
      {auralisStatus?.connected && <div className="practical-form">
        <label htmlFor="auralis-challenge">Challenge</label>
        <select id="auralis-challenge" value={selectedChallenge} onChange={e => {
          setSelectedChallenge(e.target.value);
          setCodeSource(challenges.find(c => c.id === e.target.value)?.starter || "");
          setCodeGrade(null);
        }}>
          {challenges.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
        </select>
        <p>{challenges.find(c => c.id === selectedChallenge)?.description}</p>
        <label htmlFor="auralis-source">Restricted Python solution</label>
        <textarea id="auralis-source" rows={6} maxLength={2500} spellCheck={false} value={codeSource} onChange={e => setCodeSource(e.target.value)} />
        <div className="interview-actions"><button disabled={codeBusy || !selectedChallenge || !codeSource.trim()} onClick={runAuralisCode}>{codeBusy ? "Checking..." : "Run Auralis test cases"}</button></div>
        {codeGrade && <div className="code-results" role="status">
          <strong>{codeGrade.passed} / {codeGrade.total} tests passed</strong>
          <p>{codeGrade.all_passed ? "All fixed challenge tests passed." : "Some fixed challenge tests did not pass."}</p>
          <div className="code-test-list">{codeGrade.tests.map(t => <span key={t.test} className={"test-pill " + (t.status === "pass" ? "passed" : "failed")}>Test {t.test}: {t.status}{t.public ? " · public" : " · hidden"}</span>)}</div>
          <p className="fineprint">{codeGrade.limitations}</p>
        </div>}
        {codeError && <p className="error" role="alert">{codeError}</p>}
      </div>}
    </section><footer>Local synthetic prototype only · No real accounts, real student data or public deployment. Auralis scripted interviews are unscored; its restricted coding tests are independently graded.</footer>
  </main>;
}
