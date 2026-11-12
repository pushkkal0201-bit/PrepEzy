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

## Development priorities (authentication intentionally deferred)

This milestone **does not include login, registration, JWT, Supabase or any other account system**. Focus on the adaptive policy, evidence model, skill taxonomy, assessment and event contracts, original learning workflows, and tested integration boundaries. Identity can be added later behind a dedicated interface once the core works; demo IDs must never be treated as real user identity.

The new local API routes are:
- `GET /api/demo/skillgraph`: curriculum prerequisite graph.
- `GET /api/demo/learners/{learner_id}/roadmap`: evidence-based practice plan (15–120 minute budget).
- `GET /api/demo/learners/{learner_id}/evidence`: recorded server-graded outcomes.
- `GET /api/demo/learners/{learner_id}/next-question`: chooses a question for the currently prioritized skill.

No Auralis, Cracked skill execution, Serviette, or JobSearch runtime integration is claimed.

## Production warning

**This is a local prototype, not a multi-user release.** Its two learner identifiers are public synthetic names, not authenticated users. Do not deploy publicly or add real resumes, interviews, personally identifiable information or API keys. The demo API refuses startup unless `PREPEZY_ENV=development` (or unset). Its practice checks are not a hiring-readiness score.

## Build roadmap

See [integration matrix](docs/INTEGRATION_MATRIX.md) and [architecture](docs/ARCHITECTURE.md). The immediate milestones are deeper SkillGraph and PrepLoop tests, trusted evidence adapter contracts and verified Auralis integration, followed by Cracked execution adapters, isolated Serviette, JobSearch workflows and the adaptive project lab. Supabase and multi-user infrastructure are deliberately deferred.

Original third-party licenses and attribution must remain preserved. No claim of end-to-end integration or production readiness is made.
