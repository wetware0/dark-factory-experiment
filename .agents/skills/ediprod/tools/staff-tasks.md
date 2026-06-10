# staff-tasks

Returns tasks assigned to a staff member across all their PAVE buffer boards, as a flat list.

## When To Use

- Finding out what you (or a colleague) are working on right now
- Discovering what tasks are ready to start next
- Getting a prioritised view of pending work before a standup

## Input

```yaml
staffCode:
  type: string
  required: false
  description: Staff code (2-3 characters, e.g., BAS, S.V). If omitted, returns tasks for the currently authenticated user.
includeCapabilityPool:
  type: boolean
  required: false
  default: false
  description: When true, also includes unclaimed items from capability pools the staff member belongs to.
status:
  type: string[]
  required: false
  description: Filter by task status code(s). Valid values: ASN (assigned), WRK (working/in-progress), SUS (suspended). When omitted, returns all tasks assigned to the staff member.
```

## Output

Returns a TOON-encoded flat array of tasks. Each task has:

- `sequence` — task sequence number within the workflow
- `type` — task type code (e.g. CDF, REV)
- `description` — task description
- `status` — task status code (e.g. ASN, WRK, SUS)
- `readyToStart` — whether the task can be started right now
- `capability` — assigned capability code (null if staff-assigned)
- `hasNotes` — whether notes are attached
- `criticality` — parent job criticality (e.g. CR1, CR5)
- `releasedAt` — ISO datetime when the job was released into the buffer (null if not set)
- `startableAt` — ISO datetime since when the task has been startable (null if not set)
- `jobNumber` — parent job identifier (e.g. WI00902989, CS02312860)
- `jobTitle` — parent job description
- `boardZone` — buffer zone identifier, (e.g. `'Zero'`, `'One'`, `'Two'`) depending on board configuration — lower value = higher priority
- `boardName` — which PAVE board this came from

Returns an informational message if no boards are configured or no matching tasks exist.

## Examples

```
staff-tasks()                                                        // Current user
staff-tasks(staffCode: "BAS")                                        // Specific staff
staff-tasks(staffCode: "BAS", status: ["WRK"])                       // Only working tasks
staff-tasks(staffCode: "BAS", status: ["ASN", "SUS"])                // Assigned or suspended
staff-tasks(staffCode: "BAS", includeCapabilityPool: true)           // Include pool items
```

## Tips

- Call without parameters to check your own current work
- Use `staff-get` first if you need to look up a staff code by name
- `boardZone` corresponds to urgency: `Zero` = overdue, higher zones = newer work
- Only PAVE buffer boards (created in the new productivity portal) are surfaced — legacy boards are not supported
