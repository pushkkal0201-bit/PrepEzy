# PrepEzy architecture — initial design

## Implemented foundation

```text
Next.js local client (localhost:3000)
  -> FastAPI local demo API (127.0.0.1:8000)
       -> DemoEngine (deterministic server-side scoring and recommendations)
       -> SQLite (optional, synthetic attempts only)
       -> Cracked skill metadata discovery (read only)
```

## Target architecture (NOT yet implemented)

```text
Next.js web -> FastAPI gateway -> Supabase authentication
                           |-> owner-scoped PostgreSQL evidence
                           |-> SkillGraph + PrepLoop event contracts
                           |-> Auralis interview engine
                           |-> Cracked practice adapters + isolated code runner
                           |-> Serviette RAG over permission-filtered documents
                           |-> JobSearch career adapters, with human approval
                           |-> Adaptive Build Lab + curated Skill Studio
```

## Proposed shared event format

Each adapter eventually emits a versioned `LearningEvidence` event containing `owner_id`, `assessment_id`, `competency_id`, `evidence_type`, `rubric_version`, `result`, `source_reference`, `timestamp`, and consent scope. Assessment events must be verified at the originating engine; the browser is not allowed to supply authoritative scores.

## Current no-auth scope

Authentication is intentionally not part of the current foundation. All current learner IDs are public, hard-coded synthetic fixtures. Keep local development bound to loopback; do not upload any personal/student data and do not claim multi-user access isolation. Before inviting real students or exposing the API publicly, add account verification, tenant isolation and a privacy/retention strategy.

## Isolation

The demo uses synthetic account IDs that are *not* authentication. Do not expose them publicly. In production, authenticate and authorize all writes and reads, enforce row-level ownership at the database boundary, isolate code execution, limit third-party agent permissions, and validate retrieved document ownership before prompting an LLM.

## Priorities

1. Build prerequisite-aware SkillGraph, PrepLoop policy and server-graded Evidence Passport for synthetic learners.
2. Preserve Auralis tests and connect verified interview evidence through typed adapters.
3. Connect Cracked assessments and isolated grading, then Serviette and JobSearch via explicit interfaces.
4. Evaluate adaptation against fixed practice baselines.
5. Add verified identity and account-scoped storage before any public or real-student deployment.

## Stage 4 Cracked adaptation (implemented in this branch)

The existing Cracked `skills/interview/pattern-coach/SKILL.md` supplies the Socratic learning specification. PrepEzy implements original static exercises in `app/cracked.py`. No untrusted `SKILL.md` is executed. `PatternCoach` advances through checked stages, records hint requests and stores graded answers in SQLite. Only each pattern's first transfer result supplies one distinct DSA concept-recognition observation; retries cannot inflate independent evidence. This is not equivalent to independently executed algorithm implementations.

The `PatternCoach` Next.js component talks to local `/api/demo/.../cracked` endpoints. All profiles are synthetic; no remote agent or LLM is called.

## Stage 6: One local verified evidence pipeline

`UnifiedEvidence` (under `platform/services/api/app/unified.py`) reuses the **single** `LocalLab` SQLite connection and its lock. The service instantiates the Cracked-derived `PatternCoach` with the local-only namespace `local-device-only`, preserving historical synthetic demo profiles separately. The local Auralis coding endpoint calls `AuralisClient.grade_code` (with upstream test/source checks) before recording a normalized coding observation. Arbitrary browser-supplied scores are never accepted.

`GET /api/local/skillgraph` returns seven competency dimensions (SQL, DBMS, OS, CN, OOP, DSA concept recognition, restricted Python code) with first independent attempt counts, provenance reference IDs and goal-weighted next activities. These assessment types are **not** collapsed into one readiness score. Recommendations are an interpretable heuristic.

Resetting the workspace deletes local SQL, core, pattern attempts/hints and restricted Python evidence, without touching the old synthetic demo namespaces. The local browser now refreshes unified recommendations after each checked activity. **No authentication was added.**

## Stage 7: Docker-only code execution

`CodingArena` under `services/api/app/coding_arena.py` shares the local SQLite database and lock with `UnifiedEvidence`; it never opens a host interpreter for student source. All user code is written into temporary files and mounted read-only into short-lived Docker containers with `--network none`, `--read-only`, `--cap-drop ALL`, `--security-opt no-new-privileges`, `--user 65534:65534`, CPU/memory/PID limits and bounded `/tmp`.

Timed sessions are enforced by backend timestamps. Outputs are compared against deterministic private test inputs, and submitted code itself is not persisted (only SHA-256 and results). Source evidence is `prepezy-docker-isolated-code-runner`; a separate eighth skill dimension prevents coding performance being conflated with theoretical DSA pattern checks.

**This is an educational local judge, not a certified multi-tenant untrusted-code service.** Do not publicly expose its API or Docker daemon. Use immutable image digests, stronger isolation and independent security review before any public deployment.

## Stage 8: Serviette ingestion and retrieval boundary

