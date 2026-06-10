---
name: pave
description: >
  Guide for interacting with PAVE (Productivity Acceleration and Visualization Engine) via the MCP server.
   Use when working with task lifecycle operations, task CRUD, project management, workflow approvals,
   or network diagram (NCN) operations including creating diagrams, inspecting diagram structure,
   visualizing NCNs as Mermaid, and summarizing NCN status. Applies to any PAVE-related automation,
   scheduling, or visualization tasks.
---

# PAVE MCP Server Skill

This skill provides guidance for interacting with PAVE through the MCP server tools.

## About PAVE

**PAVE** (Productivity Acceleration and Visualization Engine) is the scheduling, prioritisation, and
visualisation layer within CargoWise's ediProd system. It manages:

- **Task lifecycle** - claiming, starting, suspending, resuming, completing, and cancelling tasks
- **Task management** - creating, updating, assigning, and reordering tasks within workflows
- **Project management** - creating projects, managing stages, sections, and product criteria
- **Workflow operations** - approval status
- **Network diagrams (NCN)** - visual task networks with shapes, dependencies, affinities, and statuses
- **Staff capacity** - querying staff workload and availability

## Task Lifecycle

Tasks follow a defined state machine. Invalid transitions return HTTP 422.

```
            ┌──────────┐
            │  (new)    │
            └────┬─────┘
                 │ claim
                 ▼
            ┌──────────┐      ┌──────────┐
            │  Claimed  │─────►│  Started  │
            └──────────┘start └────┬─────┘
                                   │
                          ┌────────┼────────┐
                          │        │        │
                     suspend   complete   cancel
                          │        │        │
                          ▼        ▼        ▼
                    ┌─────────┐ ┌────────┐ ┌──────────┐
                    │Suspended│ │Complete│ │Cancelled │
                    └────┬────┘ └────────┘ └──────────┘
                         │                       ▲
                      resume                     │
                         │                    reopen
                         ▼                       │
                    ┌─────────┐            ┌─────┴────┐
                    │ Started │            │ Complete  │
                    └─────────┘            └──────────┘
```

### Lifecycle Tool

All lifecycle transitions use a single tool: `tasks-action`.

| Action            | Precondition                                    |
| ----------------- | ----------------------------------------------- |
| `claim`           | Task is unclaimed                               |
| `start`           | Task is claimed                                 |
| `claim-and-start` | Task is unclaimed (single call, more efficient) |
| `suspend`         | Task is started                                 |
| `resume`          | Task is suspended                               |
| `complete`        | Task is started                                 |
| `cancel`          | Task is started or claimed                      |
| `reopen`          | Task is complete                                |

Required params: `taskId` (GUID), `action` (one of the above).

Optional: `reopenStatus` (required for `reopen` - one of `Working`, `Assigned`, `Suspended`), `actualDurationInMinutes` (for `complete`).

---

## Task CRUD

| Tool                 | Purpose                                        | Key parameters                                                                                                          |
| -------------------- | ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `tasks-create`       | Create a new task in a workflow                | `jobNumber`, `workflowId`, `type`, `description`, `estimateInMinutes`, `staffCode`, `capabilityCode`, `taskInsertAfter` |
| `tasks-update`       | Update task description, type, and/or estimate | `taskId` (GUID), optional: `newDescription`, `newType`, `estimateMinutes`                                               |
| `tasks-assign`       | Assign task to staff or capability             | `taskId` (GUID), `assignTo` (staff or capability code — auto-resolved)                                                  |
| `tasks-notes-read`   | Read task notes                                | `taskId` (GUID)                                                                                                         |
| `tasks-notes-append` | Append to task notes                           | `taskId` (GUID), `content`                                                                                              |

---

## Project Management

| Tool                        | Purpose                             | Key parameters                                                                                                                |
| --------------------------- | ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `pave-create-project`       | Create a new PRJ project            | `typeCode`, `subTypeCode`, `moduleCode`, `priorityCode`, `name`, `details`                                                    |
| `pave-manage-project`       | Read/update project details         | `projectNumber` (PRJ...), `action` (get-details, update-stage, update-criteria, append-section)                               |
| `reapply-workflow-template` | Reapply workflow templates on a job | `jobNumber` (WI/CS/PRJ); optional: `workflowAndTasksOption`, `milestonesOption`, `triggersOption`, `recalculateReleaseGroups` |

### pave-manage-project actions

| Action            | Required params                                         | Returns                           |
| ----------------- | ------------------------------------------------------- | --------------------------------- |
| `get-details`     | -                                                       | JSON with stage + productCriteria |
| `update-stage`    | `stageCode`                                             | Confirmation message              |
| `update-criteria` | `typeCode`, `subTypeCode`, `moduleCode`, `priorityCode` | Confirmation message              |
| `append-section`  | `section`, `content`                                    | Confirmation message              |

