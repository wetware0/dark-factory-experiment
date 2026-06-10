# update-workitem

Updates the title, description, and/or criteria (product/area/module/changeType/priority) of a workitem.

## Domain Meaning

Workitem criteria is a product classification chain:

`product -> area -> module -> changeType -> priority`

It describes where the work belongs in the product and how product/delivery teams should classify or route it.

- `product`, `area`, and `module` identify the product family, area, and component.
- `changeType` identifies the kind of work, such as a defect fix or product enhancement.
- `priority` identifies the urgency/routing bucket for that exact chain.

## When To Use

- Updating workitem title/summary
- Appending content to workitem description/details
- Updating or clearing workitem criteria values

## Input

```yaml
workitemNumber:
  type: string
  required: true
  description: Workitem identifier (WI...).
title:
  type: string
  required: false
  description: >
    New title/summary for the workitem. Replaces existing title. Omit to leave unchanged.
description:
  type: string
  required: false
  description: >
    Content to append to the existing description. Fetches current description first and
    appends after a newline separator. Omit to leave unchanged.
product:
  type: string
  required: false
  description: >
    Product family code (e.g. ENT). Omit to preserve. Send "" to clear.
area:
  type: string
  required: false
  description: >
    Product area code (e.g. RAT). Omit to preserve. Send "" to clear.
module:
  type: string
  required: false
  description: >
    Module/component code (e.g. ATR). Omit to preserve. Send "" to clear.
changeType:
  type: string
  required: false
  description: >
    Work category/change type code, e.g. FIX for a defect fix. Use lookup-workitem-change-types to find valid codes. Omit to preserve. Send "" to clear.
priority:
  type: string
  required: false
  description: >
    Priority/routing bucket code for the selected criteria chain. Use lookup-workitem-priorities to find valid codes. Omit to preserve. Send "" to clear.
```

> At least one of `title`, `description`, `product`, `area`, `module`, `changeType`, or `priority` must be provided.
>
> Criteria rules:
>
> - Omit a criteria field to preserve the current value.
> - Send `""` to clear a criteria field.
> - Dependency chain: product -> area -> module -> changeType -> priority.
> - A non-empty lower field requires all upper fields to be non-empty.
> - Clearing an upper field requires clearing dependent lower fields in the same call.

## Output

Updates the workitem details and returns confirmation (or an error if the requested update is not supported).

## Examples

```
update-workitem(workitemNumber: "WI00902989", title: "Updated summary for this workitem")
update-workitem(workitemNumber: "WI00902989", description: "Additional context to append")
update-workitem(workitemNumber: "WI00902989", title: "New title here", description: "More details to add")
update-workitem(workitemNumber: "WI00902989", product: "CSP", area: "COR", module: "BIL")
update-workitem(workitemNumber: "WI00902989", product: "ENT", area: "RAT", module: "WRS", changeType: "FIX", priority: "GPR")
update-workitem(workitemNumber: "WI00902989", priority: "")
update-workitem(workitemNumber: "WI00902989", module: "", changeType: "", priority: "")
```

## Tips

- Use `get-job-details` first to review current criteria values before updating.
- Description appends to existing content — no need to read and concatenate manually.
- Use `lookup-products` and `lookup-modules` to look up product and module codes. Some lookup endpoints may show inactive codes; update validation accepts active codes only.
- Use `lookup-workitem-change-types(product: "ENT", area: "RAT", module: "WRS")` to find valid `changeType` codes.
- Use `lookup-workitem-priorities(product: "ENT", area: "RAT", module: "WRS", changeType: "FIX")` to find valid `priority` codes.
- Change type and priority are product classification fields, not free-form labels. Prefer returned lookup descriptions over guessed code meanings.
- Criteria update happens before title/description — if a criteria code is invalid, no title or description changes are made.
- To clear product, also clear area, module, changeType, and priority.
- To clear area, also clear module, changeType, and priority.
- To clear module, also clear changeType and priority.
- To clear changeType, also clear priority.
