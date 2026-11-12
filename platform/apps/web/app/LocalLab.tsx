"use client";
import { useEffect, useState } from "react";
import UnifiedProgress from "./UnifiedProgress";

const API = process.env.NEXT_PUBLIC_PREPEZY_API_URL || "http://localhost:8000";
type Profile = { role: string; target_role: string; language: string; daily_minutes: number };
type Track = { id: string; assessed: number; correct_first_try: number; available: number };
type Overview = {
  profile: Profile; tracks: Track[];
  recommendation: { topic: string; type: string; reason: string };
  roadmap: { type: string; topic: string; minutes: number; why: string }[];
  recorded_sql_attempts: number; recorded_viva_attempts: number; evidence_note: string;
};
type SqlCatalog = { schema: string[]; active_definition: string; sample_employees: unknown[][];
  challenges: { id: string; title: string; topic: string; prompt: string }[] };
type VivaQ = { id: string; topic: string; prompt: string; options: Record<string, string> };
type SqlCheck = { fixture: number; passed: boolean; rows_returned?: number; actual_preview?: unknown[][]; expected_preview?: unknown[][]; error?: string };
type SqlResult = { passed: boolean; tests_passed: number; tests_total: number; checks: SqlCheck[]; notice: string };
type VivaResult = { correct: boolean; explanation: string };

async function request(path: string, options?: RequestInit) {
  const r = await fetch(API + path, options);
  if (!r.ok) {
    const error = await r.json().catch(() => ({}));
    throw new Error(error.detail || "API request failed with status " + r.status);
  }
  return r.json();
}
const jsonHeaders = { "Content-Type": "application/json" };

