# Component-Specific Troubleshooting Guides

Detailed diagnosis for each workflow component in the EdiProd buffer management system.

---

## Entry to BMS

**Diagnosis**: Workflow waiting at Buffer Management System entry point

### Automated Analysis (With MCP)

**EVERYTHING IS FINE!**

Nothing prevents workflows from moving from this component, however it can take time.

```
Your workflow is in Entry to BMS.

Last Transfer: [lastTransferAt]
Time Elapsed: [calculate] minutes

If more than 15 minutes has elapsed since the job was saved after the workflow was created, try refreshing the job again (SHIFT+F5).

If it has been clearly longer than 15 minutes and the workflow is still in 'Entry to BMS', contact your DM to investigate.
```

### Manual Analysis

Ask user: "How long has it been since the workflow was created and saved?"

- **< 15 minutes**: This is normal. Wait for automatic transfer.
- **≥ 15 minutes**: Refresh the job (SHIFT+F5)
- **Still in Entry to BMS after refresh**: Contact your DM to investigate

---

## Queue

**Diagnosis**: Workflow waiting for required tags to progress

### Required Tag Codes

Workflow needs **ONE OR MORE** of:

- RTR, RTK, WFC, RED, RDQ, CTA, SQU, CAT, ECA, CHU, MTN, LDD
- OR CSS tag code
- OR work on approved Scaled NCN (CCPM activated)

### Automated Analysis (With MCP)

**Has Required Tags:**

```
Your workflow is in Queue and has required tags: [list tags]

This is normal. Workflows transfer every 15 minutes.
Last Transfer: [lastTransferAt]

Action: Wait 15 min after transfer → Refresh (SHIFT+F5)
```

**Missing Required Tags:**

```
Your workflow is stuck in Queue - missing required tags.
Current tags: [list or "None"]

Question: Is this work on approved Scaled NCN (CCPM activated)?

If NO:
  Cannot progress without required tags.

  How to add CSS tag (most common):
  1. Add item to Constraint Sequence in EdiProd, OR
  2. Make item child of item on Constraint Sequence

  After adding: Wait 15 min → Refresh (SHIFT+F5)

If YES:
  Should progress anyway. Wait 15 min → Refresh.
  If still stuck after 15+ min, contact DM.
```

### Manual Analysis

Ask user:

```
Navigate to: Workflow & Tracking → Management → Workflow Tags
What tags do you see listed?
```

Check if any match required tag codes above.

**Common Tag Codes:**

- **CSS** - Constraint Sequence Set (most common way to progress)
- **RTR** - Ready to Release
- **CAT** - Catastrophic
- **ECA** - Escalate

---

## Value Assessment Gate (VAG)

**Diagnosis**: Workflow waiting at value assessment checkpoint before entering buffer

### Automated Analysis (With MCP)

Check `statusDescription` field to determine Open vs Blocked.

**Status: Open (OPN)**

Validate all tasks meet these requirements:

- All tasks assigned to either a staff member or a capability
- All tasks have time estimates
- All STANDARD estimates ≤10 hours (600 minutes)
- No tasks with Task Type = EXT
- Neither workflow nor Job-level workflow has Earliest Start Date (or date has passed)

**If all requirements met:**

```
Your workflow is in Value Assessment Gate (Open).

All task requirements are met:
✓ All tasks assigned
✓ All tasks estimated
✓ STANDARD tasks ≤10 hours
✓ No EXT task types
✓ No future Earliest Start Date

Workflows move between components every 15 minutes.

Last Transfer: [lastTransferAt]
Time Elapsed: [calculate] minutes

Wait until 15 minutes after the Transfer Time.
After waiting, refresh the job (SHIFT+F5).
If the workflow still hasn't progressed, notify your DM.
```

**If requirements NOT met:**

```
Your workflow is in Value Assessment Gate (Open).

The following requirements must be met:
❌ [List failed requirements with specific task details]

Fix these issues, then:
Wait 15 minutes → Refresh (SHIFT+F5)
```

**Status: Blocked (BLK)**

Check for prerequisites in Related WorkItems and Related Incidents.

**If prerequisites exist:**

```
Your workflow is blocked by: [list prerequisite workitems with their current status]

Current status of blocker(s):
[For each prerequisite, show: number, status, active tasks, assigned staff]

If it is a true prerequisite:
- Wait until they are completed before you can start your workflow
- See if you can help the person/people working on the prerequisite to finish it sooner
- Otherwise, do something else while you wait:
  • Choose another startable task from your board
  • Pick a Standby task
  • Take a well-deserved break

If it is NOT a true prerequisite:
1. Open [workitem_number] in EdiProd
2. Navigate to: Workflow & Tracking → Relationship Navigator
3. Remove the prerequisite relationship to [prerequisite_number]
4. Save and close the Relationship Navigator
5. Wait 15 minutes
6. Refresh the item (SHIFT+F5)
```

**If NO prerequisites found:**

```
Your workflow is in Value Assessment Gate (Blocked) but no prerequisites found.

Workflows move between components every 15 minutes.

Last Transfer: [lastTransferAt]
Time Elapsed: [calculate] minutes

Wait until 15 minutes after the Transfer Time.
After waiting, refresh the job (SHIFT+F5).
If the workflow still hasn't progressed, notify your DM.
```

### Manual Analysis

Ask: "What is the workflow status?" (Check statusDescription field or EdiProd UI)

