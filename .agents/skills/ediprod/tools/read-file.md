# read-file

Read content of attached documents using ediprod:/// URLs.

## When To Use

- Reading attached documents from jobs
- Reading images and screenshots embedded in documents

## Input

```yaml
fileUrl:
  type: string
  required: true
  description: Document URL from get-job-details output (starts with ediprod:///). URL matching is case-insensitive.
```

### URL Formats

```
// Documents
ediprod:///IWorkItem/{jobPK}/{documentId}.{ext}
ediprod:///IIncidentRequest/{jobPK}/{documentId}.{ext}
ediprod:///IWorkProject/{jobPK}/{documentId}.{ext}


// Images
ediprod:///docs/${documentId}/images/{filename}.{ext}
```

JobPK is the UUID of the job; documentId is the UUID of the document; ext is the file extension (e.g., pdf, docx, xlsx, png, jpg).
image {filename} is 2 digit number like 01, 02, etc., representing the image in the document in order.

Note: The scheme (`ediprod:///`), job type segment (e.g. `IWorkItem`), `docs/` and `images/` segments, and the extension at the end of the URL are treated case-insensitively.

## Output

- **Documents**: Returns text content (extracted/converted to markdown with inlined images urls if any)
- **Images**: Returns image data

## Examples

```
read-file(fileUrl: "ediprod:///IWorkItem/550e8400-e29b-41d4-a716-446655440000/a1b2c3d4-e5f6-47g8-h9i0-j1k2l3m4n5o6.pdf")
read-file(fileUrl: "ediprod:///IIncidentRequest/xyz789/screenshot.png")
```

## Supported Formats

PDF, Excel, Word, email (`.eml`, `.msg`), text files (`.txt`, `.html`, `.csv`, `.log`, `.sql`, `.xml`, `.json`, `.yaml`), ZIP archives (contents extracted and processed recursively), images (JPG, PNG, GIF, BMP, WebP, SVG).

For ZIP archives, each entry is processed with its own reader based on the entry's file extension. Unsupported or oversized entries are skipped with a note.

## Tips

- Get URLs from the `url` column in the `Attached Documents` section of `get-job-details`
- Read images embedded in documents using the image URL format to get more context
- Large documents may be truncated