export default function LocalLab() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [catalog, setCatalog] = useState<SqlCatalog | null>(null);
  const [questions, setQuestions] = useState<VivaQ[]>([]);
  const [role, setRole] = useState("backend");
  const [language, setLanguage] = useState("Java");
  const [minutes, setMinutes] = useState(45);
  const [taskId, setTaskId] = useState("joins");
  const [sql, setSql] = useState("SELECT e.name AS employee, d.name AS department\nFROM employees e JOIN departments d ON e.department_id=d.id\nWHERE e.active=1");
  const [sqlGrade, setSqlGrade] = useState<SqlResult | null>(null);
  const [topic, setTopic] = useState("dbms");
  const [questionId, setQuestionId] = useState("dbms-atomicity");
  const [answer, setAnswer] = useState("");
  const [vivaGrade, setVivaGrade] = useState<VivaResult | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [evidenceRefresh, setEvidenceRefresh] = useState(0);

  useEffect(() => {
    let active = true;
    Promise.all([request("/api/local/overview"), request("/api/local/sql/challenges"), request("/api/local/viva/questions")])
      .then(([o, c, v]) => {
        if (!active) return;
        setOverview(o); setRole(o.profile.role); setLanguage(o.profile.language);
        setMinutes(o.profile.daily_minutes); setCatalog(c); setQuestions(v.questions); setLoaded(true);
      })
      .catch(e => { if (active) { setError(String(e)); setLoaded(true); } });
    return () => { active = false; };
  }, []);

  async function save() {
    setBusy("profile"); setError(""); setNotice("");
    try {
      const p = await request("/api/local/profile", { method: "PUT", headers: jsonHeaders,
        body: JSON.stringify({ role, language, daily_minutes: minutes }) });
      setOverview(await request("/api/local/overview"));
      setNotice("Saved preferences for " + p.target_role + ".");
      setEvidenceRefresh(n => n + 1);
    } catch (e) { setError(String(e)); } finally { setBusy(""); }
  }

  async function gradeSQL() {
    setBusy("sql"); setError(""); setSqlGrade(null);
    try {
      const r = await request("/api/local/sql/attempts", { method: "POST", headers: jsonHeaders,
        body: JSON.stringify({ challenge_id: taskId, query: sql }) });
      setSqlGrade(r.result); setOverview(r.overview);
      setEvidenceRefresh(n => n + 1);
    } catch (e) { setError(String(e)); } finally { setBusy(""); }
  }

  async function gradeViva() {
    setBusy("viva"); setError(""); setVivaGrade(null);
    try {
      const r = await request("/api/local/viva/attempts", { method: "POST", headers: jsonHeaders,
        body: JSON.stringify({ question_id: questionId, choice_id: answer }) });
      setVivaGrade(r.result); setOverview(r.overview); setAnswer("");
      setEvidenceRefresh(n => n + 1);
    } catch (e) { setError(String(e)); } finally { setBusy(""); }
  }

  async function clear() {
    if (!window.confirm("Delete your local assessment history and preferences? This cannot be undone.")) return;
    setBusy("clear"); setError("");
    try {
      await request("/api/local/data", { method: "DELETE" });
      const o: Overview = await request("/api/local/overview");
      setOverview(o); setRole(o.profile.role); setLanguage(o.profile.language);
      setMinutes(o.profile.daily_minutes); setSqlGrade(null); setVivaGrade(null);
      setNotice("Local study history was cleared.");
      setEvidenceRefresh(n => n + 1);
    } catch (e) { setError(String(e)); } finally { setBusy(""); }
  }

  const task = catalog?.challenges.find(t => t.id === taskId);
  const question = questions.find(q => q.id === questionId);
  return <section className="real-workspace" aria-label="Local study workspace">
    <div className="local-heading">
      <div><p className="eyebrow">REAL ASSESSMENTS · PERSISTENT LOCAL PROGRESS</p>
        <h2>Your personal preparation workspace</h2>
        <p>Execute real SQL, assess computer science fundamentals and get a preparation plan based on checked results. No login required.</p>
      </div>
      <span className="local-mode">Single-device mode</span>
    </div>
    {!loaded && <p role="status">Connecting to the local API…</p>}
    {error && <p role="alert" className="error">{error}. Start the local backend on port 8000.</p>}
    {notice && <p role="status" className="feedback">{notice}</p>}
    <div className="local-grid">
      <section className="panel">
        <h3>Choose your goal</h3>
        <div className="local-fields">
          <label>Target role<select value={role} onChange={e => setRole(e.target.value)}>
            <option value="backend">Backend Engineer</option><option value="data">Data Analyst</option>
            <option value="ml">ML Engineer</option><option value="fullstack">Full-stack Engineer</option>
          </select></label>
          <label>Preferred language<select value={language} onChange={e => setLanguage(e.target.value)}>
            <option>Java</option><option>Python</option><option>JavaScript</option>
          </select></label>
          <label>Minutes each day<input type="number" min="15" max="120" value={minutes} onChange={e => setMinutes(Number(e.target.value))}/></label>
        </div>
        <div className="local-actions">
          <button disabled={Boolean(busy) || !loaded || minutes < 15 || minutes > 120} onClick={save}>Save preferences</button>
          <button disabled={Boolean(busy)} className="secondary-button" onClick={clear}>Delete local history</button>
        </div>
        <p className="fineprint">No authentication. This workspace must stay on your own computer; do not deploy it publicly or store private student data.</p>
      </section>
      <section className="panel">
        <h3>Evidence-backed roadmap</h3>
        <p className="sub">{overview?.profile.target_role || "Loading"} · {overview?.recorded_sql_attempts ?? 0} executed SQL attempts · {overview?.recorded_viva_attempts ?? 0} Core CS answers</p>
        <div className="local-tracks">{overview?.tracks.map(t => <div key={t.id} className="local-track">
          <span><strong>{t.id.toUpperCase()}</strong> · {t.assessed}/{t.available} distinct assessments · {t.correct_first_try} first-try passes</span>
          <div className="track"><div className="fill" style={{ width: (100 * t.assessed / t.available) + "%" }}/></div>
        </div>)}</div>
        <div className="recommend"><p className="eyebrow">PREPLOOP PRIORITY</p><strong>{overview?.recommendation.topic.toUpperCase()}</strong>
          <p>{overview?.recommendation.reason}</p></div>
        <div className="local-plan">{overview?.roadmap.map((item, i) => <div key={i}><strong>{item.topic.toUpperCase()} · {item.minutes} min</strong><p>{item.why}</p></div>)}</div>
        <p className="fineprint">{overview?.evidence_note}</p>
      </section>
    </div>
    <div className="local-grid">
      <section className="panel">
        <p className="eyebrow">EXECUTED QUERIES · TWO INDEPENDENT DATASETS</p><h3>SQL Assessment Lab</h3>
        <p className="sub">Submit a read-only SQLite query. The server executes it and compares its results with separately executed reference queries.</p>
        <label htmlFor="real-sql-task">Choose SQL challenge</label>
        <select id="real-sql-task" value={taskId} onChange={e => { setTaskId(e.target.value); setSqlGrade(null); }}>
          {catalog?.challenges.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
        </select>
        <p className="prompt">{task?.prompt}</p>
        <details className="local-schema"><summary>Database schema and example records</summary>
          <ul>{catalog?.schema.map(x => <li key={x}><code>{x}</code></li>)}</ul>
          <p>{catalog?.active_definition}</p>
          <p>Example rows: <code>{JSON.stringify(catalog?.sample_employees.slice(0, 3))}</code></p>
        </details>
        <label htmlFor="real-sql-code">Your SQL query</label>
        <textarea id="real-sql-code" className="local-code" rows={7} spellCheck={false} maxLength={1500} value={sql} onChange={e => setSql(e.target.value)} />
        <button disabled={Boolean(busy) || sql.trim().length < 12} onClick={gradeSQL}>{busy === "sql" ? "Executing…" : "Run and grade SQL"}</button>
        {sqlGrade && <div className="local-result" role="status">
          <h4>{sqlGrade.passed ? "All checks passed" : sqlGrade.tests_passed + "/" + sqlGrade.tests_total + " checks passed"}</h4>
          {sqlGrade.checks.map(c => <div key={c.fixture} className="local-test">
            <strong>Dataset {c.fixture}: {c.passed ? "PASS" : "REVIEW"}</strong>
            {c.error && <p>{c.error}</p>}
            {!c.passed && c.actual_preview && <p>Actual: <code>{JSON.stringify(c.actual_preview)}</code></p>}
            {!c.passed && c.expected_preview && <p>Expected: <code>{JSON.stringify(c.expected_preview)}</code></p>}
          </div>)}
          <p className="fineprint">{sqlGrade.notice}</p>
        </div>}
      </section>
      <section className="panel">
        <p className="eyebrow">CORE VIVA · SERVER-CHECKED FUNDAMENTALS</p><h3>Core CS Assessment</h3>
        <p className="sub">Structured DBMS, OS, computer networks and OOP checks. This is genuine answer verification, not an AI interview score.</p>
        <label htmlFor="real-core-topic">Subject</label>
        <select id="real-core-topic" value={topic} onChange={e => {
          const v = e.target.value; setTopic(v); setQuestionId(questions.find(q => q.topic === v)?.id || "");
          setVivaGrade(null); setAnswer("");
        }}><option value="dbms">DBMS</option><option value="os">Operating Systems</option>
          <option value="cn">Computer Networks</option><option value="oop">OOP</option></select>
        <label htmlFor="real-core-question">Question</label>
        <select id="real-core-question" value={questionId} onChange={e => { setQuestionId(e.target.value); setAnswer(""); setVivaGrade(null); }}>
          {questions.filter(q => q.topic === topic).map(q => <option key={q.id} value={q.id}>{q.id}</option>)}
        </select>
        <p className="prompt">{question?.prompt}</p>
        <fieldset><legend>Choose an answer</legend>{question && Object.entries(question.options).map(([id, value]) => <label key={id} className="option">
          <input name="real-core-answer" type="radio" checked={answer === id} onChange={() => setAnswer(id)}/>{value}
        </label>)}</fieldset>
        <button disabled={Boolean(busy) || !answer} onClick={gradeViva}>{busy === "viva" ? "Checking…" : "Submit answer"}</button>
        {vivaGrade && <p className="feedback" role="status">{vivaGrade.correct ? "Correct. " : "Not quite. "}{vivaGrade.explanation}</p>}
        <p className="fineprint">The SQL and Viva engines use original assessment content. Test fixtures are fictional; the SQL execution and recorded results are real.</p>
      </section>
    </div>
    <UnifiedProgress refresh={evidenceRefresh} onEvidence={() => setEvidenceRefresh(n => n + 1)} />
  </section>;
}
