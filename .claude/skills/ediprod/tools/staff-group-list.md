# staff-group-list

Search for staff groups by name or code.

## When To Use

- Finding a staff group when you know its name or part of its code
- Getting group codes for use with `staff-group-get`
- Discovering which groups exist for a team or department

## Input

```yaml
query:
  type: string
  required: true
  description: Search query — group name or code, partial match supported.
```

## Output

Returns list of matching groups:

- `code` - Group code (e.g. RATINGRG)
- `name` - Group name

## Examples

```
staff-group-list(query: "rating")
staff-group-list(query: "RATINGRG")
staff-group-list(query: "development")
```

## Tips

- Use the returned `code` with `staff-group-get` to see full member list
- Group codes often end in `RG` (Release Group)
- There is no API to look up which groups a given staff member belongs to — search by team name instead
