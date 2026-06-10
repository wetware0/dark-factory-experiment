# PAVE NCN Shapes Reference

## Shape Types

| Code  | Description          | Notes                                                                           |
| ----- | -------------------- | ------------------------------------------------------------------------------- |
| `SYS` | Root system diagram  | Container only, **hidden from UI search**. Do not use for new diagrams          |
| `DIA` | Root diagram         | Container only, **visible in UI search**. Created via `pave-ncn-create-diagram` |
| `SWF` | Workflow shape       | Maps to a PAVE process/workflow step; can be child of DIA or DLV                |
| `SHP` | Generic shape / task | Can be nested under `DLV`, `SWF`, or another `SHP`                              |
| `MIL` | Milestone            | Gate shape. Marks a completion point; can be child of DIA or DLV                |
| `DLV` | Deliverable          | **Container**. Groups related work (SHP, MIL, SWF children); child of DIA only  |
| `BUF` | Buffer               | ⚠️ **Only valid on scaled diagrams**. Do NOT use on standard diagrams           |
| `ANO` | Annotation           | Visual only. No deps, no affinities, no status                                  |

### Hierarchy constraints

- `DLV`, `SWF`, `SHP`, `MIL`, `BUF`, `ANO` can be children of `SYS` or `DIA`
- `SHP`, `MIL`, `SWF` can also be children of `DLV` (grouped inside a deliverable)
- `SHP` can also be a child of `SWF` or another `SHP`
- `ANO`, `BUF` cannot be children of `DLV`, `SWF`, or `SHP`
- **Containers** (cascade-delete children): `DIA`, `DLV`, `SWF`

---

## Shape Statuses

| Code  | Meaning   | Notes                                                                        |
| ----- | --------- | ---------------------------------------------------------------------------- |
| `UNK` | Unknown   | Use for `SWF` shapes linked to ProcessHeaders. Inherits live workflow status |
| `OPN` | Open      | Not yet started                                                              |
| `ASN` | Assigned  | Assigned to someone                                                          |
| `WRK` | Working   | In progress                                                                  |
| `SUS` | Suspended | Paused                                                                       |
| `CAN` | Cancelled | Terminal. Cannot transition out                                              |
| `CLS` | Closed    | Terminal. Server auto-sets `CompletionDateUtc` on transition                 |

**Do not** apply status to `ANO` shapes.  
**Do not** apply status to `SYS` or `DIA` shapes.

---

### Affinity eligibility

Only `SHP`, `MIL`, `SWF`, and `DLV` shapes can have affinities linked to them.
`ANO`, `DIA`, and `SYS` shapes **cannot** have affinities.

---

## Attachment (Dependency) Types

| Code  | Direction       | Use for                                                                         |
| ----- | --------------- | ------------------------------------------------------------------------------- |
| `DEP` | From → To       | Standard finish-to-start sequencing                                             |
| `RES` | From → To       | Resource contention. Shapes share a scarce resource and cannot run concurrently |
| `BUF` | BUF → protected | ⚠️ **Only valid on scaled diagrams**. Do NOT use on standard diagrams           |
| `SCL` | From → To       | ⚠️ **Only valid on scaled diagrams**. Do NOT use on standard diagrams           |

`DEP` and `RES` attachments **cannot be deleted if approved**. Decouple first.

---

## Tools

### Read

```
pave-ncn-read-shape
  shapeId: <GUID>
→ ShapeSummary (id, name, type, status, diagramId, ...)
```

### Create

```
pave-ncn-create-shape
  diagramId:     <root DIA shapeId>
  shapeTypeCode: <code from table above>
  name:          <display name>
  description:   <optional>
  parentShapeId: <parent shape ID, required for non-root shapes>
→ { shapeId: "..." }
```

### Delete

```
[NOTE: shape delete not exposed by MCP]
  shapeId: <GUID>
  confirmCascade: true    ← required for container shapes (DIA, DLV, SWF)
```

> Containers (DIA, DLV, SWF) cascade-delete all children, dependencies, and affinity links.
> Delete leaf shapes and dependencies individually before deleting containers.
> Deletion does not auto-cascade to dependencies via the MCP API.

### Update status

```
pave-ncn-update-shape-status
  shapeId:    <GUID>
  statusCode: "OPN" | "ASN" | "WRK" | "SUS" | "CAN" | "CLS"
```

Call once per shape. Do not set status on `ANO`, `SYS`, or `DIA` shapes.

### Create dependency

```
pave-ncn-create-dependency
  fromShapeId:        <prerequisite shapeId>
  toShapeId:          <dependent shapeId>
  dependencyTypeCode: "DEP" | "RES"
→ { attachmentId: "..." }
```

> ⚠️ Do NOT use `BUF` or `SCL` dependency types on standard diagrams. They are only valid on scaled diagrams.

### Delete dependency

```
[NOTE: dependency delete not exposed]
  attachmentId: <GUID>
```

---

## Common Error Codes (HTTP 422)

| Error                   | Cause                                                                                      |
| ----------------------- | ------------------------------------------------------------------------------------------ |
| `ShapeNotFound`         | `shapeId` or `diagramId` GUID does not exist. Verify with `pave-ncn-read-shape`            |
| `DiagramShapeNotFound`  | `diagramId` is not a valid diagram shape                                                   |
| `InvalidShapeType`      | `shapeTypeCode` is not a valid code. Codes are case-sensitive                              |
| `InvalidShapeStatus`    | `statusCode` is not valid or is a terminal state being re-entered                          |
| `InvalidDependencyType` | `dependencyTypeCode` is not one of: `DEP`, `RES` (or `BUF`, `SCL` on scaled diagrams only) |
| `ErrorSavingShape`      | Transient server error. Retry once                                                         |
