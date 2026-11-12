# Stage 12: GitHub Project Evidence — technical scope

## Trust and provenance

1. The learner supplies a public repo root such as \`https://github.com/owner/repository\`. Only the official \`https://api.github.com\` is queried; no arbitrary addresses, redirects, repository clone commands or GitHub OAuth credentials.
2. A read-only GitHub REST call returns repository metadata, the default branch's HEAD commit and immutable tree SHA. A bounded source inventory is retrieved and up to 14 small files are examined. A source blob is only trusted when its decoded bytes match the Git hash \`SHA1("blob " + byteLength + NUL + contentBytes)\`.
3. Findings cite the exact commit, filename and line, accompanied by a conservative code marker. They are evidence that a syntax pattern occurs in a sampled file, **not** that the behavior works, code is secure, tests pass or the learner owns the repo.
4. Original technical-defense prompts are triggered by real observed markers. The response is free-form and saved, but never graded by an LLM or counted as independently verified.
5. A deliberate consent checkbox is required before any single-file source execution. The student selects a previously inspected .py/.js/.java Git blob and supplies bounded stdin/expected stdout cases. The existing DockerRunner executes source inside a short-lived restricted non-networked container; no custom test commands, repo dependency install or full repo build is allowed. Passing only validates **learner-declared expectations**, not project correctness.
6. Snapshot metadata, ungraded answers and smoke-test verdicts are persisted in local SQLite; full repo source and stdin/expected strings are not stored. The review has a separate delete endpoint and is purged by global data reset.
7. GitHub context is returned in SkillGraph as non-scoring metadata; assessed skill dimensions and scores are untouched.

## Endpoints

- POST /api/local/repositories/inspect
- GET /api/local/repositories/history
- GET /api/local/repositories/{snapshot_id}
- POST /api/local/repositories/{snapshot_id}/defense
- GET /api/local/repositories/{snapshot_id}/evidence
- POST /api/local/repositories/{snapshot_id}/smoke (explicit approved:true)
- DELETE /api/local/repositories/data
- GET /api/local/skillgraph (unscored github_review_context added)

## Verification

Backend/API contract tests use a mock GitHub REST host with real JSON/blob schemas, including exact Git blob SHA-1 rehash. They check URL restrictions, read-only host and methods, source citations, failure on private/rate-limited/truncated responses, ungraded technical responses, explicit execution approval, local persistence, deletion and no SkillGraph inflation. Docker CI executes real Java, JavaScript and Python standalone files through the end-to-end pinned-file review path; GitHub HTTP is mocked to avoid dependencies on GitHub's rate limits or public repo changes. Do not claim any actual external project has been scanned or independently certified by CI.

## Future work

Broader authorized repository code review, multi-file dependency-aware analysis, original checked project-specific test packs, isolated build runners stronger than Docker alone, permissioned GitHub access, verified project ownership and human-reviewed interview defense. Authentication remains deferred; keep all of this on a trusted loopback-only device.
