# Agents Overview

This project uses an end-to-end skill-driven workflow for system design and implementation.

The process is **spec-driven** and progresses through clearly defined stages, with frequent user input for decisions and clarification.

---

## Skills

The workflow is powered by local skills defined in agents/skills/
Use their `SKILL.md` files as the source of truth.

---

## Workflow

- when designing the specs we will manually call local skills to sequentially populate design_phase folder
- design phase work runs in main-agent chat flow (no orchestration/subagents by default)
- whenever producing project code, use the `software-developer` local skill

---

## Orchestration Workflow

- orchestration/subagent workflow is for implementation phase only
- One subagent = one task = one branch (`task/<milestone>-<task-id>-<short-name>`). Never commit directly to `main`.
- Spawn subagents with clean context (no parent/main-agent context). Prompt only task implementation using `software-developer` skill.
- Subagent output must include: task id, branch name, commit SHA, changed files, tests run/results, and task `.md` status update.
- Orchestrator integrates only from subagent commit/branch into `main`, then pushes `origin/main` immediately.
- Keep workspace clean during orchestration: avoid committing runtime artifacts; rely on `.gitignore` for caches.
- Use unique migration revisions per task to avoid parallel migration-id collisions.

---

## Intended File Structure

- `agents/`: Local skills, agent definitions, and hooks.
- `design_phase/`: Spec-driven design inputs and outputs.
- `task_phase/`: Roadmap, milestone checklist, and decomposed tasks.
- `project/`: Project source code and its internal folder structure.

---
