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

This is an opt-in integration with the **actual Auralis application**, not an invented question generator. Auralis can start interviews, progress through questions, record answers, and generate a genuine upstream **scripted, unscored** report. PrepLoop adds a ten-minute reflection step when an Auralis interview with recorded answers is completed. Auralis demo reports never alter SkillGraph's graded competency estimates.

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

The Next.js UI will show whether the **actual** local service is reachable. Use the Interview Practice section to start, answer, finish and view the real Auralis scripted report.

The integration is deliberately local-only: the adapter blocks remote/HTTPS upstream URLs, follows no redirects, sends no user documents, and exposes only reduced session details. Demo owner tokens are deterministic synthetic namespace labels, *not credentials*. No cross-device, production or real-student privacy guarantees exist.

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
