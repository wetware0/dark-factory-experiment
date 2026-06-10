# update-project

Updates the title and/or description of a project.

## When To Use

- Updating project title/name
- Appending content to project description/details

## Input

```yaml
projectNumber:
  type: string
  required: true
  description: Project identifier (PRJ...).
title:
  type: string
  required: false
  description: >
    New title for the project. Replaces existing title. Omit to leave unchanged.
description:
  type: string
  required: false
  description: >
    Content to append to the existing description. Fetches current description first and
    appends after a newline separator. Omit to leave unchanged.
```

> At least one of `title` or `description` must be provided.
>
> Project criteria updates are not supported by this tool — only title and description updates are available. Use PAVE project tools for project product criteria.

## Output

Updates the project details and returns confirmation (or an error if the project is not found).

## Examples

```
update-project(projectNumber: "PRJ00049378", title: "New project title")
update-project(projectNumber: "PRJ00049378", description: "Additional project notes")
update-project(projectNumber: "PRJ00049378", title: "Updated title", description: "Additional notes")
```

## Tips

- For projects, only title and description updates are supported here (no product criteria)
- Description appends to existing content — no need to read and concatenate manually
- Use `get-job-details` to review current project details before updating
