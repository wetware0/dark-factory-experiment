# get-job-details

Returns comprehensive details for a workitem, incident, or project.

## When To Use

- Getting general information about a job (WI/CS/PRJ)
- Getting details about a job after searching or listing jobs with other tools
- Reviewing job status, description, and metadata
- Checking conversation history with customer for incidents
- Checking attached documents

## Input

```yaml
jobNumber:
  type: string
  required: true
  description: Job identifier with prefix WI..., CS..., or PRJ... (e.g., WI00878427).
```

## Output

Returns markdown with:

- Basic attributes (title, status, product, module, ISO 8601 dates)
- `url` — direct URL to open the record in the ediProd web app
- Description/details
- Notes (if any)
- Distinct job tags (`code`, `description`) when available
- Attached workitems, incidents, projects
- Related issues with summary fields (`issueId`, `issueNumber`, `issueMessage`)
- `Reported organisation` — organisation code + full name of the specific branch/office that filed the incident
- `Enterprise code` — 3-character code for the top-level CargoWise customer enterprise (the company that holds the CargoWise license, e.g. `DHL`). One enterprise can have many organisations; the enterprise code identifies the overall customer group while the org code identifies the specific reporting location.
- Conversation history with customer for incidents (including internal system messages when present)
- Attached documents table: `editDate|fileName|description|url`
  - Designs, specifications for workitems
  - UAT documents, logs, screenshots, customer emails, internal notes for incidents

For workitems and incidents, `Completed at` is included when all workflows are completed.

## Examples

```
get-job-details(jobNumber: "WI00902989")
get-job-details(jobNumber: "CS02134514")
get-job-details(jobNumber: "PRJ00049378")
```

## Tips

- Call only when you have a valid job number. Do not invent or guess job numbers.
- **Always include the direct ediProd URL as a markdown hyperlink when presenting a job to the user**, so they can open the record directly in ediProd. Example: `[WI00123456](https://ediprod.cw.wisetechglobal.com/link/ShowEditForm/WorkItem/...?lang=en-gb)`
- Use `get-issue-details` with an `issueId` from the `Related Issues` section to list exception occurrence summaries; use `get-exception-content` with `exceptions[].id` when you need the full raw XML or call stack.
- Use `read-file` with the `url` column from the `Attached Documents` table to read attached documents.
- Use `get-job-tasks` tool to get detailed task and workflow information for the job if needed.
- Date fields in the output are ISO 8601 strings.
