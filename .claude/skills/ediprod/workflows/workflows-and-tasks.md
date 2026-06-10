# ediProd workflows: workflows and tasks

Use this workflow when you need to understand what work is available on a job (WI/CS/PRJ), which workflow it’s in, and which task(s) are startable.

## 1) Get workflow-level overview

Call `get-job-workflows(jobNumber: "WI..." | "CS..." | "PRJ...")`.

Use it to:

- Identify `workflowId` values (for filtering tasks)
- Check workflow metadata such as `componentName`, `constrainedStatus`, `statusDescription`, `readyFor`, `earliestStartDate`, `lastTransferAt`
- See tags (`tags` is a comma-separated list of `code (description)` values)
- See release group (`releaseGroupCode` and `releaseGroupDescription`)

## 2) Fetch tasks (optionally for a single workflow)

If you only care about one workflow, pass `workflowId` (from step 1):

- `get-job-tasks(jobNumber: "WI...", workflowId: "<uuid>")`

Otherwise, fetch all tasks:

- `get-job-tasks(jobNumber: "WI...")`

Optional focus filter:

- `activeOnly: true` excludes closed tasks (`CLS`). Cancelled tasks (`CAN`) are always excluded.

## 3) Interpret task status + startability

From `get-job-tasks`, each task includes:

- `Status` (raw code like `ASN`, `WRK`, `SUS`, `CLS`, `OPN`)
- `Startable` (boolean)

Guidance:

- `Startable: true` is provided by PAVE and generally means “this task is eligible to be started now” (often the lowest-sequenced incomplete task(s) within an open workflow).
- It is normal to see multiple startable tasks if they share the same sequence number.

## 4) Drill into task notes

When a task has `Has Notes: true`, use its `Task Id` with:

- `tasks-notes-read(taskId: "...")`
- `tasks-notes-append(taskId: "...", content: "...")`
