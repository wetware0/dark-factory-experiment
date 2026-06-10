# search-workitems

Search work items using semantic search (keywords / query text).

## When To Use

- When looking for work items based on keywords, phrases, or a natural-language description
- When you need to find workitem related to a specific feature, component, requirement, or change or want to track down changes
- When you have an incident number (`CS...`) and want to find workitems related to it

## Workflow

### 1. Find relevant work items

**Incident number known**

1. Use [get-job-details](../tools/get-job-details.md) to get the incident details
2. Extract strong search terms (feature name, component names, error text, requirements)
3. Use knowledge/documentation MCP server tools for semantic search

**Generic search**

1. Gather keywords/phrases from the user describing the work
2. Use knowledge/documentation MCP server tools for semantic search

### 2. Retrieve work item details

1. For each relevant work item number found, use [get-job-details](../tools/get-job-details.md) to get full details
2. Re-evaluate relevance based on title, description, status, and related items

### 3. Reiterate as needed

If not enough relevant work items are found, refine search keywords/phrases and repeat steps 1 and 2 until you have enough high-relevance matches (or search is exhausted).
