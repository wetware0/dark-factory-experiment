# get-tickets

Get tickets (workitems and incidents) assigned to a staff member or capability on a buffer board.

## Background (PAVE buffer boards)

In PAVE, a buffer board is a Visual Board section linked to a buffer component in a Buffer Management System (BMS). It visualizes work in channels (often per staff member, group, or capability) and helps teams see when work is at risk of not being completed within the expected timeframe (the buffer timespan).

Work on a buffer board ages over time and is shown in four zones:

- Zone 3: newest work (just released to the buffer)
- Zone 2: ageing
- Zone 1: risk state (late in the buffer)
- Zone 0: overdue (not completed within the buffer timespan)

## When To Use

- Checking what a staff member is working on
- Reviewing team workload
- Finding current assignments for a person
- Viewing all tickets assigned to a specific capability
- Finding unassigned capability tickets

## Input

```yaml
boardName:
  type: string
  required: true
  description: Name of the buffer board (e.g., Customs Board).
lookupBy:
  type: enum
  required: true
  values: [staff, capability]
  description: Look up tickets by staff code or capability code.
staffCode:
  type: string
  required: when lookupBy is "staff"
  description: Staff code (2-3 characters, e.g., BAS, S.V).
capabilityCode:
  type: string
  required: when lookupBy is "capability"
  description: Capability code. Returns all tickets for that capability across all qualified staff.
```

## Output

Returns list of tickets with:

- `title` - Ticket title/summary
- `subtitle` - Additional context
- `criticality` - Criticality code (usually for incidents/eRequests; often empty for work items). Common values are `CR1`-`CR9`.
- `startable` - Whether the ticket has any startable work (matches the startable indicator on the board)
- `zone` - Buffer zone as returned by PAVE (string, typically `3`, `2`, `1`, `0`): `3` is newest and `0` is most urgent/overdue
- `type` - Parent job type
- `hasPriority` - Derived from tags: true if any tag description contains the word "priority" (case-insensitive)
- `tasks` - List of tasks with:
  - `title` - Task description
  - `type` - Task type description
  - `startable` - Can be started
  - `status` - Task status
  - `staffCode` - Assigned staff
  - `capability` - Required capability code
  - `hasNotes` - Has notes attached

When using `capabilityCode`, the output also includes:

- `capability` - The matched capability info (code, displayName)
- `staffCount` - Number of active staff with this capability
- `ticketCount` - Total number of tickets found

### Criticality codes (CR1-CR9)

When the ticket represents an incident/eRequest, `criticality` typically uses these codes:

`CR1` - Entire system is down (System failure)
`CR2` - Entire module not working (No manual work around)
`CR3` - Single function not working (No manual work around)
`CR4` - Single function not working (With manual work around)
`CR5` - Training Questions
`CR6` - Feature Request
`CR7` - Estimate / Quote Request
`CR8` - Compliance, Reference and Master Data
`CR9` - Service Request

## Examples

```
get-tickets(boardName: "Customs Board", lookupBy: "staff", staffCode: "BAS")
get-tickets(boardName: "International Logistics Buffer Board", lookupBy: "staff", staffCode: "RW")
get-tickets(boardName: "Customs Board", lookupBy: "capability", capabilityCode: "CUS")
```

## Tips

- **Must know the board name** - ask user if unknown. Make it clear that only new boards created in a new web-version of PAVE are supported. The legacy one in ediprod is not supported.
- Use `staff-list` first to find the correct staff code
- Use `capability-list` first to find the correct capability code
- When using capabilityCode, only tickets with tasks matching that specific capability are returned
- Capability queries may take longer as they fetch channels for all staff with the capability
