---
description: Claim and start one PAVE task without suspending another task for the staff code.
argument-hint: PAVE task context JSON
---

# Dark Factory PAVE Claim Safely

Use ediProd/PAVE lifecycle tools to claim and start the task.

Policy:

1. Re-check staff active/playing task immediately before claim.
2. If another task is playing for the staff code, stop and report `already_playing`.
3. Treat `C50` as the execution staff code for this dark-factory instance.
4. Treat `PWS` as the guardian staff code for clarity gaps, failures, and quality-close limitations.
5. Verify the ediProd OAuth staff code before live mutation. If OAuth is not `C50`, stop before `claim/start` unless the operator explicitly enabled the mismatch override.
6. Use the PAVE claim function because the runtime is operating under ediProd OAuth credentials.
7. Start only the claimed task.
8. Record claim attempt, claim success/failure, and start success/failure in the factory portal.

If claim/start cannot be performed because the MCP is stale or unauthenticated, pause the workflow and report `stalled_mcp`.

If start fails after claim, suspend the task if possible and assign it to the guardian staff code.
