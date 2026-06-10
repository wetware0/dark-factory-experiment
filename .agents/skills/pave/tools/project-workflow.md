# PAVE Project & Workflow Tools

Two tools for project management in PAVE.

## pave-create-project

Creates a new PRJ project in ediProd.

- **Parameters:** `typeCode`, `subTypeCode`, `moduleCode`, `priorityCode`, `name`, `details`

## pave-manage-project

Single tool for reading and updating project details. Uses an `action` enum:

| Action            | Purpose                                                      | Extra Parameters                                        |
| ----------------- | ------------------------------------------------------------ | ------------------------------------------------------- |
| `get-details`     | Returns current stage, product criteria, and section content | none                                                    |
| `update-stage`    | Advances or changes the project stage                        | `stageCode`                                             |
| `update-criteria` | Updates product criteria codes                               | `typeCode`, `subTypeCode`, `moduleCode`, `priorityCode` |
| `append-section`  | Appends content to a project section                         | `section`, `content`                                    |

All actions accept a `projectNumber` (e.g. "PRJ00049378") instead of a GUID.

### Valid section values for append-section

`problem-statement`, `benefits-for-wisetech`, `benefits-for-customers`, `outcomes`, `key-dependencies`, `key-risks`, `deliverables`, `success-criteria`, `assumptions`, `constraints`, `boundaries`

### Notes

- `update-stage` returns HTTP 422 if the transition is invalid for the current stage.
- `append-section` fetches current content first, then appends after a newline.
