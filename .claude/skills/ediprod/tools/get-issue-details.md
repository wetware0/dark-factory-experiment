# get-issue-details

Returns structured diagnostics for a related issue from `get-job-details`.

## Domain Background: Issues and Exceptions in ediProd

An **Issue** is an aggregated, deduplicated error record in ediProd's Issue Manager. The pipeline is:

1. A WTG application (e.g., CargoWise) encounters an unhandled exception.
2. The application sends an XML error report to the **Error Reporting Web Service**.
3. ediProd periodically retrieves these reports and groups them by exception fingerprint (type + source + message) into a single **Issue** record — the same recurring bug always maps to the same Issue, with `failCount` incrementing on each new occurrence.
4. Issues are linked to Work Items (and other jobs) via the **Related Issues** relationship visible in `get-job-details`.

An **Exception occurrence** (`IssueException`) is one individual report grouped under an Issue. Each occurrence has its own server, version, company, timestamp, stack trace, and custom fields (e.g., `Domain`, `HResult`).

### Key Fields

| Field                                      | Description                                                                                           |
| ------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| `issueNumber`                              | Human-readable identifier (e.g., `ISS-001`).                                                          |
| `exceptionMessage`                         | Short message from the .NET exception (e.g., `Object reference not set to an instance of an object`). |
| `exceptionType`                            | Fully-qualified .NET exception class (e.g., `System.NullReferenceException`).                         |
| `exceptionSource`                          | The .NET assembly or module where the exception originated.                                           |
| `failCount`                                | Total number of error reports grouped into this Issue.                                                |
| `firstVersionNumber` / `lastVersionNumber` | CargoWise version range across which this issue has been seen.                                        |
| `fixedCount`                               | How many times this issue has been marked as fixed.                                                   |
| `fixedDate`                                | When the issue was last marked fixed. If `lastReported > fixedDate`, the issue has regressed.         |
| `isClientVisible`                          | Whether the issue is exposed in customer-facing views.                                                |

### Exception Occurrence Fields

| Field            | Description                                                                                                                                                                                                                     |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`             | GUID identifying this occurrence. Pass to `get-exception-content` to retrieve the full XML.                                                                                                                                     |
| `company`        | CargoWise enterprise/company code where the crash occurred.                                                                                                                                                                     |
| `serverName`     | Hostname of the server where the exception was thrown.                                                                                                                                                                          |
| `versionNumber`  | CargoWise version at time of occurrence.                                                                                                                                                                                        |
| `sequence`       | Order of this occurrence among all occurrences for the issue.                                                                                                                                                                   |
| `{custom field}` | Short fields parsed from the `<ExceptionDetails>` XML (values ≥ 256 chars are dropped). Appear as top-level properties directly on the exception object (e.g. `ExceptionType`, `HResult`, `Domain`). Keys vary by error report. |

## Input

```yaml
issueId:
  type: string
  required: true
  description: Internal issue GUID from the Related Issues section returned by get-job-details.
```

## Output

Returns a toon-formatted record with issue metadata and an `exceptions` array. Exception objects include fixed fields (`id`, `company`, `serverName`, `versionNumber`, `timestamp`, `sequence`) plus short custom fields parsed from the raw XML error report (e.g. `ExceptionType`, `HResult`, `Domain`) as top-level properties. Fields with values ≥ 256 characters (including call stacks) are omitted — use `get-exception-content` to retrieve the full XML for a specific occurrence.

## Example

```
get-issue-details(issueId: "00000000-0000-0000-0000-000000000000")
```

## Tips

- Do not guess `issueId`; get it from `get-job-details`.
- If the issue has been fixed, some exception details fields may be empty or cleared.
- To get the full call stack for a specific occurrence, pass `exceptions[].id` to `get-exception-content`.
