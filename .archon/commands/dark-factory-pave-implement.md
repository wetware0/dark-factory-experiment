---
description: Implement a PAVE task across one or more CargoWise repositories.
argument-hint: Repo-set plan artifact
---

# Dark Factory PAVE Implement

Execute the repo-set plan.

Rules:

1. Work in each repository branch defined by the plan.
2. Keep changes scoped to the PAVE task.
3. Use the selected WTG.AI.Prompts skills for coding, tests, and review preparation.
4. Record generated artifacts by category: Specs, Coding, Reviews, Validation, Critic, eDoc Evidence, Self Learning.
5. For each repository, record branch, commits, PR URL if created, build status, and test status in the factory portal.
6. If any repository blocks the whole change, pause the PAVE task rather than completing partial work silently.

Do not close the PAVE task from this command.
