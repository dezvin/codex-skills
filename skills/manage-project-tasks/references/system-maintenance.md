# Task System Maintenance

Read this file only when migrating task data, changing task-system rules,
cleaning up several tasks, repairing structural drift, or testing the task
system itself.

## Preserve Before Changing

Before a structural change:

1. Read root `AGENTS.md`, this skill, `TODO.md`, and only relevant archive
   files.
2. Record the current open task titles, statuses, dates, project and area
   placement, available proof, and active archive path.
3. Identify the current owner of every rule being changed.
4. Distinguish task data from formatting or protocol changes.
5. Do not alter unrelated project instructions or domain files.

## Cleanup

For a grown or inconsistent `TODO.md`:

1. Find closed tasks still present in `TODO.md`.
2. Archive each through the normal closure procedure.
3. Avoid duplicate archive records.
4. Preserve all open tasks, statuses, dates, project and area placement, and
   available proof.
5. Remove empty `Done` sections and empty containers only when they hold no
   open work or useful `Purpose`.
6. Do not normalize unrelated open tasks merely for visual consistency.

## Changing The Task System

Keep exactly one detailed runtime owner: this skill.

When changing behavior:

1. Update the owning section here or in `SKILL.md`.
2. Keep root `AGENTS.md` limited to always-needed triggers and invariants.
3. Search active files for stale duplicates or conflicting rules.
4. Update project navigation when ownership or paths change.
5. Treat installation or portable source artifacts as separate owners; update
   them only when they are explicitly in scope.
6. Do not create a parallel protocol or second task skill.

## Structural Validation

After migration or cleanup, confirm:

- exactly one canonical `TODO.md` exists;
- only allowed statuses remain;
- open tasks, dates, placements, and available proof were preserved;
- closed tasks removed from `TODO.md` exist exactly once in the archive;
- no empty archive was created;
- root instructions point to this skill;
- references resolve;
- unrelated project instructions and task data remain intact;
- UTF-8 and Markdown are readable.

## Isolated Behavior Test

Use temporary copies, never live task files.

Minimum scenarios:

1. A short self-contained request leaves temporary task files unchanged.
2. "Add this for later" creates a `pending` task in `Later`.
3. Starting tracked work moves the task to `Active`, sets `in_progress`, and
   adds `Current Action`.
4. A real blocker sets `blocked`, preserves progress, and names the unblock
   condition.
5. Closure writes and verifies the archive before removing the task from
   temporary `TODO.md`.
6. Simulated archive-write failure leaves the task in temporary `TODO.md`.
7. Repeated closure does not create a duplicate archive record.
8. Unrelated open tasks remain unchanged.

Report only the demonstrated level:

- `implemented`
- `structurally validated`
- `behavior smoke-tested`
- `live-tested`

Do not infer a higher level from a lower one.