NotesFolder writes safe Markdown/plain-text documents to PREPEZY_KNOWLEDGE_DIR, watched separately by an external Serviette indexer. ServietteGateway calls real versioned REST endpoints under /api/v1 (health, stats, documents, retrieve, rag); the upstream URL must resolve to local loopback. If upstream /rag returns 501, the gateway retrieves real passages instead and does not invent generated text. Metadata and citations come exclusively from indexed retrieval results. Saving a note and indexing it are separate asynchronous operations. The PrepLoop knowledge suggestion follows the verified local SkillGraph without changing skill evidence.

Pathway license and model credentials stay in the separate Serviette runtime. This is a trusted single-device prototype, not secure multi-tenant RAG.

## Stage 9: JobSearch Career Intelligence

CareerEngine shares the same local SQLite connection and RLock with the SkillGraph. A refresh makes explicit, read-only HTTPS GET requests to official Greenhouse and Lever public ATS endpoints. Arbitrary URLs embedded in job descriptions are never fetched by the backend. Returned descriptions are treated as untrusted data and rendered as text only. Jobs are stable provider/token/job-id snapshots; they can become stale and must be verified on the employer page before applying.

Matching is deterministic, role-aware and grounded in assessed SkillGraph first attempts. Unassessed requirements are unknown, not failures, and the system does not calculate invented job-match percentages. Candidate facts are self-reported rather than automatically inferred. Drafts use them only for human review; there is no send/apply endpoint. Status changes are purely manual.

This separately authored integration follows the discover/rank/review/outcome architecture of AI Job Search, MIT copyright 2026 Mads Lorentzen, without executing the original Claude Code agent workflows.

## Stage 10 — Resume document intelligence

ResumeIntelligence shares the LocalLab SQLite connection and lock. Explicit file import extracts selectable text from PDF (pypdf), DOCX (python-docx), UTF-8 TXT or Markdown; the original binary is discarded. Page/paragraph (document line) provenance is stored alongside extracted source lines and the SHA-256 hash of the uploaded bytes. Document size, number of PDF pages and DOCX expanded size are bounded. The engine does not invoke OCR, host code execution or outbound model services.

Comparison requires an actual snapshot from CareerEngine.get(job_id). Literal resume keyword mentions are reported with verbatim citations; independent code/SQL/Core SkillGraph evidence is reported separately. The role preparation plan prioritizes unmentioned posting requirements for factual review, mentioned-but-unassessed requirements for practice, and existing PrepLoop recommendations. Nothing here changes the independently verified SkillGraph. A local resume deletion and the global local reset remove all stored extracted text.

All candidate claims remain self-reported, and the web app deliberately does not produce an ungrounded ATS score or hiring predictions. This remains local only until identity, privacy, and hostile-document isolation have been independently addressed.

## Stage 11 — Project Lab architecture

ProjectLab shares UnifiedEvidence's SQLite connection/RLock and the same bounded-semaphore / DockerRunner infrastructure as CodingArena. Each original project milestone defines a stable stdin/stdout specification with server-side fixtures. The browser sees only public examples; hidden tests never become user-submitted correctness criteria. Every attempt is an actual Docker verdict with source SHA-256, language and timestamp. Advanced milestones require an accepted preceding milestone. No source text or learner-supplied arbitrary executable requirements are stored.

A separate set of fixed design-defense questions is checked by server-side answer keys only after at least one actual project milestone passes. Students must submit a technical rationale, which remains locally saved and explicitly **unreviewed**; it is not included in a grade or model-generated assessment. GitHub portfolio links are validated for shape but are not cloned, inspected, or counted as evidence of code correctness.

UnifiedEvidence now adds two **distinct** dimensions: project-build (first independent Docker milestone attempt) and project-defense (first checked multiple-choice decision). Retrying cannot overwrite first-attempt evidence. Local progression and career-role recommendations are transparent heuristics. Build Your Own X supplies curated external links only and is not copied or treated as a project execution API.

No authentication and no secure hosted multi-user sandbox yet. API must remain on 127.0.0.1; future deployment requires user isolation, quotas, stronger code isolation and independently reviewed student-submitted content.

## Stage 12 — Commit-pinned GitHub evidence boundary

GitHubProjectReview uses public, fixed-host GitHub REST GET requests only. A verified default-branch commit and tree SHA define a snapshot. Small UTF-8 files are retrieved by immutable blob SHA; the actual data are rehashed using Git blob SHA-1 before source markers can be recorded. Up to fourteen source files are inspected; truncated trees or empty/invalid samples are not represented as complete inspections. The database stores bounded excerpt/citation metadata and answers, not full source files. Credentials-like excerpt lines are redacted. External repository text is never executed as a prompt or treated as instructions.

Technical-defense questions use server-authored prompts selected by actual static source pattern; written explanations remain ungraded. The opt-in one-file smoke check runs only a pinned .py/.js/.java source with up to three learner-declared stdin/expected-stdout pairs inside the shared network-disabled DockerRunner, never arbitrary test commands. These results cannot confer SkillGraph grades; GET /api/local/skillgraph only adds an unscored github_review_context. All GitHub review data are removed by the full local reset.

No authentication or private GitHub repo integration; bind API to 127.0.0.1 only. Standalone Docker does not provide guaranteed hostile-code security. Rate limits and partial sampling are transparently reported.
