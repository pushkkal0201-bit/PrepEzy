# PrepEzy

**Local-first technical interview and placement preparation — one workspace, multiple evidence-backed practice tools.**

PrepEzy brings coding assessment, DSA coaching, SQL and Core CS practice,
project work, resume and career preparation, and mock interview rehearsal
into one Next.js + FastAPI application.

> **Development scope:** This is an **unauthenticated single-device** application
> for trusted local use, not a hosted placement service or automated hiring
> decision system. Keep the API on **127.0.0.1**, do not publish its ports,
> and do not share personal documents with other users of the machine.

## Quick start (Windows)

**Requirements:** Python **3.11**, Node.js **22**, npm; Docker Desktop in
Linux-container mode for Java/Python/JavaScript coding execution.
Optional Auralis and Serviette integrations require separate local services.

Clone the consolidated **main** branch:

~~~bat
cd /d D:\Projects
git clone https://github.com/pushkkal0201-bit/PrepEzy.git
cd PrepEzy
~~~

Open **CMD terminal 1** for the FastAPI backend:

~~~bat
cd /d D:\Projects\PrepEzy\platform\services\api
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
set PREPEZY_LOCAL_DB=D:\Projects\PrepEzy\prepezy_local.sqlite
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
~~~

Open **CMD terminal 2** for the Next.js frontend:

~~~bat
cd /d D:\Projects\PrepEzy\platform\apps\web
npm install
npm run dev
~~~

Open **http://localhost:3000**. API documentation is at
**http://127.0.0.1:8000/docs**.

Already have a local checkout? First preserve or commit any local changes,
then run **git switch main** and **git pull --ff-only origin main**.

### Docker Coding Arena

Start Docker Desktop and explicitly pre-pull images:

~~~bat
docker pull python:3.11-alpine
docker pull node:22-alpine
docker pull eclipse-temurin:21-jdk-alpine
~~~

User-submitted code uses the restricted Docker runner with no host execution
fallback. Docker is **not** a hardened, hostile-code multi-tenant boundary.
Do not expose the unauthenticated API publicly.

## Unified modules

| Workspace | Implemented capability | Important boundary |
| --- | --- | --- |
| SkillGraph + PrepLoop | Shared local assessed evidence, provenance and practice recommendations | No fabricated universal mastery or hiring score |
| Pattern Coach | Curated DSA checkpoints, hints and transfer-check evidence | Guided concept checks, not unrestricted OA judging |
| SQL + Core CS | Bounded real SQLite query execution and server-checked questions | Curated fixtures, not real production databases |
| Coding Arena | Docker-executed Python/Java/JavaScript tasks with predefined tests | Needs running Docker and images |
| Adaptive Project Lab | Project milestones, checked design choices and artifact links | Prose and repository links are not verified |
| GitHub Review Studio | Public read-only commit-pinned source inspection and consented smoke checks | Limited sampling, no authorship proof |
| Mock Interview Studio | Evidence-grounded questions, learner-directed follow-ups, transcripts and reflection | Free-text answers remain ungraded |
| Resume Studio | Local PDF/DOCX analysis and role preparation | Not a verified recruiter assessment |
| Career Studio | Public Greenhouse/Lever discovery and local application records | User-controlled status; no automatic applications |
| Knowledge Hub | Local notes and optional source-cited Serviette retrieval | Serviette must be separately started and enabled |
| Auralis connector | Optional local scripted interviews and independently checked restricted Python tasks | Requires separately started Auralis |
| Cracked skills pack | Original agent-skill reference materials preserved alongside the app | Skills are not all executed by PrepEzy |

**One frontend:** platform/apps/web/app/ contains the local learner workspace,
including the UnifiedProgress, MockInterviewStudio, CodingArena, KnowledgeHub,
CareerStudio, ResumeStudio, ProjectLab and GitHubReviewStudio components.

**One backend:** platform/services/api/app/main.py exposes modular FastAPI
routes. Related assessed events share a local SQLite database selected through
the PREPEZY_LOCAL_DB environment variable.

### Optional connections

- **Auralis:** start its local server separately; set PREPEZY_AURALIS_ENABLED=1
  and PREPEZY_AURALIS_URL=http://127.0.0.1:8001 before starting PrepEzy.
- **Serviette:** start the local service and follow the setup under
  [platform documentation](platform/README.md).
- **GitHub Review:** supports public repositories, commit-pinned REST reads and
  explicit opt-in checks; no private OAuth or ownership verification.
- **Career boards:** public ATS discovery without automatic applications.

## Verify the integrated application

In **platform\services\api**, after installing dependencies:

~~~bat
.venv\Scripts\python -m pytest -q
~~~

In **platform\apps\web**:

~~~bat
npm run build
~~~

GitHub Actions validates API tests, web compilation, optional Auralis integration,
and Docker execution. Check the **latest main branch** status before relying on a build.

## Project structure

~~~text
PrepEzy/
├── platform/
│   ├── apps/web/               # Next.js frontend
│   ├── services/api/           # FastAPI and local SQLite modules
│   └── docs/                   # Design and integration documentation
├── skills/                     # Preserved Cracked agent skills
├── evals/                      # Agent-skill evaluation materials
├── scripts/                    # Original skill utilities
├── UPSTREAM_CRACKED_README.md  # Original README and attribution
└── README.md                   # Unified PrepEzy entry point
~~~

See [the platform guide](platform/README.md) for module-specific instructions
and [Stage 13 documentation](platform/docs/ADAPTIVE_MOCK_INTERVIEWS.md).

## Credits and scope

PrepEzy integrates original local modules alongside adapted open-source ideas.
The preserved [Cracked README](UPSTREAM_CRACKED_README.md) credits
[Nishant Tiwari's Cracked project](https://github.com/nishant-Tiwari24/cracked).
The original MIT license and attribution remain in this repository.
Auralis, Serviette and JobSearch are represented by their actual integration
boundaries; their complete upstream applications are not automatically bundled.

Authentication, production deployment, independently graded free-text interviews
and multi-tenant hardening remain future work.
