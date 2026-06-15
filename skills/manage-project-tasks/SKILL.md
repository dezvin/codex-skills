---
name: manage-project-tasks
description: >-
  Use before any mutation of `TODO.md` or the project task archive, and when
  starting or continuing durable tracked work, soft-capturing unfinished work,
  changing task lifecycle state, recording blockers, closing, cancelling,
  archiving, or reconstructing state for resumption, closure, proof
  verification, or deduplication. Do not use for simple read-only listing,
  filtering, existence checks, brief explanation of current entries, targeted
  lookup of a closed result, or when task files are only input to another
  workflow. When `TODO.md` is input to choosing a direction under genuine
  uncertainty, let `nearest-clarity` own the workflow and use this skill only
  if durable task state must be persisted.
---

# Manage Project Tasks

Own the runtime procedure for durable project tasks. Keep open work in
`TODO.md`, closed work in the task archive path declared by root `AGENTS.md`,
and detailed task history out of chat memory.

Root `AGENTS.md` owns the always-loaded trigger, allowed statuses, and critical
safety invariants. This skill owns how to carry them out.

## Choose The Mode

Choose exactly one mode for the current work:

- `No TODO`: use for short self-contained work that should not survive the
  session. Do not read or modify task files.
- `Soft capture`: use when spontaneous work grows, remains unfinished, becomes
  blocked, creates independent follow-up, or otherwise must survive the
  session. Capture it at the nearest natural checkpoint; do not pretend it was
  tracked from the start.
- `Tracked`: use when the user explicitly asks to add, remember, continue,
  update, block, close, cancel, archive, or reconstruct durable task state, or
  when work starts from an existing `TODO.md` task.

The number of implementation steps does not determine the mode. Durability
does.

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
   tasks, or handling an uncertain structural case.
4. Read only matching archive records or monthly files. Do not scan the entire
   archive during ordinary work.

Do not rely on conversation memory, a compacted summary, or an earlier reading
for exact templates, archive shape, or closure order. The task operation
itself, not awareness of compaction, triggers the required read.

## Create Or Capture A Task

1. Confirm that the work must survive the session.
2. Find the relevant existing `Project` and `Area`; create either only when
   genuinely necessary.
3. Check the nearby open tasks for an obvious duplicate.
4. Put current, near-current, or blocked work in `Active`; put future work in
   `Later`.
5. Use only `pending`, `in_progress`, `blocked`, `done`, or `cancelled`.
6. Use the applicable canonical template from `task-templates.md`.
7. Write only durable state. Do not preserve chat narration or speculative
   detail.

An explicitly requested future task normally starts as `pending` in `Later`.
Soft-captured work may start in `Active` when work is already underway.

## Start Or Continue Tracked Work

Before implementation:

1. Read the relevant task.
2. Move it to `Active` when needed.
3. Set `Status: in_progress`.
4. Update `Updated`.
5. Write one concrete `Current Action`.
6. Reconcile `Items` so one current item is marked `[~] in_progress` and
   remaining work is honest.

During and after work:

- update only the affected task and surrounding structure;
- keep `Items` focused on current and remaining work;
- compact completed items into at most one to three `Progress` bullets, then
  remove the corresponding `[x]` items;
- put only available evidence in `Proof`;
- keep `Next` concrete;
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
- the next safe action, if one exists.

Do not invent dependency graphs, owners, lanes, or new statuses.

## Close Or Cancel

Treat closure as one logical operation:

1. Confirm the factual final status and available evidence.
2. Read the closure and archive templates in `task-templates.md`.
3. Read the active archive pattern from root `AGENTS.md` and determine the
   monthly archive path from the closure month.
4. Check for an existing record using `Project`, `Area`, task title, and
   `Created`. If `Created` is missing, use the source `Updated` or closure date
   as the stable migration date.
5. Append or update one compact archive record.
6. Read back and verify the archive record.
7. Only after successful archive verification, remove the closed task from
   `TODO.md`.
8. Create a separate `pending` task when independent follow-up remains.

If archive writing or verification fails, keep the task in `TODO.md`.

`done` means the work was performed. `cancelled` means it was intentionally
abandoned. Plans, discussion, promises, task existence, or "probably done" are
not proof.

Routine task updates and normal closure do not need separate permission. Ask
for explicit confirmation before deleting or merging an independent unfinished
task, changing an agreed plan, or taking an action that may lose information.

## Reconstruct Task State Or History

Simple read-only listing, filtering, existence checks, brief explanation of a
current entry, and targeted lookup of a closed result do not require this
skill. Read only the relevant task sections directly when no durable state
must be changed or reconstructed.

Use this skill when current or historical task state must be reconstructed to
resume work, close or cancel a task, verify proof, detect duplicates, rebuild a
project's task state, or deduplicate closure. Search first by title, project,
area, or keywords, then read only the relevant `TODO.md` sections and matching
monthly archive files.

## Integrate With Nearest Clarity

`nearest-clarity` controls movement through uncertainty. This skill stores only
durable task state.

Using `TODO.md` as an information source does not make this skill the parent
workflow. When the task is to choose a direction under genuine uncertainty,
`nearest-clarity` owns the work. Invoke this skill only if the resulting
durable task state must be persisted or reconstructed.

For work that must survive the session:

- `Goal` may hold the target contour;
- `Current Action` holds the current iteration or concrete working step;
- `Progress` holds compact meaningful results;
- `Next` holds the next useful action;
- add `Constraints`, `Risks`, `Open Questions`, or `Decisions` only when
  necessary for continuation.

Do not turn `TODO.md` into a reasoning transcript, signal journal, hypothesis
dump, detailed decision map, or distant plan.

## Validate Task Changes

Batch related writes, then perform one final validation pass:

1. Read back the changed task sections.
2. Read back each changed monthly archive.
3. Confirm every removed closed task exists in the archive exactly once.
4. Confirm open tasks and their statuses remain in `TODO.md`.
5. Confirm required fields and allowed statuses.
6. Check UTF-8 readability after Cyrillic writes.
7. Report briefly what changed and what was left untouched.

Do not repeat the same read-back after it passes.

## Boundaries

- Do not keep a permanent `Done` section in `TODO.md`.
- Do not create an empty archive in advance.
- Do not invent proof or claim validation that did not run.
- Do not rewrite unrelated open tasks for formatting consistency.
- Do not create competing task skills, task protocols, progress logs,
  handoff files, state files, changelogs, ADRs, dependency graphs, or extra
  project-management layers without a demonstrated need or explicit request.
- Do not change this task system as part of an ordinary task update.

## References

- [references/task-templates.md](references/task-templates.md): read for exact
  open-task, future-task, cancellation, and archive formats.
- [references/system-maintenance.md](references/system-maintenance.md): read
  for migration, cleanup, task-system changes, and isolated behavior tests.
