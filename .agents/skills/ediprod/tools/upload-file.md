# upload-file

Upload a file to the eDocs of a workitem, incident, or project.

## When To Use

- Attaching documents to jobs (like investigation results to an incident)

## Input

```yaml
jobNumber:
  type: string
  required: true
  description: Job identifier (WI..., CS..., or PRJ...).
fileContentBase64:
  type: string
  required: true
  description: Base64-encoded file content.
fileName:
  type: string
  required: true
  description: File name with extension (e.g., screenshot.png).
description:
  type: string
  required: false
  description: Optional description for the file.
fileType:
  type: string
  required: false
  default: TSH
  description: Document type code.
```

## Output

Uploads the file as an eDoc attachment to the specified job.

## Examples

```
upload-file(
  jobNumber: "WI00902989",
  fileContentBase64: "SGVsbG8gV29ybGQ=",
  fileName: "notes.txt",
  fileType: "INT"
)

```

## Codes

### Document Type Codes

- `TSH`: Attachment (generic default)
- `HLD`: High Level Design
- `UAT`: Unit Acceptance Testing
- `COR`: Client Correspondence / Screenshots
- `INT`: Internal Correspondence
- `SPE`: Specification
- `SCR`: Script
- `FIL`: Sample File
- `SIMG`: Image
- `MSC`: Miscellaneous Document

## Tips

- File content must be Base64-encoded
- If fileType is invalid for the job type, error will list available types
- Use `TSH` (Attachment) as generic fallback
