# PAVE Dark Factory Worker

This repository is being reframed as a **WiseTech Global PAVE-driven dark factory worker** for CargoWise development tasks.

PAVE is the single source of truth. The worker discovers startable PAVE tasks, claims them safely through ediProd, executes an Archon workflow against the appropriate CargoWise repository set, and reports the resulting agentic artifacts back to the work item or incident. The web surface in this repo is now the **factory control portal**, not the product being built.

The original DynaChat chat/RAG application remains in the tree as inherited scaffold and an implementation harness. It is not the mission of this repository anymore.

---

## What This Worker Does

The target operating model is:

1. A small scout worker polls a configured PAVE board with low token cost.
2. The scout only chooses a task when the staff code has no other playing task.
3. The scout creates a compact task handoff for the intelligent agent.
4. The agent claims and starts exactly one PAVE task through ediProd.
5. Archon executes a deterministic DAG for research, repo-set planning, implementation, validation, critic review, evidence reporting, close/suspend handling, and self-learning.
6. All instances report telemetry, logs, MCP readiness, PR sets, artifacts, critic output, and evidence status to the central portal.
7. The final evidence report is written to the job eDoc and contains the same full log shown in the dashboard.

The worker is designed for CargoWise work, including changes that span the large `CargoWise` repository and one or more sibling `CargoWise.*` module repositories. A single PAVE work item can therefore result in multiple branches, multiple pull requests, and per-repository build/test evidence.

---

## Source Of Truth

PAVE owns:

- work discovery and prioritisation;
- task lifecycle state: claim, start, suspend, resume, complete, cancel;
- work item / incident context and final updates;
- staff-code play constraints;
- the audit trail for generated artifacts.

The portal mirrors operational state. It must not become a second work queue. GitHub remains the source control and pull-request surface only.

Required MCP services:

- `ediprod`: PAVE lifecycle, work item / incident updates, task notes, eDoc evidence.
- `wtgkb`: current WTG and CargoWise knowledge for the task being executed.
- `sbkb`: durable Second Brain learning capture during dedicated self-learning tasks.

If any required MCP is stale, unauthenticated, unauthorized, or missing, the affected scout or executor pauses. The dashboard must show the stalled state and expose the reauthentication/update action rather than letting the worker continue with partial trust.

---

## Local Services

Use the service controller to run the backend, frontend, and scout worker:

```powershell
.\scripts\factory-services.ps1 start
.\scripts\factory-services.ps1 status
.\scripts\factory-services.ps1 stop
.\scripts\factory-services.ps1 restart
```

The dashboard is served by the Vite app at:

```text
http://127.0.0.1:5173/factory
```

Detailed operating documentation is available in:

- `docs/pave-factory-user-admin-manual.html` - user and administrator manual.
- `docs/dark-factory-pave-single-source-report.md` - deep architecture and implementation handoff.
- `docs/pave-factory-implementation-decisions.md` - assumptions and decisions log.

The script creates a worker token at `.factory/factory-worker-token.txt`, stores service PIDs in `.factory/pids`, and writes logs in `.factory/logs`.

Default local operating inputs:

- PAVE board: `Peter's Board`
- execution staff code: `C50`
- guardian staff code: `PWS`
- scout dry-run: `true`
- Archon dispatch: `false`

Override these with script parameters or environment variables when running another worker pool.

The scout uses the `edi` CLI when present:

- `edi staff get` detects the staff code attached to the active OAuth credentials.
- `edi staff tasks --include-capability-pool` performs the low-token board scan.
- `edi workflow list` and `edi task list` resolve the selected staff-task row to a concrete PAVE task ID.
- `edi task start` is only called when `FACTORY_SCOUT_DRY_RUN=false`, `FACTORY_ARCHON_EXECUTE=true`, the play guard passes, and the OAuth staff code is allowed to mutate as the execution staff code.
- If the worker detects a clarity gap or failure after a task is in play, the guardian path appends task notes, suspends the task when possible, and assigns it to `PWS`.

