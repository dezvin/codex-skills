# Nearest Clarity GitHub Installer

## 0. Purpose

This installer is meant to be read by Codex inside a target project.

It installs the Nearest Clarity project workflow based on the GitHub
repository:

`https://github.com/dezvin/codex-skills`

The canonical skill files are not embedded in this document. They live in:

`skills/nearest-clarity/`

Do not recreate `SKILL.md`, `agents/openai.yaml`, or `references/method.md`
from this installer. Copy or install them exactly from the repository path
above.

This installer owns only the project integration around the skill:

- root project `AGENTS.md`;
- project-local `.agents/skills/nearest-clarity/`;
- compatibility with an existing task system, if present.

## 1. Installation Boundary

Modify only the target project.

Allowed project changes:

- create or update root `AGENTS.md`;
- create or update `.agents/skills/nearest-clarity/`.

Do not install this package globally. Do not copy, modify, or vendor the global
`zoom-out` skill. `zoom-out` remains a separate dependency.

Do not create `signals.md`, `hypotheses.md`, `decisions.md`, `state.md`,
`progress.md`, or any other work-state file by default.

Do not replace or redesign an existing task system. If `TODO.md` exists, leave
task ownership to that system. `nearest-clarity` may integrate with it only for
durable state when the skill says so.

## 2. Project Root

Use the nearest project root from the current working directory.

Prefer, in order:

1. the nearest directory explicitly named by the user;
2. the nearest Git root;
3. the nearest directory with project markers such as `AGENTS.md`, `.agents/`,
   `TODO.md`, `README.md`, `package.json`, `pyproject.toml`, or similar;
4. the current working directory.

If two plausible roots would lead to different installed files, stop and ask.

## 3. Inspect Before Writing

Before changing files, read only what is needed:

1. this installer;
2. root `AGENTS.md`, if present;
3. existing `.agents/skills/nearest-clarity/`, if present;
4. root `TODO.md`, only to detect whether a task system exists;
5. global `zoom-out` skill metadata or file, if available;
6. `skill-creator` instructions if available, especially validation rules.

Do not scan the whole project by default.

Determine:

- whether root `AGENTS.md` already has rules for uncertainty, iteration,
  planning, or Zoom out;
- whether the project has a task system;
- whether `zoom-out` is available;
- whether `nearest-clarity` already exists and is compatible;
- where a short router section belongs in `AGENTS.md`.

If a same-name skill exists with a different purpose or unknown user
extensions, stop and ask before overwriting.

If existing project rules conflict with this method and cannot be safely
merged, stop and ask.

If `zoom-out` is unavailable, do not claim a complete installation. You may
prepare the project layer, but the final status must say that the dependency is
missing.

## 4. Install The Skill From GitHub

Install the project skill into:

`<project-root>/.agents/skills/nearest-clarity/`

Preferred command when the local skill installer is available:

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" `
  --repo dezvin/codex-skills `
  --path skills/nearest-clarity `
  --dest "<project-root>\.agents\skills"
```

Expected structure:

```text
<project-root>/.agents/skills/nearest-clarity/
├── SKILL.md
├── agents/
│   └── openai.yaml
└── references/
    └── method.md
```

If the installer script is unavailable, copy the directory
`skills/nearest-clarity/` from the repository exactly. Do not hand-edit the
skill content during installation.

Do not create `README.md`, `INSTALLATION_GUIDE.md`, `QUICK_REFERENCE.md`,
`CHANGELOG.md`, or a copy of this installer inside the skill.

## 5. Root AGENTS.md Contract

Add or update exactly one Nearest Clarity routing section in root `AGENTS.md`.

Adapt heading style to the file, but keep this meaning:

```md
## Nearest Clarity Work Mode

Use `nearest-clarity` when continued work must advance through bounded
iterations because the full route cannot yet be honestly planned: the user
does not know what to do next among several viable directions, important inputs
will emerge during execution, the current plan may be stale, or the nearest
testable segment must be chosen without pretending the whole path is known.

Do not use it merely because work is complex, strategic, risky, or multi-step,
for ordinary prioritization by clear criteria, or when the route and done
condition are already clear. Use standalone `zoom-out` for a one-time
reframing, recommendation, or plan that can be completed in one pass.

When this mode applies, load
`.agents/skills/nearest-clarity/SKILL.md` and keep it as the parent workflow.
During that iterative workflow, use `zoom-out` only as the skill's dependent
reframing operation and then return to `nearest-clarity`.
```

The root contract must be self-contained as a router. It must not contain the
full method, the full reference file, a copy of the skill, a link to this
installer as runtime instruction, or installation history.

If `AGENTS.md` already contains a nearby uncertainty, iteration, planning, or
Zoom out section, update the existing section by meaning. Do not add a second
competing policy.

## 6. Task System Compatibility

Installing this workflow does not create a task system.

If the project already uses `TODO.md` or `manage-project-tasks`:

- keep `nearest-clarity` as the parent workflow when the problem is genuine
  iterative uncertainty;
- use `TODO.md` only as an information source unless durable task state must
  be persisted;
- invoke `manage-project-tasks` only for the durable task-state operation;
- do not turn `TODO.md` into a signal journal, hypothesis log, decision map, or
  transcript.

If there is no task system, do nothing task-related.

## 7. Validation

After the setup batch:

1. run `quick_validate.py` for
   `<project-root>/.agents/skills/nearest-clarity`;
2. verify the skill contains exactly `SKILL.md`, `agents/openai.yaml`,
   `references/method.md`, plus any environment technical files;
3. verify relative links in `SKILL.md` resolve;
4. verify `agents/openai.yaml` contains `$nearest-clarity` and
   `allow_implicit_invocation: true`;
5. verify global `zoom-out` is available and was not copied or modified;
6. read the installed `AGENTS.md` section and confirm it has one active
   Nearest Clarity router;
7. verify `AGENTS.md` says when to use and not use the method;
8. verify `AGENTS.md` keeps `nearest-clarity` as the parent workflow during
   iterative work;
9. verify the full method and reference text were not copied into `AGENTS.md`;
10. verify no extra state, progress, signal, hypothesis, or decision files were
    created;
11. verify any existing task system was not overwritten.

If Git is available, show the final diff. Do not commit unless the user asked
for a commit.

Final status format:

`nearest-clarity AGENTS mode installed + project skill installed + skill validated + structurally validated + fresh-context routing not tested + not live-tested`

Do not claim `fresh-context routing tested` without a separate fresh-context
test. Do not claim `live-tested` without a real task that completed the method
cycle.
