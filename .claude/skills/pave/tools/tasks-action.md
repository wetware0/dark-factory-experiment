# PAVE Task Lifecycle

Single tool `tasks-action` manages all task state transitions.

## Parameters

- `taskId` (GUID, required) - the task to transition
- `action` (enum, required) - one of: `claim`, `start`, `claim-and-start`, `suspend`, `resume`, `cancel`, `complete`, `reopen`
- `reopenStatus` (enum, optional) - required for `reopen`: `Working`, `Assigned`, or `Suspended`
- `actualDurationInMinutes` (number, optional) - only for `complete`

## Action Reference

| Action            | Precondition               | Notes                                                  |
| ----------------- | -------------------------- | ------------------------------------------------------ |
| `claim`           | Task is unclaimed          | Self-assigns to caller                                 |
| `start`           | Task is claimed            | Begins work                                            |
| `claim-and-start` | Task is unclaimed          | Atomic claim + start in one call                       |
| `suspend`         | Task is started            | Pauses work                                            |
| `resume`          | Task is suspended          | Resumes work                                           |
| `complete`        | Task is started            | Marks done. Optionally pass `actualDurationInMinutes`. |
| `cancel`          | Task is started or claimed | Cancels the task                                       |
| `reopen`          | Task is complete           | Must pass `reopenStatus`                               |

## Containment Barriers

Containment barrier tasks cannot be completed via this tool. If a task is a containment barrier, the API will return a 422 error. These must be handled manually through the PAVE UI.

## State Machine

```
unclaimed -> claim -> claimed -> start -> started -> complete -> completed
                                       -> suspend -> suspended -> resume -> started
                                       -> cancel -> cancelled
                                                               completed -> reopen -> started
```
