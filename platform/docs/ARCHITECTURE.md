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
