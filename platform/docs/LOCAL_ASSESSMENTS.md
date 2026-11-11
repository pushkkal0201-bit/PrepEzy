# Stage 5 — Local-first real technical assessments

**Scope:** A real, usable local practice product without authentication. Do not deploy publicly or accept other students' private data.

## Executed SQL, not a simulated grader

Five SQL challenges are run against **two different fixture datasets** in fresh, isolated in-memory SQLite connections. Every expected result is calculated by executing the server's reference SQL; actual and expected results are compared independent of row ordering while preserving duplicate counts and column order.

Safety boundaries include:
- Restrict submitted statements to SELECT or WITH only.
- SQLite authorizer rejects writes, schema inspection, and functions outside a small allowlist.
- Per-query progress handler, result size and output width limits.
- No subprocess, shell, extension loading, arbitrary Python or production database access.
- Historical query text is not stored; only its SHA-256 hash, test verdict, challenge and timestamp.

This is a bounded educational SQL grader, not an unrestricted sandbox or a security boundary for hosting arbitrary user programs.

## Local Core CS Viva

Twelve hand-authored and backend-checked fundamentals questions across DBMS, OS, CN and OOP. Only server-checked answers become evidence; nothing is LLM-inferred. Multiple attempts are recorded, but the first attempt on a distinct question is the baseline proficiency observation.

## Personalized recommendations

The local workspace stores target role, preferred language and available daily study time. PrepLoop ranks available topics by goal relevance, unassessed coverage and first-try test results, with transparent reasons and a bounded roadmap.

## Authentication decision

No login or signup was added. One device, one workspace, persisted in a local SQLite file. Local access checks block non-loopback peers and disallowed browser origins, but cannot secure real multi-user privacy. Do not publicly expose these routes.

## What still needs engineering

Integrate actual Auralis and Cracked outcome adapters with this local profile; implement secure isolated code running before general DSA/OA grading; build Serviette and JobSearch integrations; expand curriculum and feedback; authenticate before sharing across users or public deployment.

**Source attribution:** Cracked original skill pack is preserved. New SQL tasks, data fixtures, Core CS questions and their graders are original PrepEzy code, inspired by Cracked's Core Viva executable SQL specification.
