# Codex TODO System GitHub Installer

## 0. Purpose

This installer is meant to be read by Codex inside a target project.

It installs the project task system based on the GitHub repository:

`https://github.com/dezvin/codex-skills`

The canonical skill files are not embedded in this document. They live in:

`skills/manage-project-tasks/`

Do not recreate `SKILL.md`, `agents/openai.yaml`, or reference files from this
installer. Copy or install them exactly from the repository path above.

This installer owns only the project integration around the skill:

- root project `AGENTS.md`;
- project-local `.agents/skills/manage-project-tasks/`;
- root `TODO.md`;
- the task archive convention.

## 1. Installation Boundary

Modify only the target project.

Allowed project changes:

- create or update root `AGENTS.md`;
- create or update `.agents/skills/manage-project-tasks/`;
- create or preserve root `TODO.md`;
- create monthly archive files only if closed tasks are actually migrated.

Do not modify global `~/.codex/AGENTS.md`, global skills, `AGENTS.override.md`,
or nested `AGENTS.md` files unless the user explicitly asks.

Do not create an empty archive in advance. The default archive pattern for new
projects is:

`archive/tasks/YYYY-MM.md`

If the project already has a clear archive path, preserve it and declare that
path in root `AGENTS.md`.

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
3. root `TODO.md` or a same-name file with different case, if present;
4. existing `.agents/skills/manage-project-tasks/`, if present;
5. existing task archive directory listing, if present;
6. a specific monthly archive only when migrating closed tasks or checking a
   duplicate;
7. `skill-creator` instructions if available, especially validation rules.

Do not scan the whole project by default.

Classify the target state:

- no task system yet;
- older AGENTS-only task system;
- compatible `manage-project-tasks` installation;
- conflicting or custom task system.

If there is no task system, install without extra confirmation.

If there is an existing task system and the update would structurally change
it, summarize what was found, recommend one safe option, and wait for user
confirmation before migration or replacement.

Stop and ask if the project root is unclear, task ownership is ambiguous, or
data could be lost.

## 4. Install The Skill From GitHub

Install the project skill into:

`<project-root>/.agents/skills/manage-project-tasks/`

Preferred command when the local skill installer is available:

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" `
  --repo dezvin/codex-skills `
  --path skills/manage-project-tasks `
  --dest "<project-root>\.agents\skills"
```

Expected structure:

```text
<project-root>/.agents/skills/manage-project-tasks/
├── SKILL.md
├── agents/
│   └── openai.yaml
└── references/
    ├── task-templates.md
    └── system-maintenance.md
```

If the installer script is unavailable, copy the directory
`skills/manage-project-tasks/` from the repository exactly. Do not hand-edit the
skill content during installation.

If a same-name skill already exists:

- update it in place if it is the same system or a previous compatible version;
- stop and ask if it has a different purpose or unknown user extensions.

Do not create `README.md`, `INSTALLATION_GUIDE.md`, `QUICK_REFERENCE.md`,
`CHANGELOG.md`, or a copy of this installer inside the skill.

## 5. Root AGENTS.md Contract

Add or update exactly one task tracking section in root `AGENTS.md`.

Adapt heading style to the file, but keep this meaning. Replace
`{{TASK_ARCHIVE_PATTERN}}` with the actual project archive pattern, for example
`archive/tasks/YYYY-MM.md`.

```md
## Project Task Tracking

`TODO.md` is the source of truth for open project work that must survive the
current session. Closed tasks belong in
`{{TASK_ARCHIVE_PATTERN}}`; do not keep a permanent `Done` section in
`TODO.md`.

Use only these task statuses: `pending`, `in_progress`, `blocked`, `done`,
`cancelled`.

Simple read-only listing, filtering, existence checks, brief explanation of a
current entry, and targeted lookup of a closed result may read only the
relevant task sections directly.

Use `.agents/skills/manage-project-tasks/SKILL.md` before any change to
`TODO.md` or the task archive, and when starting or continuing tracked work,
soft-capturing unfinished work, changing lifecycle state, recording blockers,
closing, cancelling, archiving, or reconstructing state for resumption,
closure, proof verification, or deduplication.

Use `No TODO` for short self-contained work, `Soft capture` when work becomes
durable during execution, and `Tracked` for explicit or existing project tasks.

Never remove a closed task from `TODO.md` until its archive record has been
written and verified. Do not rely on conversation memory or summaries for
exact task templates or closure order. Do not invent proof.

Do not create competing task skills, task protocols, state files, progress
logs, or additional task statuses without a separate demonstrated need.
```

The root contract must be self-contained as a router and safety contract. It
must not contain full task templates, full closure or migration procedures, a
copy of the skill, or a link to this installer as runtime instruction.

If root `AGENTS.md` already contains task rules, update the existing task
section by meaning. Do not add a second competing task policy.

## 6. TODO.md

The canonical open task file is:

`<project-root>/TODO.md`

If a file such as `todo.md` or `TODO.MD` exists, treat it as a candidate
existing task system. Preserve its content. Normalize the filename to `TODO.md`
only when it is safe and does not merge two different files silently.

If `TODO.md` already exists:

- preserve open tasks, statuses, dates, proof, `Project`, `Area`, `Purpose`,
  `Goal`, `Current Action`, `Done When`, and `Next` where present;
- do not rewrite unrelated open tasks for formatting;
- remove a permanent `Done` section only after successfully archiving those
  closed tasks, and only if the user approved that migration when needed.

If `TODO.md` does not exist, create the minimal file:

```md
# TODO.md

Project task ledger for open work that must survive the current session.

Closed tasks are archived in `archive/tasks/YYYY-MM.md`.
```

Use the actual archive pattern chosen for the project if it differs from the
default. Do not create demonstration projects or tasks.

## 7. Migration Rules

Closed tasks may be migrated only as a deliberate cleanup or upgrade step.

When migrating:

1. preserve task title, project, area, status, result or cancellation reason,
   dates, proof, and follow-up;
2. write or update exactly one matching monthly archive record;
3. read back the archive record;
4. remove the closed task from `TODO.md` only after archive verification;
5. leave ambiguous data in place and ask the user.

Do not delete or rename independent legacy task files or archives.

## 8. Validation

After the setup batch:

1. run `quick_validate.py` for
   `<project-root>/.agents/skills/manage-project-tasks`;
2. verify the skill contains exactly the expected files plus any environment
   technical files;
3. verify relative links in `SKILL.md` resolve;
4. verify `agents/openai.yaml` contains `$manage-project-tasks` and
   `allow_implicit_invocation: true`;
5. read the installed `AGENTS.md` section and confirm it has one active task
   policy, the actual archive pattern, and no `{{TASK_ARCHIVE_PATTERN}}`;
6. verify `TODO.md` has exact casing and open task state was preserved;
7. verify no empty archive was created;
8. verify no duplicate task policy, task skill, task protocol, `state.md`,
   `progress.md`, changelog, or installation log was created.

If Git is available, show the final diff. Do not commit unless the user asked
for a commit.

Final status format:

`manage-project-tasks installed + AGENTS contract installed + TODO checked + skill validated + structural validation passed`
