# filter-projects

Search for projects using structured filter criteria.

## When To Use

- Searching onboarding/teardown/program projects by type, subType, and module
- Filtering projects by status or priority
- Finding projects by manager or client code
- Looking for projects created/updated within a time window

## When Not Use

- Keyword/semantic project search in free text. Use documentation/knowledge semantic search tools for that.

## Input

```yaml
type:
  type: string[]
  required: false
  description: Project type code(s), e.g. RMA, LIC, PRG.
subType:
  type: string[]
  required: false
  description: Project sub-type code(s), e.g. ONB, ADM, INT.
module:
  type: string[]
  required: false
  description: Module code(s), e.g. CW1, HTD, ICO.
status:
  type: string[]
  required: false
  description: Project status code(s). Default excludes CLS.
priority:
  type: string[]
  required: false
  description: Priority code(s).
managerCode:
  type: string
  required: false
  description: Project manager staff code.
clientCode:
  type: string
  required: false
  description: Client organisation code.
createdAfter:
  type: string
  required: false
  description: Filter projects created on or after this ISO date.
createdBefore:
  type: string
  required: false
  description: Filter projects created on or before this ISO date.
updatedAfter:
  type: string
  required: false
  description: Filter projects updated on or after this ISO date.
updatedBefore:
  type: string
  required: false
  description: Filter projects updated on or before this ISO date.
sortBy:
  type: string
  required: false
  description: Sort field, default createdAt descending.
sortOrder:
  type: string
  required: false
  description: Sort direction (asc/desc), default asc when sortBy is provided.
skip:
  type: integer
  required: false
  default: 0
  description: Pagination offset.
top:
  type: integer
  required: false
  default: 50
  description: Results per page (max 200).
```

## Output

TOON format with:

- `types`: `{ Code, Description }[]` for type values present in the result set
- `subTypes`: `{ Code, Description }[]` for subType values present in the result set
- `modules`: `{ Code, Description }[]` for module values present in the result set
- `statuses`: `{ Code, Description }[]` for status values present in the result set
- `staff`: `{ Code, Name }[]` for staff codes present in the result set
- `organisations`: `{ Code, Name }[]` for client organisation codes present in the result set
- `projects`: project rows

## Examples

```
filter-projects(type: ["RMA"], subType: ["ONB"], module: ["CW1"])
filter-projects(status: ["OPN", "WRK"], managerCode: "ABC", top: 50)
filter-projects(clientCode: "WTGAU", createdAfter: "2026-01-01")
```

## Tips

- If the user wants only active projects, rely on the default status filter (CLS is excluded).
- Use `skip` + `top` for pagination when scanning large project sets.
- Keep `top` small when you plan to follow up with per-project detail calls.
