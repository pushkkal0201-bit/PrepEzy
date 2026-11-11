# PrepEzy feature-preservation and integration matrix

**Statuses:** `implemented-local` = exists and locally testable in this branch; `catalogued` = metadata discoverable but not executable as a PrepEzy feature; `planned` = still to build; `development-tool` = assists engineering and should not run for student accounts. These are not claims of production readiness.

| Source | Major capabilities to preserve | Destination | Current status | Missing integration |
|---|---|---|---|---|
| Auralis (`pushkkal0201-bit/auralis-interview-studio`, staging) | Adaptive interviews, voice/text, feedback/replay, Answer Repair, CodeProof, incidents, practical/calculation labs, compare roles, Skill Evolution, campus portal, bilingual coach | Interview/learning adapters | planned | Auth migration, event mapping, consented model/provider integration and actual acceptance tests |
| Cracked (`nishant-Tiwari24/cracked`) | DSA mock, OA simulator, system design, core viva, HR round, project defence, company intel, resume/JD match, prep plans, rejection review, referrals, offer analysis | Practice and career adapters | catalogued | Convert agent instructions to typed services, test real execution, use secure code runner |
| Serviette (`pathwaycom/serviette`) | Live indexing, cited RAG, hybrid retrieval, document comparison, vector backends | Separate RAG service | planned | Private indexing, retrieval permissions, infra and Pathway terms |
| JobSearch (`ai-job-search-dev/ai-job-search`) | Profile, scrape/rank, application drafter-reviewer, interview, outcomes, follow-up, upskill, reporting, templates and integrations | Career engine | planned | Regional job sources, profile consolidation, external-action approval |
| Emil Kowalski Skills | Motion, UI gestures and performance | Engineering workflow | development-tool | No runtime dependency required |
| Impeccable | UX and accessibility audits, responsive design checks | Engineering/CI workflow | development-tool | Review hooks and permissions first |
| Taste Skill | Visual design, typography and branding | Design workflow | development-tool | Apply selectively to educational interface |
| SkillIssue | Skill discovery, creation, packaging and sharing | Moderated Skill Studio | planned | Skill provenance, licensing, review and sandboxed capabilities |
| REA | Authorized application inspection | Developer diagnostics only | development-tool | Never bundle general reverse-engineering tools in student runtime |
| Build Your Own X | Tutorial index for systems built from scratch | Adaptive Build Lab | planned | Curate links, create original tasks/tests, honor tutorial licenses |

## What has actually been implemented

`platform/services/api/app/core.py` contains a **local-only** server-graded learning prototype. It derives role-weighted priority recommendations from a fixed five-question bank. The `platform/apps/web` client displays real API responses. The existing Cracked repository skills remain untouched and are read only as metadata. This prototype does **not** claim a validated general adaptive learning model.

## Feature-parity acceptance work

1. Pin source commits and build a file-level inventory of actual implemented upstream functions and tests.
2. Complete the local SkillGraph, prerequisite graph, evidence contracts and adaptive recommendation tests with synthetic fixtures; defer authentication.
3. Integrate Auralis engines without regressing existing interview tests; preserve voice, replay and optional providers.
4. Convert Cracked skills to explicit API operations with clear capability permissions; use isolated, resource-constrained code grading.
5. Run Serviette in an isolated Linux/WSL2 environment, protect document ownership and evaluate citation correctness.
6. Add supported, authorized job connectors and user-reviewed application actions; never fabricate job listings or work history.
7. Implement Skill Studio and Adaptive Build Lab, initially using curated and attributed resources, not unreviewed code.
8. Add verified authentication, PostgreSQL owner-scoped evidence, account deletion and privacy controls before accepting real student data or a public launch.
9. Run backend, UI, accessibility, security, live-connector, restore, deployment and end-to-end tests before public launch.

## Scope/claims

Reusing MIT-licensed sources does not remove attribution requirements. Check Pathway and third-party tutorial licensing separately. Keep design tools out of the product runtime. No hackathon eligibility claim is made without event-specific rules.
