---
name: workitem-status
description: Generate a table showing detailed status of work items
disable-model-invocation: true
---

# Work Item Status

## Overview

This skill analyzes ediProd work items and creates or updates:

1. **XLSX file**: Comprehensive status table with all fields for detailed analysis
2. **Markdown table**: Summary view with key fields for quick reference

It uses parallel subagent retrieval for efficient data gathering across multiple work items and treats the XLSX output as a persistent report that must be refreshed from live ediProd MCP data on every invocation.

# Work Item Status Table Generator

Generate both XLSX and markdown tables showing work item status using parallel subagent retrieval.

## Task

Fetch the latest ediProd data, then create, update, or non-destructively check an XLSX file and generate a markdown table displaying the status of provided work items with exact schema compliance.

**Input**:

- List of work item numbers (e.g., WI00954718, WI00959109, WI00960886), OR
- Project number (e.g., PRJ00049378) - in this case, retrieve ALL work items associated with the project

## Instructions

1. **Input Processing**:
   - **For work item input**: Parse list of work item numbers (e.g., WI00954718, WI00959109)
   - **For project input** (starts with `PRJ`):
     - Call `mcp_ediprod-mcp_get-project-details` to retrieve project details
     - Extract ALL work item numbers from the "Attached WorkItems" section
     - Include both active (Working) and closed work items
     - Exclude cancelled work items
     - Organize final results by status: Active work items first, then completed work items
   - Normalize the input before generating output:
     - Remove duplicates from work item input.
     - Sort work item numbers in ascending order for deterministic processing.
     - Preserve the project number exactly for project input.

2. **Workbook Identity and Reuse**:
   - The XLSX report must use a deterministic filename and be reused on reruns for the same logical input.
   - **For project input**:
     - Use `workitem-status-{project_number}.xlsx`.
     - Example: `workitem-status-PRJ00049378.xlsx`.
   - **For direct work item input**:
     - Build the report identity from the sorted, deduplicated work item list.
     - Use a deterministic filename derived from that exact canonicalized set.
     - If the joined list is still practical as a filename, use it directly.
     - If the joined list would be unwieldy, use a stable hash derived from the canonicalized list, but the hash must always resolve to the same filename for the same exact work item set.
   - Before creating a new workbook, check whether the matching workbook already exists in the workspace.
   - If the workbook already exists, load it and update it instead of creating a separate workbook.
   - If the workbook already exists but cannot be updated for any reason, stop the process and tell the user what prevented the update.
   - Example failure cases include the workbook being locked by another process, missing write permissions, or any other read/write error.
   - In these failure cases, do not generate a replacement workbook, do not generate a second workbook with a different name, and do not silently fall back to CSV.
   - If the workbook does not exist, create it with the full schema including the `Update Notes` column.

3. **Execution Modes**:
   - Support two execution modes:
     - **Update mode**: This is the default mode. Fetch the latest ediProd data, create the workbook if it does not exist, or update the existing workbook if differences are found.
     - **Check mode**: Perform the same comparison logic, but do not modify the workbook.
   - Unless the user explicitly asks for verification-only behavior, use update mode.
   - Use check mode only for verification runs or when the user explicitly asks for a non-destructive status check.
   - Check mode must report whether the workbook is missing, out of date, or already up to date.
   - Check mode must never clear, rewrite, or otherwise alter existing `Update Notes` values.
   - If the implementation exposes a CLI, provide a non-destructive flag such as `--check` for this mode.

4. **Parallel Retrieval**:
   - **Same process for both work item and project input**
   - On every invocation, always retrieve the latest live data from the ediProd MCP tools before deciding whether the workbook needs to be updated.
   - Never assume the existing workbook is current without fetching fresh data first.
   - Launch a subagent for each work item to gather details independently
   - Each subagent must call `mcp_ediprod-mcp_get-job-details` and `mcp_ediprod-mcp_get-job-tasks`
   - Subagents should return structured summaries with all required fields
   - **Note**: The only difference for project input is the initial call to get-project-details to extract the work item list

