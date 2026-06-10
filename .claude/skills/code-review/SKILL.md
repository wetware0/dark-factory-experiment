---
name: code-review
description: >
  Performs a focused code review for mcp-ediprod, checking: Regression & Breaking Changes, KISS & Simplicity, Design & Coupling, Style & Readability, Test Coverage, Performance. Use this to review PRs, commits, branches, or uncommitted changes in this repository.
---

# Code Review — mcp-ediprod

MCP server + CLI (`edi`) for structured access to Glow/ediProd, a freight/logistics platform built on CargoWise (CW1). Exposes tools for incidents, workitems, workflows, tasks, staff, documents, and projects via Glow OData and REST APIs.

Checks: Spec Compliance, Regression & Breaking Changes, KISS & Simplicity, Design & Coupling, Style & Readability, Test Coverage.

## When to Use

- `/code-review {PR number}` — review a pull request
- `/code-review {branch name}` — review a branch
- `/code-review {commit SHA}` — review a commit
- `/code-review` — review current uncommitted changes

Append `--comment` to post findings as inline GitHub comments.

---

## Constraints

- **NEVER modify, create, or delete any source files.**
- Stop and ask the user before posting Critical or Major findings as GitHub comments.

---

## Repository Context

- **Stack**: TypeScript (ESM, strict), Bun runtime, Zod validation, Biome + Prettier linting/formatting
- **Layout**: Single repo — `src/apps/mcp/` (MCP server), `src/apps/cli/` (Commander.js CLI), `src/packages/glow-client/` (typed Glow API client with betterApi layer), `src/packages/services/` (document reading), `src/packages/logging/` (Pino + OpenTelemetry)

---

## VARIABLES

| Variable        | Source                                 |
| --------------- | -------------------------------------- |
| `PR_NUMBER`     | From `$ARGUMENTS`                      |
| `COMMIT_HASH`   | From `$ARGUMENTS`                      |
| `BRANCH_NAME`   | From `$ARGUMENTS`                      |
| `INSTRUCTIONS`  | Free-text directives from `$ARGUMENTS` |
| `POST_COMMENTS` | `true` if `--comment` in `$ARGUMENTS`  |

---

## PHASE 1 — Gather Context and Write Workspace

Create a temporary workspace to share context with aspect agents:

```bash
WORKSPACE=$(mktemp -d /tmp/code-review-XXXXXX)
mkdir -p "$WORKSPACE/aspects" "$WORKSPACE/files"
```

### Step 1.1: Locate the Changes

| Input             | Action                                                     |
| ----------------- | ---------------------------------------------------------- |
| No arguments      | `git diff HEAD`, `git diff --cached`, `git status --short` |
| Short or full SHA | `git show {COMMIT_HASH}`                                   |
| Branch name       | `git diff {BRANCH_NAME}...HEAD`                            |
| PR number         | `gh pr view {PR_NUMBER}`, then `gh pr diff {PR_NUMBER}`    |

Save the full diff to `$WORKSPACE/diff.patch`.

### Step 1.2: Read Full Files

Read the complete content of every file modified in the diff. Save each one to `$WORKSPACE/files/` using a flattened filename (replace `/` with `__`). Do not skip this — diffs alone miss context that changes meaning entirely.

### Step 1.3: Understand the Problem

Use `gh pr view` (or the PR diff header) to extract the PR title, description, and commit messages.

Save a problem summary to `$WORKSPACE/context.md`:

```markdown
# Review Context

## Intent

<What the change is trying to accomplish — 2-4 sentences>

## Requirements / Acceptance Criteria

<Bullet list if found in PR description; otherwise "Inferred from PR description and commit messages">

## Changed Files

<List each file with a one-line description of what changed>

## Additional Context

<INSTRUCTIONS from user if any>
```

### Step 1.4: Sanity Check

Before launching agents, verify the workspace contains:

- `diff.patch` — non-empty
- At least one file in `files/`
- `context.md` — written

---

## PHASE 2 — Launch Aspect Agents in Parallel

