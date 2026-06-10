---
name: ediprod
description: Guide for interacting with the ediProd system via the MCP server. Use when working with work items (WI), incidents (CS), projects (PRJ), workflows, tasks, staff management, or document operations in ediProd/PAVE. Applies to any ediProd data queries, job tracking, incident management, or productivity tool operations.
---

# ediProd MCP Server Skill

This skill provides guidance for interacting with the ediProd system through the MCP server tools.

## About ediProd

**ediProd** is WiseTech Global's internal CargoWise implementation used for corporate operations. It integrates with **PAVE (Productivity Acceleration and Visualization Engine)** which manages work scheduling, prioritization, visibility, and measurement.

## Main Entities

### Jobs

Jobs are top-level containers of work representing deliverables. Three job types are supported:

| Type          | Prefix | Description                                                       |
| ------------- | ------ | ----------------------------------------------------------------- |
| **Work Item** | `WI`   | Development or administrative work units (e.g., `WI00878427`)     |
| **Incident**  | `CS`   | Client-reported issues or requests (e.g., `CS00034343`)           |
| **Project**   | `PRJ`  | Lead projects that group related work items (e.g., `PRJ00049378`) |

### Workflows

Workflows are collections of one or more tasks that represent a discrete deliverable or stage of work within a job. Workflows can be connected via dependency relationships; a workflow may be **blocked** when prerequisites are incomplete.

Some systems also include a special “job-level workflow” which reflects overall job status.

### Issues and Exceptions

**Issues** are aggregated error records automatically created by ediProd's Issue Manager from application crash reports. They are **not** the same as Incidents (CS jobs filed by customers). The pipeline:

1. A WTG application (e.g., CargoWise/CW1) throws an unhandled exception and sends an XML error report to the **Error Reporting Web Service**.
2. ediProd periodically retrieves these reports and deduplicates them by exception fingerprint (type + source + message) into a single Issue. The same recurring bug always maps to the same Issue; `failCount` increments on each new occurrence.
3. Issues are linked to Work Items via the **Related Issues** relationship in the job record.

An **Exception occurrence** is one individual crash report grouped under an Issue. Each has a server name, product version, company code, timestamp, and custom fields (e.g., `Domain`, `HResult`). Summary tools omit long fields such as call stacks.

Key fields: `issueNumber`, `exceptionMessage`, `exceptionType`, `exceptionSource`, `failCount`, `firstVersionNumber`/`lastVersionNumber` (version range where the bug was seen), `fixedDate` (if set but `lastReported` is later, the issue has regressed), `isClientVisible`.

Related tools: `get-job-details` (exposes the Related Issues table with `issueId`), `get-issue-details` (issue metadata and short occurrence fields), `get-exception-content` (full raw XML and call stack for a specific occurrence).

### Tasks

Tasks are single units of work assigned to staff or capabilities. Tasks have:

- **Status**: raw task status code returned by [get-job-tasks](tools/get-job-tasks.md)
- **Staff assignment** or **Capability** (user group)
- **Duration estimates** and actual time tracking
- **Task notes** for communication

### Buffer Board / Visual Board

The Buffer Board displays tasks organized by staff channels and zones (aging indicators). Tasks move up the board as they age, with zones representing urgency levels.

## Presenting Jobs to Users

When presenting a job (workitem, incident, or project) to the user, always include the direct ediProd URL from the metadata block as a clickable markdown hyperlink:

```markdown
[WI00123456](https://ediprod.cw.wisetechglobal.com/link/ShowEditForm/WorkItem/...?lang=en-gb)
[CS00034343](https://ediprod.cw.wisetechglobal.com/link/ShowEditForm/SupportIncident/...?lang=en-gb)
[PRJ00049378](https://ediprod.cw.wisetechglobal.com/link/ShowEditForm/Project/...?lang=en-gb)
```

`get-job-details` returns this value as `url` in the metadata block.

## Reference Codes

Tool-specific code lists are documented alongside the tools that use them:

- Incident criticality and status codes: [filter-incidents](tools/filter-incidents.md)
- Project status and criteria code guidance: [filter-projects](tools/filter-projects.md)
- Workitem change type codes: [lookup-workitem-change-types](tools/lookup-workitem-change-types.md)
- Workitem priority codes: [lookup-workitem-priorities](tools/lookup-workitem-priorities.md)
- Document type codes: [upload-file](tools/upload-file.md)
- Task status codes (raw): [get-job-tasks](tools/get-job-tasks.md)

