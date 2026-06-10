# PAVE Task CRUD & Assignment Tools

Tools for creating, updating, and assigning tasks within PAVE workflows.

## Tools

### tasks-create

Creates a new task within a workflow.

- **Parameters:** `jobNumber`, `workflowId`, `type`, `description`, `estimateInMinutes?`, `capabilityCode?`, `staffCode?`, `taskInsertAfter?`
- **Notes:** The job number is resolved to a PAVE job ID internally. Use `get-job-workflows` to find workflow IDs. Task is created in unclaimed state. Use `tasks-notes-append` to add notes after creation.

### tasks-update

Updates task description, type, and/or estimate.

- **Parameters:** `taskId` (required), `newDescription?`, `newType?`, `estimateMinutes?`
- **Notes:** At least one field must be provided. Description replaces existing content (minimum 20 characters). Current type and estimate hash are fetched automatically — no need to supply previous values.

### tasks-assign

Assigns a task to a staff member or capability by code.

- **Parameters:** `taskId` (required), `assignTo` (staff or capability code — auto-resolved)
- **Notes:** Codes are resolved to GUIDs internally. Use `staff-list` or `capability-list` to find codes.

### tasks-notes-read

Returns current notes on a task as markdown.

- **Parameters:** `taskId` (required)

### tasks-notes-append

Appends content to existing task notes.

- **Parameters:** `taskId` (required), `content` (required)