5. **Workflow Detection and Handling**:
   - **Check for workflows**: Analyze task data to detect if work item has multiple workflows
   - **Workflow identification**: Workflows are indicated by task group names or workflow names in task descriptions
   - **Foundation vs. Domain workflows**:
     - **Foundation workflows**: Generic phases like "Design", "Coding", "Testing", "Review and "Publish"
       - These should be consolidated into a SINGLE row using the work item description
       - **CRITICAL (Project input only)**: When processing work items from a project, do NOT create separate rows for different tasks within the same foundation workflow (e.g., Review task, Sign Off task, Publish task)
       - The "Current Task" field should show the first active/pending task in the workflow sequence
       - Aggregate their durations and key details in the Notes field
     - **Domain-specific workflows**: Workflows with specific module/area/feature names like "ServiceManager", "Operations/Freight/Forwarding", "XML Import"
       - Each domain workflow gets a SEPARATE row
       - Work Item Description should be: "{Work Item Title} - {Domain Name}"
       - Example: "Code fix for CW1206 - DoNotUseNkVessel - Operations/Accounting Customs"
   - **Single-workflow work items**: If no workflows detected, create one row with work item description
   - **CRITICAL**: For domain-specific workflows, each row must contain the SPECIFIC details for that workflow:
     - Current Task: The active task WITHIN that specific domain workflow (not the overall work item's task)
     - Assignee: The person assigned to THAT domain workflow's current task
     - Current Phase: Status of THAT specific domain workflow (not the overall work item)
     - Effort: Total and remaining effort for THAT domain workflow only
     - Notes: Specific to THAT domain workflow
     - Each row is independent and shows the specific state of that domain workflow

6. **Field Extraction**: Extract the following from each work item/workflow:
   - **Work Item Number**: Unique identifier (e.g., WI00960194) - same for all rows from same work item
   - **Work Item Description**:
     - For foundation workflow row: Use work item title as-is
     - For domain-specific workflow rows: "{Work Item Title} - {Domain/Module Name}"
     - For single-workflow items: Use work item title
   - **Current Phase**: Determine by analyzing task progression and workflow status for THIS SPECIFIC WORKFLOW:
     - 🟠 **Design** - Schema design, HLD creation, or early planning tasks active
     - 🟡 **Development** - Active coding, code review, aspect review tasks
       - Use "Code Review" sub-label when code review OR aspect review tasks are active
       - Use generic label for mixed development phases
     - 🟢 **Testing** - In UAT or formal usability review (usually by product team)
     - 🔵 **Completed** - All development complete AND pull request merged to master by DAT
       - If "Pull Request is being merged by DAT to the master branch" is Closed, mark as Completed
       - Remaining update note/signoff tasks don't prevent Completed status
       - DAT merge task = Closed AND remaining tasks are only admin (Update Note, Signoff) also indicates Completed
       - Work item status = CLS (Closed) also indicates Completed
     - ⚫ **Cancelled** - Work item status shows cancelled
   - **Current Task**: Extract the actual 3-letter task code from ediProd task data, followed by task description (e.g., "CBC - Code Review", "CDF - Coding of Functionality").
   - **Assignee**: Staff initials only (e.g., "SKW", "BPD", "DAT")
   - **Assignee Name**: Full name of staff assigned to current task (e.g., "Qing(Skyla) Wang", "Bigya Paudyal")
   - **Current Task Status**: Map task status codes to human-readable labels:
     - ASN → "Not Started"
     - WRK → "Working"
     - CAN → "Cancelled"
     - CLS → Determine based on task type:
       - If task is CHK (Submit for merging) or CH0 (Pull Request merged) → "Merged"
       - Otherwise → "Closed"
     - RST (Ready to Start) → "Not Started"
     - UCL (Unclaimed) → "Not Started"
   - **Prerequisite Work Items**: Work item numbers only, comma-separated (e.g., "WI00960194, WI00960886")
   - **Duration calculations (Estimated vs Actual)**:
     - Use **Estimated Duration** as planned effort.
     - Use **Actual Duration** as consumed effort.
     - If **Actual Duration is N/A**, treat it as **0m**.
     - Per-task remaining effort is: remaining = max(estimated - actual, 0).
     - If **Estimated Duration is N/A**, remaining cannot be computed reliably; use "N/A" at the aggregate level.
   - **Total Dev Effort**: Sum **Estimated Duration** for ALL development tasks (coding, design, testing, code review, aspect review), across both closed and active tasks; format "Xh Ym" or "Xh" or "Xm"; if no tasks available, use "N/A"
   - **Remaining Dev Effort**: Sum per-task remaining effort for ONLY active/pending development tasks (Working, Not Started, Ready to Start). With the rule above, tasks with Actual = N/A count as full estimated remaining. If all dev tasks are closed, use "0m"; if cannot determine, use "N/A"
   - **Total Prod Effort**: Sum **Estimated Duration** for ALL product tasks (HLD/detailed design, functional review, usability review, update note creation/review/publication, signoff), across both closed and active tasks; format "Xh Ym" or "Xh" or "Xm"; if there are no product tasks, use "0m"
   - **Remaining Prod Effort**: Sum per-task remaining effort for ONLY active/pending product tasks (Working, Not Started, Ready to Start). With the rule above, tasks with Actual = N/A count as full estimated remaining. If there are no product tasks, use "0m". If all prod tasks are closed, use "0m"; if cannot determine, use "N/A"
   - **Due Date**: Target completion date from work item attributes; if not set, use "N/A"
   - **Estimated Due Date**:
     - If work item is closed/completed: use last updated date
     - If work item is active: calculate as today's date + remaining effort (Total Dev Effort + Total Prod Effort)
       - Assume 3 available hours per day for conversion, and exclude weekends and holidays.
       - Format as YYYY-MM-DD or DD-MMM-YY
     - If no remaining effort data available: use "N/A"
   - **Last Updated**: Most recent update timestamp
   - **Notes**: Highlights for discussion - do NOT repeat the work item description:
     - Blockers: What is blocking this WI, or what other WIs this WI is blocking
     - Key decisions and design choices that impact delivery
     - Risks and dependencies
     - Chunking/scope changes (workflows moved to other WIs)
     - Cancellation reasons if applicable
     - Leave empty if no significant discussion points exist
   - **Update Notes**:
     - This column exists only in the XLSX output.
     - If the workbook is being created for the first time, leave every `Update Notes` cell empty.
     - `Update Notes` should describe the current refresh only, not accumulate historical notes from earlier runs.
     - If an existing workbook is being updated, write notes only for rows that were added or whose data changed.
     - Use concise old-to-new diffs for changed rows.
     - Example: `Assignee: SKW -> BPD; Current Task: CBC - Code Review -> CHK - Submit for merging`.
     - For newly added rows, use `Row added`.
     - For unchanged rows, leave `Update Notes` empty.

7. **Workbook Comparison and Update Rules**:
   - Use a stable row key of `Work Item Number + Work Item Description`.
   - This row key must be used to match existing workbook rows to the newly generated data.
   - The comparison must always be based on newly retrieved ediProd MCP results from the current invocation.
   - Compare normalized row values for all XLSX columns except `Update Notes`.
   - Perform the comparison in memory before making any workbook changes.
   - Treat the following as report updates:
     - One or more changed cell values in an existing row.
     - A newly added row.
     - A previously existing row that no longer appears in the fresh source data.
   - If no differences are found:
     - In update mode, do not rewrite the workbook.
     - In check mode, report that the workbook is already up to date.
     - Leave any existing `Update Notes` values unchanged.
   - If differences are found and update mode is being used:
     - Clear the existing `Update Notes` values so the column reflects only the latest written refresh.
   - If an update is required but the existing workbook cannot be written successfully, abort the run and report the error to the user.
   - Do not partially update the workbook.
   - Do not create any alternate output file when the intended workbook update fails.
   - If a row changed, update the row values in the workbook and write the old-to-new diffs into `Update Notes`.
   - If a row did not change, leave the row values and `Update Notes` empty.
   - If a row is newly added, insert it into the workbook and set `Update Notes` to `Row added`.
   - If a row no longer exists in the fresh source data, delete that row from the workbook.
   - Report deleted rows in the run summary because deleted rows cannot retain an `Update Notes` value.

8. **Table Generation**:
   - **XLSX File** (deterministic filename from the normalized input identity):
     - For Python environment setup, invoke the `python-setup` skill
     - For XLSX generation approach, invoke the `xlsx-generation` skill
     - **Note**: If these skills are not available, then generate CSV instead, and advise the user to install them from the development plugin in https://github.com/WiseTechGlobal/WTG.AI.Prompts.
     - If the target workbook already exists, read it first and update it in place rather than generating a brand-new unrelated workbook.
     - If running in check mode, read the workbook and compare it, but do not write any workbook changes back to disk.
     - Preserve the existing worksheet structure and header order when updating.
     - Include ALL fields in this exact order: Work Item Number, Work Item Description, Current Phase (text labels only, NO emojis: Design, Development, Testing, Completed, Cancelled), Current Task, Assignee (initials only), Assignee Name (full name), Current Task Status, Prerequisite Work Items (comma-separated), Total Dev Effort (format: Xh Ym, Xh, or Xm), Remaining Dev Effort, Total Prod Effort, Remaining Prod Effort, Due Date, Estimated Due Date, Last Updated, Notes, Update Notes

   - **Markdown Table** (summary for display):
     - Include ONLY these fields: Work Item Number, Work Item Description, Current Phase (emoji labels: 🟠 Design, 🟡 Development, 🟢 Testing, 🔵 Completed, ⚫ Cancelled), Current Task, Assignee (initials only), Current Task Status, Notes

9. **Output**:
   - In update mode, generate or update the XLSX file in the workspace.
   - In check mode, do not modify the XLSX file in the workspace.
   - Display the markdown table in the response
   - Include summary statistics below the markdown table:
     - Total work items (or work streams for multi-workflow items)
     - Status distribution with counts and percentages
   - If an existing workbook was updated, include a concise run summary that states:
     - How many rows were changed
     - How many rows were added
     - How many rows were deleted
     - Whether the workbook was already up to date
   - If check mode was used, include a concise verification summary that states:
     - Whether the workbook exists
     - Whether the workbook is already up to date
     - How many rows would change
     - How many rows would be added
     - How many rows would be deleted
   - If the existing workbook could not be updated, tell the user the process stopped, describe the reason, and confirm that no new file was generated.

10. **Verification Expectations**:
    - First run for a new project number or work item set must create exactly one deterministic workbook and leave all `Update Notes` cells empty.
    - Every normal invocation of the skill must fetch fresh ediProd MCP data before deciding whether the workbook needs an update.
    - A rerun for the same input with no source-data differences in update mode must leave the workbook unchanged and preserve any existing `Update Notes` values from the last written refresh.
    - A verification rerun in check mode must not modify the workbook and must report whether it is already up to date.
    - A rerun for the same input with changed source data must update only the affected rows and populate `Update Notes` with old-to-new diffs for those rows only.
    - A rerun for a project must add newly discovered work item rows, delete rows that are no longer present in the project, and include those counts in the run summary.
    - If the target workbook is locked or otherwise cannot be updated, the skill must stop and report the failure without generating any replacement file.