---

## Database

Factory portal state defaults to SQL Server because that is the WTG operational database standard:

```powershell
$env:FACTORY_STORAGE_PROVIDER = "sqlserver"
$env:FACTORY_SQLSERVER_CONNECTION_STRING = "Driver={ODBC Driver 18 for SQL Server};Server=YOURSERVER;Database=DarkFactory;Trusted_Connection=yes;TrustServerCertificate=yes;"
```

The SQL Server repository creates factory tables idempotently and stores JSON-shaped fields as `NVARCHAR(MAX)` payloads.

For Peter's local RYZEN2 SQL Server, use an ODBC connection string shaped like this after creating/selecting the target database:

```powershell
$env:FACTORY_STORAGE_PROVIDER = "sqlserver"
$env:FACTORY_SQLSERVER_CONNECTION_STRING = "Driver={ODBC Driver 18 for SQL Server};Server=RYZEN2;Database=DarkFactory;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;Application Name=Dark Factory;"
```

For isolated local smoke tests, the factory portal can use SQLite:

```powershell
$env:FACTORY_STORAGE_PROVIDER = "sqlite"
$env:FACTORY_SQLITE_PATH = ".factory/factory.sqlite3"
```

SQLite is a local test provider only. It is not the multi-instance coordination store for a running dark-factory pool.

The inherited chat/RAG scaffold still requires its original `DATABASE_URL` Postgres/pgvector database. Migrating that legacy retrieval code to SQL Server is a separate task because it depends on Postgres full-text search and pgvector.

---

## Architecture

```mermaid
flowchart LR
    PAVE["PAVE / ediProd<br/>single source of truth"] --> Scout["Scout worker<br/>cheap polling and play guard"]
    Scout --> Agent["Intelligent agent<br/>one authorized task"]
    Agent --> Archon["Archon DAG"]
    Archon --> Repos["CargoWise repository set<br/>CargoWise + CargoWise.*"]
    Archon --> Portal["Factory portal<br/>logs, MCP state, artifacts"]
    Archon --> PAVE
    Portal --> Operator["Human operator<br/>stalls, reauth, tooling updates"]
    Archon --> SBKB["Second Brain<br/>approved learnings"]
    Archon --> WTGKB["WTG knowledge<br/>task context"]
```

Important design constraints:

- The scout is cheap and conservative. It polls PAVE, checks the staff-code play guard, and passes only compact task context to the expensive agent.
- Claim safety comes from PAVE lifecycle operations, not portal-side locks.
- A task must not start if starting it would suspend another playing task for the staff code.
- This instance polls `C50` tasks. `PWS` is the guardian/escalation staff code, not the execution queue.
- The critic is a normal Archon DAG node.
- Self-learning is a dedicated PAVE task at the end of the work item or incident lifecycle. It is identified by PAVE task type `INT` with `Self Learning` in the task description and routes to `FACTORY_SELF_LEARNING_WORKFLOW_NAME`.
- Skills/plugins are versioned operational dependencies. The portal tracks installed versions, latest known versions, update status, and update jobs.
- Archon DAG nodes should declare the skills/plugins they are allowed to use. Claude-backed nodes can use native per-node `skills:`; Codex-backed nodes currently require the factory executor to enforce the allow-list by loading only the nominated skill context.
- Dashboard tooling update jobs are executed by the worker for known local git-backed tooling (`WTG.sbkb-mcp`, `WTG.AI.Prompts`) using fast-forward pulls. OAuth MCP reauth remains a separate stalled-state action.

---

## Key Paths

