# get-job-workflows

Returns a list of workflows for a workitem, incident, or project, including tags and release groups.

## When To Use

- Getting a quick overview of workflows without task-level details
- Finding release groups assigned to a job
- Querying tags across workflows for reporting purposes
- Building reports on release group distribution across jobs
- Troubleshooting board assignment issues by checking workflow release groups

## Input

```yaml
jobNumber:
  type: string
  required: true
  description: Job identifier (WI..., CS..., or PRJ...).
```

## Output

Returns a TOON-encoded object containing:

- `jobNumber`: the input job number
- `workflows`: tabular list of workflow rows (uniform fields)

Each workflow includes (when available):

- `workflowId` (use with `get-job-tasks` workflowId parameter to filter tasks by workflow)
- `title`
- `type`
- `componentName`
- `constrainedStatus` (constraint status relative to Capacity Constrained Resources)
- `readyFor` (how long the next startable work has been ready)
- `statusDescription` (workflow status)
- `earliestStartDate` (do not start before)
- `lastTransferAt` (last release/transfer time)
- `completedAt` (ISO timestamp when all tasks completed; empty if incomplete)
- `tags` (comma-separated `code (description)` values)
- `releaseGroupCode`
- `releaseGroupDescription`

## Release Groups

Release groups are provided by the workflow process header.

Common examples:

- `LTRANSRG` - Land Transport parent release group
- `LTRANS1RG` - Land Transport sub-team 1 release group
- `LTRANS2RG` - Land Transport sub-team 2 release group

This allows teams to partition work by release group and use the MCP server to report on:

- Which workitems are in which release group
- Workitems incorrectly assigned to the wrong team/release group
- Release group distribution across jobs

## Examples

```
get-job-workflows(jobNumber: "WI00902989")
get-job-workflows(jobNumber: "CS02134514")
get-job-workflows(jobNumber: "PRJ00049378")
```

## Comparison with get-job-tasks

| Aspect            | get-job-workflows                                                | get-job-tasks                    |
| ----------------- | ---------------------------------------------------------------- | -------------------------------- |
| Focus             | Workflow metadata + tags + release groups                        | Tasks grouped by workflow        |
| Payload size      | Lightweight                                                      | Can be large with many tasks     |
| Use case          | Reporting, release group queries, board troubleshooting          | Task assignment, status tracking |
| Workflow metadata | ✅ Full (componentName, constrainedStatus, tags, release groups) | Minimal (title only)             |
| Tasks             | ❌ Not included                                                  | ✅ Full task details             |

Use `get-job-workflows` for reporting across many jobs where you only need workflow-level metadata and release group information.

Use `get-job-tasks` when you need detailed task information (assignments, durations, statuses, task IDs for notes).

## Tips

- Use this tool for batch reporting across multiple jobs
- Release groups enable querying workitems by team assignment
- `releaseGroupCode` and `releaseGroupDescription` are separate flat fields for filtering and reporting
