# pave-ncn-get-diagrams

Returns NCN (Network Visualisation) diagrams associated with a given workitem, incident, or project. For projects, includes approval status and creation date.

## When To Use

- Viewing network diagrams (NCN) linked to a job
- Checking diagram approval status on projects
- Understanding the visual network structure of a job
- Generating a Mermaid dependency graph for a job's network

## Input

```yaml
jobNumber:
  type: string
  required: true
  description: Job number (WI/CS/PRJ format)
```

## Output

Returns NCN diagrams associated with the job. For projects, includes approval status and creation date.
Each breakdown row includes `shapeId` so you can map shapes to diagram connections via `fromShapeId` and `toShapeId`.

Each diagram contains two key sections:

### Breakdown (shape hierarchy)

Each shape in the breakdown includes:

| Field           | Description                                                                              |
| --------------- | ---------------------------------------------------------------------------------------- |
| `shapeId`       | Unique GUID identifying the shape                                                        |
| `name`          | Display name of the shape                                                                |
| `type`          | Shape type: `Diagram`, `Shape`, `Milestone`, `Deliverable`, `Job`, `WorkItem`, `Project` |
| `status`        | Shape status: `Working`, `Closed`, `Cancelled`, `Ready`, `Blocked`, `NotAchieved`, etc.  |
| `jobNumber`     | Linked job number (e.g. `WI00987654`), if any                                            |
| `depth`         | Nesting depth in the hierarchy tree (0 = root diagram)                                   |
| `lastUpdate`    | Last update timestamp for the shape                                                      |
| `completedTime` | Completion timestamp for the shape, when available                                       |

### Connections (dependency arrows)

Each connection includes:

| Field         | Description                                                                             |
| ------------- | --------------------------------------------------------------------------------------- |
| `fromShapeId` | GUID of the source shape                                                                |
| `toShapeId`   | GUID of the target shape                                                                |
| `type`        | Connection type: `DEP` (dependency), `BUF` (buffer), `RES` (resource), `SCL` (schedule) |

## Mermaid Diagram Generation

> **Tip:** Use the `[visualize-ncn-diagram]` workflow skill to automatically visualize a diagram without manually constructing it. The steps below are for reference if you need to build it yourself.

Use the breakdown and connections output to generate a Mermaid `flowchart LR` diagram.

### Mapping Rules

| Tool Output Field                | Mermaid Element                                                                                                                           |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `shapeId`                        | Node ID — sanitize GUID to short ID (strip hyphens first, then take the first 8 characters, prefix with `shape_`)                         |
| `name` + `jobNumber`             | Node label (use `<br/>` for line breaks; preserve `name` exactly as returned)                                                             |
| `status`                         | Emoji icon in node label: 🟢 Working, ✅ Closed, ❌ Cancelled, ⬜ Ready, 🔴 Blocked, ⭕ NotAchieved                                       |
| `type`                           | Node shape: rectangle `["..."]` for WorkItem/Project/Job, stadium `(["..."])` for Milestone, hexagon `{{"..."}}` for Shape/Buffer/Diagram |
| `connections` with `type: "DEP"` | Solid arrow `-->` with label `\|DEP\|`                                                                                                    |
| `connections` with `type: "BUF"` | Dashed arrow `-.->` with label `\|BUF\|`                                                                                                  |
| `connections` with `type: "RES"` | Solid arrow `-->` with label `\|RES\|`                                                                                                    |
| `connections` with `type: "SCL"` | Dotted arrow `-.->` with label `\|SCL\|`                                                                                                  |
| `depth` hierarchy                | Group shapes by top-level diagram using `subgraph`                                                                                        |

> **Note:** The `fromShapeId`/`toShapeId` values in connections correspond directly to the `shapeId` field in the breakdown.

### Example

Given a diagram with three shapes and two connections, a Mermaid diagram would look like:

```
flowchart LR
    subgraph "Diagram: Main Workflow"
        shape_abc123["Import Customs<br/>WI00987654<br/>🟢 Working"]
        shape_def456["Transport Booking<br/>WI00987655<br/>⬜ Ready"]
        shape_ghi789["Final Delivery<br/>Milestone<br/>⭕ NotAchieved"]
    end

    shape_abc123 -->|DEP| shape_def456
    shape_def456 -->|DEP| shape_ghi789
    shape_abc123 -.->|BUF| shape_def456
```

## Examples

```
pave-ncn-get-diagrams(jobNumber: "WI00878427")
pave-ncn-get-diagrams(jobNumber: "PRJ00049378")
pave-ncn-get-diagrams(jobNumber: "CS00034343")
```

## Tips

- For project jobs (`PRJ`), the output includes both project-level diagrams (with approval status and creation date) and job-level related diagrams.
- For workitems (`WI`) and incidents (`CS`), only related diagrams are returned.
- Use `shapeId` values from the breakdown to match connections — the `fromShapeId` and `toShapeId` fields reference the same GUIDs.
- When generating Mermaid diagrams, group shapes by their root diagram (depth 0) using `subgraph` blocks for clarity.
- Sanitize GUIDs to valid Mermaid node IDs: strip hyphens first, then take the first 8 characters, and prefix with `shape_`.
- Use the `name` field verbatim in node labels; do not remove parenthesized suffixes or other repeated markers.
