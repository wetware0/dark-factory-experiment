# lookup-workitem-change-types

Retrieve workitem change type code-description pairs for a criteria chain.

## Domain Meaning

`changeType` is the work category under a specific product/area/module. Product teams use it to distinguish why work exists and how it should be treated, for example defect fixes, product enhancements, requests for refinement, performance work, maintenance, or design/investigation work.

The code is not global. A code is valid only for the selected product/area/module chain. The same product may expose different change types in different areas or modules.

## When To Use

- Finding valid `changeType` codes for `filter-workitems`
- Choosing a `changeType` before calling `update-workitem`
- Understanding whether a workitem represents a fix, enhancement, issue, maintenance task, design task, or another product work category
- Preparing to look up priorities, because `lookup-workitem-priorities` requires `changeType`

## Input

```yaml
product:
  type: string
  required: true
  description: Product code, e.g. ENT.
area:
  type: string
  required: true
  description: Area code within the product, e.g. RAT.
module:
  type: string
  required: true
  description: Module code within the product/area, e.g. WRS.
```

## Output

Returns CSV with:

- `code` - change type code, e.g. `FIX`
- `description` - change type description

Common descriptions seen in tests and live lookups include `FIX` = `Defect Fix` and `PRD` = `Product Enhancement`. Always prefer the returned `description` over memorized code meanings.

## Examples

```
lookup-workitem-change-types(product: "ENT", area: "RAT", module: "WRS")
```

## Tips

- Use `lookup-products()` and `lookup-modules(product: "ENT")` first when product or module code is unknown.
- Known values include `FIX`, `PRD`, `ISS`, `RFF`, `PER`, `AMN`, `DEP`, `ENO`, `PRU`, `GEN`, `SPI`, `DES`, `QIN`, and `MTN`, but availability depends on the product/area/module chain.
- Use change type to narrow searches by intent. Example: `FIX`/defect fix for regression hunting; `PRD`/product enhancement for feature history.
- After choosing a change type, call `lookup-workitem-priorities` with the same product, area, and module to find the valid priority/routing buckets.
