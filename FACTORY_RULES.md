# Factory Rules

This file governs how PAVE Dark Factory workers operate. It is read by scout, execution, validation, critic, evidence, and self-learning workflows.

**Hierarchy:** `MISSION.md` defines what the worker exists to do. `CLAUDE.md` defines how code is written in this repository. `FACTORY_RULES.md` defines how workers operate safely. When they disagree, `MISSION.md` wins on scope, `CLAUDE.md` wins on code style, and this file wins on process.

---

## 1. Work Intake

PAVE is the only authoritative work queue.

The scout worker may read configured PAVE boards, tasks, workflows, staff state, and related work item or incident details. It must not invent work from GitHub issues, local files, portal rows, chat messages, or model suggestions.

The scout may select a task only when all of the following are true:

- the task is startable according to PAVE prerequisites;
- the task belongs to an allowed board, staff code, or capability pool;
- the required MCPs are ready;
- no task is currently playing for the staff code;
- the candidate has enough context for a compact handoff;
- the portal does not show the worker instance as paused.

If the worker cannot prove these conditions, it records a stalled or skipped state and takes no lifecycle action.

---

## 2. Claim And Play Safety

PAVE allows only one playing task per staff code. Starting a different task can suspend the currently playing task. The worker must therefore treat claim/start as a guarded operation.

Required sequence:

1. Treat configured `PAVE_STAFF_CODE` as the execution staff code. For this experiment it is `C50`.
2. Treat configured `PAVE_GUARDIAN_STAFF_CODE` as the human guardian/escalation owner. For this experiment it is `PWS`.
3. Detect the staff code for the active ediProd OAuth identity when possible.
4. Permit read-only polling when OAuth staff differs from execution staff.
5. Block live claim/start when OAuth staff differs from execution staff unless an operator explicitly enables `FACTORY_ALLOW_OAUTH_STAFF_MISMATCH=true`.
6. Check current playing task state for the execution staff code.
7. Re-read the selected task immediately before claim/start.
8. Use PAVE lifecycle operations to claim and start the task.
9. Execute only if claim/start succeeds.

Never start a task as a side effect of polling. Never start a second task to inspect it. Never continue after a lifecycle call returns an ambiguous result without reconciling the PAVE state.

---

## 3. MCP Readiness

Required MCPs for normal execution:

- `ediprod` for PAVE lifecycle, work item / incident updates, task notes, and eDoc evidence.
- `wtgkb` for current task knowledge.
- `sbkb` for durable learning capture during approved self-learning.

If a required MCP is stale, unauthenticated, unauthorized, missing, or lacks required mutation tools, the affected process pauses. This is a stalled state, not a normal retry loop.

The dashboard must show:

- MCP name and role;
- status and last successful check;
- reason for stall;
- affected worker instance or run;
- available reauthentication or update action;
- last error without leaking secrets.

---

## 4. Execution Scope

The intelligent agent receives one compact PAVE task handoff from the scout and treats it as the only authorized task for the run.

The agent must:

- load the PAVE work item or incident contract;
- retrieve current task knowledge from `wtgkb`;
- retrieve relevant durable context from `sbkb` without writing new learnings;
- resolve the CargoWise repository set before implementation;
- keep all changes scoped to the PAVE task;
- track branch, commit, PR, build, test, and validation state per repository;
- pause rather than silently ship partial work when one repository blocks the whole change.

CargoWise is modular. A single work item may require `CargoWise` plus one or more `CargoWise.*` repositories and may require multiple PRs.

---

## 5. Archon Workflow Requirements

PAVE execution workflows must be deterministic at phase boundaries and artifact-driven between AI nodes.

Required DAG phases:

- PAVE context load;
- safe claim/start;
- WTG and Second Brain research;
- CargoWise repository-set plan;
- implementation;
- per-repository validation;
- critic review;
- evidence report generation and eDoc upload;
- close-or-suspend lifecycle decision;
- self-learning task creation or execution when applicable.

The critic is a normal DAG node. It must produce an artifact that is visible in the portal and included in the evidence report.

Self-learning is not hidden inside the implementation run. It is a dedicated PAVE task that assesses whether generated artifacts were used as generated, surfaces manual changes as learning candidates, and writes approved learnings to `sbkb`.

---

## 6. Quality Gates

Every code-producing run must provide evidence for:

- requirement fit against the PAVE task;
- affected repository list and ownership assumptions;
- build/test results per repository;
- static analysis or review checks expected for the touched stack;
- CargoWise coding standards and generated-code constraints;
- security and authorization impact;
- critic findings and disposition;
- final PR set and merge/readiness state.

Validation must evaluate the outcome against the PAVE contract. It must not rely on the coder's private plan as proof of correctness.

---

## 7. Evidence And Audit

Every run must create an evidence report against the PAVE job in eDoc.

The evidence report must include:

- PAVE board, execution staff code, guardian staff code, task ID, work item or incident, workflow ID, and claim/start timestamps;
- full dashboard log as shown to the user;
- artifact index with Specs, Coding, Review, Critic, Validation, eDoc Evidence, and Self Learning categories;
- repository set and PR set;
- build/test/validation results;
- MCP readiness events and stalls;
- critic output;
- close, suspend, assign, or escalation decision;
- any self-learning task ID or waiver.

If eDoc upload is unavailable, the worker records the failed upload attempt, keeps the evidence locally, and follows close policy by suspending or escalating rather than falsely completing the task.

---

## 8. Close, Suspend, And Assignment

The worker may complete a PAVE task only when the task is started, the required artifacts exist, validation policy is satisfied, and evidence reporting succeeded or was explicitly waived.

If the quality iteration close path is unavailable through MCP, the worker must suspend the task and assign it to the configured guardian staff code, currently `PWS` for this experiment.

Never mark a run completed in the portal if PAVE could not be updated truthfully.

---

## 9. Tooling Currency

Skills and plugins are operational dependencies.

The dashboard tracks:

- installed version;
- latest known version;
- source;
- last check time;
- update availability;
- update job status.

Workers must use the latest approved WTG.AI.Prompts skills available for the task phase. Updating skills/plugins from the dashboard is auditable work and must not occur silently inside an unrelated PAVE task.

---

## 10. Protected Behavior

Worker-authored runs must not:

- weaken PAVE lifecycle checks;
- bypass MCP readiness pauses;
- write secrets, OAuth tokens, API keys, or `.env` files;
- make the portal a competing queue;
- write to `sbkb` outside approved learning flow;
- ignore a required CargoWise repository;
- delete or hide dashboard logs needed for eDoc evidence;
- modify `MISSION.md`, `FACTORY_RULES.md`, or `CLAUDE.md` unless the PAVE task is explicitly a governance update assigned by a human.

Human-authored governance changes are allowed. This file is expected to evolve as the experiment matures.
