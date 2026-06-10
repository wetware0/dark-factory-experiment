# PAVE Factory Implementation Decisions

Generated: 2026-06-10

This log records the assumptions, decisions, and operational constraints used while forking the Dark Factory experiment into the `wetware0` fork and implementing PAVE as the single source of truth.

## Repository And Branch

- Fork target: `wetware0/dark-factory-experiment`.
- Upstream source: `coleam00/dark-factory-experiment`.
- Current working branch: `codex/c50-guardian-execution`.
- Remote used for the user's fork: `wetware0`.

## Repository Identity Decision

- The repository is now framed as the PAVE Dark Factory Worker for WiseTech Global CargoWise development tasks.
- PAVE tasks, not GitHub issues or the inherited sample web app, define what the worker should do.
- The central portal is the primary user-facing surface and is served at `/factory`.
- The inherited DynaChat chat/RAG application remains available as legacy scaffold at `/chat`, `/c/:conversationId`, and `/admin` until a future PAVE cleanup task removes or separates it.
- Governance files now describe PAVE/CargoWise worker behavior. Worker-authored runs still must not modify governance unless a human explicitly assigns a governance-update PAVE task.

## PAVE Operating Inputs

- PAVE board name: `Peter's Board`.
- Dark-factory execution staff code: `C50`.
- Guardian / escalation staff code: `PWS`.
- Runtime default staff code is configurable through `PAVE_STAFF_CODE`.
- Runtime guardian staff code is configurable through `PAVE_GUARDIAN_STAFF_CODE`.
- The worker must detect the staff code belonging to the active ediProd OAuth credentials before live claim/start. Read-only polling can target `C50` while authenticated as `PWS`, but live mutation is blocked unless OAuth staff matches `C50` or an explicit override is set.

## Live Tool Constraint Found During Initial Implementation

- `codex mcp list` showed `ediprod`, `wtgkb`, and `sbkb` configured.
- The live `ediprod` MCP mutation namespace was not exposed as a callable tool in this thread.
- The fallback `edi` CLI was not installed locally.
- Therefore, implementation must not pretend to claim, start, close, suspend, assign, or upload eDoc evidence until a concrete MCP or CLI adapter is available at runtime.
- The system fails closed by pausing scout/agent work when required MCPs are stale, unauthenticated, or unavailable, and the dashboard visualizes the stalled state.

## Live Tool Update After edi CLI Install

- `edi` is now available on PATH at `C:\Users\peter\.bun\bin\edi.exe`.
- `edi staff get` detects the OAuth staff code as `PWS`.
- A read-only `edi staff tasks PWS --include-capability-pool` probe returned Peter's Board tasks and confirmed no `WRK` task was playing for `PWS` at the time of the probe.
- A read-only `edi staff get C50` probe confirmed `C50` exists as `Copilot Code Reviewer (C50)`.
- A read-only `edi staff tasks C50 --include-capability-pool` probe returned zero tasks, zero playing tasks, and zero startable Peter's Board tasks at the time of the probe.
- The scout can resolve a selected Peter's Board task to a concrete PAVE task ID by using `edi workflow list` and `edi task list` after the cheap staff-task scan.
- The local scout still defaults to `FACTORY_SCOUT_DRY_RUN=true`. Claim/start mutation through `edi task start` requires explicitly setting `FACTORY_SCOUT_DRY_RUN=false` and `FACTORY_ARCHON_EXECUTE=true`.
- With current `PWS` OAuth credentials, live `C50` mutation is blocked unless `FACTORY_ALLOW_OAUTH_STAFF_MISMATCH=true` is explicitly set. The default is fail-closed.
- Project-local WTG/PAVE skills were added under `.agents/skills` and `.claude/skills`, with `skills-lock.json` recording hashes.

## Database Decision

- Factory portal state should use SQL Server by default because SQL Server is the standard WTG operational database.
- Runtime selector: `FACTORY_STORAGE_PROVIDER=sqlserver`.
- Required SQL Server setting: `FACTORY_SQLSERVER_CONNECTION_STRING`.
- Peter's local SQL Server is reachable on `RYZEN2` with Windows integrated authentication through `ODBC Driver 18 for SQL Server`. The recommended factory connection string should include an explicit factory database, for example `Database=DarkFactory`.
- The SQL Server repository creates factory tables idempotently on first use and stores JSON-shaped fields as `NVARCHAR(MAX)` payloads.
- SQLite is supported as a local smoke-test provider through `FACTORY_STORAGE_PROVIDER=sqlite` and `FACTORY_SQLITE_PATH`.
- SQLite stores JSON-backed factory entities in a single local database file. It is not the multi-instance coordination store for a real dark-factory pool.
- The inherited DynaChat chat/RAG application was already Postgres/pgvector-backed before the PAVE factory work. That storage remains separate in this PR because replacing pgvector and Postgres full-text retrieval with SQL Server equivalents is a broader migration.
- A Postgres factory repository and migration remain available as a compatibility path, but they are not the preferred WTG deployment target.

## PAVE Lifecycle Policy

- PAVE remains the driving single source of truth.
- The scout worker polls PAVE cheaply for startable tasks.
- The scout only escalates a task to an intelligent agent when no other task is playing for the same staff code.
- This instance polls startable work for `C50`.
- The agent must claim using the PAVE claim function because lifecycle state belongs in PAVE, not the portal.
- Only one task may be playing for a staff code at a time. Starting a new task can suspend the existing task, so the scout has to check staff activity before claiming.
- If the MCP quality iteration close path is unavailable, the agent must suspend the task and assign it to guardian `PWS` rather than attempting a false close.

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
- Worker-side automated updates are limited to known local git-backed tooling (`C:\git\WTG.sbkb-mcp` and `C:\git\WTG.AI.Prompts`) and use `git pull --ff-only`.
- OAuth-backed MCP reauthentication is handled through the stalled MCP reauth flow rather than by a tooling update job.
