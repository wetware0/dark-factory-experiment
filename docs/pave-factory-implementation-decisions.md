# PAVE Factory Implementation Decisions

Generated: 2026-06-10

This log records the assumptions, decisions, and operational constraints used while forking the Dark Factory experiment into the `wetware0` fork and implementing PAVE as the single source of truth.

## Repository And Branch

- Fork target: `wetware0/dark-factory-experiment`.
- Upstream source: `coleam00/dark-factory-experiment`.
- Working branch: `codex/pave-dark-factory-wetware0`.
- Remote used for the user's fork: `wetware0`.

## PAVE Operating Inputs

- PAVE board name: `Peter's Board`.
- Staff code for this run: `PWS`.
- Runtime default staff code is configurable through `PAVE_STAFF_CODE`.
- The worker must still try to detect the staff code belonging to the active ediProd OAuth credentials before claiming work. If detection is unavailable, it must fall back to the configured staff code and mark the MCP readiness state as degraded.

## Live Tool Constraint Found During Implementation

- `codex mcp list` showed `ediprod`, `wtgkb`, and `sbkb` configured.
- The live `ediprod` MCP mutation namespace was not exposed as a callable tool in this thread.
- The fallback `edi` CLI was not installed locally.
- Therefore, implementation must not pretend to claim, start, close, suspend, assign, or upload eDoc evidence until a concrete MCP or CLI adapter is available at runtime.
- The system fails closed by pausing scout/agent work when required MCPs are stale, unauthenticated, or unavailable, and the dashboard visualizes the stalled state.

## PAVE Lifecycle Policy

- PAVE remains the driving single source of truth.
- The scout worker polls PAVE cheaply for startable tasks.
- The scout only escalates a task to an intelligent agent when no other task is playing for the same staff code.
- The agent must claim using the PAVE claim function because it is operating through the user's PAVE credentials.
- Only one task may be playing for a staff code at a time. Starting a new task can suspend the existing task, so the scout has to check staff activity before claiming.
- If the MCP quality iteration close path is unavailable, the agent must suspend the task and assign it to `PWS` rather than attempting a false close.

## MCP And Knowledge Policy

- Required MCPs for execution: `ediprod`, `wtgkb`, and `sbkb`.
- `ediprod` owns PAVE lifecycle, work item / incident updates, and eDoc evidence upload.
- `wtgkb` owns current-task WTG knowledge retrieval.
- `sbkb` owns durable second-brain learning capture.
- Stale or unauthenticated MCPs pause the affected process. They do not produce partially trusted results.
- The dashboard must show stalled MCP state and provide reauthentication workflow state tracking.

## Archon And Repo Policy

- Archon workflows must support modular repository sets, not only a monorepo.
- A single PAVE work item may produce multiple PRs across `CargoWise` and `CargoWise.*` repositories.
- The runtime stores repository participation, branch names, commit SHAs, PR URLs, build/test results, and per-repo artifacts for each PAVE run.
- Critic is modeled as a normal DAG node.
- Self-learning is modeled as a dedicated PAVE task after the work item, not as an implicit hidden phase.

## Audit And Evidence Policy

- Every run must produce an audit / evidence report against the job in the eDoc.
- The evidence report must include the same full log visible in the dashboard.
- Critic output must be included in the evidence report.
- Generated artifacts are tracked by category such as Specs, Coding, Review, Critic, Validation, eDoc Evidence, and Self Learning.

## Tooling Currency Policy

- Skills and plugins are treated as versioned operational dependencies.
- The dashboard tracks installed versions, latest known versions, update status, and update jobs.
- Updating skills/plugins from the dashboard is recorded as an auditable operation.
