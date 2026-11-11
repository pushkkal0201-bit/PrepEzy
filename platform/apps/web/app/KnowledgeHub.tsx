"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_PREPEZY_API_URL || "http://localhost:8000";

type Status = { upstream: { enabled: boolean; connected: boolean; status: string;
  backend?: string; indexed_documents?: number; message: string }; saved_notes: number;
  folder: string };
type Note = { name: string; bytes: number };
type Document = { name: string; id: string; chunks: number };
type Result = { question: string; mode: string; answer: string | null; grounded: boolean;
  source_count: number; notice: string;
  sources: { text: string; source: string; score: number | null }[] };
type Suggested = { skill: string; query: string; reason: string };

async function api(path: string, options?: RequestInit) {
  const res = await fetch(API + path, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : "API returned status " + res.status);
  }
  return res.json();
}

export default function KnowledgeHub({ refresh }: { refresh: number }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [suggestion, setSuggestion] = useState<Suggested | null>(null);
  const [filename, setFilename] = useState("study-notes.md");
  const [content, setContent] = useState("# My study notes\n\n");
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<"retrieve" | "answer">("retrieve");
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [indexMessage, setIndexMessage] = useState("");
  const [error, setError] = useState("");

  async function updateLocal() {
    const [state, saved] = await Promise.all([
      api("/api/local/knowledge/status"), api("/api/local/knowledge/notes")
    ]);
    setStatus(state);
    setNotes(saved.notes);
  }

  async function updateIndex() {
    try {
      const x = await api("/api/local/knowledge/documents?limit=50");
      setDocuments(x.documents || []);
      setIndexMessage(x.notice || "Document index queried.");
    } catch (e) {
      setDocuments([]);
      setIndexMessage(String(e));
    }
  }

  useEffect(() => {
    let active = true;
    api("/api/local/knowledge/recommendation")
      .then(data => { if (active) { setSuggestion(data); setQuestion(q => q || data.query); } })
      .catch(e => { if (active) setError(String(e)); });
    return () => { active = false; };
  }, [refresh]);

  useEffect(() => {
    updateLocal().catch(e => setError(String(e)));
    updateIndex();
  }, []);

  async function save() {
    setBusy("save"); setError(""); setMessage("");
    try {
      const saved = await api("/api/local/knowledge/notes", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename, content }),
      });
      await updateLocal();
      setMessage(saved.detail);
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  async function open(name: string) {
    setBusy("open"); setError("");
    try {
      const note = await api("/api/local/knowledge/notes/" + encodeURIComponent(name));
      setFilename(note.filename); setContent(note.content);
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  async function remove(name: string) {
    if (!window.confirm("Delete " + name + " from local knowledge folder?")) return;
    setBusy("delete"); setError("");
    try {
      const answer = await api("/api/local/knowledge/notes/" + encodeURIComponent(name), { method: "DELETE" });
      await updateLocal();
      await updateIndex();
      setMessage("Deleted locally. " + answer.status.replaceAll("-", " ") + ".");
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  async function ask() {
    setBusy("query"); setError(""); setResult(null);
    try {
      const reply = await api("/api/local/knowledge/query", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, mode, k: 5 }),
      });
      setResult(reply);
    } catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  }

  return <section className="panel knowledge-hub">
    <p className="eyebrow">STAGE 8 · REAL RETRIEVAL AND SOURCE CITATIONS</p>
    <h2>Knowledge Hub</h2>
    <p className="sub">Create study notes, let Serviette index them, and ask source-grounded questions. PrepLoop recommends topics based on actual SkillGraph evidence.</p>
    <div className="knowledge-status">
      <div><strong>Serviette</strong><span>{status?.upstream.connected ? "Connected" : status?.upstream.status || "Checking..."}</span></div>
      <div><strong>Vector database</strong><span>{status?.upstream.backend || "Not reported"}</span></div>
      <div><strong>Local notes</strong><span>{status?.saved_notes ?? "–"}</span></div>
      <div><strong>Indexed documents</strong><span>{status?.upstream.indexed_documents ?? "Unknown"}</span></div>
    </div>
    {status && !status.upstream.connected && <div className="judge-setup">
      <strong>Serviette is not connected</strong>
      <p>{status.upstream.message} Start the separate Serviette service and enable PREPEZY_SERVIETTE_ENABLED=1. There are no simulated answers or citations.</p>
    </div>}
    <div className="knowledge-buttons">
      <button className="secondary-button" disabled={Boolean(busy)} onClick={() => updateLocal().catch(e => setError(String(e)))}>Recheck service</button>
      <button className="secondary-button" disabled={Boolean(busy)} onClick={updateIndex}>Refresh indexed documents</button>
    </div>
    <div className="knowledge-grid">
      <div>
        <h3>My study notes</h3>
        <p className="fineprint">Saved notes are not automatically marked indexed. Serviette must watch the same directory.</p>
        <label htmlFor="kh-filename">Safe filename (.md or .txt)</label>
        <input id="kh-filename" value={filename} maxLength={70} onChange={e => setFilename(e.target.value)} />
        <label htmlFor="kh-note">Note content</label>
        <textarea id="kh-note" rows={9} maxLength={50000} value={content} onChange={e => setContent(e.target.value)}/>
        <button disabled={Boolean(busy) || !content.trim()} onClick={save}>{busy === "save" ? "Saving..." : "Save to watched folder"}</button>
        <div className="knowledge-file-list">
          <h4>Saved locally</h4>
          {notes.length === 0 && <p className="fineprint">No saved notes yet.</p>}
          {notes.map(note => <div key={note.name}>
            <button className="knowledge-link" disabled={Boolean(busy)} onClick={() => open(note.name)}>{note.name}</button>
            <small>{note.bytes} bytes</small>
            <button className="knowledge-delete" disabled={Boolean(busy)} onClick={() => remove(note.name)}>Delete</button>
          </div>)}
        </div>
      </div>
      <div>
        <h3>Ask your indexed sources</h3>
        {suggestion && <div className="recommend">
          <p className="eyebrow">PERSONALIZED FROM PREPLOOP</p>
          <strong>{suggestion.skill.toUpperCase()}</strong>
          <p>{suggestion.reason}</p>
          <button className="secondary-button" onClick={() => setQuestion(suggestion.query)}>Use suggested topic</button>
        </div>}
        <label htmlFor="kh-question">Question</label>
        <textarea id="kh-question" rows={3} maxLength={800} value={question} onChange={e => setQuestion(e.target.value)}/>
        <label htmlFor="kh-mode">Answer mode</label>
        <select id="kh-mode" value={mode} onChange={e => setMode(e.target.value as "retrieve" | "answer")}>
          <option value="retrieve">Retrieve indexed passages</option>
          <option value="answer">Generate answer via Serviette (requires its configured LLM)</option>
        </select>
        <button disabled={Boolean(busy) || !status?.upstream.connected || question.trim().length < 3}
          onClick={ask}>{busy === "query" ? "Retrieving..." : "Search real documents"}</button>
        {result && <div className="knowledge-result" role="status">
          <p className="eyebrow">{result.mode === "source-grounded-answer" ? "SERVIETTE GENERATED ANSWER" : "SOURCE PASSAGES ONLY"}</p>
          {result.answer && <p className="knowledge-answer">{result.answer}</p>}
          <h4>{result.source_count} supporting passage(s)</h4>
          {!result.grounded && <p className="error">No supporting source passages were returned. This answer is unverified.</p>}
          {result.sources.map((source, i) => <div key={i} className="knowledge-citation">
            <strong>[{i + 1}] {source.source}</strong>
            <p>{source.text || "No text in source response"}</p>
            {source.score !== null && <small>Retrieval score: {source.score}</small>}
          </div>)}
          <p className="fineprint">{result.notice}</p>
        </div>}
      </div>
    </div>
    {message && <p className="feedback" role="status">{message}</p>}
    {error && <p className="error" role="alert">{error}</p>}
    <div className="knowledge-index">
      <h3>Documents actually reported by Serviette</h3>
      <p className="fineprint">{indexMessage}</p>
      {documents.length === 0 && <p className="fineprint">No indexed documents were returned.</p>}
      {documents.map((doc, i) => <div key={doc.id + i}><strong>{doc.name}</strong><span>{doc.chunks} chunks</span></div>)}
    </div>
    <p className="fineprint">This local-only knowledge system is not a private multi-user service. External LLM providers can receive retrieved excerpts if configured in Serviette; avoid sensitive notes and do not expose this unauthenticated API publicly.</p>
  </section>;
}
