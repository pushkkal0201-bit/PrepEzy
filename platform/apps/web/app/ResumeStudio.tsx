"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_PREPEZY_API_URL || "http://localhost:8000";
const MAX_BYTES = 2 * 1024 * 1024;

type ResumeStatus = {
  uploaded: boolean; filename?: string; format?: string; sha256?: string;
  pages?: number; extracted_lines?: number; imported_at?: string; notice: string;
};
type Ref = { locator: string; line: number; quote: string };
type Inspection = {
  document: ResumeStatus;
  sections: Record<string, { detected: boolean; references: { locator: string; line: number }[] }>;
  mentioned_skills: Record<string, Ref[]>;
  skill_mention_count: number;
  checks: { type: string; message: string }[];
  sample_lines: { locator: string; line: number; text: string }[];
  notice: string;
};
type Job = { id: string; title: string; company: string; location: string };
type Analysis = {
  job: { id: string; company: string; title: string; url: string; fetched_at: string };
  resume: ResumeStatus;
  requirements_count: number;
  mentioned_requirements: { requirement: string; mentions: Ref[] }[];
  unmentioned_requirements: string[];
  separate_assessment_evidence: {
    requirement: string; skillgraph_skill: string; independent_checks: number;
    first_try_correct_unassisted: number; interpretation: string;
  }[];
  preparation_actions: { priority: string; skill: string; task: string; reason: string }[];
  exact_resume_excerpts: ({ requirement: string } & Ref)[];
  interpretation: string;
};

async function call(path: string, options?: RequestInit) {
  const r = await fetch(API + path, options);
  if (!r.ok) {
    const d = await r.json().catch(() => ({}));
    throw new Error(typeof d.detail === "string" ? d.detail : "Resume API returned HTTP " + r.status);
  }
  return r.json();
}

