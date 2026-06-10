# capability-get

Get detailed information about a capability, including the list of staff members assigned to it.

## When To Use

- Looking up who is assigned to a capability by its code
- Getting the full member list for a capability to determine task assignment options
- Verifying a capability's active status before using it for task creation

## Input

```yaml
capabilityCode:
  type: string
  required: true
  description: The capability code to look up, e.g. RATING. Use capability-list to search for codes first.
```

## Output

Returns capability details:

- `code` - Capability code (e.g. RATING)
- `displayName` - Display name
- `isActive` - Whether the capability is active
- `members` - List of staff assigned to this capability:
  - `code` - Staff code
  - `displayName` - Staff display name

## Examples

```
capability-get(capabilityCode: "RATING")
capability-get(capabilityCode: "HRA")
```

## Tips

- Use `capability-list` first to find the correct capability code
- If the code is not found, the tool returns up to 5 suggestions from a partial-match search
- Use the returned staff `code` values with `get-tickets` or `tasks-assign`
