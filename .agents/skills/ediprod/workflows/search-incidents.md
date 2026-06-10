# search-incidents

Search incidents using semantic search (keywords / query text).

## When To Use

- When looking for incidents based on keywords, phrases, problems described in natural language
- When you have an incident number (`CS...`) and want to find similar incidents

## Workflow

### 1. Find relevant incidents

**Incident number known**

1. Use [get-job-details](../tools/get-job-details.md) to get the incident details
2. Extract strong search terms (product/module, error text, UI labels, key symptoms)
3. Use knowledge/documentation MCP server tools for semantic search

**Incident number unknown**

1. Gather keywords/phrases from the user describing the issue/question
2. Use knowledge/documentation MCP server tools for semantic search

### 2. Retrieve incident details

1. For each relevant incident number found, use [get-job-details](../tools/get-job-details.md) to get full details
2. Re-evaluate relevance based on description, status, product/module, and conversation history

### 3. Reiterate as needed

If not enough relevant incidents are found, refine search keywords/phrases and repeat steps 1 and 2 until you have enough high-relevance matches (or search is exhausted).
