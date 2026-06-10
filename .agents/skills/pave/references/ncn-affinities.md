# PAVE NCN Affinities Reference

## What Are Affinities?

Affinities are **named resource groups** attached to a network diagram. When multiple shapes
belong to the same affinity, the `allowedConcurrency` value caps how many of them can be in
active states simultaneously, enforcing resource leveling.

**Examples:**

- A crane affinity with `allowedConcurrency: 1` → only one task using the crane can run at a time
- A review team affinity with `allowedConcurrency: 2` → at most two reviews can run in parallel
- `allowedConcurrency: 0` → unlimited (affinity is informational only)

### Storage model

Affinities are **non-persistent**. They are stored as XML within the root diagram shape
(`DIA`), not as separate database rows. This means:

- Affinities are scoped to a single diagram
- Deleting the diagram deletes all its affinities
- Always use `pave-ncn-manage-affinity (action: list)` to list current affinities before creating new ones,
  to avoid duplicates when extending an existing diagram

---

## Tools

### List affinities on a diagram

```
pave-ncn-manage-affinity (action: list)
  diagramId: <root DIA shapeId>
→ AffinityDefinition[]. Each has { affinityId, name, color, allowedConcurrency }
```

### Create an affinity

```
pave-ncn-manage-affinity (action: create)
  diagramId:          <root DIA shapeId>
  name:               "Resource Group Name"
  color:              "DodgerBlue"    (Microsoft KnownColor name, NOT hex)
  allowedConcurrency: 1
→ { affinityId: "..." }
```

Affinities can be created in parallel with each other. They don't reference one another.

### Delete an affinity

```
pave-ncn-manage-affinity (action: delete)
  diagramId:  <root DIA shapeId>
  affinityId: <GUID>
```

Unlink the affinity from all shapes **before** deleting it.

### Link an affinity to a shape

```
pave-ncn-manage-affinity (action: link)
  shapeId:    <shapeId to tag>
  affinityId: <affinityId>
```

A shape can belong to multiple affinities. Create one call per `(shape, affinity)` pair.
Links must be executed sequentially to avoid HTTP 412 ETag conflicts on the diagram.

### Unlink an affinity from a shape

```
pave-ncn-manage-affinity (action: unlink)
  shapeId:    <shapeId>
  affinityId: <affinityId>
```

---

## Colour Format

Colours must be **Microsoft KnownColor names**, not hex values.

Examples: `"DodgerBlue"`, `"ForestGreen"`, `"Coral"`, `"MediumPurple"`, `"Gold"`, `"OrangeRed"`,
`"Teal"`, `"Salmon"`, `"DarkBlue"`, `"LightSkyBlue"`, `"Tomato"`, `"SlateBlue"`.

Any valid .NET `System.Drawing.KnownColor` name is accepted. Choose colours that make sense
for the diagram's context.

---

## Common Patterns

### Exclusive resource (one at a time)

```
pave-ncn-manage-affinity (action: create)  name:"<resource name>"  color:"<any KnownColor>"  allowedConcurrency:1
→ link to all shapes that use this resource
```

### Bounded parallel (limited team)

```
pave-ncn-manage-affinity (action: create)  name:"<team name>"  color:"<any KnownColor>"  allowedConcurrency:3
→ link to all shapes that need this team
```

### Multiple affinities on one shape

A shape that needs both a crane and a QA reviewer:

```
pave-ncn-manage-affinity (action: link)  shapeId:TASK-X  affinityId:CRANE-AFF
pave-ncn-manage-affinity (action: link)  shapeId:TASK-X  affinityId:QA-AFF
```

Both calls must be executed sequentially (HTTP 412 ETag conflicts occur on parallel writes).

---

## Ordering Rules

1. **Create affinities before linking**. A link call with an unknown `affinityId` returns HTTP 422
2. **List before creating on existing diagrams**. Use `pave-ncn-manage-affinity (action: list)` to avoid duplicates
3. **Unlink before deleting**. Removing an affinity while shapes are still linked may cause errors

---

## Common Errors (HTTP 422)

| Error                  | Cause                                                                                                      |
| ---------------------- | ---------------------------------------------------------------------------------------------------------- |
| `DiagramShapeNotFound` | `diagramId` is not a valid diagram shape GUID                                                              |
| `AffinityNotFound`     | `affinityId` does not exist on this diagram. Check with `pave-ncn-manage-affinity (action: list)`          |
| `ShapeNotFound`        | `shapeId` does not exist. Check with `pave-ncn-read-shape`                                                 |
| `InvalidAffinityLink`  | Attempting to link an `ANO`, `DIA`, or `SYS` shape. Only SHP, MIL, SWF, and DLV shapes can have affinities |
