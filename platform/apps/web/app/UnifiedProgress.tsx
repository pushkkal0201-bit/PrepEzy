"use client";

import { useEffect, useState } from "react";
import PatternCoach from "./PatternCoach";
import CodingArena from "./CodingArena";
import KnowledgeHub from "./KnowledgeHub";
import CareerStudio from "./CareerStudio";
import ResumeStudio from "./ResumeStudio";
import ProjectLab from "./ProjectLab";

const API = process.env.NEXT_PUBLIC_PREPEZY_API_URL || "http://localhost:8000";

type Skill = {
  id: string; name: string; kind: string; available: number; distinct_assessments: number;
  first_try_correct_unassisted: number; coverage: number; status: string;
  interpretation: string; priority: number;
};
type Graph = {
  version: string; skills: Skill[];
  recommendation: { skill: string; activity: string; why: string; minutes: number } | null;
  roadmap: { skill: string; activity: string; minutes: number; why: string }[];
  sources: Record<string, number>; event_count: number; interpretation: string;
};
type Challenge = { id: string; title: string; description: string; starter: string; hint: string };
type CodeResult = {
  passed: number; total: number; all_passed: boolean; limitations: string;
  tests: { test: number; status: string; public: boolean }[];
};

export default function UnifiedProgress({ refresh, onEvidence }: { refresh: number; onEvidence: () => void }) {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [error, setError] = useState("");
  const [codeError, setCodeError] = useState("");
  const [status, setStatus] = useState<{ connected: boolean; enabled: boolean } | null>(null);
  const [challenges, setChallenges] = useState<Challenge[]>([]);
  const [selected, setSelected] = useState("");
  const [code, setCode] = useState("");
  const [grade, setGrade] = useState<CodeResult | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    fetch(API + "/api/local/skillgraph")
      .then(r => { if (!r.ok) throw Error("Unified SkillGraph unavailable"); return r.json(); })
      .then(data => { if (active) setGraph(data); })
      .catch(e => { if (active) setError(String(e)); });
    return () => { active = false; };
  }, [refresh]);

  useEffect(() => {
    let active = true;
    fetch(API + "/api/demo/integrations/auralis")
      .then(r => r.json())
      .then(data => {
        if (!active) return;
        setStatus(data);
        if (data.connected) {
          fetch(API + "/api/local/auralis/challenges")
            .then(r => { if (!r.ok) throw Error("Auralis challenge catalog unavailable"); return r.json(); })
            .then(catalog => {
              if (!active) return;
              const items: Challenge[] = catalog.challenges || [];
              setChallenges(items);
              if (items.length) {
                setSelected(items[0].id);
                setCode(items[0].starter || "");
              }
            })
            .catch(e => { if (active) setCodeError(String(e)); });
        }
      })
      .catch(() => { if (active) setStatus({ connected: false, enabled: false }); });
    return () => { active = false; };
  }, []);

  async function runCode() {
    if (!selected || !code.trim()) return;
    setBusy(true); setCodeError(""); setGrade(null);
    try {
      const r = await fetch(API + "/api/local/auralis/code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ challenge_id: selected, code }),
      });
      if (!r.ok) {
        const detail = await r.json().catch(() => ({}));
        throw Error(detail.detail || "Auralis grader returned HTTP " + r.status);
      }
      const data = await r.json();
      setGrade(data.result);
      setGraph(data.skillgraph);
      onEvidence();
    } catch (e) { setCodeError(String(e)); }
    finally { setBusy(false); }
  }

  return <div className="unified-section">
    <section className="panel unified-graph-panel">
      <p className="eyebrow">PREPEZY SKILLGRAPH · ONE LOCAL EVIDENCE PIPELINE</p>
      <h3>One connected view of your real assessments</h3>
      <p className="sub">SQL executions, checked Core CS answers, guided DSA transfer results, Docker-executed coding and restricted Auralis tests are tracked separately with traceable sources. This is not a hiring score.</p>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="unified-evidence-counts">
        {graph && Object.entries(graph.sources).map(([source, count]) =>
          <div key={source}><strong>{count}</strong><span>{source.replaceAll("_", " ")}</span></div>
        )}
      </div>
      <div className="unified-grid">
        {graph?.skills.map(skill => <div className="unified-skill" key={skill.id}>
          <div className="unified-skill-title"><strong>{skill.name}</strong>
            <span>{skill.distinct_assessments}/{skill.available} distinct checks</span>
          </div>
          <div className="track"><div className="fill" style={{ width: (100 * skill.coverage) + "%" }}/></div>
          <p>{skill.interpretation}</p>
        </div>)}
      </div>
      {graph?.recommendation && <div className="recommend">
        <p className="eyebrow">YOUR CURRENT PRIORITY</p>
        <h3>{graph.recommendation.skill.toUpperCase()} · {graph.recommendation.activity.replaceAll("-", " ")}</h3>
        <p>{graph.recommendation.why}</p>
      </div>}
      <div className="unified-plan">
        {graph?.roadmap.map(x => <div key={x.skill}>
          <strong>{x.skill.toUpperCase()} · {x.minutes} min</strong><p>{x.why}</p>
        </div>)}
      </div>
      <p className="fineprint">{graph?.interpretation}</p>
    </section>
    <PatternCoach learner="local" local onEvidence={onEvidence}/>
    <CodingArena onEvidence={onEvidence}/>
    <KnowledgeHub refresh={refresh}/>
    <CareerStudio refresh={refresh}/>
    <ResumeStudio refresh={refresh}/>
    <ProjectLab refresh={refresh} onEvidence={onEvidence}/>
    <section className="panel unified-auralis">
      <p className="eyebrow">AURALIS · REAL RESTRICTED CODE CHECKS</p>
      <h3>Python practice with executed test cases</h3>
      <p className="sub">Optional local Auralis integration. Its restricted-AST evaluator runs predefined challenges against fixed tests; only validated results enter the local evidence graph.</p>
      <p className="fineprint">{status?.connected ? "Local Auralis is connected." : "Auralis not connected. Start the optional local Auralis service on port 8001 and enable PREPEZY_AURALIS_ENABLED=1 in PrepEzy API."}</p>
      {status?.connected && <div className="local-auralis-form">
        <label htmlFor="unified-auralis-task">Challenge</label>
        <select id="unified-auralis-task" value={selected} onChange={e => {
          const id = e.target.value; setSelected(id);
          setCode(challenges.find(c => c.id === id)?.starter || "");
          setGrade(null);
        }}>
          {challenges.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
        </select>
        <p>{challenges.find(c => c.id === selected)?.description}</p>
        <label htmlFor="unified-auralis-code">Restricted Python solution</label>
        <textarea id="unified-auralis-code" rows={6} spellCheck={false} maxLength={2500}
          value={code} onChange={e => setCode(e.target.value)} />
        <button disabled={busy || !selected || code.trim().length < 8} onClick={runCode}>
          {busy ? "Grading…" : "Run verified Auralis tests"}
        </button>
        {grade && <div className="local-result" role="status">
          <h4>{grade.passed}/{grade.total} test cases passed</h4>
          <div className="code-test-list">{grade.tests.map((t, i) => <span key={i} className={"test-pill " + (t.status === "pass" ? "passed" : "failed")}>
            Case {t.test}: {t.status}{t.public ? " (public)" : " (hidden)"}
          </span>)}</div>
          <p className="fineprint">{grade.limitations}</p>
        </div>}
        {codeError && <p className="error" role="alert">{codeError}</p>}
      </div>}
    </section>
  </div>;
}
