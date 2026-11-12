"use client";

import { useEffect, useMemo, useState } from "react";

const API = process.env.NEXT_PUBLIC_PREPEZY_API_URL || "http://localhost:8000";
type Language = "python" | "java" | "javascript";
type MiniProgress = { passed_milestones: number; total_milestones: number; checked_defense_questions: number };
type ProjectSummary = {
  id: string; title: string; category: string; description: string;
  role_relevant: boolean; progress: MiniProgress;
};
type Milestone = {
  id: string; title: string; statement: string; test_count: number;
  public_examples: { input: string; output: string }[];
  unlocked: boolean; status: string; latest_verdict: string | null;
  attempt_count: number; first_try_passed: boolean;
};
type Defense = {
  id: string; prompt: string; options: Record<string, string>;
  attempted: boolean; attempt_count: number; latest_choice_correct: boolean | null;
  first_try_correct: boolean | null; feedback: string | null; rationale_reviewed: boolean | null;
};
type ProjectDetail = {
  id: string; title: string; category: string; description: string;
  resources: { label: string; url: string; via: string }[];
  milestones: Milestone[];
  defense_questions: Defense[];
  defense_unlocked: boolean; all_milestones_passed: boolean;
  progress: MiniProgress; artifact: { url: string; notes: string; verification: string } | null; notice: string;
};
type Catalog = {
  projects: ProjectSummary[];
  recommendation: { project_id: string; milestone_id: string; reason: string } | null;
  languages: Language[]; runner_status: Record<Language, boolean>;
  source_index: string; notice: string;
};
type Grade = {
  verdict: string; tests_passed: number; tests_total: number; all_passed: boolean;
  checks: { case: number; status: string; feedback?: string }[]; notice: string;
};
type DefenseGrade = { correct: boolean; explanation: string; rationale_reviewed: boolean; notice: string };
const STARTERS: Record<Language, string> = {
  python: "import sys\n\nlines = sys.stdin.read().splitlines()\n# Read the input specification and print only the requested outputs.\n",
  java: "import java.util.*;\n\npublic class Main {\n    public static void main(String[] args) {\n        Scanner sc = new Scanner(System.in);\n        // Read input and print your results.\n    }\n}\n",
  javascript: "const fs = require('fs');\nconst lines = fs.readFileSync(0, 'utf8').trim().split(/\\r?\\n/);\n// Read input and print only the requested outputs.\n",
};

async function api(path: string, options?: RequestInit) {
  const r = await fetch(API + path, options);
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw Error(typeof body.detail === "string" ? body.detail : "Project Lab returned HTTP " + r.status);
  }
  return r.json();
}
const JSON_HEADERS = { "Content-Type": "application/json" };

