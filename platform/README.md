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

## Stage 7 — Real Docker-isolated Java, Python and JavaScript Coding Arena

PrepEzy now includes an **actual multi-language coding judge**, not an LLM score or visual mock-up. Users can type complete programs, start practice or timed sessions (15, 30, 45, or 60 minutes), run tests and save verified execution outcomes to the same local SkillGraph and Evidence Passport.

**Requirements:** Docker Desktop running in **Linux-container mode** (Windows users should enable the WSL2 backend). In CMD or PowerShell, pull the three images **before** using the judge:

```bat
docker pull python:3.11-alpine
docker pull node:22-alpine
docker pull eclipse-temurin:21-jdk-alpine
docker image ls
```

These images are pinned by major/minor tag for local development; pin immutable digests for production. Docker images are not silently downloaded by the app.

**Real execution:** Every submitted Java, Python or JavaScript source file is mounted read-only into a newly created, unprivileged container with network disabled, read-only root filesystem, dropped Linux capabilities, `no-new-privileges`, memory/PID/CPU limits, bounded temporary filesystem, bounded output, and an enforced wall-time budget. No host execution fallback exists. Java code must use `public class Main`, read standard input and print standard output. The backend checks outputs against private predefined tests, records the verdict and a SHA-256 hash of the submitted source (not the source itself). Four original coding problems are included; expand the bank in later stages.

**Local APIs** (no login; bind to `127.0.0.1`):
- `GET /api/local/arena/problems` — public problem metadata, examples and starter code (no hidden cases).
- `GET /api/local/arena/status` — installed-image readiness and active session.
- `POST /api/local/arena/sessions` — start timed or practice session.
- `POST /api/local/arena/sessions/{session_id}/finish` — finish current session.
- `POST /api/local/arena/submissions` — execute, grade and record a submission.
- `GET /api/local/arena/evidence` — persisted verdict history.

A new **eighth SkillGraph dimension** called *Executed coding problems* uses only the first submission per distinct task as independent evidence. Graded execution, DSA pattern recognition, core MCQs and restricted Auralis code remain visibly different categories. Answering a pattern-recognition question never proves executable coding competence.

**Safety and limitations:** This is for a **trusted, single-user local machine only**, not a public or adversarially hardened code-execution service. Docker isolation provides defense in depth but is not a guarantee of complete security. Never expose an unauthenticated judge to the internet. Neither the full Cracked OA feature set nor untrusted public contest submissions are production-ready. Java/Python/JavaScript judge tests run in a separate, opt-in Docker integration CI job.

## Stage 8 — Serviette-powered Knowledge Hub

