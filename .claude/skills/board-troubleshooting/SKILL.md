---
name: board-troubleshooting
description: Troubleshoot why work items or workflows are not appearing on buffer boards in EdiProd. Apply when users report missing workitems, workflows not visible on boards, or tasks not showing up as startable. Uses mcp-ediprod tools to automatically retrieve workflow and task data.
---

## Overview

**Purpose:** Diagnose why workflows or work items are not visible on buffer boards in EdiProd using automated data retrieval.

**When to Use:**

- User reports a workflow/workitem is not on their board
- User asks "Where is my workflow?" or "Why can't I see WI00XXXXXX?"
- User expects to see work but it's missing

**Approach:**

1. **Symptom-Based Responses** - If user describes specific symptoms (task estimates, prerequisites, filters), provide immediate help without data retrieval (see [references/symptom-responses.md](references/symptom-responses.md))
2. **Automated Diagnosis** - Use MCP ediprod tools to retrieve and analyze workflow data

## Quick Reference

**Most Common Resolutions:**

- **Wait 15 minutes** after Transfer Time → Refresh with **SHIFT+F5**
- **Missing tags** → Add CSS tag or add to Constraint Sequence
- **Task estimates** → Ensure STANDARD tasks ≤10 hours, all tasks estimated
- **Prerequisites** → Remove unnecessary or wait for completion
- **Board filters** → Remove filters and refresh

**Component-Specific Guides:**

- [Entry to BMS](references/component-guides.md#entry-to-bms) - Normal delay
- [Queue](references/component-guides.md#queue) - Missing required tags
- [Value Assessment Gate](references/component-guides.md#value-assessment-gate-vag) - Task criteria or prerequisites
- [Value Assessment Gate RTR](references/component-guides.md#vag-rtr-ready-to-release) - Capacity constraints
- [Buffer Zones](references/component-guides.md#buffer-zones-active-work) - Board filters or config
- [Free Parking](references/component-guides.md#free-parking) - Prerequisites (incidents only)

## Automated Diagnosis Workflow

Use this workflow when user provides work item number or symptoms require data retrieval.

### Step 1: Get Job Number

Ask user:

```
What is the workitem or incident number? (e.g., WI00878427 or CS00034343)
```

### Step 2: Retrieve Data

```
I'll retrieve the workflow information for [job_number]...
```

**Call `get-job-workflows` first** to retrieve workflow-level metadata:

- componentName (needed for Step 3), constrainedStatus, statusDescription, lastTransferAt, earliestStartDate
- Tags and release groups
- workflowId (use to filter tasks in the next step)

**If task-level analysis is needed** (e.g., VAG task validation, assignment checks), call `get-job-tasks` with the specific `workflowId` to retrieve:

- Task assignments, estimates, statuses, startable flags

Note: `get-job-tasks` output groups tasks by workflow title and does not echo the workflowId back in the output, so prefer filtering by `workflowId` when you’re diagnosing a single workflow.

### Step 3: Identify Component

From tool output, extract **ONLY** the `componentName` field from the workflow section.

**DO NOT analyze or extract any other fields yet** - they will be checked inside the decision tree as needed.

### Step 4: Analyze by Component

Based on `componentName` value, follow decision tree:

| componentName                   | Action                                               |
| ------------------------------- | ---------------------------------------------------- |
| Entry to BMS                    | Check time elapsed → Wait or escalate                |
| Queue                           | Check tags → Add CSS tag if missing                  |
| Value Assessment Gate (Open)    | Validate task requirements                           |
| Value Assessment Gate (Blocked) | Ask about prerequisites                              |
| Value Assessment Gate RTR       | Guide to Transfer Diagnosis                          |
| Buffer - Zone X                 | Check Ready For → Remove filters                     |
| Free Parking                    | Ask about prerequisites                              |
| Other                           | Inform about hundreds of components → Escalate to DM |

**Note:** There are hundreds of different components in the Buffer Management System. This tool only addresses those most commonly encountered. If you are having an issue with a component not listed in this tool, contact your team's Delivery Manager for assistance.
**For detailed diagnosis steps for each component**, see [component-guides.md](references/component-guides.md).

### Step 5: Calculate Time Elapsed

Calculate time elapsed since `lastTransferAt`. If < 15 minutes, tell user to wait remaining time. If ≥ 15 minutes, tell user to refresh (SHIFT+F5).

### Step 6: Provide Diagnosis

Include in response:

- Current workflow state summary
- Specific issues found
- Actions required
- Timeline (15-minute cycles)
- Escalation path if needed

## Common Patterns

### Pattern: Standard Transfer Wait

**When**: Any status where workflow should progress after time delay

**Response Template**:

```
Last Transfer: [lastTransferAt]
Time Elapsed: [calculated] minutes

Workflows transfer every 15 minutes.
- If <15 min: Wait [remaining] more minutes
- If ≥15 min: Refresh (SHIFT+F5) and check again
```

### Pattern: Tag Requirements (Queue)

**Check**: Does workflow have any of these tag codes?

- RTR, RTK, WFC, RED, RDQ, CTA, SQU, CAT, ECA, CHU, MTN, LDD
- OR CSS tag

**If missing**:

```
Missing required tags.

Current tags: [list all tags or "None"]

To add CSS tag:
1. Add item to Constraint Sequence, OR
2. Make item child of item on Constraint Sequence

Then wait 15 min → Refresh (SHIFT+F5)
```

### Pattern: Task Requirements (Value Assessment Gate)

**Validate all tasks**:

- All assigned to staff or capability
- All have estimates
- STANDARD estimates ≤10 hours (600 minutes)
- No task type = EXT
- Earliest start date is null or past

**If requirements not met**:

```
Requirements not met for Value Assessment Gate:

Issues:
[List specific task issues with IDs]

Fix these issues → Wait 15 min → Refresh (SHIFT+F5)
```

## Escalation

**When to escalate to Delivery Manager**:

- Workflow still not progressing after 15+ minutes and refresh
- Status is uncommon (not in common list)
- Data shows workflow should be on board but it's not visible
- User has checked board filters and refresh didn't help

**Escalation message**:

```
This requires Delivery Manager support.

Current state:
- componentName: [value]
- statusDescription: [value]
- Last Transfer: [time]
- Time Elapsed: [minutes]

Please contact your DM for assistance.
```

## Key Principles

1. **Automate First** - Retrieve data before asking questions
2. **Be Specific** - Reference actual field values
3. **Calculate Time** - Don't ask "has it been 15 minutes?" - calculate it
4. **Progressive Disclosure** - Link to detailed guides for complex cases
5. **Clear Escalation** - Know when to hand off to DM

## Advanced Topics

For specialized scenarios, see these reference files:

- **[Component-Specific Guides](references/component-guides.md)** - Detailed decision trees for each component
- **[Symptom Responses](references/symptom-responses.md)** - Edge case symptom-based troubleshooting
- **[Manual Workflow](references/manual-workflow.md)** - Guide user if MCP tools unavailable
