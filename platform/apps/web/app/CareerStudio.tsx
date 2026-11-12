"use client";
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_PREPEZY_API_URL || "http://localhost:8000";
type Board = { provider: "greenhouse" | "lever"; token: string; company: string };
type Match = {
  role_title_relevance: boolean;
  observed_evidence: { tag: string; skillgraph: string }[];
  unassessed_requirements: string[];
  practice_gaps: { tag: string }[];
  explanation: string;
};
type Job = {
  id: string; provider: string; company: string; title: string; location: string;
  url: string; fetched_at: string; description?: string; integrity_alerts: string[];
  match: Match;
};
type App = { job_id: string; stage: string; notes: string; updated_at: string; company: string; title: string };
type Draft = { id: number; content: string; status: string; notice: string };
type Refresh = { saved: number; sources: { company: string; provider: string; result: string; saved: number; message?: string }[]; notice: string };
async function api(path: string, options?: RequestInit) {
  const res = await fetch(API + path, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw Error(typeof body.detail === "string" ? body.detail : "Career API status " + res.status);
  }
  return res.json();
}
const headers = { "Content-Type": "application/json" };

export default function CareerStudio({ refresh }: { refresh: number }) {
  const [boards, setBoards] = useState<Board[]>([]);
  const [provider, setProvider] = useState<Board["provider"]>("greenhouse");
  const [token, setToken] = useState("");
  const [company, setCompany] = useState("");
  const [facts, setFacts] = useState("");
  const [preferredLocation, setPreferredLocation] = useState("");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("");
  const [selected, setSelected] = useState<Job | null>(null);
  const [applications, setApplications] = useState<App[]>([]);
  const [stage, setStage] = useState("saved");
  const [notes, setNotes] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [refreshed, setRefreshed] = useState<Refresh | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [ready, setReady] = useState(false);

  async function load() {
    const [b, p, j, a] = await Promise.all([
      api("/api/local/careers/boards"),
      api("/api/local/careers/profile"),
      api("/api/local/careers/jobs?limit=60"),
      api("/api/local/careers/applications"),
    ]);
    setBoards(b.boards);
    setFacts(p.facts);
    setPreferredLocation(p.preferred_location);
    setJobs(j.jobs);
    setApplications(a.applications);
  }

  useEffect(() => {
    let active = true;
    Promise.all([
      api("/api/local/careers/boards"),
      api("/api/local/careers/profile"),
      api("/api/local/careers/jobs?limit=60"),
      api("/api/local/careers/applications"),
    ]).then(([b, p, j, a]) => {
      if (!active) return;
      setBoards(b.boards); setFacts(p.facts); setPreferredLocation(p.preferred_location);
      setJobs(j.jobs); setApplications(a.applications); setReady(true);
    }).catch(e => { if (active) { setError(String(e)); setReady(true); } });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    if (!ready) return;
    const params = new URLSearchParams({ q: query, location, limit: "60" });
    api("/api/local/careers/jobs?" + params.toString())
      .then(data => { if (active) setJobs(data.jobs); })
      .catch(e => { if (active) setError(String(e)); });
    return () => { active = false; };
  }, [refresh, ready, query, location]);

  async function act(name: string, task: () => Promise<void>) {
    setBusy(name); setError(""); setNotice("");
    try { await task(); } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  const addBoard = () => act("board", async () => {
    const data = await api("/api/local/careers/boards", {
      method: "POST", headers,
      body: JSON.stringify({ provider, token: token.trim(), company: company.trim() }),
    });
    await load();
    setToken(""); setCompany("");
    setNotice(data.notice);
  });

  const fetchJobs = () => act("refresh", async () => {
    const data = await api("/api/local/careers/refresh", { method: "POST" });
    setRefreshed(data); await load();
    setNotice(data.notice);
  });

  const saveProfile = () => act("profile", async () => {
    await api("/api/local/careers/profile", {
      method: "PUT", headers,
      body: JSON.stringify({ facts, preferred_location: preferredLocation }),
    });
    setNotice("Your self-reported facts were saved in local SQLite; no job provider received them.");
  });

  const openJob = (job: Job) => act("open", async () => {
    const data = await api("/api/local/careers/jobs/" + encodeURIComponent(job.id));
    setSelected(data); setDraft(null);
    const previous = applications.find(a => a.job_id === job.id);
    setStage(previous?.stage || "saved");
    setNotes(previous?.notes || "");
  });

  const prepareDraft = () => act("draft", async () => {
    if (!selected) return;
    setDraft(await api("/api/local/careers/jobs/" + encodeURIComponent(selected.id) + "/drafts", {
      method: "POST",
    }));
  });

  const saveStage = () => act("stage", async () => {
    if (!selected) return;
    const data = await api("/api/local/careers/applications/" + encodeURIComponent(selected.id), {
      method: "PUT", headers, body: JSON.stringify({ stage, notes }),
    });
    const rows = await api("/api/local/careers/applications");
    setApplications(rows.applications); setNotice(data.notice);
  });

  const deleteData = () => act("delete", async () => {
    if (!window.confirm("Delete your locally stored career boards, job snapshots, drafts and self-reported facts?")) return;
    await api("/api/local/careers/data", { method: "DELETE" });
    await load(); setSelected(null); setDraft(null); setRefreshed(null);
    setNotice("Local career data deleted.");
  });

  const removeBoard = (b: Board) => act("remove", async () => {
    await api("/api/local/careers/boards/" + b.provider + "/" + b.token, { method: "DELETE" });
    await load();
  });

  return <section className="panel career-studio">
    <p className="eyebrow">STAGE 9 · JOBSEARCH-INSPIRED · VERIFIED EXTERNAL SOURCES</p>
    <h2>Career Intelligence</h2>
    <p className="sub">Discover jobs through official public Greenhouse or Lever feeds, compare requirements against your real SkillGraph, prepare truthful drafts, and track your own applications. Nothing is applied to or sent automatically.</p>
    {!ready && <p role="status">Loading local career workspace…</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {notice && <p className="feedback" role="status">{notice}</p>}

    <div className="career-grid">
      <div className="career-panel">
        <h3>1. Configure employer boards</h3>
        <p className="fineprint">Find the board token in an employer's official Greenhouse or Lever careers URL. There are no preloaded synthetic jobs. All discovery uses public, read-only ATS requests.</p>
        <label>Job board provider
          <select value={provider} onChange={e => setProvider(e.target.value as Board["provider"])}>
            <option value="greenhouse">Greenhouse</option><option value="lever">Lever</option>
          </select>
        </label>
        <label>Employer label
          <input value={company} maxLength={120} placeholder="Company name" onChange={e => setCompany(e.target.value)}/>
        </label>
        <label>Public board token
          <input value={token} maxLength={60} placeholder="From public careers URL" onChange={e => setToken(e.target.value)}/>
        </label>
        <button disabled={Boolean(busy) || !token.trim() || company.trim().length < 2} onClick={addBoard}>Add board</button>
        <div className="career-board-list">
          {boards.length === 0 && <p className="fineprint">No employer boards configured yet.</p>}
          {boards.map(b => <div key={b.provider + b.token}>
            <span><strong>{b.company}</strong><small>{b.provider} / {b.token}</small></span>
            <button disabled={Boolean(busy)} className="secondary-button" onClick={() => removeBoard(b)}>Remove</button>
          </div>)}
        </div>
        <button disabled={Boolean(busy) || !boards.length} onClick={fetchJobs}>
          {busy === "refresh" ? "Fetching published jobs…" : "Refresh live job boards"}
        </button>
        {refreshed && <div className="career-fetch" role="status">
          <p><strong>{refreshed.saved} job snapshot(s) saved</strong></p>
          {refreshed.sources.map((s, i) => <p key={i}>{s.company}: {s.result === "fetched" ? s.saved + " returned" : s.message}</p>)}
        </div>}
      </div>
      <div className="career-panel">
        <h3>2. Your verified-by-you career facts</h3>
        <p className="fineprint">Enter only true experiences you can defend, one per line. These are self-reported and not independently verified by PrepEzy. Drafts reuse your wording instead of inventing achievements.</p>
        <label>Experience, skills and project facts
          <textarea rows={9} maxLength={6000} value={facts} onChange={e => setFacts(e.target.value)}
            placeholder={"Built an API using FastAPI\nUsed SQL joins in a project"}/>
        </label>
        <label>Preferred location (optional)
          <input value={preferredLocation} maxLength={100} onChange={e => setPreferredLocation(e.target.value)} placeholder="India / Remote"/>
        </label>
        <button disabled={Boolean(busy)} onClick={saveProfile}>Save local facts</button>
        <p className="fineprint">Stored in the single-device SQLite database. Avoid putting confidential identifiers or account credentials here.</p>
      </div>
    </div>

    <div className="career-panel">
      <h3>3. Review published job snapshots</h3>
      <div className="career-filters">
        <label>Keywords<input value={query} maxLength={100} onChange={e => setQuery(e.target.value)} placeholder="Intern, software, Python"/></label>
        <label>Location<input value={location} maxLength={100} onChange={e => setLocation(e.target.value)} placeholder="Remote or city"/></label>
      </div>
      <p className="fineprint">{jobs.length} job(s) shown. Postings can close or change after retrieval. Always check the official employer page.</p>
      <div className="career-job-grid">
        {jobs.length === 0 && <p className="fineprint">No actual job results yet. Add and refresh a real employer board or change your filters.</p>}
        {jobs.map(job => <div key={job.id} className="career-job">
          <strong>{job.title}</strong>
          <p>{job.company} · {job.location || "Location unspecified"}</p>
          <p className="fineprint">{job.provider} · fetched {job.fetched_at}</p>
          {job.match.role_title_relevance && <span className="career-pill">Related job title</span>}
          {job.match.observed_evidence.length > 0 && <span className="career-pill">{job.match.observed_evidence.length} evidence signals</span>}
          {job.integrity_alerts.length > 0 && <span className="career-pill">Untrusted content warning</span>}
          <div><button className="secondary-button" disabled={Boolean(busy)} onClick={() => openJob(job)}>Review job</button></div>
        </div>)}
      </div>
    </div>

    {selected && <div className="career-panel">
      <div className="career-selected-job">
        <div><p className="eyebrow">OFFICIAL POSTING SNAPSHOT</p>
          <h3>{selected.title}</h3><p>{selected.company} · {selected.location}</p></div>
        <a href={selected.url} target="_blank" rel="noopener noreferrer">Open actual employer listing</a>
      </div>
      {selected.integrity_alerts.map((alert, i) => <p className="error" key={i}>{alert}</p>)}
      <details className="career-description"><summary>View sanitized job description (external untrusted text)</summary>
        <p>{selected.description || "No description available in the published feed."}</p>
      </details>
      <div className="career-evidence">
        <h4>SkillGraph evidence comparison</h4>
        <p>Title relevant to target role: {selected.match.role_title_relevance ? "Yes" : "Not established"}</p>
        <p>Limited positive evidence: {selected.match.observed_evidence.map(x => x.tag).join(", ") || "None"}</p>
        <p>Unassessed requested skills: {selected.match.unassessed_requirements.join(", ") || "None extracted"}</p>
        <p>Assessed practice gaps: {selected.match.practice_gaps.map(x => x.tag).join(", ") || "None"}</p>
        <p className="fineprint">{selected.match.explanation}</p>
      </div>
      <div className="career-grid">
        <div>
          <h4>4. Review a facts-only draft</h4>
          <p className="fineprint">Nothing is sent or submitted. Your facts are self-reported and must be checked.</p>
          <button disabled={Boolean(busy)} onClick={prepareDraft}>Create draft for my review</button>
          {draft && <div className="career-draft" role="status">
            <strong>DRAFT ONLY — NOT SENT</strong>
            <pre>{draft.content}</pre>
            <button className="secondary-button" onClick={() => navigator.clipboard.writeText(draft.content).catch(() => setError("Clipboard permission unavailable"))}>Copy draft</button>
            <p className="fineprint">{draft.notice}</p>
          </div>}
        </div>
        <div>
          <h4>5. Track your outcome manually</h4>
          <p className="fineprint">Saving “applied” merely records what you report; it does not submit an application.</p>
          <label>Status
            <select value={stage} onChange={e => setStage(e.target.value)}>
              {["saved", "applied", "interviewing", "offer", "rejected", "withdrawn"].map(x => <option key={x}>{x}</option>)}
            </select>
          </label>
          <label>Personal notes<textarea rows={5} value={notes} maxLength={1500} onChange={e => setNotes(e.target.value)}/></label>
          <button disabled={Boolean(busy)} onClick={saveStage}>Record my status</button>
        </div>
      </div>
    </div>}
    <div className="career-panel">
      <h3>Application outcome history</h3>
      {applications.length === 0 && <p className="fineprint">No applications tracked yet. The employer's response is never inferred.</p>}
      {applications.map(app => <div key={app.job_id} className="career-outcome">
        <strong>{app.company} · {app.title}</strong>
        <span>{app.stage}</span><small>{app.updated_at}</small>
      </div>)}
    </div>
    <div className="career-danger">
      <p className="fineprint">This is a local single-device prototype without authentication. Do not expose it publicly.</p>
      <button disabled={Boolean(busy)} className="secondary-button" onClick={deleteData}>Delete all locally stored career data</button>
    </div>
  </section>;
}
