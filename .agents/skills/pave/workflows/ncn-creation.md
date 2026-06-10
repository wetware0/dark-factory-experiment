---
name: ncn-creation
description: >
  Build complete PAVE Network Diagrams (NCN) end-to-end. Use when creating or extending network
  diagrams with shapes (workflows, milestones, deliverables, annotations), dependencies,
  affinities, and statuses via the mcp-ediprod PAVE tools.
---

# PAVE Network Diagram (NCN) Creation

A **PAVE Network Diagram (NCN)** is a hierarchical task network used for project planning and
schedule protection in CargoWise Buffer Management. It is composed of:

- **Shapes** - tasks, milestones, deliverables, annotations arranged in a hierarchy
- **Dependencies** - directed arrows expressing "X must finish before Y starts"
- **Affinities** - named resource groups that enforce concurrency limits across shapes

---

## ⛔ CRITICAL - Read Before Building

### ⛔ NEVER add `BUF` shapes unless explicitly requested

Buffer shapes (`BUF`) exist **only** for critical-chain schedule protection. If the spec or work
item does not mention "buffer", "CCPM", "schedule protection", or "feeding buffer" - **omit all
`BUF` shapes and `BUF`-type dependencies entirely.**

The worked example in this skill has **zero** buffers. New diagrams do not need them by default.

### ⛔ NEVER use hex values for affinity colours

Affinity colours must be **Microsoft KnownColor names** - the API does not accept hex values.

Examples: `"DodgerBlue"`, `"ForestGreen"`, `"Coral"`, `"MediumPurple"`, `"Gold"`, `"OrangeRed"`,
`"Teal"`, `"Salmon"`, `"DarkBlue"`, `"LightSkyBlue"`, `"Tomato"`, `"SlateBlue"`.

Pass KnownColor name directly: `color:"DodgerBlue"` - never a hex value like `"#BAE6FD"`.
Any valid .NET `System.Drawing.KnownColor` name is accepted.

### ⛔ NEVER use `ANO` shapes as structural elements

`ANO` (Annotation) shapes are **diagram comments only**. They cannot have dependencies,
affinities, or status updates. Use them solely for human-readable notes like:

- `"Critical path: Backend → QA → Release"`
- `"External dependency on Platform team"`

**Never** use `ANO` to represent a task, hand-off, or gate.

---

## Domain Rules

These rules are enforced server-side. Violating them returns HTTP 422.

### Shape types

| Code  | Description                                      | Can be child of DIA? | Can be child of DLV? |   Can have children?    |   Can have deps?   |
| ----- | ------------------------------------------------ | :------------------: | :------------------: | :---------------------: | :----------------: |
| `DIA` | Root diagram - **visible in UI search**          |     No (is root)     |          No          |           Yes           |         No         |
| `SYS` | Root system diagram - **hidden from UI**         |     No (is root)     |          No          |           Yes           |         No         |
| `DLV` | Deliverable - **container for related work**     |       **Yes**        |          No          | **Yes** (SWF, SHP, MIL) |      **Yes**       |
| `SWF` | Workflow (maps to a process step)                |         Yes          |       **Yes**        | **Yes** (SHP children)  |      **Yes**       |
| `SHP` | Generic shape / task                             |         Yes          |       **Yes**        | **Yes** (SHP children)  |      **Yes**       |
| `MIL` | Milestone (zero-duration checkpoint)             |         Yes          |       **Yes**        |           No            |      **Yes**       |
| `BUF` | Buffer (schedule protection - explicit use only) |         Yes          |          No          |           No            | **Yes** (BUF type) |
| `ANO` | Annotation (comment only)                        |         Yes          |          No          |           No            |         No         |

Key notes:

- `DIA` shapes created via `pave-ncn-create-diagram` appear in the BufferManagement UI search
- `SYS` shapes are **not visible** in the UI - do not use for new diagrams
- `DLV` is a **container**: SHP, MIL, and SWF shapes can be direct children of a DLV
- `SWF` can also hold SHP children when used to represent a process step
- `SHP` can nest under DLV, SWF, or another SHP
- `MIL` can live inside a `DLV` (as a deliverable checkpoint) or at diagram root (as a project gate)
- `ANO` is visual only - no dependencies, no affinities, no status updates
- `BUF` shapes protect upstream chains; their penetration is auto-derived from prerequisites
- **Containers** that cascade-delete children: `DIA`, `DLV`, `SWF`

### Deliverables as Containers

Deliverables (`DLV`) can be used as containers to group related shapes (SWF, SHP, MIL) by setting
`parentShapeId: <DLV shapeId>`.

Milestones can live inside a DLV (as a deliverable checkpoint) or at diagram root (as a project gate).

### Dependencies