export default function ProjectLab({ onEvidence, refresh }: { onEvidence: () => void; refresh: number }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [projectId, setProjectId] = useState("key-value-store");
  const [detail, setDetail] = useState<ProjectDetail | null>(null);
  const [milestoneId, setMilestoneId] = useState("lookup");
  const [language, setLanguage] = useState<Language>("python");
  const [source, setSource] = useState(STARTERS.python);
  const [grade, setGrade] = useState<Grade | null>(null);
  const [selectedDefense, setSelectedDefense] = useState("");
  const [choice, setChoice] = useState("");
  const [rationale, setRationale] = useState("");
  const [defenseGrade, setDefenseGrade] = useState<DefenseGrade | null>(null);
  const [repoUrl, setRepoUrl] = useState("");
  const [artifactNotes, setArtifactNotes] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loaded, setLoaded] = useState(false);

  async function loadCatalog() {
    const data: Catalog = await api("/api/local/projects/catalog");
    setCatalog(data);
    return data;
  }

  async function loadProject(pid: string) {
    const project: ProjectDetail = await api("/api/local/projects/" + encodeURIComponent(pid));
    setDetail(project);
    setRepoUrl(project.artifact?.url || "");
    setArtifactNotes(project.artifact?.notes || "");
    return project;
  }

  useEffect(() => {
    let mounted = true;
    Promise.all([api("/api/local/projects/catalog"), api("/api/local/projects/key-value-store")])
      .then(([c, d]) => {
        if (!mounted) return;
        setCatalog(c); setDetail(d); setLoaded(true);
        setMilestoneId(d.milestones[0].id);
      })
      .catch(e => { if (mounted) { setError(String(e)); setLoaded(true); } });
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    if (!loaded) return;
    loadCatalog().catch(e => setError(String(e)));
  }, [refresh, loaded]);

  async function chooseProject(pid: string) {
    setBusy("project"); setError(""); setGrade(null); setDefenseGrade(null);
    setProjectId(pid); setSelectedDefense(""); setChoice(""); setRationale("");
    setSource(STARTERS[language]);
    try {
      const next = await loadProject(pid);
      setMilestoneId(next.milestones[0].id);
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  const step = useMemo(() => detail?.milestones.find(x => x.id === milestoneId), [detail, milestoneId]);
  const question = useMemo(() => detail?.defense_questions.find(x => x.id === selectedDefense), [detail, selectedDefense]);
  const dockerReady = Boolean(catalog?.runner_status[language]);
  const recommended = catalog?.recommendation;

  async function submitCode() {
    if (!detail || !step?.unlocked || !dockerReady) return;
    setBusy("code"); setError(""); setGrade(null); setNotice("");
    try {
      const result = await api(
        "/api/local/projects/" + encodeURIComponent(detail.id) +
        "/milestones/" + encodeURIComponent(step.id) + "/submit",
        { method: "POST", headers: JSON_HEADERS,
          body: JSON.stringify({ language, code: source }) }
      );
      setGrade(result.result);
      setDetail(result.project);
      await loadCatalog();
      onEvidence();
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  async function submitDefense() {
    if (!detail || !question || !choice || rationale.trim().length < 20) return;
    setBusy("defense"); setError(""); setDefenseGrade(null);
    try {
      const result = await api(
        "/api/local/projects/" + encodeURIComponent(detail.id) +
        "/defense/" + encodeURIComponent(question.id) + "/submit",
        { method: "POST", headers: JSON_HEADERS,
          body: JSON.stringify({ choice_id: choice, rationale }) }
      );
      setDefenseGrade(result.result);
      setDetail(result.project);
      setChoice("");
      setRationale("");
      onEvidence();
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  async function saveArtifact() {
    if (!detail) return;
    setBusy("artifact"); setError(""); setNotice("");
    try {
      const record = await api("/api/local/projects/" + encodeURIComponent(detail.id) + "/artifact", {
        method: "PUT", headers: JSON_HEADERS,
        body: JSON.stringify({ repo_url: repoUrl, notes: artifactNotes }),
      });
      await loadProject(detail.id);
      setNotice(record.notice);
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  return <section className="panel build-lab" aria-label="Adaptive build and project defense lab">
    <p className="eyebrow">STAGE 11 · BUILD → TEST → DEFEND → IMPROVE</p>
    <h2>Adaptive Project Lab</h2>
    <p className="sub">Build real mini-components inspired by curated Build Your Own X tutorial topics. Your code runs against actual hidden tests in the Docker judge. Design decisions are checked separately; written explanations are recorded for review, not graded by a fictional AI interviewer.</p>
    {!loaded && <p role="status">Loading curated projects and local progress…</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {notice && <p className="feedback" role="status">{notice}</p>}
    <div className="build-index-line">
      <span>Curated resources from <a href={catalog?.source_index || "https://github.com/codecrafters-io/build-your-own-x"} target="_blank" rel="noopener noreferrer">Build Your Own X</a></span>
      <span>{catalog?.projects.length || 0} projects · 6 original executable milestones</span>
    </div>

    <div className="build-tiles">
      {catalog?.projects.map(item => <button type="button" className={"build-tile" + (projectId === item.id ? " build-selected" : "")}
        key={item.id} onClick={() => chooseProject(item.id)} disabled={Boolean(busy)}>
        <span className="eyebrow">{item.category} {item.role_relevant ? "· relevant to your goal" : ""}</span>
        <strong>{item.title}</strong>
        <small>{item.description}</small>
        <span className="build-progress">{item.progress.passed_milestones}/{item.progress.total_milestones} verified executable milestones</span>
      </button>)}
    </div>
    {recommended && <div className="build-recommend">
      <span className="eyebrow">PREPLOOP'S PROJECT SUGGESTION</span>
      <p>{recommended.reason}</p>
      <button className="secondary-button" disabled={Boolean(busy)} onClick={() => chooseProject(recommended.project_id)}>
        Open suggested project and next milestone
      </button>
    </div>}

    {detail && <div className="build-workspace">
      <div className="build-heading">
        <div><p className="eyebrow">{detail.category.toUpperCase()} · ORIGINAL EDUCATIONAL MILESTONES</p>
          <h3>{detail.title}</h3><p>{detail.description}</p></div>
        <span className="build-completion">{detail.progress.passed_milestones}/{detail.progress.total_milestones} checked</span>
      </div>
      <div className="build-resources">
        <h4>External learning references</h4>
        <p className="fineprint">Tutorials are linked rather than copied or executed. Each publisher controls its own content and license.</p>
        {detail.resources.map(item => <a key={item.url} href={item.url} target="_blank" rel="noopener noreferrer">
          {item.label} <span>· {item.via}</span>
        </a>)}
      </div>

      <div className="build-columns">
        <div className="build-editor-panel">
          <h4>1. Implement a working milestone</h4>
          <div className="build-milestones">
            {detail.milestones.map(m => <button key={m.id} disabled={Boolean(busy)}
              className={"build-milestone" + (milestoneId === m.id ? " current" : "")}
              onClick={() => { setMilestoneId(m.id); setSource(STARTERS[language]); setGrade(null); }}>
              <strong>{m.title}</strong><small>{m.unlocked ? m.status : "locked — pass previous milestone"}</small>
            </button>)}
          </div>
          {step && <>
            <p className="build-statement">{step.statement}</p>
            <details className="build-example">
              <summary>Public test example · {step.test_count} total tests</summary>
              {step.public_examples.map((ex, i) => <div key={i}>
                <strong>Input</strong><pre>{ex.input}</pre>
                <strong>Expected output</strong><pre>{ex.output}</pre>
              </div>)}
            </details>
            <label htmlFor="project-code-language">Programming language</label>
            <select id="project-code-language" value={language} onChange={e => {
              const lang = e.target.value as Language; setLanguage(lang);
              setSource(STARTERS[lang]); setGrade(null);
            }}>
              {catalog?.languages.map(lang => <option key={lang} value={lang}>
                {lang === "javascript" ? "JavaScript" : lang === "python" ? "Python" : "Java"} · {catalog.runner_status[lang] ? "Docker ready" : "Docker image missing"}
              </option>)}
            </select>
            <label htmlFor="project-code-editor">Program source (stdin → stdout)</label>
            <textarea id="project-code-editor" rows={14} spellCheck={false} maxLength={12000}
              className="build-code" value={source} onChange={e => setSource(e.target.value)}/>
            <button onClick={submitCode} disabled={Boolean(busy) || !step.unlocked || !dockerReady || source.length < 12}>
              {busy === "code" ? "Running real tests…" : "Execute Docker milestone tests"}
            </button>
            {!dockerReady && <p className="fineprint">Docker or its selected language image isn't ready. Install/pull the images from Stage 7. The judge has no host-execution fallback.</p>}
            {!step.unlocked && <p className="fineprint">Complete the previous milestone's tests to unlock this one.</p>}
            {grade && <div className="build-verdict" role="status">
              <strong>{grade.verdict.replaceAll("_", " ").toUpperCase()} · {grade.tests_passed}/{grade.tests_total} tests passed</strong>
              <div className="build-test-tags">{grade.checks.map(x => <span key={x.case} className={x.status === "accepted" ? "accepted" : "failed"}>
                Case {x.case}: {x.status.replaceAll("_", " ")}
              </span>)}</div>
              {grade.checks.filter(x => x.feedback).map(x => <p key={x.case}>{x.feedback}</p>)}
              <p className="fineprint">{grade.notice}</p>
            </div>}
          </>}
        </div>
        <div className="build-defense-panel">
          <h4>2. Defend your design decisions</h4>
          <p className="fineprint">First pass at least one executable milestone. The selected answer is checked by the server; your written reasoning is retained but not automatically scored.</p>
          {!detail.defense_unlocked && <p className="fineprint">Technical-defense questions unlock after one verified milestone.</p>}
          <label htmlFor="project-defense-question">Design question</label>
          <select id="project-defense-question" disabled={!detail.defense_unlocked} value={selectedDefense}
            onChange={e => { setSelectedDefense(e.target.value); setChoice(""); setDefenseGrade(null); }}>
            <option value="">Choose a question</option>
            {detail.defense_questions.map(q => <option key={q.id} value={q.id}>
              {q.id.replaceAll("-", " ")} {q.attempted ? "· attempted" : ""}
            </option>)}
          </select>
          {question && <>
            <p className="build-defense-prompt">{question.prompt}</p>
            <fieldset><legend>Choose an engineering answer</legend>
              {Object.entries(question.options).map(([id, value]) => <label className="option" key={id}>
                <input type="radio" name="project-defense-choice" checked={choice === id} onChange={() => setChoice(id)}/>
                {value}
              </label>)}
            </fieldset>
            <label htmlFor="project-rationale">Explain your reasoning (20–1200 characters)</label>
            <textarea id="project-rationale" rows={5} value={rationale} maxLength={1200}
              placeholder="Explain why you chose that design, its tradeoffs, and one case it should handle."
              onChange={e => setRationale(e.target.value)}/>
            <button disabled={Boolean(busy) || !choice || rationale.trim().length < 20}
              onClick={submitDefense}>{busy === "defense" ? "Checking answer…" : "Check design choice and save reasoning"}</button>
            {question.attempted && <p className="fineprint">{question.attempt_count} recorded answer(s). Your original first attempt remains the baseline evidence.</p>}
            {defenseGrade && <div className="build-verdict" role="status">
              <strong>{defenseGrade.correct ? "Checked answer: correct" : "Checked answer: review needed"}</strong>
              <p>{defenseGrade.explanation}</p>
              <p className="fineprint">{defenseGrade.notice}</p>
            </div>}
          </>}
          <div className="build-artifact">
            <h4>3. Link your real project repository (optional)</h4>
            <p className="fineprint">The link is saved as self-reported evidence only. PrepEzy does not clone, execute, or verify that GitHub repository.</p>
            <label htmlFor="project-repo-url">GitHub repository URL</label>
            <input id="project-repo-url" value={repoUrl} maxLength={220}
              placeholder="https://github.com/owner/repository"
              onChange={e => setRepoUrl(e.target.value)}/>
            <label htmlFor="project-artifact-notes">My implementation notes</label>
            <textarea id="project-artifact-notes" rows={4} value={artifactNotes} maxLength={1800}
              onChange={e => setArtifactNotes(e.target.value)}/>
            <button className="secondary-button" disabled={Boolean(busy) || !repoUrl.trim()}
              onClick={saveArtifact}>Save unverified project link</button>
            {detail.artifact && <p className="fineprint">Saved locally: {detail.artifact.verification}. No link review has been performed.</p>}
          </div>
        </div>
      </div>
      <p className="fineprint">{detail.notice}</p>
    </div>}
    <p className="fineprint">This is a trusted single-device learning lab. No authentication, no arbitrary host code execution, and no claims of production database/search/interpreter certification.</p>
  </section>;
}
