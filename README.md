# Codex Skills

Personal Agent Skills for Codex.

## Available skills

| Skill | Description |
| --- | --- |
| [`handoff`](skills/handoff) | Create a compact continuation handoff and a ready-to-use prompt for a fresh Codex chat. |
| [`manage-project-tasks`](skills/manage-project-tasks) | Maintain durable project task state in `TODO.md` and monthly task archives. |
| [`nearest-clarity`](skills/nearest-clarity) | Work through uncertain, multi-iteration problems by choosing the nearest clear segment. |
| [`universal-visual-prompt-builder`](skills/universal-visual-prompt-builder) | Build, adapt, repair, and structure portable image prompts without generating images. |
| [`zoom-out`](skills/zoom-out) | Step back from a local request, map the wider system, verify decision-critical foundations, and return with a better execution frame. |

## Install a skill

Ask Codex:

```text
Use $skill-installer to install a skill from:
https://github.com/dezvin/codex-skills/tree/main/skills/<skill-name>
```

Examples:

```text
Use $skill-installer to install the handoff skill from:
https://github.com/dezvin/codex-skills/tree/main/skills/handoff
```

```text
Use $skill-installer to install the manage-project-tasks skill from:
https://github.com/dezvin/codex-skills/tree/main/skills/manage-project-tasks
```

```text
Use $skill-installer to install the nearest-clarity skill from:
https://github.com/dezvin/codex-skills/tree/main/skills/nearest-clarity
```

```text
Use $skill-installer to install the zoom-out skill from:
https://github.com/dezvin/codex-skills/tree/main/skills/zoom-out
```

```text
Use $skill-installer to install the universal-visual-prompt-builder skill from:
https://github.com/dezvin/codex-skills/tree/main/skills/universal-visual-prompt-builder
```

Or run the installer script directly:

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" `
  --repo dezvin/codex-skills `
  --path skills/<skill-name>
```

Restart Codex after installation.

## Project workflow installers

Some skills are project-scoped systems rather than standalone global skills.
They work best with a root `AGENTS.md` routing contract and project files that
must be installed into the current project.

These installers are bootstrap documents: they do not duplicate skill file
contents. The canonical skill contents live under `skills/<skill-name>/`.
If a project-local skill already exists, update it in place only after
confirming it is the same compatible workflow; the installer helper itself
aborts on existing destination directories.

- `manage-project-tasks` uses `TODO.md`, a task archive path, and root
  `AGENTS.md` rules so Codex knows when durable task state must be preserved.
- `nearest-clarity` can integrate with `TODO.md` for durable state and expects
  the global `zoom-out` skill to be available.

For a full project setup, ask Codex from the target project:

```text
Read and apply this installer to the current project:
https://raw.githubusercontent.com/dezvin/codex-skills/main/installers/codex-todo-system.md

Install only the necessary project files, preserve existing project conventions
when the installer allows it, and show the final diff before committing.
```

```text
Read and apply this installer to the current project:
https://raw.githubusercontent.com/dezvin/codex-skills/main/installers/nearest-clarity-method.md

Install only the necessary project files, preserve existing project conventions
when the installer allows it, and show the final diff before committing.
```

Use skill-only installation for these two only when the target project already
has the matching `AGENTS.md`, `TODO.md`, archive, and dependency conventions.
For a project-local skill-only install:

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" `
  --repo dezvin/codex-skills `
  --path skills/manage-project-tasks `
  --dest .agents\skills
```

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" `
  --repo dezvin/codex-skills `
  --path skills/nearest-clarity `
  --dest .agents\skills
```

## `handoff` origin and differences

The `handoff` skill was derived from Matt Pocock's original productivity
[`handoff` skill](https://github.com/mattpocock/skills/blob/main/skills/productivity/handoff/SKILL.md).

The original is a compact instruction-only skill: it asks the agent to summarize
the current conversation into a handoff document, save it to the OS temp
directory, include suggested skills, reference existing artifacts instead of
duplicating them, redact secrets, and use the user's argument as the next-session
focus.

This version keeps the continuation idea, but makes it more operational for
Codex:

- creates both a handoff file and a ready-to-use prompt for a fresh Codex chat;
- treats handoff as transfer of working state, not a chronological summary;
- saves project-related handoffs in the nearest project root, falling back to
  the OS temp directory only for projectless work;
- uses stable names like `handoff-<topic>.md`, creates numbered versions for
  new handoff conflicts, and updates an explicitly provided existing handoff
  path in place;
- separates decisions, constraints, artifacts, completed work, remaining work,
  and the next concrete action;
- optionally separates confirmed facts, assumptions, and items that must be
  verified when uncertainty matters;
- suggests only skills that are actually available, and omits the section rather
  than inventing names when the skill list cannot be inspected;
- adapts to non-development work by preserving relevant audience, outcome,
  format, tone, channel, stakeholder constraints, accepted or rejected
  directions, and usefulness criteria;
- removes `argument-hint` from frontmatter to match Codex's `name` +
  `description` skill metadata convention.

## `zoom-out` origin and differences

The `zoom-out` skill was inspired by Matt Pocock's original engineering-focused
[`zoom-out` skill](https://github.com/mattpocock/skills/blob/main/skills/engineering/zoom-out/SKILL.md).

The original is intentionally tiny: it asks the agent to go up one abstraction
level in unfamiliar code and map relevant modules and callers using the
project's domain vocabulary.

This version keeps that core move, but expands it into a broader Codex workflow:

- applies to both code and non-code work, including strategy, research,
  marketing, content, documents, agent instructions, and workflows;
- separates verified facts, reported claims, inferences, assumptions, and
  unknowns before acting;
- asks the agent to verify decision-critical foundations instead of accepting
  the user's framing as fact;
- introduces an Execution Frame so the result stays aligned with purpose,
  constraints, evidence, risks, success criteria, and downstream use;
- includes proportionate output modes and task-type frames for marketing,
  business, strategy, research, document/content, and code tasks;
- adds explicit checks against overconfidence, unsupported generalization,
  stale context, scope drift, and solving the wrong problem.

## Repository structure

```text
skills/
  handoff/
    SKILL.md
  manage-project-tasks/
    agents/
    references/
    SKILL.md
  nearest-clarity/
    agents/
    references/
    SKILL.md
  universal-visual-prompt-builder/
    agents/
    references/
    SKILL.md
  zoom-out/
    SKILL.md
installers/
  codex-todo-system.md
  nearest-clarity-method.md
```

Each skill is stored in its own directory so it can be installed independently.
Project workflow installers are stored separately because they may update files
outside the skill folder.