Dependencies can connect any combination of shapes and deliverables. Avoid redundant dependencies
(e.g. if `DLV-A → DLV-B` already exists, you don't also need every child of A connected to every child of B).

### Attachment (dependency) types

| Code  | Use for                                                                     |
| ----- | --------------------------------------------------------------------------- |
| `DEP` | Standard finish-to-start sequencing between tasks                           |
| `RES` | Resource contention - two shapes share a scarce resource                    |
| `BUF` | Buffer protecting a workflow - connects `BUF` shape to each protected shape |
| `SCL` | Links a non-scaled shape to its scaled diagram variant                      |

### Shape statuses

| Code  | Meaning                                                                        |
| ----- | ------------------------------------------------------------------------------ |
| `UNK` | Unknown - use for `SWF` shapes linked to ProcessHeaders (inherits live status) |
| `OPN` | Open / not yet started                                                         |
| `ASN` | Assigned                                                                       |
| `WRK` | In progress                                                                    |
| `SUS` | Suspended                                                                      |
| `CAN` | Cancelled (terminal)                                                           |
| `CLS` | Closed / complete (terminal) - server auto-sets `CompletionDateUtc`            |

**Do not** set status on `ANO` shapes.  
**Do not** set status on `SYS` or `DIA` shapes.  
**Do not** transition out of `CAN` or `CLS` - they are terminal.

### Critical ordering constraint

**You cannot create a dependency before both endpoint shapes exist.**  
Plan creation order: shapes first, dependencies after.

---

## Creation Protocol

Follow this seven-phase sequence. Skipping phases causes cascade failures.

```
Phase 1 → Create the root diagram (DIA shape via pave-ncn-create-diagram)
Phase 2 → Create all non-root shapes (DLVs first, then their children; parents before children)
Phase 3 → Create affinity definitions (before linking any shape to them)
Phase 4 → Create all dependencies (both endpoints must already exist)
Phase 5 → Link shapes to affinities
Phase 6 → Set initial statuses
Phase 7 → Apply auto-layout (FINAL STEP - positions shapes automatically)
```

---

## Phase 1 - Root Diagram

The root `DIA` shape anchors everything. Its `shapeId` (returned as `diagramId`) becomes the
`diagramId` for all subsequent calls. Use the dedicated `pave-ncn-create-diagram` tool -
**not** `pave-ncn-create-shape` - so the diagram appears in the BufferManagement UI search.

**If the diagram already exists:** use `pave-ncn-read-shape` with its known ID. Skip creation.

**If creating from scratch:**

```
pave-ncn-create-diagram
  name: "Project Name Network Diagram"

→ Returns: { diagramId: "ROOT-ID" }
```

Store `ROOT-ID`. Every other call in this diagram uses it as `diagramId`.

> **Why not `pave-ncn-create-shape shapeTypeCode:SYS`?**
> `SYS` shapes are hidden from the UI network diagram search by default.  
> `pave-ncn-create-diagram` calls the same server-side factory that the UI uses (`Factory.New<BMNCNRootDiagramShape>()`)
> which sets `BNS_ShapeType = "DIA"`, making the diagram visible in the search screen.

---

## Phase 2 - Create Shapes

### Creation order

1. Create DLV shapes first (they are parents - children cannot reference them until they exist)
2. Create SWF/SHP/MIL children of each DLV (with `parentShapeId = DLV-ID`)
3. Create root-level MIL shapes (project gates, `parentShapeId = ROOT-ID`)
4. Create ANO shapes last (cosmetic, no dependencies needed from them)

### Parallelisation

Shapes that don't reference each other as parents can be created in parallel.  
Example: all sibling DLV shapes under ROOT-ID can be fired simultaneously.  
Example: all SHP/SWF children of the same DLV can be fired simultaneously.

**Rule:** Parallelise any set of shapes where none of them is a parent of another in the same batch.

### Tool call

```
pave-ncn-create-shape
  diagramId:     ROOT-ID
  shapeTypeCode: "SWF" | "SHP" | "MIL" | "DLV" | "ANO"
  name:          "Human-readable label"
  notes:         "Optional - reference real code artefacts (file paths, class names, what changes)"
  parentShapeId: "PARENT-SHAPE-ID"   ← REQUIRED for all non-DIA/SYS shapes

→ Returns: { shapeId: "SHAPE-ID" }
```

> **CRITICAL:** `parentShapeId` is mandatory for every shape except `SYS` and `DIA` shapes.
> The DB enforces `BNS_BNS_ParentShape NOT NULL` - omitting it causes a 422 / ErrorSavingShape.
>
> - DLV shapes: `parentShapeId = ROOT-ID`
> - SHP/MIL/SWF children of a DLV: `parentShapeId = DLV-ID`
> - SHP children of a SWF: `parentShapeId = SWF-ID`
> - SHP children of another SHP: `parentShapeId = PARENT-SHP-ID`
> - Root-level MIL (project gate): `parentShapeId = ROOT-ID`
> - ANO shapes: `parentShapeId = ROOT-ID`

**Capture every returned `shapeId`.** You need them in all subsequent phases.

### Naming conventions

Use descriptive names for shapes - no strict naming rules, just make them clear.

---

## Phase 3 - Create Affinities

Skip this phase if there are no resource constraints to enforce.

Affinities are stored on the root diagram shape and can be created in parallel with each other.

```
pave-ncn-manage-affinity (action: create)
  diagramId:          ROOT-ID
  name:               "Resource Group Name"
  color:              "DodgerBlue"    ← ALWAYS a Microsoft KnownColor name, NEVER hex
  allowedConcurrency: 1            (1 = exclusive; 2+ = bounded parallel; 0 = unlimited)

→ Returns: { affinityId: "AFF-ID" }
```

Create all affinities **before** Phase 5 (linking shapes). They can't be linked until they exist.

Colour must be a Microsoft KnownColor name (e.g. `"DodgerBlue"`, `"Coral"`, `"ForestGreen"`) - not hex.
Choose any KnownColor that makes sense for the diagram.

---

## Phase 4 - Create Dependencies

A dependency means "From must finish before To can start."

```
pave-ncn-create-dependency
  fromShapeId:        <prerequisite shapeId>
  toShapeId:          <dependent shapeId>
  dependencyTypeCode: "DEP"    (use "RES" for resource contention)

→ Returns: { attachmentId: "ATT-ID" }
```

All dependencies can be fired **in parallel** once Phase 2 is complete (all shapes exist).

### Dependency planning

Before calling tools, map the dependency graph. Prefer DLV→DLV for cross-deliverable sequencing:

```
# Correct - deliverable-level sequencing
DLV-Backend → DLV-Frontend    (entire backend must finish before frontend starts)
```
