---
name: manage-project-tasks
description: >-
  Use before changing `TODO.md` or `archive/tasks/YYYY-MM.md`, and when the
  user asks to add, remember, start, continue, update, block, close, cancel,
  archive, deduplicate, or reconstruct durable project task state. Also use
  implicitly when authorized project work becomes unfinished, blocked, or
  creates independent follow-up that must survive the current session. Do not
  use merely because work is complex or multi-step, for work completed within
  the current session, for discussion or speculation that has not become
  project work, for simple read-only listing or filtering, or when task files
  are only input to another workflow.
---

# Manage Project Tasks

Manage durable project work without depending on installation location,
external project instructions, conversation memory, or another task protocol.
Keep open work in `TODO.md`. Archive closed work lazily in
`archive/tasks/YYYY-MM.md`, using the task's closure month.

Project task statuses describe only the durable ledger. Do not map them to or
use them to change Codex goal, plan, session, or execution states.

## Decide Whether State Must Persist

Write task state only when authorized project work must survive the current
session. Persist it when work remains unfinished, becomes concretely blocked,
or produces independent required follow-up. Capture at the nearest natural
checkpoint, such as after a bounded result, before a forced stop, when a
blocker appears, or before ending the session.

Do not create task state for:

- work completed in the current session;
- discussion, advice, ideas, or hypotheses that have not become project work;
- several steps that are being completed now;
- complexity, duration, or risk alone;
- read-only task listing, filtering, existence checks, brief explanation of a
  current entry, or targeted lookup of a closed result.

An explicit request to remember or add future work is sufficient reason to
persist it.

## Resolve The Project And Storage

Determine the project root independently of where this skill is installed.
Prefer, in order:

1. the project path explicitly named by the user;
2. the nearest ancestor containing the canonical `TODO.md`;
3. the nearest Git root;
4. the current working directory.

If plausible roots or task systems would lead to different writes, stop and
ask. Treat `todo.md`, `TODO.MD`, another archive convention, or a custom task
schema as possible existing systems; do not rename, merge, or replace them
silently.

For this system:

- the canonical open-task file is `<project-root>/TODO.md`;
- the fixed archive pattern is `<project-root>/archive/tasks/YYYY-MM.md`;
- archive directories and files are created only on the first real closure.

When a task must be written and no task system exists, create `TODO.md`
without a separate confirmation using this minimal content:

```md
# TODO.md

Open project work that must survive the current session.
```

Do not create a demonstration task or an empty archive.

## Read Before Mutation

Before changing `TODO.md` or the task archive:

1. Read the affected task and its surrounding `Project`, `Area`, `Active`, or
   `Later` context.
2. Read [references/task-templates.md](references/task-templates.md) when
   creating a task, repairing task structure, closing or cancelling a task, or
   writing an archive record.
3. Read
   [references/system-maintenance.md](references/system-maintenance.md) only
   when changing the task system, migrating task data, cleaning up several
   tasks, handling an uncertain structure, or testing this skill.
4. Read only matching archive records or monthly files. Do not scan the entire
   archive during ordinary work.

Do not rely on conversation memory, a compacted summary, or an earlier reading
for exact templates, archive shape, or closure order. The task operation
itself triggers the required read.

## Create Or Capture A Task

1. Confirm that the work must survive the session.
2. Find the relevant existing `Project` and `Area`; create either only when
   genuinely necessary.
3. Check nearby open tasks for an obvious duplicate.
4. Put current, near-current, or blocked work in `Active`; put future work in
   `Later`.
5. Use only `pending`, `in_progress`, `blocked`, `done`, or `cancelled`.
6. Use the applicable canonical template from `task-templates.md`.
7. Write only the durable state needed for continuation. Do not preserve chat
   narration, a reasoning transcript, or speculative detail.

An explicitly requested future task normally starts as `pending` in `Later`.
Work captured after execution has begun may start as `in_progress` in `Active`.

## Start Or Continue Work

Before implementation:

1. Read the relevant task.
2. Move it to `Active` when needed.
3. Set `Status: in_progress`.
4. Update `Updated`.
5. Mark exactly one bounded current work item as `[~] in_progress`.
6. Write one concrete `Current Action` being performed now.
7. Write `Next` as the action after the current action or the safe resumption
   point after an interruption. Do not duplicate `Current Action` in `Next`.

