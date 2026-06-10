# get-exception-content

Returns the raw exception XML for a specific exception occurrence, including the complete call stack.

## When to use

Use this tool when you need the **full call stack** or any raw exception field — `get-issue-details` only returns short summary fields and silently drops content longer than 256 characters (which includes most call stacks).

Typical workflow:

1. Call `get-job-details` to find `issueId` in the Related Issues section.
2. Call `get-issue-details` to list exception occurrences and find the `id` of the one to inspect.
3. Call `get-exception-content` with `issueId` and the exception `id` to get the full XML.

## Input

```yaml
issueId:
  type: string
  required: true
  description: Internal issue GUID from the Related Issues section of get-job-details.

exceptionId:
  type: string
  required: true
  description: The id (GUID) of the specific exception occurrence. Obtain from exceptions[].id in get-issue-details.
```

## Output

Raw XML string — the full error report as submitted to ediProd's Error Reporting Web Service. Includes `<ExceptionDetails>` with all fields (including call stack) and any other sections present in the original report.

## Example

```
get-exception-content(
  issueId: "00000000-0000-0000-0000-000000000000",
  exceptionId: "11111111-2222-3333-4444-555555555555"
)
```

## Tips

- Always obtain both GUIDs from prior tool calls — never guess them.
- The `exceptionId` parameter corresponds to `exceptions[].id` in `get-issue-details` output, not `exceptions[].exceptionId` (that field no longer exists).
- If you only need summary fields (type, message, server, version), `get-issue-details` is sufficient and faster.