### Project Section Codes

The `section` parameter in `append-section` accepts:
`problem-statement`, `benefits-for-wisetech`, `benefits-for-customers`, `outcomes`, `key-dependencies`, `key-risks`, `deliverables`, `success-criteria`, `assumptions`, `constraints`, `boundaries`

---

## Network Diagrams (NCN)

Network diagrams are visual task networks in PAVE's Buffer Management module.
All NCN tools are prefixed with `pave-ncn-*` for easy filtering.

### NCN Tools

| Tool                           | Purpose                                                                                                            |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| `pave-ncn-get-diagrams`        | Query existing NCN diagrams for a job (WI/CS/PRJ)                                                                  |
| `pave-ncn-create-diagram`      | Create root DIA shape (first step)                                                                                 |
| `pave-ncn-create-shape`        | Add shapes (SHP, MIL, DLV, ANO, SWF). Read `references/ncn-shapes.md` for shape types, hierarchy, and CRUD details |
| `pave-ncn-create-dependency`   | Create dependency between shapes. Read `references/ncn-shapes.md` for dependency types                             |
| `pave-ncn-read-shape`          | Read a shape's properties                                                                                          |
| `pave-ncn-update-shape`        | Update shape name, notes, or completionCriteria                                                                    |
| `pave-ncn-update-shape-status` | Update shape status (OPN, ASN, WRK, SUS, CLS, CAN)                                                                 |
| `pave-ncn-manage-affinity`     | Manage affinities (`action: list \| create \| link \| unlink \| delete`)                                           |
| `pave-ncn-auto-layout`         | Apply auto-layout (FINAL step)                                                                                     |

### NCN Workflows

- [ncn-creation](workflows/ncn-creation.md) - Build complete PAVE Network Diagrams (NCN) end-to-end
- [visualize-ncn-diagram](workflows/visualize-ncn-diagram.md) - Generate Mermaid diagrams from NCN breakdown and connection data
- [ncn-status](workflows/ncn-status.md) - Summarize NCN progress across linked work items and phases

### Critical NCN Constraints

1. **No BUF shapes on standard diagrams** - BUF (buffer) shapes and BUF/SCL dependency types are
   only valid on **scaled** diagrams. Using them on standard diagrams causes a runtime
   `DeveloperNotificationException`. Use only SHP, MIL, DLV, ANO, SWF shapes and DEP, RES dependencies.

2. **Affinity colours must be Microsoft KnownColor names** - e.g. `"DodgerBlue"`, `"ForestGreen"`,
   `"Coral"`, `"MediumPurple"`. NOT hex values.

3. **parentShapeId is required** for all non-root shapes. The DB enforces `NOT NULL`.
   - DLV/ANO: parent = DIA root
   - SHP/MIL/SWF: parent = DIA root or a DLV (to group inside a deliverable)
   - SHP can also nest under SWF or another SHP

4. **Create shapes before dependencies** - both endpoint shapes must exist before creating a dependency.

5. **Link affinities sequentially** - parallel affinity links cause HTTP 412 etag conflicts.

6. **Affinity eligibility** - only SHP, MIL, SWF, and DLV shapes can have affinities. ANO, DIA, and SYS cannot.

7. **DLV shapes require the diagram to be linked to a project** - the diagram's `relatedEntityId` must be set to the project GUID for DLV shapes to be valid.

---

### NCN Creation Workflow

Follow this seven-phase sequence when building a network diagram from scratch. Skipping phases causes cascade failures.

```
Phase 1 → Create root diagram (DIA via pave-ncn-create-diagram)
Phase 2 → Create all shapes (DLVs first as containers, then children; parents before children)
Phase 3 → Create affinity definitions (before linking shapes to them)
Phase 4 → Create all dependencies (both endpoint shapes must exist first)
Phase 5 → Link shapes to affinities (SEQUENTIAL — parallel causes 412 etag conflicts)
Phase 6 → Set initial statuses via pave-ncn-update-shape-status (statusCode)
Phase 7 → Apply auto-layout (FINAL step — pave-ncn-auto-layout)
```

#### Shape types

| Code  | Description                              | Can be child of DIA? | Can be child of DLV? |   Can have children?    | Can have deps? |
| ----- | ---------------------------------------- | :------------------: | :------------------: | :---------------------: | :------------: |
| `DIA` | Root diagram (visible in UI search)      |     No (is root)     |          No          |           Yes           |       No       |
| `DLV` | Deliverable (container for related work) |       **Yes**        |          No          | **Yes** (SWF, SHP, MIL) |    **Yes**     |
| `SWF` | Workflow (maps to a process step)        |         Yes          |       **Yes**        | **Yes** (SHP children)  |    **Yes**     |
| `SHP` | Generic shape / task                     |         Yes          |       **Yes**        | **Yes** (SHP children)  |    **Yes**     |
| `MIL` | Milestone (zero-duration checkpoint)     |         Yes          |       **Yes**        |           No            |    **Yes**     |
| `ANO` | Annotation (visual comment only)         |         Yes          |          No          |           No            |       No       |

