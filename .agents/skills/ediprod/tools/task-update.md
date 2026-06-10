# tasks-update

## Description

Updates a task's description, type, and/or estimate. Only provided fields are changed.

## When To Use

- Replacing a task description with corrected or updated text
- Changing the task type code (e.g. from `DES` to `REV`)
- Setting or updating the estimated effort in minutes

## Input

```yaml
taskId:
  type: string
  required: true
  description: Task ID (GUID) from tasks-list or tasks-create.
newDescription:
  type: string
  required: false
  description: New description replacing the existing one. At least 20 characters. Short label field (~50 chars max).
newType:
  type: string
  required: false
  description: New 3-character task type code (e.g. "DES", "REV", "COD"). Current type is shown by tasks-list.
estimateMinutes:
  type: integer
  required: false
  description: Estimate in minutes for the task (non-negative integer).
```

At least one of `newDescription`, `newType`, or `estimateMinutes` must be provided.

## Output

Confirmation message listing the updated fields, e.g. `Task <taskId> updated: description, type, estimate.`

## Examples

```
tasks-update(taskId: "task-uuid", newDescription: "Implement OAuth login flow for mobile app")
tasks-update(taskId: "task-uuid", newType: "REV")
tasks-update(taskId: "task-uuid", estimateMinutes: 90)
tasks-update(taskId: "task-uuid", newDescription: "Review authentication changes", newType: "REV", estimateMinutes: 60)
```

### Important Behavior

- **Description replaces** the existing value (not appended)
- **Type** is updated atomically — the current type is fetched automatically, no need to supply it
- **Estimate** sets the low estimate field; the current hash is fetched automatically
- Description must be at least 20 characters
