# Stage 11 — Adaptive Project Lab: real learning-loop integration

## Attribution and content provenance

External index: https://github.com/codecrafters-io/build-your-own-x (Build Your Own X).

This repository supplies **links to tutorials owned and published by their respective authors**, not an agent runtime, learning platform API or a uniform content license. PrepEzy stores a small curated list of source links and writes **original, self-contained milestone specifications and deterministic tests**. It does not mirror, rehost or execute external tutorial source code.

## Implemented tracks

1. Build a Small Key-Value Store: PUT/GET overwrite and missing-key semantics; then DELETE/SIZE with distinct-key invariants.
2. Build a Tiny Search Index: one-term inverted-index queries; then AND queries as intersection of postings lists.
3. Build a Tiny Expression Interpreter: + and - left-to-right; then operator precedence with multiplication.

Each track has two executable milestones, original independent fixtures, and two objective technical-defense questions with written explanations saved as unreviewed.

## Real execution and evidence

The existing Stage 7 DockerRunner is the only execution path. It uses unprivileged, short-lived network-disabled containers with bounded resources. Source is submitted as a complete Java/Python/JavaScript stdin/stdout program, not as arbitrary shell commands. Hidden cases stay on the server. Missing Docker/images fail closed and do not create assessment evidence.

A passing milestone must match **all** hidden and public fixtures. Its SHA-256 and verdict are saved in SQLite; program source is not retained. The next milestone unlocks only after an accepted result. Defense questions unlock after an accepted milestone; selected choice is server-graded while free-form explanation remains unverified.

Unified SkillGraph evidence is source-typed:
- \`docker_project_milestone\`: independently tested code, distinct first-attempt baseline.
- \`project_defense_choice\`: checked conceptual answer only; written rationale not scored.

These are **not** blended with generic DSA pattern choices, standard CodingArena problems, SQL checks or self-reported GitHub artifacts. The role-aware recommendation uses local goals and milestone completion, not a fabricated AI project-quality score.

## API

GET  /api/local/projects/catalog
GET  /api/local/projects/{project_id}
POST /api/local/projects/{project_id}/milestones/{milestone_id}/submit
POST /api/local/projects/{project_id}/defense/{question_id}/submit
PUT  /api/local/projects/{project_id}/artifact
GET  /api/local/projects/evidence/all
DELETE /api/local/data  (also clears Project Lab evidence, rationales and artifact links)

## Verification and limits

Unit/API tests cover original public catalog contents (no hidden case exposure), progression and unlock rules, retry resistance, failed Docker availability, actual local persistence, source provenance, defense rationale policy, and reset/delete. GitHub Docker CI executes original Java, Python and JavaScript solutions against Project Lab milestone fixtures in real containers.

This is a **trusted local prototype**. Docker is not a complete adversarial sandbox; use on 127.0.0.1 only, without remote access. Authentication is intentionally deferred. Written rationale requires a human/mentor review to assess its quality; linking a GitHub URL does not verify or inspect repository content. Expanded projects, deep project-test harnesses, honest code-review feedback and original tutorial licensing review are future work.
