# PrepEzy Platform — Adaptive Foundation

This is the first **implemented** student-facing foundation, developed in `platform/` alongside the existing Cracked agent-skill pack. The original repo root and its existing skill scripts are preserved.

## What works now

- Next.js interface for two clearly labeled **synthetic demo learners** with different target roles.
- FastAPI API offering ten server-scored knowledge questions and rule-based, goal-aware recommendations.
- Competency evidence from actual server-side answer checking, with a transparent, limited mastery estimate.
- Optional local SQLite persistence of demo events; without a DB path, attempts reset on API restart.
- Transparent prerequisite graph, per-learner evidence passport, suggested next question, and bounded adaptive practice roadmap.
- Read-only discovery of existing Cracked skill files. This is **not** executing Cracked, Auralis, Serviette, or JobSearch.
- Twenty automated backend tests, including input validation, persistence, different learning goals and separate demo profiles.

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

- \`GET /api/demo/cracked/patterns\`: curated pattern catalog with attribution.
- \`GET /api/demo/learners/{learner_id}/cracked/recommendation\`: deterministic pattern suggestion.
- \`GET /api/demo/learners/{learner_id}/cracked/patterns/{pattern_id}\`: next step without its answer key.
- \`POST /api/demo/learners/{learner_id}/cracked/patterns/{pattern_id}/hint\`: record help and return a hint.
- \`POST /api/demo/learners/{learner_id}/cracked/patterns/{pattern_id}/answers\`: server-check the answer.
- \`GET /api/demo/learners/{learner_id}/cracked/evidence\`: attempt history and first-transfer-check evidence.

Only the first transfer check per distinct pattern contributes a DSA **concept-recognition** observation. A correct answer after assistance or retry may complete the lesson but does not retroactively count as unassisted proficiency. No arbitrary code is executed, and the larger Cracked OA simulator, company intelligence and core viva remain separate future milestones.

All data is synthetic and local; authentication remains deferred.

## Development priorities (authentication intentionally deferred)

This milestone **does not include login, registration, JWT, Supabase or any other account system**. Focus on the adaptive policy, evidence model, skill taxonomy, assessment and event contracts, original learning workflows, and tested integration boundaries. Identity can be added later behind a dedicated interface once the core works; demo IDs must never be treated as real user identity.

The new local API routes are:
- `GET /api/demo/skillgraph`: curriculum prerequisite graph.
- `GET /api/demo/learners/{learner_id}/roadmap`: evidence-based practice plan (15–120 minute budget).
- `GET /api/demo/learners/{learner_id}/evidence`: recorded server-graded outcomes.
- `GET /api/demo/learners/{learner_id}/next-question`: chooses a question for the currently prioritized skill.

Auralis is **optionally** connected to the actual local scripted-demo service when enabled and running. Cracked execution, Serviette and JobSearch are not yet integrated.

## Production warning

**This is a local prototype, not a multi-user release.** Its two learner identifiers are public synthetic names, not authenticated users. Do not deploy publicly or add real resumes, interviews, personally identifiable information or API keys. The demo API refuses startup unless `PREPEZY_ENV=development` (or unset). Its practice checks are not a hiring-readiness score.

## Build roadmap

See [integration matrix](docs/INTEGRATION_MATRIX.md) and [architecture](docs/ARCHITECTURE.md). The immediate milestones are deeper SkillGraph and PrepLoop tests, trusted evidence adapter contracts and verified Auralis integration, followed by Cracked execution adapters, isolated Serviette, JobSearch workflows and the adaptive project lab. Supabase and multi-user infrastructure are deliberately deferred.

Original third-party licenses and attribution must remain preserved. No claim of end-to-end integration or production readiness is made.