During and after work:

- update only the affected task and surrounding structure;
- update durable state when the status, current work item, resumption point,
  blocker, acceptance condition, meaningful progress, or evidence changes;
- do not rewrite the task after every technical step;
- keep `Items` focused on current and remaining work;
- compact completed items into at most one to three `Progress` bullets, then
  remove the corresponding `[x]` items;
- add `Proof` only when real evidence exists;
- leave the task `in_progress` or `blocked` when work remains.

Multiple tasks may be `in_progress`, but do not mark unrelated work active.

## Record A Blocker

Use `blocked` only when the task cannot proceed without a concrete input,
decision, file, access grant, or external result.

Record:

- the blocked item;
- the specific reason;
- completed progress that must not be lost;
- the event or input that will unblock the task;
- `Next` as the first safe action after unblocking.

Do not keep `Current Action` merely to make a blocked task look active. Do not
invent dependency graphs, owners, lanes, or new statuses.

## Close Or Cancel

Treat closure as one logical operation:

1. Confirm the factual final status and available evidence.
2. For `done`, require real proof that the work was performed. For
   `cancelled`, require a concrete cancellation reason; proof is optional.
3. Read the closure and archive templates in `task-templates.md`.
4. Determine `archive/tasks/YYYY-MM.md` from the closure month.
5. Check for an existing record using `Project`, `Area`, task title, and
   `Created`. If `Created` is missing, use the source `Updated` or closure date
   as the stable migration date.
6. Append or update one compact archive record.
7. Read back and verify the archive record.
8. Only after successful archive verification, remove the closed task from
   `TODO.md`.
9. Create a separate `pending` task when independent follow-up remains.

If archive writing or verification fails, keep the task in `TODO.md`.

`done` means the work was performed. `cancelled` means it was intentionally
abandoned. Plans, discussion, promises, task existence, or "probably done"
are not proof.

Routine creation, updates, capture, blocking, and factual closure do not need
separate permission. Ask before deleting or merging an independent unfinished
task, choosing between conflicting task systems, performing an ambiguous
migration, overwriting contradictory durable state, or taking an action that
may lose information. This skill does not add a separate approval rule for
changing a plan; follow the authority already established for the task.

## Reconstruct Task State Or History

Simple read-only listing, filtering, existence checks, brief explanation of a
current entry, and targeted lookup of a closed result do not require this
skill. Read only the relevant task sections directly when no durable state
must be changed or reconstructed.

Use this skill when current or historical task state must be reconstructed to
resume work, close or cancel a task, verify proof, detect duplicates, rebuild
a project's task state, or deduplicate closure. Search first by title,
project, area, or keywords, then read only the relevant `TODO.md` sections and
matching monthly archive files.

## Validate Task Changes

Batch related writes, then perform one final validation pass:

1. Read back the changed task sections.
2. Read back each changed monthly archive.
3. Confirm every removed closed task exists in the archive exactly once.
4. Confirm open tasks and their statuses remain in `TODO.md`.
5. Confirm required fields, field meanings, and allowed statuses.
6. Confirm project task statuses did not change Codex runtime states.
7. Check UTF-8 readability after Cyrillic writes.
8. Report briefly what changed and what was left untouched.

Do not repeat the same read-back after it passes.

## Boundaries

- Do not keep a permanent `Done` section in `TODO.md`.
- Do not create an empty archive in advance.
- Do not invent proof or claim validation that did not run.
- Do not rewrite unrelated open tasks for formatting consistency.
- Do not create competing task skills, task protocols, progress logs,
  handoff files, state files, changelogs, ADRs, dependency graphs, or extra
  project-management layers without a demonstrated need or explicit request.
- Do not modify external project instructions as part of this task system.
- Do not change this task system as part of an ordinary task update.

## References

- [references/task-templates.md](references/task-templates.md): read for exact
  open-task, future-task, cancellation, and archive formats.
- [references/system-maintenance.md](references/system-maintenance.md): read
  for migration, cleanup, task-system changes, and isolated behavior tests.