#### Shape statuses

| Code  | Meaning                      |
| ----- | ---------------------------- |
| `OPN` | Open / not yet started       |
| `ASN` | Assigned                     |
| `WRK` | In progress                  |
| `SUS` | Suspended                    |
| `CAN` | Cancelled (terminal)         |
| `CLS` | Closed / complete (terminal) |

Do not set status on `ANO`, `SYS`, or `DIA` shapes. `CAN` and `CLS` are terminal — no transitions out.

#### Dependency types

| Code  | Use for                                                  |
| ----- | -------------------------------------------------------- |
| `DEP` | Standard finish-to-start sequencing between tasks        |
| `RES` | Resource contention — two shapes share a scarce resource |

> Do NOT use `BUF` or `SCL` dependency types on standard diagrams.

#### Affinities

Affinities are named resource groups that cap how many linked shapes can be active simultaneously.
Colours must be **Microsoft KnownColor names** (e.g. `"DodgerBlue"`, `"Coral"`) — not hex values.
Only SHP, MIL, SWF, and DLV shapes can have affinities. Link sequentially to avoid HTTP 412 etag conflicts.

#### Worked example — 3-phase project with deliverables

```
DIA: "Software Release v2.0"
├── DLV: "Backend Development"
│   ├── SWF: "Requirements Analysis"
│   ├── SWF: "Build & Integration"
│   └── MIL: "Build Verified"
├── DLV: "Testing & QA"
│   └── SWF: "Test Execution"
├── DEP: DLV-Backend → DLV-Testing
├── MIL: "Release Approved" (project-level)
├── DEP: DLV-Testing → MIL-Release
└── ANO: "Critical path: Backend → QA → Release"
```

Phase 1: `pave-ncn-create-diagram name:"Software Release v2.0"` → `{ diagramId: ROOT }`
Phase 2: Create DLVs (parallel, parentShapeId=ROOT), then children (parentShapeId=DLV-ID)
Phase 3: `pave-ncn-manage-affinity action:create diagramId:ROOT name:"Review Team" color:"ForestGreen" allowedConcurrency:2`
Phase 4: Create all DEP dependencies (parallel — all shapes exist)
Phase 5: Link shapes to affinities (sequential, one at a time)
Phase 6: Set statuses via `pave-ncn-update-shape-status statusCode:"OPN"` (exclude ANO shapes)
Phase 7: `pave-ncn-auto-layout diagramId:ROOT` (final step)

Read `references/ncn-shapes.md` for full hierarchy constraints, shape CRUD tools, and error codes.
Read `references/ncn-affinities.md` for affinity tool operations, concurrency patterns, and colour examples.
For end-to-end diagram creation with worked examples, use the [ncn-creation](workflows/ncn-creation.md) workflow.

#### Recovery from failure

Shapes already created persist — do not recreate them. Resume from the phase that failed.
HTTP 412 etag conflicts on affinity links: retry sequentially with ~300ms gaps.

---

## Staff & Time Recording

| Tool              | Purpose                                        | Key parameters                                |
| ----------------- | ---------------------------------------------- | --------------------------------------------- |
| `staff-list`      | Find staff by name or code                     | `query`                                       |
| `capability-list` | Find capabilities by code or description       | `query`                                       |
| `staff-get`       | Get current user's staff details               | `staffCode` (optional, omit for current user) |
| `get-tickets`     | Get tickets on a board for staff or capability | `boardName`, `staffCode` or `capabilityCode`  |

To find board names, use `staff-get` (returns `bufferBoards` list for the staff member) or ask the user directly.

---

## Common Error Codes

| HTTP | Error                   | Cause                                                                     |
| ---- | ----------------------- | ------------------------------------------------------------------------- |
| 422  | Business rule violation | Invalid state transition, missing required field, or constraint violation |
| 412  | Etag conflict           | Concurrent modification - retry after reading latest state                |
| 404  | Not found               | Invalid GUID or job number                                                |

---

## Related Skills

| Skill                     | Use when                                                               |
| ------------------------- | ---------------------------------------------------------------------- |
| **ediprod**               | Working with core ediProd entities (jobs, incidents, staff, documents) |
| **board-troubleshooting** | Diagnosing why tasks don't appear on buffer boards                     |
