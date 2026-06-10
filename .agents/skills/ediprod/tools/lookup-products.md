# lookup-products

Retrieve product code-description pairs.

## When To Use

- Finding valid product codes for `filter-incidents` or `filter-workitems`
- Exploring what products are available in the system

## Input

```yaml
code:
  type: string
  required: false
  description: Optional product code to return a single product.
```

## Output

Returns CSV with:

- `code` - product code (e.g., `ENT`)
- `description` - product description (e.g., `CargoWise / ediEnterprise`)

## Examples

```
lookup-products()
lookup-products(code: "ENT")
```

## Tips

- Call without arguments first when product code is unknown
- Use returned product codes with `lookup-modules`, `lookup-workitem-change-types`, `lookup-workitem-priorities`, `filter-incidents`, and `filter-workitems`
- Product codes are usually 3 characters
- The flagship product is `ENT` (CargoWise / ediEnterprise). If product is unclear, default to `ENT` or ask the user.
