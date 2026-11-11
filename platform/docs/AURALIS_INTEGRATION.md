# Stage 3 — Auralis interview integration

## Upstream source

- Repository: `pushkkal0201-bit/auralis-interview-studio`
- Pinned staging commit for CI: `bed71fe2556841c918848b289457c8cc6d6738d9`
- Auralis source files: `auralis/app/main.py`, `engine.py`, `schemas.py`, `demo.py`
- Actual Auralis local endpoints: `GET /api/health`, `POST /api/sessions`, `POST /api/sessions/{sid}/start`, `POST /api/sessions/{sid}/actions`, `POST /api/sessions/{sid}/finish`, `GET /api/sessions/{sid}`

## How it works

PrepEzy's FastAPI gateway talks to **a separate running copy** of upstream Auralis over an HTTP loopback address. The adapter deliberately rejects non-loopback hosts and external/HTTPS URLs, preventing arbitrary destinations and accidental upload of interview content to cloud services.

The gateway uses only hard-coded fictional CV/JD profiles for two synthetic demo learners, posts them to upstream Auralis with `provider=demo`, `synthetic_data=true`, and `consent=false`, and returns bounded response fields rather than raw CVs, internal metadata, or credentials.

Auralis local mode requires an `X-Owner-Token` header, even without login. PrepEzy derives a different **public/deterministic synthetic namespace** token for each fixture profile. This is not authentication or account privacy. Keep these services bound to loopback and never use real student data.

After a real Auralis session completes, PrepEzy stores an `auralis_interviews` row and an answer count. The adaptive roadmap can add a reflection activity with a source session ID. **It does not produce or import a numerical skill score**: Auralis's scripted demo report is explicitly unscored.

## Student-facing API (local-only)

| Operation | PrepEzy route | Expected behavior |
|---|---|---|
| Check health | `GET /api/demo/integrations/auralis` | Connected only if real local Auralis responds and advertises demo mode |
| Start interview | `POST /api/demo/learners/{id}/interviews` | Creates and starts an actual upstream synthetic session |
| Read recorded history | `GET /api/demo/learners/{id}/interviews` | Local linked session metadata |
| Resume | `GET /api/demo/learners/{id}/interviews/{sid}` | Fetches current state from upstream |
| Answer | `POST /api/demo/learners/{id}/interviews/{sid}/answer` | Actual upstream answer action |
| Finish | `POST /api/demo/learners/{id}/interviews/{sid}/finish` | Returns Auralis's genuine, unscored scripted report |
| Roadmap | `GET /api/demo/learners/{id}/roadmap` | Adds ten-minute evidence reflection when appropriate |

## Verification

- Python unit/contract tests check host restrictions, response sanitization, local-only configuration, input guardrails, synthetic learner linkage, evidence provenance and roadmap updates.
- A separate GitHub Actions job checks out Auralis at a **pinned source commit**, starts the real FastAPI app on port 8001, and exercises a complete interview journey from PrepEzy's gateway.
- `test_auralis_live.py` is skipped in normal local runs unless `PREPEZY_RUN_AURALIS_LIVE=1` and the upstream server is running.
- The upstream engine has its own tests. These are not silently replaced or mocked by PrepEzy's contract tests.

## Explicit limitations

This is a working **scripted-demo runtime adapter**, not live LLM grading, real-person identity, continuous speech transcription, or a production interview service. The latter will require consent, explicit model integration, owner-scoped storage and stronger trust boundaries. Do not use any numerical competency claims from scripted Auralis sessions.
