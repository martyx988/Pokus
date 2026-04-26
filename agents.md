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
- whenever producing project code, use the `software-developer` local skill

---

## Intended File Structure

- `agents/`: Local skills, agent definitions, and hooks.
- `design_phase/`: Spec-driven design inputs and outputs.
- `task_phase/`: Roadmap, milestone checklist, and decomposed tasks.
- `project/`: Project source code and its internal folder structure.

---

## Rules

- always commit and merge to Github remote main after you finish

---