This stage integrates Serviette (https://github.com/pathwaycom/serviette) via its **real REST API**. Serviette is MIT-licensed (© 2026 Sergey Kulik); the underlying Pathway runtime additionally requires a **free Pathway license key**. Serviette runs as an independent local service and is not bundled into PrepEzy.

Working modules when Serviette is running:
- Save, open, edit and delete text/Markdown notes in the watched folder with filename validation and a 50 KB document-size limit.
- Report SAVED notes separately from documents actually indexed by Serviette.
- Ask questions via POST /api/v1/retrieve and display actual retrieved source passages, metadata, scores and file citations.
- Optionally call POST /api/v1/rag when Serviette has an answer-generating LLM configured. If upstream returns 501, show real retrieved passages instead, *without claiming a generated answer*.
- Show real /api/v1/health, /api/v1/stats and /api/v1/documents status.
- Use a suggested search topic from the current PrepLoop SkillGraph, clearly labeled as a suggestion rather than a search result.

### Running Serviette from Windows with WSL2

1. Create D:\Projects\PrepEzy-Knowledge in Windows. In WSL2 Ubuntu this appears as /mnt/d/Projects/PrepEzy-Knowledge.
2. In WSL2 Ubuntu, create a separate Python 3.12 venv and install Serviette, for example pip install "serviette[local]" --extra-index-url https://download.pytorch.org/whl/cpu. This may download substantial local embedding models and libraries. Consult the upstream Serviette README for supported model/provider alternatives and more precise prerequisites.
3. Obtain a free Pathway key from https://pathway.com/framework/get-license and export PATHWAY_LICENSE_KEY in the WSL2 terminal. Never commit it to GitHub.
4. Run serviette wizard, configure the filesystem source as /mnt/d/Projects/PrepEzy-Knowledge, choose a local embedder and DuckDB (or another supported backend), and save a config file OUTSIDE PrepEzy. Start serviette up --config config.yaml. Default API port is 8989.
5. In the Windows CMD terminal where you run the PrepEzy API set:
    set PREPEZY_KNOWLEDGE_DIR=D:\Projects\PrepEzy-Knowledge
    set PREPEZY_SERVIETTE_ENABLED=1
    set PREPEZY_SERVIETTE_URL=http://127.0.0.1:8989
6. Restart the PrepEzy backend on 127.0.0.1:8000 and Next.js on localhost:3000, open Knowledge Hub, recheck Serviette, save a note, and refresh the indexed catalog. Windows-to-WSL2 localhost forwarding must be enabled; do not expose the unauthenticated service on public interfaces.

The REST integration is opt-in; if Serviette is missing, the UI reports unavailability instead of simulating retrieval. Retrieved snippets may be sent to an external LLM provider if configured in Serviette: keep sensitive student data out of this local no-auth prototype.

### Verification and limitations

Stage 8 API tests validate the current upstream Serviette HTTP schema with a mocked transport, verifying note persistence, provenance, genuine fallback behavior and error states. They do NOT claim an actual Pathway indexer with live documents ran inside CI, because that requires a separate dependency-heavy installation and Pathway license. A full live-service validation should be performed after you configure Serviette.

No multi-user document permissions, robust prompt-injection security or confidential student-data workflows are included; authentication remains deferred as requested.

## Stage 9 — JobSearch-inspired Career Intelligence

PrepEzy now supports actual public employer-job discovery from Greenhouse and Lever ATS job-board JSON APIs. There are no preloaded fake openings. Enter a real employer's public job-board token, refresh the source, and review the actual returned postings. Greenhouse documentation: https://docs.greenhouse.io/job-board . Lever documentation: https://github.com/lever/postings-api .

The original AI Job Search framework (https://github.com/ai-job-search-dev/ai-job-search, MIT, copyright 2026 Mads Lorentzen) is a Claude Code skill-and-command system, not a turn-key web API. PrepEzy implements its discover, evaluate, draft, review and outcome workflow as original code. It does NOT execute the original JobSearch agent skills, portal scrapers, Gmail integration or LaTeX CV compiler.

### What works

- Up to 12 Greenhouse or Lever sources from employer board tokens. Backend fetches JSON only from the two fixed official public ATS endpoints via HTTPS GET. No applications or outreach are automatically sent.
- Saved job snapshots include provider, official posting link, timestamp, description and extracted technical requirements. Each provider failure is shown rather than filled with synthetic jobs.
- Role-aware comparison uses PrepEzy's actual local SkillGraph evidence and distinguishes limited positive assessed evidence, first-attempt practice gaps and requirements with no assessment evidence. No hiring probability, ATS percentage or guaranteed fit.
- A private on-device profile for self-reported, actual projects and experience. Deterministic draft generation copies only user-supplied facts, avoids invented contact details or achievements, and always requires human review.
- Manual application status tracking: saved, applied, interviewing, offer, rejected, withdrawn. Recording an outcome NEVER submits an application. Data lives in the local SQLite workspace.
- Full Next.js Career Intelligence panel and delete-local-career-data action.

### Running Stage 9

No additional Python or Node package is required beyond the previous stage. Start the existing local FastAPI backend at 127.0.0.1:8000 and Next.js at localhost:3000. In the Career Intelligence section, choose an employer's Greenhouse or Lever board, enter its token from its public careers URL, and press Add board then Refresh live job boards. Choose a posting to inspect its employer link and comparison to SkillGraph. Provide your own true experience statements to generate an editable review draft. Manually mark applications and outcomes after you take action outside PrepEzy.

### Security and verification limits

User-provided board tokens are validated and cannot change the HTTP host. Posting HTML is converted into plain text; script/style and some hidden content are filtered, and posting text never becomes LLM instructions. Do not assume this sanitization is complete against every adversarial posting.

CI tests verify real adapter code against mocked official JSON schemas, local database persistence, security boundaries, no-send behavior, and evidence-based explanations. CI does not claim that any employer is hiring today, or that a real external employer board was queried during testing. Live functionality requires a valid public board token and successful upstream requests.

Authentication remains deferred. Use only on a trusted local machine, never publicly deploy, and do not commit personal career data to GitHub.

## Stage 10 — Local Resume Intelligence and role-specific preparation

**Implemented:** Real PDF, DOCX, UTF-8 TXT and Markdown resume text extraction (not a simulated parser); source-located excerpts; conservative document-structure checks; literal skill mention detection; comparison with an employer posting actually fetched through the Career Studio; separate verified SkillGraph evidence; and a role-specific study/review plan.

### Use it

Install Stage 10 dependencies once after fetching this branch:

    cd /d D:\Projects\PrepEzy-Platform\platform\services\api
    .venv\Scripts\python -m pip install -r requirements.txt

Start the existing FastAPI backend on 127.0.0.1:8000 and Next.js frontend on localhost:3000. In Resume Intelligence, explicitly select and import a PDF/DOCX/TXT/Markdown file (maximum 2 MiB; PDFs up to 8 pages), review its extraction/sections, and choose a real job that you previously fetched in Career Intelligence. The resulting comparison shows the original resume snippets with page/line or document/line locations, unmentioned posting requirements, separately assessed SkillGraph outcomes, and next actions based on actual available evidence.

No account system was added. **Only extracted text and provenance are saved in the local SQLite database; original uploaded PDF/Word bytes are not stored.** The local resume can be replaced or deleted, and the global reset also deletes it. The API never sends the resume to an external LLM, ATS provider or employer. Do not use this unauthenticated version for confidential resumes, or expose it to other devices.

### Trust and verification limits

- All resume statements are **self-reported**. Seeing a technology word on a resume does not verify the user can use it; actual SQL/coding assessments are reported as a distinct category.
- PrepEzy does not invent an ATS match percentage, infer personal achievements, certify job readiness, claim that a company reviewed the resume, or submit applications.
- Images and scanned/image-only PDFs are explicitly **not OCR-processed**. The importer reports that there is insufficient selectable text rather than inventing an extraction.
- It is a simple text/heading extractor. Complex PDF layouts, columns, graphics, tables, and skill synonyms can lead to omissions. Users should inspect the text sample and review findings.
- Uploaded PDF/DOCX parsing is performed by local Python libraries with file, page and decompression limits; these are not a substitute for fully hardened adversarial file processing in a public service.
- Candidate job requirements are selected from previously fetched public Greenhouse or Lever snapshots; availability and terms may have changed.

### Local API

- GET /api/local/resume/status
- POST /api/local/resume/upload (multipart form file)
- GET /api/local/resume/inspection
- GET /api/local/resume/jobs/{job_id}/analysis
- DELETE /api/local/resume

**Verification:** Automated tests include actual selectable-text PDF parsing (hand-built valid PDF), DOCX parsing using python-docx, UTF-8 parsing, malformed and image-only PDF rejection, decompression limits, local persistence and deletion, linked job/SkillGraph comparison, no fake assessments, and origin policy.

## Stage 11 — Adaptive Project Lab and Project Defense

This stage turns Build Your Own X (https://github.com/codecrafters-io/build-your-own-x) into **curated external tutorial links plus PrepEzy-authored executable milestones**. The upstream repository is a list of independently published tutorials, not an application API, automated grader or blanket permission to republish authors' tutorials. This project does not copy their content.

### Working local features

- **Three project tracks**: a tiny in-memory key-value store (database topic), an inverted document index (search engine topic), and a small arithmetic expression interpreter (programming language topic). These are educational components, **not complete commercial databases, search engines, or interpreters**.
- **Six original executable milestones**: each has a precise input/output contract, one public example and additional private fixtures. Source submissions run inside the existing Docker-only Java, Python and JavaScript judge with bounded resources. An unavailable Docker image causes an explicit error rather than unsafe host execution or a fabricated result.
- **Prerequisite enforcement**: an advanced milestone cannot be submitted until its predecessor passed all Docker tests.
- **Six design-defense questions**, each checked against an original correct answer. The student also writes technical reasoning, which is stored locally for self/mentor review but **not graded by AI** or counted as a verified quality score. Defense unlocks after at least one executable milestone passes.
- **Adaptive project recommendation** based on the chosen career role and actual passed/attempted milestones; the next project task is transparent and deterministic.
- **Unified SkillGraph** now has **10 separate dimensions**. Docker project milestones and checked design choices contribute as distinct evidence types; personal rationale and user-submitted GitHub project links are never silently counted as independently verified code or qualifications. Only the **first attempt** on each distinct milestone/question determines baseline assessment evidence.
- **Optional GitHub project artifact link** and implementation notes, stored as *self-reported, unverified*. The project lab does not clone or execute repositories supplied by the user.
- **Persistence and deletion** in the single-device SQLite database. Global local data reset also deletes local project milestones, defense reasoning and artifact links.

### Running

Switch to `feat/adaptive-project-lab` and use the existing backend (`127.0.0.1:8000`) and frontend (`http://localhost:3000`). For real Java/Python/JavaScript submissions, start Docker Desktop in Linux-container mode and pull the Stage 7 images:

```bat
docker pull python:3.11-alpine
docker pull node:22-alpine
docker pull eclipse-temurin:21-jdk-alpine
```

Go to **Adaptive Project Lab**. Select a curated project or the recommended next project. Open the public test example, write a full stdin/stdout solution, and execute real private test cases. Complete milestones to unlock harder contracts; respond to technical-defense questions with a selected answer **and your own written reasoning**. If you attach a GitHub repository URL, the app labels it unverified.

### Safety, intellectual-property and validation limits

This is a trusted, **single-device educational prototype**, not an adversarially hardened hosted build service. No authentication has been added. The Docker code execution engine never runs student source directly on the Windows host, but Docker is not an absolute security boundary; never publicly expose this unauthenticated API. External linked tutorials have their own copyright/license terms; use them as references rather than copying or redistributing them. The project-defense objective questions are deterministic knowledge checks, not a full human or AI architectural evaluation. The stage intentionally avoids public repository cloning, LLM scoring of free-form technical narratives, invented project completion, and arbitrary command execution.

**Verification:** In addition to unit/API contract tests, the existing opt-in Docker GitHub Actions job executes real Python/JavaScript/Java programs against the first project milestone. More extensive reliability/performance tests and open-ended project-defense evaluations remain future work.

## Stage 12 — GitHub Project Evidence and Technical Defense

A real **PUBLIC, read-only GitHub REST integration** inspects a student-chosen repository URL, resolves its default-branch HEAD to an immutable commit and tree, and reads a bounded source subset. No git cloning, arbitrary URL crawling, automatic repository commands, fabricated code findings or authorship assertions.

**Implemented:**
- Accept only HTTPS `github.com/owner/repo` roots; outbound traffic is limited to read-only `api.github.com` repository, commit, tree and blob endpoints. No GitHub token is required for public repos; API rate limits apply. Private repos, truncated trees, very large files and unrecognized formats are explicitly unsupported. Limit: 14 small UTF-8 file inspections per snapshot, up to 24 KB per eligible file.
- Verify each fetched blob's **Git SHA-1** from actual content; save a timestamped, commit-pinned source inventory and specific code-marker line citations. Test-file discovery is based on filenames only, **not evidence that tests passed**. Missing findings in the bounded subset are never treated as proof of missing features.
- Source-triggered technical-defense prompts (routes, database actions, tests, React state, networking or algorithms). Explanations are saved locally for self/mentor review and explicitly **not graded**; project quality, code security and ownership are not inferred from regex markers.
- Optional, **explicitly user-approved** smoke check for one previously inspected standalone Python/JavaScript/Java file. The file is retrieved at its exact pinned Git blob; the student supplies one to three stdin/expected-stdout cases. The existing restricted, network-disabled Docker runner executes actual source. **No arbitrary shell command, npm/pytest command, repository cloning or host execution**. A matching output means only that the actual program matched the *student's own declared expectation*, NOT that independently authored tests passed.
- A **non-scoring GitHub review context** is included in `GET /api/local/skillgraph`. Static inspections, written explanations and self-defined smoke tests NEVER increase or reduce SkillGraph mastery or modify assessment event count. All data can be deleted locally; authentication is still deferred.
- A Next.js GitHub Review Studio with snapshots, source-linked questions, ungraded response history, file selection, explicit approval checkbox, actual Docker verdicts and deletion controls.

**Run:** Update to the Stage 12 branch and start the existing local FastAPI backend on 127.0.0.1:8000 and Next.js frontend on localhost:3000. Open **GitHub Project Evidence**, inspect a public repo, select an actual source citation and write your technical explanation. Running a standalone repo file is strictly optional; pull the Stage 7 Docker image for Python, Node or Java and approve the exact file and expected output before doing so.

**Verification boundary:** Contract tests exercise actual GitHub REST metadata/tree/blob formats via mocked HTTP responses (not live GitHub network scans inside CI). A separate opt-in Docker job executes real Python/JavaScript/Java pinned-source smoke programs, using mock GitHub responses. Real public repository inspection requires GitHub access and sufficient API quota at runtime. The code is a trusted single-device prototype, **not** a secure public untrusted-code execution service. Do not expose the unauthenticated API to the internet.

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