Select aspects to review based on the change and user instructions. Spawn one agent per aspect, each with the relevant aspect `.md` file as instructions.
Spawn selected agents **simultaneously** as background tasks. Each agent reads shared context from the workspace and writes its findings back to it.

**Pass in every agent prompt:**

- The resolved workspace path (the actual `/tmp/code-review-XXXXXX` path, not the shell variable)
- Instructions to read `context.md`, `diff.patch`, and relevant files from `files/`
- Instructions to write findings to `$WORKSPACE/aspects/{aspect-name}.md`
- The path to the repository root, so agents can query it directly for additional context (callers, convention files, adjacent code, etc.) if the workspace files are not enough
- The **full verbatim contents** of the aspect's `.md` file — agents cannot read skill files themselves; never summarise or paraphrase
- Any `INSTRUCTIONS` provided by the user

**Agents to spawn:**

| Agent                        | Aspect file                    | Writes to                                 |
| ---------------------------- | ------------------------------ | ----------------------------------------- |
| Spec Compliance reviewer     | `aspects/spec-compliance.md`   | `$WORKSPACE/aspects/spec-compliance.md`   |
| Regression reviewer          | `aspects/regression.md`        | `$WORKSPACE/aspects/regression.md`        |
| KISS & Simplicity reviewer   | `aspects/kiss-simplicity.md`   | `$WORKSPACE/aspects/kiss-simplicity.md`   |
| Design & Coupling reviewer   | `aspects/design-coupling.md`   | `$WORKSPACE/aspects/design-coupling.md`   |
| Style & Readability reviewer | `aspects/style-readability.md` | `$WORKSPACE/aspects/style-readability.md` |
| Test Coverage reviewer       | `aspects/test-coverage.md`     | `$WORKSPACE/aspects/test-coverage.md`     |

---

## PHASE 3 — Synthesise the Final Report

Once all agents have written their findings to `$WORKSPACE/aspects/`, read all findings files.

**Validate before including any finding:**

- Clearly present in the diff — not speculative
- Introduced by this change, not pre-existing
- A senior engineer would actually want this flagged
- Does not rely on unstated runtime assumptions that can't be confirmed from the code

Discard unconfirmed findings. Merge duplicates (same issue found by multiple agents) into a single entry — keep the most complete description.

### Report Format

Output a **single unified review** — not a breakdown by aspect. Order all findings Critical → Major → Minor.

```
## Code Review — {PR title or change summary}

### Summary
{2–3 sentences: what the change does and overall verdict}

### Issues

**Critical**

- **C{num} {Title}** · `{file}:{start-end}`
  {State WHY it is a problem. Include the scenario/inputs under which it manifests. Enough detail that an engineer reading this as a PR inline comment immediately grasps the issue and how to fix it. If the fix is small and self-contained, include a suggestion block with the exact code to commit.}

- ...

**Major**

- **MJ{num} {Title}** · `{file}:{start-end}`
  {same format as Critical, but less severe}

- ...

**Minor**

- **MN{num} {Title}** · `{file}:{start-end}`
  {same format as Critical, but less severe}

- ...

> No issues found.   ← use this instead of the sections above when there are none

### Verdict
**Approve** | **Approve with suggestions** | **Request changes** — {one-sentence justification}
```

**Verdict criteria:**

- **Approve** — no issues
- **Approve with suggestions** — Minor findings only
- **Request changes** — any Critical or Major finding

---

## PHASE 4 — GitHub Comments (only if `POST_COMMENTS` is true)

If `--comment` was not provided, stop after outputting the report.

**Stop and show the user the full list of planned comments. Wait for explicit approval before posting anything.**

For each validated finding, post one inline comment via `mcp__github__pull_request_review_write`:

- Location: the file path and line range from the finding
- Body: the one-paragraph description already written in the report
- Suggestion block: only for fully self-contained fixes ≤5 lines that entirely resolve the issue when committed

Never post duplicate comments.

---

## Output Guidelines

- Reference file paths and line numbers directly
- State _when_ or _under what conditions_ a bug manifests — not just that it exists
- Don't overstate severity
- Tone: matter-of-fact, not accusatory or flattering
- No filler: no "Great job...", "Thanks for...", no trailing praise