## Available Tools

### Job Information Tools

- [get-job-details](tools/get-job-details.md) - Get comprehensive workitem/incident/project details
- [get-job-tasks](tools/get-job-tasks.md) - Get tasks grouped by workflow (assignments, durations, startable, notes)
- [get-job-workflows](tools/get-job-workflows.md) - Get workflow summary with tags and release groups
- [update-workitem](tools/update-workitem.md) - Update workitem title / description / criteria (product/area/module/changeType/priority)
- [lookup-products](tools/lookup-products.md) - List product code-description pairs
- [lookup-modules](tools/lookup-modules.md) - List module code-description pairs
- [lookup-workitem-change-types](tools/lookup-workitem-change-types.md) - List workitem change type code-description pairs
- [lookup-workitem-priorities](tools/lookup-workitem-priorities.md) - List workitem priority code-description pairs

### Issue Tools

- [get-issue-details](tools/get-issue-details.md) - Get issue metadata and short exception occurrence fields
- [get-exception-content](tools/get-exception-content.md) - Get raw exception XML and full call stack for an occurrence

### Incident Tools

- [filter-incidents](tools/filter-incidents.md) - Search incidents by criteria
- [update-incident](tools/update-incident.md) - Append to incident summary
- [send-conversation-message](tools/send-conversation-message.md) - Post an internal incident conversation message

### Project Tools

- [filter-projects](tools/filter-projects.md) - Search projects by criteria
- [update-project](tools/update-project.md) - Update project title / description

### Staff Tools

- [staff-list](tools/staff-list.md) - Find staff by name or code
- [staff-get](tools/staff-get.md) - Get detailed staff profile including capabilities
- [staff-group-list](tools/staff-group-list.md) - Find staff groups by name or code
- [staff-group-get](tools/staff-group-get.md) - Get staff group details and member list
- [capability-list](tools/capability-list.md) - Find capabilities by code or description
- [capability-get](tools/capability-get.md) - Get capability details and assigned staff
- [get-tickets](tools/get-tickets.md) - Get tickets for staff or capability
- [staff-tasks](tools/staff-tasks.md) - Get running and startable tasks for a staff member across PAVE boards

### Task Tools

- [task-notes-read](tools/task-notes-read.md) - Read task notes
- [task-notes-append](tools/task-notes-append.md) - Append to task notes
- [task-update](tools/task-update.md) - Update task description, type, and/or estimate

### Document Tools

- [read-file](tools/read-file.md) - Read attached documents
- [upload-file](tools/upload-file.md) - Upload documents to jobs

## Common Workflows

Use these workflows as your starting point for common ediProd tasks.
If you can't find an exact match, use check other workflow, learn the patterns and adapt.
Start with [getting-started](workflows/getting-started.md) for the core operations.

- [getting-started](workflows/getting-started.md) - Core workflows for jobs, incidents, staff, and documents
- [workflows-and-tasks](workflows/workflows-and-tasks.md) - How to inspect workflows, startable tasks, and task notes
- [search-incidents](workflows/search-incidents.md) - Search incidents using semantic search
- [search-workitems](workflows/search-workitems.md) - Search work items using semantic search

---

## PAVE Tools

For PAVE-specific operations (task lifecycle, task CRUD, NCN diagrams, projects),
see the dedicated **pave** skill. PAVE tools include:

- **Task lifecycle**: `tasks-action` (actions: claim, start, claim-and-start, suspend, resume, cancel, complete, reopen)
- **Task CRUD**: `tasks-create`, `tasks-update`, `tasks-assign`
- **Task notes**: `tasks-notes-read`, `tasks-notes-append`
- **NCN diagrams**: `pave-ncn-create-diagram`, `pave-ncn-create-dependency`, `pave-ncn-auto-layout`, `pave-ncn-get-diagrams`
- **NCN shapes**: `pave-ncn-create-shape`, `pave-ncn-read-shape`, `pave-ncn-update-shape`, `pave-ncn-update-shape-status`
- **NCN affinities**: `pave-ncn-manage-affinity` (list/create/link/unlink/delete)
- **Projects**: `pave-create-project`, `pave-manage-project` (get-details/update-stage/update-criteria/append-section)
- **Workflow templates**: `reapply-workflow-template` (reapply templates on WI/CS/PRJ)
