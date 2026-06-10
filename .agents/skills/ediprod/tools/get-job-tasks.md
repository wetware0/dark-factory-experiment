# get-job-tasks

Returns task information for a workitem, incident, or project. For workflow-level metadata (componentName, constrainedStatus, tags, release groups, etc.), use `get-job-workflows`.

## When To Use

- Getting detailed task status for a job
- Finding task assignments and durations
- Tracking who worked on a job
- Retrieving tasks for a specific workflow (using `workflowId` filter)

## Input

```yaml
jobNumber:
  type: string
  required: true
  description: Job identifier (WI..., CS..., or PRJ...).
activeOnly:
  type: boolean
  required: false
  default: false
  description: If true, exclude closed and cancelled tasks (Status = CLS or CAN).
workflowId:
  type: string (UUID)
  required: false
  description: Optional workflow ID to return tasks for a specific workflow only. Get workflow IDs from get-job-workflows.
```

## Output

Returns a TOON-encoded object containing `Staff` and `Capabilities` reference tables, followed by workflows with task lists. Tasks only include staff and capability codes.

Reference tables:

- `Staff` with `Code`, `Name`
- `Capabilities` with `Code`, `Description`

Each workflow includes:

- `title`

Each task includes:

- `Sequence Number`, `Type`, `Description`
- `Staff` (code only, use reference table for name)
- `Capability` (code only, use reference table for description)
- `Status` (raw status code)
- `Created At`, `Started At`, `Completed At` (when available)
- `Estimated Duration`, `Actual Duration`
- `Startable`
- `Has Notes`
- `Task Id` (use with `tasks-notes-read` / `tasks-notes-append`)

## Terminology

### Workflow

- A workflow is a grouped set of tasks used for scheduling, dependency management, chunking, and visualizing related work.
- For workflow-level metadata (statusDescription, constrainedStatus, componentName, tags, release groups), use `get-job-workflows`.

### Task startability

- `Startable` is provided by PAVE.
- In many workflows it corresponds to the next task(s) that can be started (often the lowest-sequenced incomplete task(s) in an open workflow).
- There can be multiple startable tasks if multiple tasks share the same lowest sequence number.

### Staff vs capability

- `Staff` is the specific person assigned to the task.
- `Capability` represents a group/role that can work the task.
- A task can be assigned to a capability with no staff claimed yet.

## Examples

```
get-job-tasks(jobNumber: "WI00902989")
get-job-tasks(jobNumber: "CS02134514", activeOnly: true)
get-job-tasks(jobNumber: "WI00902989", workflowId: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
```

### Task Status Codes (raw)

The tool returns the raw status code in `Status`.

- `ASN`: assigned (to staff or capability)
- `WRK`: in progress / working
- `SUS`: suspended
- `CLS`: closed
- `CAN`: cancelled
- `OPN`: open placeholder (typically “pending allocation”)

## Common Task Types (examples)

Task types are 3-character codes used to categorize work. The full list varies by workflow type and configuration, but these are commonly seen in ediProd development workflows:

- `AST`: Assisting (helping another person/job)
- `CB?`: Containment barrier (quality checkpoint; third character varies)
- `CHK`: DAT merge placeholder (change to `CH0` to action)
- `CH0`: DAT merges pull request(s) after build/test
- `SHV`: DAT test placeholder (change to `SH0` to action)
- `SH0`: DAT builds/tests pull request(s) (may also deploy if configured)
- `UAT`: DAT deploy placeholder (change to `UA0` to action)
- `UA0`: DAT builds/deploys pull request(s) (skips testing)
- `AS0`: DAT aspect-only build (no tests)

## Tips

- Task IDs in output can be used with `tasks-notes-read` / `tasks-notes-append`
- Use `activeOnly: true` to focus on pending work
- Use `workflowId` to retrieve tasks for a specific workflow (get IDs from `get-job-workflows`).
- Use `get-job-workflows` for workflow metadata (componentName, tags, release groups, constrainedStatus)
