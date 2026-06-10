---
name: ncn-status
description: "Use when asked to report on NCN progress, check which work items are done or blocked, or get a phase-level overview of an ediProd network diagram."
---

# NCN Status Summary

Produces a concise, decision-oriented markdown status report for an ediProd Necessary Condition Network (NCN). Work end to end and return the final markdown result only. Do not stop for intermediate confirmation unless the NCN is ambiguous.

## Guardrails

- Do not stop for intermediate confirmation unless the NCN cannot be resolved unambiguously.
- Do not include raw tool output or JSON in the report.
- Do not speculate — use explicit workflow and job metadata only.
- If a WI status and its workflow statuses disagree, mark the WI as open and flag the mismatch in Key Observations.
- If a WI's workflows cannot be fetched after one retry, mark it as `Status Unknown` in the table and note the fetch failure in Key Observations. Do not abort the report.
- **Never stop mid-execution and return control to the user due to cancelled or failed tool calls.** Cancelled calls are a transient transport issue — always retry before giving up. Stopping mid-workflow is a failure mode, not a valid outcome.

## Step 1 — Resolve the NCN Job Number

If the input is already a valid job number (`WI…`, `CS…`, or `PRJ…`), use it directly.

Otherwise:

1. Search WTGKB or ediProd for the description to find any WI linked to the NCN.
2. Use that WI number for Step 2 — any WI in the diagram resolves the full network.
3. If multiple plausible matches remain, return a short ambiguity note listing candidate job numbers.
4. If nothing credible is found, return a short failure note.

## Step 2 — Load Network Diagrams

Call `mcp_ediprod_pave-ncn-get-diagrams(jobNumber)`. From the returned breakdown tree:

1. Collect every unique job number prefixed with `WI`.
2. Preserve visible grouping or parent breakdown context.
3. Ignore shapes not linked to a WI job number.
4. If no WIs are found, report that the NCN contains no linked work items.

## Step 3 — Load WI Details and Workflows

The ediProd MCP server can drop connections intermittently, which surfaces as cancelled tool calls rather than errors. Use the batching and retry strategy below to stay resilient.

### Batching

Call `mcp_ediprod_get-job-workflows(jobNumber)` in batches of **at most 3 WIs at a time**. Wait for each batch to complete before dispatching the next.

### Retry on cancellation

**A "cancelled" result is never a reason to stop or hand back to the user.** If a call returns a "cancelled" or empty result (not a real data payload), it is always a transient transport failure. You **must** retry before continuing:

1. **Immediately** re-issue each failed call **one at a time**, sequentially (do not batch retries).
2. If a call fails a second time with another cancellation, mark that WI as `Status Unknown` and continue to the next WI — do not stop the report.
3. If an **entire batch** is cancelled, wait briefly and then retry the batch sequentially, one call at a time.
4. Continue processing all remaining WIs regardless of individual failures.

### Enrichment (optional)

After workflows are loaded, call `mcp_ediprod_get-job-details(jobNumber)` for WIs that have blockers, missing titles, or ambiguous statuses.

Capture per WI: job number, title, overall status, any blocker or progress notes.
Capture per workflow: title, constrained status, ready-for value, status description, earliest start date.

## Step 4 — Determine Status

Treat a workflow as **done** only when clearly completed, closed, or cancelled.
Treat a workflow as **open** when active, pending, blocked, buffered, gated, or waiting.

Treat a WI as **Done** when its status is clearly closed/completed **and** all workflows are done.
Treat a WI as **Open** when any workflow is open, or when the WI itself is not clearly complete.

## Step 5 — Assign Phase

Assign each open WI to one primary phase using the **earliest still-open** phase in this order: **Design → Development → Review**.

Exact workflow-name mappings take priority over keyword inference:

| Workflow Name                                              | Phase       |
| ---------------------------------------------------------- | ----------- |
| Product Design, Design Review, Technical Design            | Design      |
| Development, Coding                                        | Development |
| Review, Review and Publish, Publish, Publish Documentation | Review      |

Keyword fallback when no exact match:

| Phase       | Keywords                                                                                                       |
| ----------- | -------------------------------------------------------------------------------------------------------------- |
| Design      | analysis, discovery, design, spec, specification, architecture, solution, assessment, estimate, planning, gate |
| Development | develop, development, implement, implementation, build, code, fix, test, integration, deploy prep              |
| Review      | review, qa, validate, validation, verify, verification, approval, sign-off, release, rollout                   |

If still unclear, assign to **Development** and note the conservative inference.

## Step 6 — Produce Markdown Output

Return this structure:

```markdown
# NCN Status Summary

> **Input:** original user input
> **Resolved Job Number:** PRJ/WI/CS…
> **Work Item Count:** N
> **Generated:** YYYY-MM-DD

## Summary Status

| Category    | Count |
| ----------- | ----: |
| Done WIs    |     X |
| Open WIs    |     Y |
| Design      |     A |
| Development |     B |
| Review      |     C |

## Work Item Status Table

| WI  | Title | WI Status | Open Workflows | Open Coding WFs | Phase | Notes |
| --- | ----- | --------- | -------------: | --------------: | ----- | ----- |

## Done

- `WI…` — title

## Open — Development

### `WI…` — title

- **WI Status:** …
- **Notes / Blockers:** …
- **Open Workflows:**
  - workflow title — short status note

## Open — Review

### `WI…` — title

- **WI Status:** …
- **Notes / Blockers:** …
- **Open Workflows:**
  - workflow title — short status note

## Key Observations

- Short, concrete observation
```

**Output rules:**

1. Include every WI exactly once in the status table, except for WIs that use multi-row expansion (rule 8) — those span multiple rows.
2. **Open — Design** is a compact flat list (one line per WI). Do not expand individual workflows for Design-phase WIs.
3. **Open — Development** and **Open — Review** use the full per-WI breakdown with open workflows listed.
4. Use `None identified` when there is no credible blocker signal.
5. Mention blockers, gates, and status mismatches in Key Observations.
6. If all WIs are done, produce the full markdown with empty open sections.
7. If no WIs are done, state that explicitly.
8. **Multi-row expansion:** For any WI that is **not** in the Design phase **and** has 2 or more distinct coding (Development) workflows (matched by the Development phase keyword rules in Step 5), expand that WI into multiple consecutive rows in the status table — one row per coding workflow. Only the first row carries the WI number, title, WI status, total open workflow count, open coding WF count, and phase. All subsequent rows for the same WI have empty WI, title, WI status, total open WF, open coding WF, and phase cells; the Notes cell shows `↳ <workflow title> — <constrained status / short status note>`.
9. **Open Coding WFs** column: count only workflows that map to the Development phase (exact name match or keyword fallback from Step 5) and are still open. Done/closed coding workflows do not count.
