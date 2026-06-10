# Mission

## What This Repository Is

This repository is the **PAVE Dark Factory Worker** for WiseTech Global CargoWise development tasks.

Its job is to operate agentic workers against tasks defined in the WTG PAVE system. PAVE is the authoritative queue, lifecycle state, and audit surface. The repository contains the worker, the central control portal, Archon workflow definitions, and the operational rules required to safely let many worker instances act on startable PAVE tasks.

The inherited DynaChat web application is retained as scaffold only. It is not the product mission.

## Who It Is For

Primary users:

- WTG engineers and operators supervising dark factory workers.
- Agent instances that need deterministic rules for PAVE task discovery, claim/start, CargoWise implementation, validation, critic review, evidence reporting, and learning capture.
- Reviewers who need a dashboard and eDoc evidence trail showing exactly what an agent did.

The worker is not a public SaaS product, a generic coding assistant, or a replacement for PAVE.

## Core Capabilities

**PAVE-first work intake**

- Discover startable work from configured PAVE boards.
- Use a low-token scout worker for frequent polling and candidate ranking.
- Confirm the staff code has no other playing task before claiming or starting work.
- Claim and start tasks through ediProd/PAVE lifecycle operations only.

**CargoWise execution**

- Execute tasks for the CargoWise codebase and sibling `CargoWise.*` module repositories.
- Support one work item producing multiple branches and PRs across multiple repositories.
- Track repository participation, branches, commits, PR URLs, builds, tests, and artifacts per repository.
- Use WTG and CargoWise skills strategically by phase.

**Archon workflow orchestration**

- Run deterministic DAGs for context loading, research, repo-set planning, implementation, validation, critic review, evidence upload, close/suspend handling, and self-learning.
- Keep critic behavior as an explicit DAG node.
- Keep self-learning as a dedicated PAVE task at the end of the work item or incident lifecycle.

**Knowledge integration**

- Use `wtgkb` for current WTG task knowledge and CargoWise context.
- Use `sbkb` for durable Second Brain learning capture only in approved learning/writeback phases.
- Use ediProd/PAVE as the only source for task lifecycle and work-item status.

**Portal observability**

- Show all worker instances, runs, phases, logs, artifacts, stalled MCPs, PR sets, tool versions, critic output, evidence reports, and learning assessments.
- Display stalled MCP state clearly and support reauthentication/update workflows.
- Store the full dashboard log and critic output in the final eDoc evidence report.

## Out Of Scope

The factory must not:

- Treat GitHub issues, local queues, or portal rows as the source of work truth.
- Start a PAVE task when another task is already playing for the same staff code.
- Continue execution when required MCPs are stale, unauthenticated, unauthorized, or unavailable.
- Complete a PAVE task without truthful evidence that reporting and close policy were satisfied.
- Write to `sbkb` outside a dedicated self-learning or approved learning phase.
- Assume CargoWise is a monorepo.
- Collapse multiple required CargoWise repository changes into an untracked single-repo PR.
- Modify generated CargoWise `Auto*` code directly unless the relevant CargoWise generator pattern explicitly requires it.

## Hard Invariants

1. **PAVE is the single source of truth.** The portal mirrors state; it does not own the queue.
2. **One playing task per staff code.** The scout must prove no task is playing before claim/start and must repeat the check immediately before start.
3. **Fail closed on MCP readiness.** Required MCP failures pause scouts/executors and are shown as stalled states.
4. **Claim before execution.** No code mutation or PAVE update occurs unless the worker has an authorized task handoff and claim/start succeeded, except explicit dry-run diagnostics.
5. **Evidence is mandatory.** The eDoc report must contain the full dashboard log, critic output, artifact index, PR set, validation results, and final lifecycle decision.
6. **Self-learning is explicit.** Learning capture is a dedicated PAVE task and writes candidate learnings to Second Brain under the approved policy.
7. **Modular CargoWise is first-class.** Repo discovery, planning, implementation, builds, tests, PRs, and reporting are per repository.
8. **Human-authored governance changes are allowed; worker-authored governance changes are not.** Agent runs must not change `MISSION.md`, `FACTORY_RULES.md`, or `CLAUDE.md` unless a human explicitly assigns a governance-update PAVE task.

## Definition Of Done

A worker-handled PAVE task is not done until:

- the PAVE lifecycle state is truthful;
- every required repository has build/test/review evidence;
- all generated artifacts are indexed by type: Specs, Coding, Review, Critic, Validation, eDoc Evidence, Self Learning;
- critic output has been produced and recorded;
- the eDoc evidence report has been uploaded or the task has been suspended with the upload failure recorded;
- stale or unavailable MCP/tooling state is visible in the portal;
- any required self-learning follow-up task has been created or explicitly waived by policy.
