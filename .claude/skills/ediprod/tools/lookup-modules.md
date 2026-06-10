# lookup-modules

Retrieve module code-description pairs.

## When To Use

- Finding valid module codes within a product
- Exploring what modules are available in the system

## Input

```yaml
product:
  type: string
  required: false
  description: Optional product code to scope module results.
code:
  type: string
  required: false
  description: Optional module code to return a single module.
```

## Output

Returns CSV with:

- `code` - module code (e.g., `CUS`, `BAU`)
- `description` - module description (e.g., `Customs Compliance`, `Australia`)

## Examples

```
lookup-modules()
lookup-modules(product: "ENT")
lookup-modules(product: "ENT", code: "CUS")
```

## Tips

- Use `lookup-products()` first when product code is unknown
- Use returned module codes with `lookup-workitem-change-types`, `lookup-workitem-priorities`, `filter-incidents`, and `filter-workitems`
- Module codes vary by product
- Teams usually handle multiple modules within a product, some teams handle up to 10 modules
