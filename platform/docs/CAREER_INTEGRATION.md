# PrepEzy Stage 9 — JobSearch Career Intelligence

## Source projects and credit

- AI Job Search: https://github.com/ai-job-search-dev/ai-job-search (MIT, copyright © 2026 Mads Lorentzen)
- Greenhouse Job Board API: https://docs.greenhouse.io/job-board
- Lever Postings API: https://github.com/lever/postings-api

The upstream AI Job Search project is a Claude Code skill/command framework, not an HTTP service. This stage implements a separate, original Python/FastAPI and Next.js career pipeline based on its discover -> rank -> draft -> review -> outcome workflow. The original AI agents and portal scripts are not executed.

## Actual API integrations

- Greenhouse: GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true
- Lever: GET https://api.lever.co/v0/postings/{board_token}?mode=json&limit=100

Only these two fixed API domains can be contacted by the career backend. Up to 12 explicit employer sources are supported, with a maximum of 100 parsed posts per board refresh and a response size limit. A network error, invalid data or no published jobs is reported honestly; no results are fabricated. The stored job record has provider, board token, external posting identifier, original URL, text, requested-skill tags and UTC fetch timestamp.

These are snapshots. There is no guarantee that listings are open when a student later views or applies to them. Search is over locally fetched jobs, not a global search engine.

## Evidence matching

The CareerEngine uses UnifiedEvidence.skillgraph from the actual local SQL, Core CS, Cracked-derived pattern and executed coding assessments. Requested technical skills with matching positive assessment evidence are labeled limited positive evidence; absent assessment records remain unassessed rather than unqualified. Other extracted skills are simply listed as not evaluated by the current assessments. No hiring probabilities or fabricated ATS fit percentages.

## Resume and application drafts

Students can save their own truthful career facts as plain text in local SQLite. Drafts quote only these self-reported facts and the job title and employer from the retrieved board. Drafts carry explicit review-only markings, including no submission claim. There is no automatic network POST to an employer or email sender. Manually setting a status to applied does NOT submit an application.

## API routes

- GET /api/local/careers/boards
- POST /api/local/careers/boards
- DELETE /api/local/careers/boards/{provider}/{token}
- POST /api/local/careers/refresh
- GET /api/local/careers/profile
- PUT /api/local/careers/profile
- GET /api/local/careers/jobs
- GET /api/local/careers/jobs/{job_id}
- GET /api/local/careers/jobs/{job_id}/drafts
- POST /api/local/careers/jobs/{job_id}/drafts
- GET /api/local/careers/applications
- PUT /api/local/careers/applications/{job_id}
- DELETE /api/local/careers/data

## Trust boundaries and next development

External descriptions are untrusted data. The backend strips basic HTML, embedded scripts, hidden content and selected invisible characters, but this is not a complete malicious-content defense. Neither posting text nor URLs are passed into an agent with tools. The only outbound operations for discovery are fixed read-only ATS GET requests. User-selected employer posting links are opened by the browser only after an explicit action.

The single-device FastAPI prototype is NOT authenticated and should remain bound to 127.0.0.1. Do not deploy publicly or store confidential identifiers. Future work includes authenticated user isolation, richer candidate-reported evidence, secure ATS/PDF analysis, additional permissioned sources and employer board compatibility checks.

## Test coverage

Automated tests use httpx.MockTransport with official provider JSON contract shapes. They check that the implemented network calls use fixed trusted hosts and GET only, board failures do not invent results, job snapshots are persisted and deduplicated, career matching reads actual SkillGraph evidence, drafts contain no invented achievements, and no draft/status operation sends an external request. Full live network smoke testing is a separate operational step with real employer board tokens.
