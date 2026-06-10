# staff-get

Get detailed information about a staff member.

## When To Use

- Getting detailed staff information (job title, email, location)
- Finding staff capabilities
- Getting current user's information
- Personalizing responses based on staff details and role

## Input

```yaml
staffCode:
  type: string
  required: false
  description: Staff code (2-3 characters, e.g., BAS, S.V). If omitted, returns current user's info.
```

## Output

Returns staff details:

- `name` - Full name
- `displayName` - Display name
- `jobTitle` - Job title
- `email` - Email address
- `location` - Office location
- `capabilities` - List of capabilities/skills with:
  - `code` - Capability code
  - `description` - Capability description
  - `level` - Proficiency level
  - `gained` - Date capability was gained (ISO 8601)

## Examples

```
staff-get()                    // Current user
staff-get(staffCode: "BAS")    // Specific staff
staff-get(staffCode: "S.V")
```

## Tips

- Call without parameters to get current user info to personalize responses
- Use `staff-list` first if you only have a name, not a code
- Staff capabilities indicate what types of work they can be assigned
