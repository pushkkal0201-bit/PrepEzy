# Stage 13 — Evidence-grounded adaptive mock interviews

This feature adds a **real, locally persisted mock-interview workflow** in the PrepEzy
single-device workspace. It builds on Stages 5–12. It does not require the optional
Auralis service, an LLM, GitHub OAuth, or new authentication.

## What is implemented

- Start a balanced, coding-first, or project-first interview for the currently
  configured local role.
- Questions are ordered from the **actual current SkillGraph priority**. The
  coding question cites the most recent Docker-checked coding attempt, if any.
  Without a checked attempt, the UI says that no evidence is available.
- Project questions can link a **commit-pinned** marker from a previously saved
  Stage 12 public GitHub inspection. GitHub syntax markers are *unscored context*,
  not proof of authorship, correctness, security, or interview competence.
- The learner chooses a follow-up direction: edge cases, trade-offs, or
  verification. The next question is inserted into that same persisted session.
  No answer text is classified by keywords or graded by AI.
- Answers, follow-up order, session state, and completed/ended-early reflection
  reports persist in the shared PREPEZY_LOCAL_DB SQLite database.
- Review prior interviews, continue active sessions, stop an interview, remove
  interview data, or clear it through the existing global local-data reset.

## HTTP interface

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | /api/local/mock-interviews | Saved local session index |
| POST | /api/local/mock-interviews | Start with focus; optional saved snapshot_id |
| GET | /api/local/mock-interviews/{session_id} | Current question, transcript and report |
| POST | /api/local/mock-interviews/{session_id}/responses | Answer next question with selected probe |
| POST | /api/local/mock-interviews/{session_id}/finish | Finish or stop early |
| DELETE | /api/local/mock-interviews | Delete sessions and responses |
| DELETE | /api/local/data | Existing full local workspace reset, including Stage 13 |

Example starting request:

~~~json
{"focus":"project","snapshot_id":1}
~~~

The snapshot ID is optional. Without it, a saved latest inspection is used if
available; otherwise a clearly labeled general project question is asked.
Snapshot IDs are **local database IDs**, not GitHub repository IDs.

Example response:

~~~json
{
  "question_id": "project",
  "response": "I would explain the storage boundary, transactional failure cases, and tests that isolate the behavior.",
  "probe": "verification"
}
~~~

A successful response changes the session's next question, **not SkillGraph
grades**. Completion is based on questions answered, not perceived correctness.

## Trust, privacy and limits

- Existing Docker judge outcomes retain their own provenance. Stage 13 neither
  reexecutes untrusted repository code nor creates new checked-test grades.
- Only the reviewed GitHub source markers are included in the interview. They
  are never labeled independently verified implementations.
- Interview explanations are explicitly **ungraded**. Suggested practice is
  general coaching guidance, not a hiring score or a correctness decision.
- The database stores the learner's answer text locally. Use the delete action
  to purge records. Session limits cap local storage growth.
- As before, FastAPI must bind only to 127.0.0.1. No authentication or public
  deployment has been added. This is not a secure multi-tenant interview service.
- Auralis scripted interviews remain their own upstream unscored integration.
  This stage does **not** claim to merge those transcripts or run live voice AI
  interviewers. Future consented integration could explicitly link them.

## Verification

Run from platform/services/api:

~~~bat
.venv\Scripts\python -m pytest -q tests/test_mock_interview.py
~~~

Run the entire backend suite and frontend build before merging:

~~~bat
.venv\Scripts\python -m pytest -q
cd ..\..\apps\web
npm run build
~~~

Tests cover actual stored coding-evidence attribution, source-pinned GitHub
markers, adaptive follow-up sequencing, persistence across restarts, response
validation, deletion and no invented SkillGraph score changes. CI remains the
source of truth for the final branch head.
