# Codex Skills

Personal Agent Skills for Codex.

## Available skills

| Skill | Description |
| --- | --- |
| [`handoff`](skills/handoff) | Create a compact continuation handoff and a ready-to-use prompt for a fresh Codex chat. |
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
Use $skill-installer to install the zoom-out skill from:
https://github.com/dezvin/codex-skills/tree/main/skills/zoom-out
```

Or run the installer script directly:

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" `
  --repo dezvin/codex-skills `
  --path skills/<skill-name>
```

Restart Codex after installation.

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
  zoom-out/
    SKILL.md
```

Each skill is stored in its own directory so it can be installed independently.
