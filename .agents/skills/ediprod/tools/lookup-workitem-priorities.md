# lookup-workitem-priorities

Retrieve workitem priority code-description pairs for a criteria chain.

## Domain Meaning

`priority` is the relative business urgency or routing bucket for a workitem after its product classification is known.

Priority values are not global. Valid codes depend on the full criteria chain:
`product -> area -> module -> changeType -> priority`

This is why the tool requires `changeType`; a product enhancement and a defect fix in the same module may have different priority options.

## When To Use

- Finding valid `priority` codes before calling `update-workitem`
- Checking which priorities are valid for a selected product/area/module/changeType chain
- Explaining what priority buckets are available for a work category before changing workitem criteria
- Avoiding invalid updates when moving a workitem between product areas or change types

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
changeType:
  type: string
  required: true
  description: Change type code, e.g. FIX.
```

## Output

Returns CSV with:

- `code` - priority code, e.g. `GPR`
- `description` - priority description

Common descriptions seen in tests and live lookups include `ALP` = `Alpha Release` (means merge to alpha branch), `GPR` = `General Public Release` (means to merge to general public branch and make it available to customers immediately (it takes up to 6 month to promote ALP to GPR)).

## Examples

```
lookup-workitem-priorities(product: "ENT", area: "RAT", module: "WRS", changeType: "FIX")
```

## Tips

- Use `lookup-workitem-change-types` first when `changeType` is unknown.
- Known values include `GPR`, `STD`, `ALP`, `DPR`, `ETL`, `GPC`, `HIH`, `LPB`, `LPR`, `LOW`, `MOD`, and `NON`, but availability depends on the full criteria chain.
- Do not assume a higher/lower ordering from the code text alone. Use the returned description and the surrounding product context.
- If changing product, area, module, or changeType on a workitem, re-check priorities for the new full chain before setting `priority`.