**If Open:**
Ask user to verify task requirements listed above. Guide them through fixes if needed.

**If Blocked:**
Ask: "Does this workflow have prerequisites?" (Workflow & Tracking → Relationship Navigator)

- Yes → Guide based on whether it's a true prerequisite
- No → Standard 15-minute wait → Refresh → Escalate if stuck

### VAG Logic

**Purpose**: Ensure tasks meet quality requirements (Open) or prerequisites are handled (Blocked) before releasing to buffer

**Status Types**:

- **Open (OPN)**: Ready for release pending task validation
- **Blocked (BLK)**: Held by prerequisites or other blocking conditions

---

## VAG-RTR (Ready to Release)

**Diagnosis**: Workflow passed value assessment but being held for capacity management

### Automated Analysis (With MCP)

**DO NOT use MCP data.** Guide user to check Transfer Diagnosis in EdiProd.

Ask user:

```
Please check Transfer Diagnosis in EdiProd:

1. Open [workitem_number] in EdiProd
2. Navigate to: Workflow & Tracking → Management → Transfer Diagnosis
3. Find the "[workflow_title]" workflow

In the 'Transfers to Other Components' section of the window, is there one line that is bold?
```

**If YES (workflow appears in Transfer Diagnosis):**

```
Transfer Diagnosis shows capacity constraints preventing release.

Below are the resources whose capacity is preventing the workflow's release:
[Have user tell you what the FailureReason shows]

Your options are:
- If it's you, finish some tasks to free up capacity
- See if you can help a capacity constrained person finish some of their tasks
- Speak to your team leadership about adjusting your item's position on the constraint sequence
- Speak to your team leadership about removing a lower priority item from the board
- Select another task while you wait
```

**If NO (workflow does NOT appear in Transfer Diagnosis):**

```
Workflows move between components every 15 minutes.

Last Transfer: [lastTransferAt from MCP data]
Time Elapsed: [calculate from current time]

Wait until 15 minutes after the Transfer Time.
After waiting, refresh the job (SHIFT+F5).

If the workflow still hasn't progressed, notify your DM.
```

### Manual Analysis

Ask: "Do you see your workflow in Transfer Diagnosis?" (Workflow & Tracking → Management → Transfer Diagnosis)

- **Yes** → Ask: "What does the FailureReason show?" → Provide capacity constraint options (above)
- **No** → Standard 15-minute wait → Refresh → Escalate to DM if still stuck

### VAG-RTR Logic

**Purpose**: Capacity-controlled release - workflow is ready but being held to manage team capacity

**Progression depends on**: Whether workflow passed filter rules (shown in Transfer Diagnosis)

- **PassedFilterRules = true**: Held by capacity constraints → Options to adjust capacity/priority
- **PassedFilterRules = false (or not in diagnosis)**: Normal transfer wait → 15 minutes → Refresh

---

## Buffer Zones (Active Work)

**Diagnosis**: Workflow is in an active buffer zone

Common buffer components: "Buffer ([X] day) - Zone [Y]"

### Automated Analysis (With MCP)

```
Your workflow is in [componentName].

Make sure you don't have any filters applied on your buffer board and look again.
You can check by clicking the 'Filters' button in the top-right of the screen.

Try searching for the item's ID Number ([workitem_number]) in the search box at the top-right of the buffer board.

Did you find your item?
```

**If user says they FOUND the item:**

```
Glad we could be of assistance.
```

**If user says they DID NOT find the item:**

```
There may be something wrong with the configuration of your Buffer Board.
Contact your Delivery Manager for support.
```

### Manual Analysis

Ask user:

1. "Do you have any filters applied on your buffer board?" (Check 'Filters' button top-right)
2. "Can you search for [workitem_number] in the search box at the top-right of the buffer board?"
3. "Did you find your item?"

- **Found** → Issue resolved
- **Not found** → Buffer board configuration issue → Contact DM

---

## Free Parking

**Diagnosis**: Workflow is parked (For incidents only)

### Automated Analysis (With MCP)

Check for prerequisites (look for related workflows/incidents in job details).

**If prerequisites exist:**

```
Your workflow is in Free Parking with prerequisites.

If it is a true prerequisite:
- Wait until they are completed before you can start your workflow
- See if you can help the person/people working on the prerequisite to finish it sooner
- Otherwise, do something else while you wait:
  • Choose another startable task from your board
  • Pick a Standby task
  • Take a well-deserved break

If it is NOT a true prerequisite:
1. Adjust the Relationship Navigator to accurately reflect the relationships between the workflows
2. Save then close the Relationship Navigator
3. Wait 15 minutes
4. Refresh the item (SHIFT+F5)
```

**If NO prerequisites found:**

```
Your workflow is in Free Parking but no prerequisites found.

Workflows move between components every 15 minutes.

Last Transfer: [lastTransferAt]
Time Elapsed: [calculate] minutes

Wait until 15 minutes after the Transfer Time.
After waiting, refresh the job (SHIFT+F5).

If the workflow still hasn't progressed, notify your DM.
```

### Manual Analysis

Ask: "Does this incident have prerequisites?" (Workflow & Tracking → Relationship Navigator)

- **Yes** → Guide based on whether it's a true prerequisite (see above)
- **No** → Standard 15-minute wait → Refresh → Escalate to DM if still stuck

### Free Parking Logic

**Purpose**: For incidents only - holds workflows that have prerequisites or other blocking conditions

**Note**: Free Parking is only used for incidents, not for workitems
