# staff-list

Search for staff members by name or code.

## When To Use

- Finding a staff member when you know their name or code
- Getting staff codes for other tools

## Input

```yaml
query:
  type: string
  required: true
  description: Search query (name, code, or partial match).
```

## Output

Returns list with:

- `code` - Staff code (2-3 characters, e.g., `BAS`, `S.V`, `RW`)
- `displayName` - Full display name
- `isActive` - Whether staff is active

## Examples

```
staff-list(query: "John Smith")
staff-list(query: "Smith")
staff-list(query: "JS")
```

## Tips

- Use the returned `code` with `staff-get` for detailed profile including capabilities
- Use the returned `code` with `get-tickets` to see assignments
- Partial name and code matches are supported
