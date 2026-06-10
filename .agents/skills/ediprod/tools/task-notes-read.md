# tasks-notes-read

## Description

Read notes for a specific task. Returns notes content as markdown.

## When To Use

- Reading notes on a task to understand context or prior updates

## Input

```yaml
taskId:
  type: string
  required: true
  description: Task identifier from get-job-tasks.
```

## Output

Returns task notes as Markdown, or `No notes found.`

## Examples

```
tasks-notes-read(taskId: "task-id-UUID")
```

### Important Behavior

- Get task IDs from `get-job-tasks` output (look for `Has Notes: true`)
- Notes are returned as markdown converted from HTML
