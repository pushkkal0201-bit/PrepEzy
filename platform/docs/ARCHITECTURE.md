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

## Isolation

The demo uses synthetic account IDs that are *not* authentication. Do not expose them publicly. In production, authenticate and authorize all writes and reads, enforce row-level ownership at the database boundary, isolate code execution, limit third-party agent permissions, and validate retrieved document ownership before prompting an LLM.

## Priorities

1. Make real identity and storage safe.
2. Preserve Auralis tests and migrate actual interview evidence.
3. Connect Cracked assessment workflows to independently graded outcomes.
4. Connect Serviette and JobSearch through explicit typed interfaces.
5. Evaluate adaptation against fixed-practice baselines, then add new capabilities.
