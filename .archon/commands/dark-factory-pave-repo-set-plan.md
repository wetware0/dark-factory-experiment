---
description: Plan a modular CargoWise repository set for a single PAVE change.
argument-hint: PAVE context plus research artifacts
---

# Dark Factory PAVE Repo-Set Plan

Plan the implementation across CargoWise modular repositories.

Requirements:

1. Identify every repository required for the change, including `CargoWise` and any `CargoWise.*` repositories.
2. Define ownership, branch name, base branch, expected PR count, build/test commands, and cross-repo dependency order.
3. Decide whether one repository can be safely changed alone or multiple PRs are required.
4. Record repository participation in the factory portal before implementation.
5. Select WTG.AI.Prompts skills by phase. Examples: coding, CargoWise C# standards, schema, testing, review, Customs-specific overlays when relevant.

Output an implementation plan that an agent can execute repo by repo without assuming a monorepo.
