# Symptom-Based Troubleshooting Responses

Edge case symptoms where immediate guidance can be provided without retrieving workflow data.

---

## Tasks Missing Estimates or Task >10 Hours

**User says:** "Tasks are missing estimates" or "Task is more than 10 hours"

**Response:**

```
Issues found:
1. Missing estimates - add time estimates to all tasks
2. STANDARD task >10 hours - must be ≤10 hours

Fix:
- Add estimates to missing tasks
- For tasks >10 hours: Break into smaller tasks or change to LONG_JOB

After fixing: Wait 15 min → Refresh (SHIFT+F5)
```

---

## Workflow Blocked by Prerequisites

**User says:** "Workflow is blocked by prerequisites"

**Response:**

```
Blocked by prerequisites.

Options:
1. TRUE prerequisite: Wait, help them finish, or choose another task
2. NOT true: Adjust Relationship Navigator → Save → Wait 15 min → Refresh (SHIFT+F5)
```

---

## No Bold Line in Transfer Diagnosis

**User says:** "No bold line in Transfer Diagnosis" or "Transfer Diagnosis doesn't show anything"

**Response:**

```
Not enough time has passed.

Action:
1. Close Transfer Diagnosis
2. Wait 15 minutes
3. Refresh (SHIFT+F5)
4. Re-open Transfer Diagnosis

Still no bold line = capacity constraints (check Buffer Release Outcome)
```

---

## Board Filters Applied

**User says:** "Workflow should be on board but I don't see it"

**Response:**

```
Check if board filters are applied:

1. Look for filter icon/indicator on board
2. Remove all filters
3. Refresh (SHIFT+F5)
4. Check if workflow now visible

If still not visible after removing filters, retrieve workflow data to diagnose.
```

---

## Recent Status Change

**User says:** "Just moved workflow to X status but it's not on the board"

**Response:**

```
Workflows transfer every 15 minutes.

If you just changed status:
1. Note current time
2. Wait 15 minutes from status change
3. Refresh (SHIFT+F5)

If still not visible after 15+ minutes, retrieve workflow data to diagnose.
```
