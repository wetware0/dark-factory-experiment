# PAVE NCN (Network Diagram) Tools

Tools for creating and managing PAVE network diagrams - visual task networks with shapes,
dependencies, affinities, and statuses.

For end-to-end creation workflows, see the NCN section in the **pave** skill.

## Diagram Lifecycle

### pave-ncn-create-diagram

Creates a new root DIA shape visible in the BufferManagement UI search.

- **Parameters:** `name`
- **Returns:** `{ diagramId }` - use as `diagramId` for all subsequent NCN calls.

### pave-ncn-auto-layout

Applies automatic graph layout (MSAGL Sugiyama) to all shapes in a diagram.

- **Parameters:** `diagramId`
- **Call as the FINAL step** after all shapes, dependencies, and affinities are created.
- Only works on standard (non-scaled) diagrams - do NOT use on scaled diagrams or diagrams containing BUF shapes.

## Shape Operations

### pave-ncn-create-shape

Creates a shape within a diagram.

- **Parameters:** `diagramId`, `shapeTypeCode`, `name`, `notes?`, `completionCriteria?`, `parentShapeId`
- **Valid types:** `SHP` (task), `MIL` (milestone), `DLV` (deliverable), `ANO` (annotation), `SWF` (workflow)
- ⚠️ Do NOT use `BUF` - only valid on scaled diagrams
- ⚠️ Do NOT use `DIA` - use `pave-ncn-create-diagram` instead
- ⚠️ `DLV` shapes require the diagram to be linked to a project (relatedEntityId must be set on the DIA root). The tool validates this before creating.
- **parentShapeId** is required for non-root shapes:
  - DLV/ANO: use DIA root ID
  - SHP/MIL/SWF: use DIA root ID or a DLV ID (to group inside a deliverable)
  - SHP can also nest under SWF or another SHP

### pave-ncn-read-shape

Reads shape details.

- **Parameters:** `shapeId`
- **Returns:** Shape summary (id, name, type, status, diagramId, children, etc.)

### pave-ncn-update-shape

Updates shape properties (name, notes, completion criteria).

- **Parameters:** `shapeId`, optional: `name`, `notes`, `completionCriteria`
- Notes and completionCriteria are appended to existing content.
- Update one shape per call.

### pave-ncn-update-shape-status

Updates shape status.

- **Parameters:** `shapeId`, `statusCode`
- **Valid codes:** `OPN` (Open), `ASN` (Assigned), `WRK` (Working), `SUS` (Suspended), `CLS` (Closed), `CAN` (Cancelled), `UNK` (Unknown)
- Do NOT set status on `ANO`, `SYS`, or `DIA` shapes
- `MIL`/`DLV` shapes only accept: `OPN`, `CLS`, `CAN`
- For bulk updates, call once per shape (no batch endpoint)

## Dependency Operations

### pave-ncn-create-dependency

Creates a finish-to-start dependency between two shapes.

- **Parameters:** `fromShapeId`, `toShapeId`, `dependencyTypeCode`
- **Valid types:** `DEP` (standard), `RES` (resource contention)
- ⚠️ Do NOT use `BUF` or `SCL` - only valid on scaled diagrams
- **Returns:** `{ attachmentId }`

## Affinity Operations

### pave-ncn-manage-affinity (action: create)

Creates an affinity (resource group) on a diagram.

- **Parameters:** `diagramId`, `action: "create"`, `name`, `color` (Microsoft KnownColor name), `allowedConcurrency`
- **Color examples:** `"DodgerBlue"`, `"ForestGreen"`, `"Coral"`, `"MediumPurple"`, `"Gold"`
- NOT hex values

### pave-ncn-manage-affinity (action: list)

Lists all affinities on a diagram.

- **Parameters:** `diagramId`, `action: "list"`

### pave-ncn-manage-affinity (action: delete)

Deletes an affinity. Unlink from all shapes first.

- **Parameters:** `diagramId`, `action: "delete"`, `affinityId`

### pave-ncn-manage-affinity (action: link)

Tags a shape with an affinity.

- **Parameters:** `shapeId`, `action: "link"`, `affinityId`
- ⚠️ Link affinity-shape pairs **sequentially** - parallel calls cause HTTP 412 etag conflicts

### pave-ncn-manage-affinity (action: unlink)

Removes an affinity tag from a shape.

- **Parameters:** `shapeId`, `action: "unlink"`, `affinityId`
