# PrepEzy Platform — Adaptive Foundation

This is the first **implemented** student-facing foundation, developed in `platform/` alongside the existing Cracked agent-skill pack. The original repo root and its existing skill scripts are preserved.

## What works now

- Next.js interface for two clearly labeled **synthetic demo learners** with different target roles.
- FastAPI API offering ten server-scored knowledge questions and rule-based, goal-aware recommendations.
- Competency evidence from actual server-side answer checking, with a transparent, limited mastery estimate.
- Optional local SQLite persistence of demo events; without a DB path, attempts reset on API restart.
- Transparent prerequisite graph, per-learner evidence passport, suggested next question, and bounded adaptive practice roadmap.
- Read-only discovery of existing Cracked skill files. This is **not** executing Cracked, Auralis, Serviette, or JobSearch.
- Automated backend tests cover the adaptive foundation, Auralis adapters, Cracked practice and the new local-first assessment workflows. Check the latest CI results.

## Run on Windows

From the repository root, in CMD terminal 1:

```bat
cd platform\services\api
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In CMD terminal 2:

```bat
cd platform\apps\web
npm install
npm run dev
```

Open http://localhost:3000 after both processes are started. API documentation is at http://127.0.0.1:8000/docs.

Run tests from `platform\services\api`:

```bat
.venv\Scripts\python -m pytest -q
```

To store only **synthetic demo** attempts across local restarts, set an optional environment variable before starting the backend:

```bat
set PREPEZY_DEMO_DB=D:\Projects\prepezy-demo.sqlite
```

## Stage 3: Real Auralis local interview connector (authentication remains deferred)

This is an opt-in integration with the **actual Auralis application**, not an invented question generator. Auralis can start interviews, progress through questions, record answers, and generate a genuine upstream **scripted, unscored** report. PrepLoop adds a ten-minute reflection step when an Auralis interview with recorded answers is completed. Auralis demo reports never alter SkillGraph's graded competency estimates. **Auralis's independent restricted-AST coding lab DOES produce deterministic graded evidence**: a solution is evaluated against fixed public/hidden test cases, and each distinct challenge adds at most one Python competency observation. Repeated attempts do not inflate the independent evidence count.

The local API uses Auralis's real `/api/sessions`, `/start`, `/actions` and `/finish` endpoints, plus `/api/health`. Real student data, hosted providers and login are not enabled.

**Start Auralis separately** from your checkout at `D:\\Projects\\PrepEzy-Sources\\auralis-interview-studio\\auralis` (adjust path to your actual clone):

```bat
cd /d D:\\Projects\\PrepEzy-Sources\\auralis-interview-studio\\auralis
py -3.11 -m venv .venv
.venv\\Scripts\\python -m pip install -r requirements.txt
.venv\\Scripts\\python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Then, in your PrepEzy backend terminal, before starting uvicorn:

```bat
set PREPEZY_AURALIS_ENABLED=1
set PREPEZY_AURALIS_URL=http://127.0.0.1:8001
.venv\\Scripts\\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The Next.js UI will show whether the **actual** local service is reachable. Use the Interview Practice section to start, answer, finish and view the real Auralis scripted report. The Adaptive Coding Lab independently grades restricted Python submissions through Auralis and updates the Python evidence summary.

The integration is deliberately local-only: the adapter blocks remote/HTTPS upstream URLs, follows no redirects, sends no user documents, and exposes only reduced session details. Demo owner tokens are deterministic synthetic namespace labels, *not credentials*. No cross-device, production or real-student privacy guarantees exist.

## Stage 4: Cracked Pattern Coach — real local reasoning workflow

PrepEzy includes a deterministic adaptation of Cracked's Socratic [pattern-coach skill](../../skills/interview/pattern-coach/SKILL.md), not a claimed Claude Code execution. The Next.js module uses the local FastAPI service to guide four curated DSA patterns: two pointers, sliding window, binary search on the answer, and breadth-first search. Each has an ordered brute-force, insight, and transfer checkpoint. Students can request hints; answers are validated on the backend, and attempts, hints and transfer-check evidence are stored in SQLite.

- `GET /api/demo/cracked/patterns`: curated pattern catalog with attribution.
- `GET /api/demo/learners/{learner_id}/cracked/recommendation`: deterministic pattern suggestion.
- `GET /api/demo/learners/{learner_id}/cracked/patterns/{pattern_id}`: next step without its answer key.
- `POST /api/demo/learners/{learner_id}/cracked/patterns/{pattern_id}/hint`: record help and return a hint.
- `POST /api/demo/learners/{learner_id}/cracked/patterns/{pattern_id}/answers`: server-check the answer.
- `GET /api/demo/learners/{learner_id}/cracked/evidence`: attempt history and first-transfer-check evidence.

Only the first transfer check per distinct pattern contributes a DSA **concept-recognition** observation. A correct answer after assistance or retry may complete the lesson but does not retroactively count as unassisted proficiency. No arbitrary code is executed, and the larger Cracked OA simulator, company intelligence and core viva remain separate future milestones.

All data is synthetic and local; authentication remains deferred.

## Stage 5: Actual SQL execution and local Core CS assessment

This stage adds a **usable single-device workspace** rather than another synthetic learner selector. Choose a role (Backend, Data Analyst, ML or Full-stack), preferred language and daily study time. The setting persists in a local SQLite file (default `prepezy_local.sqlite` in the backend working directory).

- Five SQL challenges: JOIN, GROUP BY/HAVING, anti-join, correlated subquery and window ranking.
- User-entered **read-only SQL is executed in isolated in-memory SQLite fixture databases**, with a SQLite authorizer, permitted built-in functions, progress-handler time limit and row/output limits. Expected results are computed by running reference queries for **two different datasets**. No OS commands, external databases, network access or arbitrary Python scripts are executed.
- Twelve original DBMS, OS, CN and OOP questions graded on the server.
- Evidence-based personal study roadmap that uses target-role relevance, distinct challenges attempted and **first-try** correctness (a retry cannot inflate independent evidence).
- Persisted local attempts with SHA-256 hashes of submitted SQL; private query text is not saved in history. Read-only evidence endpoint and delete-local-history action.
- Local-network middleware denies remote peers and untrusted browser origins. **This is not real account authentication and cannot protect against malicious local programs.**

Run the API on `127.0.0.1` only. To select a persistent local database explicitly in Windows CMD before starting FastAPI:

```bat
set PREPEZY_LOCAL_DB=D:\Projects\prepezy_local.sqlite
```

**Local endpoints:** `GET /api/local/profile`, `PUT /api/local/profile`, `GET /api/local/overview`, `GET /api/local/sql/challenges`, `POST /api/local/sql/attempts`, `GET /api/local/viva/questions`, `POST /api/local/viva/attempts`, `GET /api/local/evidence`, `DELETE /api/local/data`.

These are genuinely executed/graded exercises over *fictional fixture records*. They are not a claim that the entire Cracked Core Viva, full remote Auralis, Serviette, JobSearch or all ten repo feature sets have been integrated. The older Auralis and Cracked experiment modules still retain clearly labeled synthetic profiles.

## Stage 6 — Unified, verified, local-first SkillGraph

PrepEzy now connects **four genuinely checked assessment sources** into the same single-device evidence pipeline:

1. Five SQL practicals: independently executed queries against two fixture datasets.
2. Twelve Core CS Viva questions: server-checked original answer keys.
3. Four Cracked-inspired guided DSA patterns: only the **first transfer attempt** per pattern is an independent concept-recognition observation; hints and retries remain visible.
4. Optional Auralis restricted Python practice: only validated `restricted_ast_test_runner` results can add code evidence.

The `UnifiedEvidence` service shares the same persistent `PREPEZY_LOCAL_DB` file as the local SQL/Core assessments and the local Pattern Coach, so one device has **one study record without login**. The Next.js workspace displays evidence counts, seven skill dimensions, per-source provenance, coverage and a goal-aware PrepLoop roadmap. Practice from the local Pattern Coach or Auralis coding panel updates this same graph after each server-checked result. The previous synthetic learner exercises remain isolated and are not silently imported.

Routes:
- `GET /api/local/skillgraph` — seven skills and a transparent adaptive roadmap.
- `GET /api/local/unified-evidence` — source-attributed evidence events.
- `GET /api/local/cracked/patterns`, `GET /api/local/cracked/patterns/{pattern_id}`, and `POST .../hint`, `POST .../answers` — guided pattern practice in the **real local** workspace.
- `GET /api/local/auralis/challenges`, `POST /api/local/auralis/code`, `GET /api/local/auralis/evidence` — optional actual Auralis restricted coding evaluations.
- `DELETE /api/local/data` — clears SQL, Core CS, local Cracked attempts/hints and Auralis coding records, and resets preferences.

Evidence sources are deliberately **not** averaged into a fake global proficiency score. First unassisted attempts and missing evidence inform explainable recommendations. Scripted Auralis interviews remain **unscored** and do not invent skill measurements.

### Limitations

- No authentication or public multi-user deployment. Keep FastAPI bound to `127.0.0.1` and avoid storing personal student data.
- Cracked's full CLI/agent workflows, unrestricted programming judge and timed OA platform are **not** integrated. The local Pattern Coach is a PrepEzy implementation of Cracked's learning method.
- Auralis code evaluation is real only when the separate local Auralis service is running and advertises its restricted runner. Scripted interviews remain separate and unscored.
- Serviette RAG and JobSearch career services, the Adaptive Build Lab, Skill Studio, and development-only tooling are future milestones.

## Development priorities (authentication intentionally deferred)

This milestone **does not include login, registration, JWT, Supabase or any other account system**. Focus on the adaptive policy, evidence model, skill taxonomy, assessment and event contracts, original learning workflows, and tested integration boundaries. Identity can be added later behind a dedicated interface once the core works; demo IDs must never be treated as real user identity.

The new local API routes are:
- `GET /api/demo/skillgraph`: curriculum prerequisite graph.
- `GET /api/demo/learners/{learner_id}/roadmap`: evidence-based practice plan (15–120 minute budget).
- `GET /api/demo/learners/{learner_id}/evidence`: recorded server-graded outcomes.
- `GET /api/demo/learners/{learner_id}/next-question`: chooses a question for the currently prioritized skill.

Auralis is **optionally** connected to the actual local scripted-demo service when enabled and running. Cracked execution, Serviette and JobSearch are not yet integrated.

## Production warning

**This is a single-device local workspace, not a multi-user release.** Its two learner identifiers are public synthetic names, not authenticated users. Do not deploy publicly or add real resumes, interviews, personally identifiable information or API keys. The demo API refuses startup unless `PREPEZY_ENV=development` (or unset). Its practice checks are not a hiring-readiness score.

## Build roadmap

See [integration matrix](docs/INTEGRATION_MATRIX.md) and [architecture](docs/ARCHITECTURE.md). The immediate milestones are deeper SkillGraph and PrepLoop tests, trusted evidence adapter contracts and verified Auralis integration, followed by Cracked execution adapters, isolated Serviette, JobSearch workflows and the adaptive project lab. Supabase and multi-user infrastructure are deliberately deferred.

Original third-party licenses and attribution must remain preserved. No claim of end-to-end integration or production readiness is made.
