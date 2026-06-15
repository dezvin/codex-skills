# Codex Skills

Personal Agent Skills for Codex.

## Available skills

| Skill | Description |
| --- | --- |
| [`handoff`](skills/handoff) | Create a compact continuation handoff and a ready-to-use prompt for a fresh Codex chat. |

## Install a skill

Ask Codex:

```text
Use $skill-installer to install the handoff skill from:
https://github.com/dezvin/codex-skills/tree/main/skills/handoff
```

Or run:

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" `
  --repo dezvin/codex-skills `
  --path skills/handoff
```

Restart Codex after installation.

## Repository structure

```text
skills/
  handoff/
    SKILL.md
```

Each skill is stored in its own directory so it can be installed independently.
