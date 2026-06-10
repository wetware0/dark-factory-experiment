---
description: Load PAVE work context and factory run contract.
argument-hint: PAVE task payload from the scout worker
---

# Dark Factory PAVE Context

Load the PAVE task payload supplied by the scout worker and establish the run contract.

Required checks:

1. Confirm the source board is `Peter's Board` unless the runtime explicitly overrides it.
2. Confirm the scout selected the configured execution staff code, currently `C50`.
3. Record the ediProd OAuth staff code separately from the execution staff code.
4. Confirm the task is still startable and no task is already playing for the execution staff code.
5. Record PAVE task, work item, incident, board, execution staff code, guardian staff code, and initial dashboard log event.
6. Treat PAVE as the single source of truth. Do not substitute GitHub issue state for PAVE state.

Stop conditions:

- Any required MCP is stale, unauthenticated, or unavailable.
- OAuth staff-code detection conflicts with the execution staff code when the workflow is about to mutate PAVE and no explicit mismatch override is set.
- A different task is already playing for the staff code.

Output a concise JSON object containing `pave_task_id`, `work_item_id`, `incident_id`, `board_name`, `staff_code`, `guardian_staff_code`, `task_title`, and `stop_reason`.