export default function ResumeStudio({ refresh }: { refresh: number }) {
  const [status, setStatus] = useState<ResumeStatus | null>(null);
  const [inspection, setInspection] = useState<Inspection | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobId, setJobId] = useState("");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function readResume() {
    const found: ResumeStatus = await call("/api/local/resume/status");
    setStatus(found);
    if (found.uploaded) {
      const document: Inspection = await call("/api/local/resume/inspection");
      setInspection(document);
    } else {
      setInspection(null);
      setAnalysis(null);
    }
    return found;
  }

  async function listJobs() {
    const response = await call("/api/local/careers/jobs?limit=100");
    setJobs(response.jobs || []);
    return response.jobs as Job[];
  }

  useEffect(() => {
    let active = true;
    Promise.all([call("/api/local/resume/status"), call("/api/local/careers/jobs?limit=100")])
      .then(async ([found, postings]) => {
        if (!active) return;
        setStatus(found);
        setJobs(postings.jobs || []);
        if (found.uploaded) {
          const result: Inspection = await call("/api/local/resume/inspection");
          if (active) setInspection(result);
        }
      })
      .catch(e => { if (active) setError(String(e)); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    listJobs()
      .then(async () => {
        if (jobId && status?.uploaded) {
          const data: Analysis = await call("/api/local/resume/jobs/" + encodeURIComponent(jobId) + "/analysis");
          if (active) setAnalysis(data);
        }
      })
      .catch(e => { if (active) setError(String(e)); });
    return () => { active = false; };
  }, [refresh, jobId, status?.uploaded]);

  async function upload() {
    if (!file) return;
    if (file.size > MAX_BYTES) { setError("The resume must be 2 MiB or smaller."); return; }
    setBusy("upload"); setError(""); setNotice("");
    try {
      const form = new FormData();
      form.append("file", file, file.name);
      const result: ResumeStatus = await call("/api/local/resume/upload", {
        method: "POST", body: form,
      });
      setFile(null);
      await readResume();
      setNotice("Parsed " + result.filename + ". " + result.notice);
      if (jobId) await analyze(jobId);
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  async function analyze(id: string) {
    setJobId(id); setAnalysis(null); setError("");
    if (!id || !status?.uploaded) return;
    setBusy("analyze");
    try {
      const data: Analysis = await call("/api/local/resume/jobs/" + encodeURIComponent(id) + "/analysis");
      setAnalysis(data);
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  async function erase() {
    if (!window.confirm("Delete the extracted resume content and its metadata from the local database?")) return;
    setBusy("erase"); setError("");
    try {
      await call("/api/local/resume", { method: "DELETE" });
      await readResume();
      setFile(null);
      setNotice("Local resume document and extracted text deleted.");
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  return <section className="panel resume-studio" aria-label="Resume document inspection">
    <p className="eyebrow">STAGE 10 · ACTUAL DOCUMENT EXTRACTION · SOURCE-GROUNDED REVIEW</p>
    <h2>Resume Intelligence</h2>
    <p className="sub">Import your own PDF, Word or text resume. PrepEzy reads the actual document, records the location of skill mentions, and compares them to an employer's published requirements plus separate assessed SkillGraph results.</p>
    <div className="resume-privacy">
      <strong>Local-only document handling</strong>
      <p>Importing saves the extracted text in your local SQLite file, not in GitHub. No resume is sent to an LLM or employer. Since authentication is deferred, only use this on your own trusted computer and avoid sensitive identity details.</p>
    </div>
    <div className="resume-upload-row">
      <label htmlFor="resume-upload-file">Choose a PDF, DOCX, TXT or Markdown resume (maximum 2 MiB)</label>
      <input id="resume-upload-file" type="file" accept=".pdf,.docx,.txt,.md"
        onChange={e => setFile(e.target.files?.[0] || null)}/>
      <button disabled={!file || Boolean(busy)} onClick={upload}>
        {busy === "upload" ? "Extracting actual text…" : "Import and inspect resume"}
      </button>
      {status?.uploaded && <button className="secondary-button" disabled={Boolean(busy)}
        onClick={erase}>Delete saved resume text</button>}
    </div>
    {error && <p className="error" role="alert">{error}</p>}
    {notice && <p className="feedback" role="status">{notice}</p>}
    {status?.uploaded ? <div className="resume-state">
      <strong>{status.filename}</strong><span>{status.format?.toUpperCase()} · {status.pages} page/document part(s) · {status.extracted_lines} extracted lines</span>
      <small>Imported {status.imported_at}. No claim has been independently verified.</small>
    </div> : <p className="fineprint">No resume imported. Select a real file above to begin. Scanned/image-only PDFs need OCR and will be rejected rather than guessed.</p>}

    {inspection && <div className="resume-inspection">
      <div className="resume-summary-grid">
        <div className="resume-mini">
          <h3>Detected section headings</h3>
          {Object.entries(inspection.sections).map(([section, value]) => <div key={section}>
            <span>{section}</span><strong>{value.detected ? "Found" : "Not clearly detected"}</strong>
          </div>)}
        </div>
        <div className="resume-mini">
          <h3>Technical skill mentions</h3>
          <p className="fineprint">Literal words only. Mentioning a skill does not verify proficiency.</p>
          <div className="resume-tags">{Object.keys(inspection.mentioned_skills).map(skill =>
            <span key={skill}>{skill.replaceAll("-", " ")}</span>
          )}</div>
        </div>
      </div>
      <details className="resume-extraction"><summary>Inspect the extracted text sample and its locations</summary>
        {inspection.sample_lines.map((item, i) => <p key={i}>
          <small>{item.locator}, line {item.line}</small> {item.text}
        </p>)}
      </details>
      {inspection.checks.length > 0 && <div className="resume-review">
        <h3>Items to review manually</h3>
        {inspection.checks.map((item, i) => <p key={i}>{item.message}</p>)}
      </div>}
    </div>}

    <div className="resume-job-select">
      <h3>Compare your resume with an actual saved job</h3>
      <p className="fineprint">First fetch a real employer posting in Career Intelligence. No job descriptions or vacancies are made up.</p>
      <label htmlFor="resume-choose-job">Employer role</label>
      <select id="resume-choose-job" value={jobId}
        onChange={e => analyze(e.target.value)} disabled={!status?.uploaded}>
        <option value="">Choose one of your fetched postings</option>
        {jobs.map(job => <option key={job.id} value={job.id}>
          {job.company} — {job.title}
        </option>)}
      </select>
      <button className="secondary-button" disabled={Boolean(busy)}
        onClick={() => listJobs().catch(e => setError(String(e)))}>Refresh employer postings</button>
      {busy === "analyze" && <p role="status">Comparing actual text with published requirements…</p>}
    </div>

    {analysis && <div className="resume-analysis">
      <div className="resume-role-heading"><p className="eyebrow">EXPLAINABLE ROLE PREPARATION</p>
        <h3>{analysis.job.title} · {analysis.job.company}</h3>
        <p className="fineprint">{analysis.requirements_count} technology tags found in the saved job snapshot. Missing text is not evidence of missing ability.</p>
      </div>
      <div className="resume-summary-grid">
        <div className="resume-mini">
          <h3>Requirements mentioned in resume</h3>
          {analysis.mentioned_requirements.length === 0 && <p className="fineprint">No literal overlaps detected.</p>}
          {analysis.mentioned_requirements.map(row => <div className="resume-mention" key={row.requirement}>
            <strong>{row.requirement}</strong>
            {row.mentions.slice(0, 1).map((m, i) => <p key={i}><small>{m.locator} · line {m.line}</small> “{m.quote}”</p>)}
          </div>)}
        </div>
        <div className="resume-mini">
          <h3>Requirements not explicitly mentioned</h3>
          {analysis.unmentioned_requirements.length === 0 && <p className="fineprint">No missing literal requirements from the extracted technology list.</p>}
          <div className="resume-tags">
            {analysis.unmentioned_requirements.map(x => <span key={x}>{x}</span>)}
          </div>
          <p className="fineprint">Only add a skill if it reflects experience you actually have.</p>
        </div>
      </div>
      <div className="resume-mini">
        <h3>Independently checked PrepEzy evidence</h3>
        <p className="fineprint">Results from SQL, coding and other assessments are not drawn from your resume text. These are small assessment samples, not professional certification.</p>
        {analysis.separate_assessment_evidence.length === 0 && <p>No relevant first-party assessment evidence yet.</p>}
        {analysis.separate_assessment_evidence.map(row => <div key={row.requirement} className="resume-evidence-row">
          <strong>{row.requirement}</strong>
          <span>{row.first_try_correct_unassisted}/{row.independent_checks} distinct first attempts passed without assistance</span>
        </div>)}
      </div>
      <div className="resume-mini">
        <h3>Role-specific action plan</h3>
        {analysis.preparation_actions.length === 0 && <p className="fineprint">No action can be inferred from current assessed requirements.</p>}
        {analysis.preparation_actions.map((item, i) => <div key={i} className="resume-action">
          <p className="eyebrow">{item.priority.replaceAll("-", " ")} · {item.skill}</p>
          <strong>{item.task}</strong><p>{item.reason}</p>
        </div>)}
      </div>
      <p className="fineprint">{analysis.interpretation}</p>
    </div>}
    <p className="fineprint">No fictitious ATS score, generated resume achievements, or application submission. Extraction of screenshots and scanned PDFs is not supported yet.</p>
  </section>;
}
