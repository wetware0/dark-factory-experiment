# update-incident

Updates the summary of an incident.

## When To Use

- Appending content to incident summary/title

## Input

```yaml
incidentNumber:
  type: string
  required: true
  description: Incident identifier (CS...).
title:
  type: string
  required: true
  description: >
    Content to append to the existing incident summary.
```

> Only title/summary updates are supported for incidents — no description or criteria updates.

## Output

Updates the incident summary and returns confirmation (or an error if the incident is not found).

## Examples

```
update-incident(incidentNumber: "CS00034343", title: "Appendix note to summary")
```

## Tips

- Only title/summary updates are supported for incidents (no description, no criteria)
- Title content is appended to the existing summary, not replaced
- Use `get-job-details` to review current summary before updating
