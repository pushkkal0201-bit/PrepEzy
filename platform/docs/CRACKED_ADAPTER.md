# Cracked Pattern Coach — integration design and verification

Upstream: **Cracked** by Nishant Tiwari (https://github.com/nishant-Tiwari24/cracked), MIT license.
Specification: \`skills/interview/pattern-coach/SKILL.md\`. The original skill pack and its notices remain in the PrepEzy root. PrepEzy does not execute the Markdown skills: it uses Cracked's *Socratic coaching method* to implement original, deterministic guided exercises in \`app/cracked.py\`.

## Working features

- Four patterns: two pointers, sliding window, binary-search-on-answer and BFS.
- Three ordered stages: brute-force reasoning, spot repeated work, independent transfer.
- Server-side correct-choice checks; answer keys withheld until successful grading.
- Hints recorded as assistance.
- Prevention of skipped stages.
- Synthetic demo learner-specific SQLite evidence records.
- The **first transfer attempt per distinct pattern** provides one DSA concept-recognition observation. A hint-assisted or initially failed transfer step does not become unassisted evidence merely because the lesson is later completed.
- Role-sensitive roadmap suggestions can refer users to the next relevant pattern.
- API and policy tests covering source attribution, stage gating, retries, persistence, independence and isolation of synthetic namespaces.

## Explicit limitations

- Does not execute Cracked's Claude Code agent or skill instructions.
- No student source code is executed or compiled.
- Does not yet include full Cracked OA simulation, company-specific sourcing, timed mock interviews or live model generation.
- It is not an authenticated, real-student, or production-grade assessment service.

## Planned follow-on

Add bounded SQL-verification for Core Viva, then implement a genuinely isolated coding grader for timed OA sessions. Company-specific intel and project-defense adapters should be independently verified and license-attributed. Evaluate adaptive learning effectiveness against a fixed curriculum before making outcome claims.
