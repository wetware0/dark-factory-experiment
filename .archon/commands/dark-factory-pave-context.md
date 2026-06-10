---
description: Load PAVE work context and factory run contract.
argument-hint: PAVE task payload from the scout worker
---

# Dark Factory PAVE Context

Load the PAVE task payload supplied by the scout worker and establish the run contract.

Required checks:

1. Confirm the source board is `Peter's Board` unless the runtime explicitly overrides it.
2. Confirm the staff code selected by the scout matches the staff code detected from ediProd OAuth credentials.
3. Confirm the task is still startable and no task is already playing for this staff code.
4. Record PAVE task, work item, incident, board, staff code, and initial dashboard log event.
5. Treat PAVE as the single source of truth. Do not substitute GitHub issue state for PAVE state.

Stop conditions:

- Any required MCP is stale, unauthenticated, or unavailable.
- OAuth staff-code detection conflicts with configured staff code.
- A different task is already playing for the staff code.

Output a concise JSON object containing `pave_task_id`, `work_item_id`, `incident_id`, `board_name`, `staff_code`, `task_title`, and `stop_reason`.
