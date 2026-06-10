# capability-list

Search for capabilities by code or description.

## When To Use

- Finding a capability when you know its code or description
- Getting capability codes for use with `capability-get` or `get-tickets`

## Input

```yaml
query:
  type: string
  required: true
  description: Search query (code or description, partial matches supported).
```

## Output

Returns list with:

- `capabilityId` - Unique capability identifier (GUID)
- `code` - Capability code
- `displayName` - Display name with code
- `isActive` - Whether capability is active

## Examples

```
capability-list(query: "CUS")
capability-list(query: "Customs")
capability-list(query: "Development")
```

## Tips

- Use the returned `code` with `capability-get` to see assigned staff members
- Use the returned `code` with `get-tickets` to see all tickets for that capability
- Partial code and description matches are supported
