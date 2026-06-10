# tasks-notes-append

## Description

Append content to existing notes on a task. Fetches current notes, appends new content after a newline separator, and saves.

## When To Use

- Adding investigation findings, status updates, or comments to a task

## Input

```yaml
taskId:
  type: string
  required: true
  description: Task identifier from get-job-tasks.
content:
  type: string
  required: true
  description: Content to append to existing notes.
```

## Output

Confirmation message with updated hash and the full updated notes.

## Examples

```
tasks-notes-append(taskId: "task-id-UUID", content: "Investigation complete — root cause identified.")
```

### Important Behavior

- **Append adds new content** below existing notes (newest at bottom)
- Get task IDs from `get-job-tasks` output
- Notes support basic formatting, but do not use markdown
