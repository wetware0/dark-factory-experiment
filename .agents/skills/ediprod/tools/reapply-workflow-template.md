# reapply-workflow-template

Reapplies workflow templates on a workitem, incident, or project. Deletes unactioned tasks and empty workflows, then recreates from the current template.

## When To Use

- After workflow templates have been updated and need to be refreshed on existing jobs
- To reset workflow structure while preserving in-progress and completed work
- To add new tasks from a recently modified template without affecting active work

## Input

```yaml
jobNumber:
  type: string
  required: true
  description: >
    Workitem (WI00878427), incident (CS00034343), or project (PRJ00049378) number.
workflowAndTasksOption:
  type: string
  required: false
  default: DeleteUnactionedAndReapply
  description: >
    How to handle existing workflows/tasks:
    - "DeleteUnactionedAndReapply": deletes open/assigned tasks and now-empty workflows, preserves in-progress/completed.
    - "DeleteAllAndReapply": deletes ALL workflows and tasks, reapplies from scratch.
milestonesOption:
  type: string
  required: false
  default: Exclude
  description: >
    How to handle milestones:
    - "Exclude": keep existing milestones unchanged.
    - "DeleteAllAndReapply": delete all milestones and recreate from template.
triggersOption:
  type: string
  required: false
  default: Exclude
  description: >
    How to handle triggers:
    - "Exclude": keep existing triggers unchanged.
    - "DeleteAllAndReapply": delete all triggers and recreate from template.
recalculateReleaseGroups:
  type: boolean
  required: false
  default: false
  description: >
    Whether to recalculate release groups after reapplication.
```

## Output

Returns a confirmation message on success, or an error message if the backend call fails.

## Examples

```
reapply-workflow-template(jobNumber: "WI00878427")
reapply-workflow-template(jobNumber: "CS00034343", workflowAndTasksOption: "DeleteAllAndReapply")
reapply-workflow-template(jobNumber: "PRJ00049378", milestonesOption: "DeleteAllAndReapply", triggersOption: "DeleteAllAndReapply")
```

## Tips

- Default behavior preserves in-progress and completed work — safe to use on active jobs
- Use `get-job-workflows` first to see the current workflow state before reapplying
- If you need a full reset, use `workflowAndTasksOption: "DeleteAllAndReapply"` — this will delete all workflows including active ones
- The tool applies templates to ALL workflows on the job; individual workflow targeting is not supported
