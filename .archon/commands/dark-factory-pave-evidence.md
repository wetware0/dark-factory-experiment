---
description: Generate and upload the full dashboard/evidence report to PAVE eDoc.
argument-hint: Factory run ID
---

# Dark Factory PAVE Evidence

Generate the evidence report from the factory portal, not from a separate summary.

The evidence report must include:

1. PAVE task, work item, incident, board, staff code, and workflow ID.
2. Full dashboard log in chronological order.
3. Critic output and findings.
4. Generated artifacts by category.
5. Repository/branch/PR/build/test state for each participating repository.
6. Any MCP stalls, reauth actions, or quality-close limitations.

Upload the report to the job eDoc through ediProd/PAVE. If upload is unavailable, record an eDoc upload attempt with status `stalled_mcp` and keep the PAVE task open or suspended according to close policy.
