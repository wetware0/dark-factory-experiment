# ediProd workflows: Getting started

## Look up a job (WI/CS/PRJ)

1. Use `get-job-details` with the job number (WI/CS/PRJ prefix).
2. Review the returned info: title, status, description, related jobs, attached documents.
3. If you need workflow-level metadata (components/tags/release group) or workflow IDs, use `get-job-workflows`.
4. If you need task-level details (startable, assignments, notes), use `get-job-tasks`.

See also: [workflows-and-tasks](workflows-and-tasks.md).

## Find incidents by criteria

1. Use `lookup-products()` to find valid product codes (if unknown).
2. Use `lookup-modules(product: "ENT")` to find module codes (if needed).
3. Use `filter-incidents` with `product` and optional `module`, `criticality`, `status` filters.

## Find workitems by criteria

1. Use `lookup-products()` to find valid product codes (if unknown).
2. Use `lookup-modules(product: "ENT")` to find module codes (if needed).
3. Use `lookup-workitem-change-types(product: "ENT", area: "RAT", module: "WRS")` to find change type codes when filtering by `changeType`.
4. Use `filter-workitems` with `product` and optional `area`, `module`, `status`, `changeType`, `createdUser`, `completedAfter`, and `completedBefore` filters.

## Work with staff

1. Use `staff-list` with a name to find a staff member and get their code.
2. Use `staff-get` with the staff code for detailed info.
3. Use `get-tickets` with the board name and staff code to see assigned work.

## Retrieve staff tickets or check staff buffer board

1. Use `staff-get` to find details about current user
2. Check buffer boards secion for boards the staff is on
3. If multiple boards, ask user to select which board to check
4. Use `get-tickets` with the selected board name and staff code to retrieve assigned work and task

## Suggest staff for an incident

1. Get incident details using `get-job-details` and open tasks using `get-job-tasks`.
2. Identify the capabilities required for the open tasks.
3. Find similar incidents using [search-incidents](search-incidents.md).
4. Review multiple incidents; similarity does not have to be exact.
5. Identify staff who resolved those incidents or contributed the most.
6. Prioritize:
   - Staff who is active and available
   - Staff who matches the required capabilities
   - Staff who has worked on more relevant incidents

## Suggest staff for a work item

1. Get work item details using `get-job-details` and open tasks using `get-job-tasks`.
2. Identify the capabilities required for the open tasks.
3. Find similar work items using [search-workitems](search-workitems.md).
4. Based on the work item and similar work items, identify related files/methods in the repository.
5. Identify staff who resolved those work items or contributed the most.
6. Identify staff who has experience with the related files/methods in the repository.
7. Prioritize:
   - Staff who is active and available
   - Staff who has more recent and frequent experience with the related files/methods
   - Staff who matches the required capabilities
   - Staff who has worked on more relevant work items

## Manage documents

1. Use `get-job-details` to find attached documents in the `Attached Documents` table.
2. Use the `url` column (`ediprod:///...`) with `read-file` to read document content.
3. Use `upload-file` to attach new documents.