| Path | Purpose |
| --- | --- |
| `app/backend/factory/worker.py` | Scout worker entry point. |
| `app/backend/factory/edi_cli.py` | `edi` CLI adapter for staff detection, startable-task polling, task ID resolution, and guarded lifecycle calls. |
| `app/backend/routes/factory.py` | Factory portal API. |
| `app/backend/db/factory_store.py` | Factory storage provider selector. |
| `app/backend/db/factory_sqlserver_repository.py` | SQL Server factory storage. |
| `app/frontend/src/pages/FactoryDashboard.tsx` | Central factory dashboard. |
| `.archon/workflows/pave-dark-factory-execute-task.yaml` | PAVE-native execution workflow. |
| `.archon/commands/dark-factory-pave-self-learning.md` | Self-learning command contract for dedicated learning tasks. |
| `.archon/commands/dark-factory-pave-*.md` | Archon command contracts for PAVE execution. |
| `docs/pave-factory-user-admin-manual.html` | Detailed user and administrator manual. |
| `docs/dark-factory-pave-single-source-report.md` | Deep implementation handoff report. |
| `docs/pave-factory-implementation-decisions.md` | Assumptions and decisions log. |
| `scripts/factory-services.ps1` | Start/stop/status controller. |
| `.agents/skills/` | Project-local WTG/PAVE skills used by agent workers. |
| `.claude/skills/` | Claude-compatible copy of project skills. |
| `skills-lock.json` | Hash lock for the project-local skills. |

---

## Legacy App Harness

The inherited FastAPI/React code still includes a RAG chat application. It exists because the upstream dark factory experiment shipped as a web app, and the current branch reuses that authenticated frontend/backend shell for the factory portal.

Legacy chat routes remain available for now:

- `/chat`
- `/c/:conversationId`
- `/admin`

The default authenticated route is `/factory`.

Do not treat legacy DynaChat requirements as the mission for new work. New work should serve the PAVE/CargoWise worker unless a PAVE task explicitly targets legacy scaffold cleanup.

---

## Implementation Status

Implemented in this branch:

- PAVE factory portal backend API.
- SQL Server factory storage path, with Postgres compatibility retained.
- Scout worker with fail-closed MCP readiness behavior, stable instance identity, PWS OAuth/C50 execution-staff support, C50 startable-task discovery via the Peter's Board fallback, and dry-run selection recording.
- Dashboard views for runs, stalled MCPs, tooling currency, artifacts, critic reports, evidence logs, and learning assessments.
- PAVE-native Archon workflow and command files.
- Local service controller for start, stop, restart, and status.
- Tooling page grouping for runtime dependencies versus skill/plugin catalogs.
- Dedicated self-learning task classification: PAVE task type `INT` with `Self Learning` in the description.

Known live-tool state:

- `ediprod`, `wtgkb`, and `sbkb` are configured in Codex.
- The local `edi` CLI is installed and detects the current OAuth staff code as `PWS`.
- The configured execution staff code is `C50`; `PWS` is the guardian for this instance.
- Peter's Board fallback discovery can see startable `C50` work even when `edi staff tasks C50` returns no published staff-board view rows.
- The scout defaults to dry-run. Set `FACTORY_SCOUT_DRY_RUN=false` and `FACTORY_ARCHON_EXECUTE=true` only when the operator wants the scout to call `edi task start` after the play guard and OAuth staff guard both pass.
- With the current `PWS` OAuth profile, live `C50` mutation is blocked unless `FACTORY_ALLOW_OAUTH_STAFF_MISMATCH=true` is explicitly set.
- The local `C:\git\WTG.AI.Prompts` clone is optional; when absent, the Tooling page reports it as unavailable and workers should use installed project skills plus `wtgkb`/GitHub metadata fallback.

---

## Validation

Focused local validation commands:

```powershell
cd app
uv --project backend run python -m compileall -q backend/main.py backend/config.py backend/factory backend/db/factory_store.py backend/db/factory_sqlserver_repository.py backend/routes/factory.py

cd frontend
bun run type-check
bunx biome check src/pages/FactoryDashboard.tsx src/components/BrandingHeader.tsx src/App.tsx src/lib/api.ts
```

The full inherited chat/RAG test suite still belongs to the legacy scaffold. Factory changes should prefer targeted backend, frontend, service-control, and Archon workflow validation unless the PAVE task touches chat/RAG behavior directly.
