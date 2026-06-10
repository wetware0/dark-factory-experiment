# staff-group-get

Get detailed information about a staff group, including its full member list.

## When To Use

- Getting all members of a staff group for task assignment or escalation
- Verifying group membership before routing work
- Looking up a group's members by group code

## Input

```yaml
groupCode:
  type: string
  required: true
  description: The staff group code to look up, e.g. RATINGRG. Use staff-group-list to find codes.
```

## Output

Returns group details:

- `code` - Group code (e.g. RATINGRG)
- `name` - Group name
- `members` - Ordered list of group members:
  - `code` - Staff code
  - `displayName` - Staff display name

## Examples

```
staff-group-get(groupCode: "RATINGRG")
staff-group-get(groupCode: "DEVTEAMRG")
```

## Tips

- Use `staff-group-list` first to find the correct group code
- If the group code is not found, a not-found error is returned
- Use the returned member `code` values with `tasks-assign` or `get-tickets`
