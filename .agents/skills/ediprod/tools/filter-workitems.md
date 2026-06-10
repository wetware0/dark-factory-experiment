# filter-workitems

Search for workitems using filter criteria.

## When To Use

- Searching for workitems by product, module, or change type
- Finding workitems with specific status
- Looking for workitems created by a specific user
- Finding workitems created within a time window
- Finding closed workitems completed within a time window
- Getting an overview of recent workitems

## When Not Use

- Searching workitems by keywords/query text. Use semantic search tools instead available in knowledge/documentation MCPs.

## Input

```yaml
product:
  type: string
  required: true
  description: Product code (e.g., ENT). Use lookup-products() to find valid codes.
area:
  type: string[]
  required: false
  description: Product area codes (3-character). A high-level categorization within a product.
module:
  type: string[]
  required: false
  description: Module codes (activity types). Use lookup-modules(product: "ENT") to find codes.
status:
  type: string[]
  required: false
  description: Status codes (OPN, ASN, WRK, SUS, CLS, CAN).
changeType:
  type: string[]
  required: false
  description: Work category/change type codes. Use lookup-workitem-change-types(product: "ENT", area: "RAT", module: "WRS") to find codes.
createdUser:
  type: string
  required: false
  description: Staff code of creator. Use staff-list to find codes.
createdAfter:
  type: string
  required: false
  description: Filter workitems created on or after this ISO date (e.g. 2026-01-01).
createdBefore:
  type: string
  required: false
  description: Filter workitems created on or before this ISO date (e.g. 2026-03-31).
completedAfter:
  type: string
  required: false
  description: Filter workitems where all workflows are completed and the latest completion is on or after this ISO date (e.g. 2026-01-01).
completedBefore:
  type: string
  required: false
  description: Filter workitems where all workflows are completed and the latest completion is on or before this ISO date (e.g. 2026-12-31).
sortBy:
  type: string
  required: false
  description: Sort results by field. Valid values: number, title, product, area, module, changeType, status, createdAt, updatedAt. Default: createdAt (descending).
sortOrder:
  type: string
  required: false
  description: Sort direction when sortBy is specified. Valid values: asc, desc. Default: asc.
skip:
  type: integer
  required: false
  default: 0
  description: Pagination - number of results to skip.
top:
  type: integer
  required: false
  default: 20
  description: Pagination - results per page (max 50).
```

## Output

CSV format with columns:
Number, Summary, Product, Area, Module, ChangeType, Status, Created, Updated, Completed, Created By

- `Created`, `Updated`, and `Completed` are ISO 8601 date strings (`YYYY-MM-DD`).
- `Completed` is `N/A` unless all workflows on the workitem have a completion date.

## Examples

```
filter-workitems(product: "ENT")
filter-workitems(product: "ENT", area: ["IAM"])
filter-workitems(product: "ENT", status: ["WRK"], createdAfter: "2026-01-01")
filter-workitems(product: "ENT", module: ["CUS"], changeType: ["FIX"])
filter-workitems(product: "ENT", createdUser: "JDS")
filter-workitems(product: "ENT", status: ["CLS"], completedAfter: "2026-01-01")
filter-workitems(product: "ENT", status: ["CLS"], completedAfter: "2026-01-01", completedBefore: "2026-12-31")
filter-workitems(product: "ENT", skip: 20, top: 20)  // Page 2
filter-workitems(product: "ENT", sortBy: "updatedAt", sortOrder: "desc")  // Most recently updated first
filter-workitems(product: "ENT", sortBy: "createdAt", sortOrder: "asc")   // Oldest first
```

## References

### Product Codes

It is a 3-letter internal code. Use `lookup-products()` to find all valid product codes and their descriptions.

### Area

It is a 3-letter code representing a high-level categorization of workitems within a product.

### Module Codes

It is a 3-letter code representing a specific module or component within the product. Use `lookup-modules(product: "ENT")` to find valid module codes and their descriptions.

### Change Type Codes

Change type is the product-facing category of work under a product/area/module. Use it to filter by intent: defect fixes, product enhancements, issue work, performance work, maintenance, design/investigation work, and similar categories. It is also required before you can look up valid priority values.

```yaml
Known values: FIX, PRD, ISS, RFF, PER, AMN, DEP, ENO, PRU, GEN, SPI, DES, QIN, MTN
```

**Note:** Use `lookup-workitem-change-types(product: "ENT", area: "RAT", module: "WRS")` to find valid codes for the exact product/area/module chain.

### Priority Codes

Priority is not available as a `filter-workitems` filter today, but it matters when updating criteria. It is the urgency/routing bucket for the full product/area/module/changeType chain. Use `lookup-workitem-priorities(product: "ENT", area: "RAT", module: "WRS", changeType: "FIX")` before setting priority with `update-workitem`.

### Status Codes

```yaml
OPN: Open Pending Allocation
ASN: Assigned
WRK: Working
SUS: Suspended (Temporary Pause)
CLS: Closed as Completed
CAN: Cancelled
```

### Created By

It is a 3-character staff code representing the user who created the workitem. Use `staff-list` to find staff codes and their corresponding names.

## Pagination

Use `skip` and `top` parameters for pagination:

- Results 1-20: `skip: 0, top: 20` (default)
- Results 21-40: `skip: 20, top: 20`
- Results 41-60: `skip: 40, top: 20`

When results equal the `top` value, more results may be available.

## Tips

- Always start with product filter (required)
- Use at least 2 filters to narrow down results effectively
- `completedAfter` and `completedBefore` only match workitems where every workflow is completed
- Resolve required codes (product, module, change type, status, user) from the context and other ediprod tools available to you. If a code is required but can't be resolved, ask the user for it instead of making assumptions.
