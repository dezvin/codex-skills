# Task System Maintenance

Read this file only when migrating task data, changing task-system rules,
cleaning up several tasks, repairing structural drift, or testing the task
system itself.

## Contents

- Preserve before changing
- Detect compatibility
- Cleanup
- Change the task system
- Structural validation
- Isolated behavior test

## Preserve Before Changing

Before a structural change:

1. Read this skill, `TODO.md`, and only relevant archive files.
2. Record current open task titles, statuses, dates, project and area
   placement, available proof, and existing archive structure.
3. Distinguish task data from formatting or protocol changes.
4. Do not alter unrelated project instructions or domain files.

## Detect Compatibility

Treat the system as compatible when it has one canonical `TODO.md`, uses the
same task purpose and lifecycle, and can archive closed work in
`archive/tasks/YYYY-MM.md` without losing existing data.

Treat lowercase or differently cased task filenames, another archive path,
unknown statuses, materially different templates, or competing task ledgers
as possible custom systems. Inspect only enough to decide whether ordinary
operation is safe.

If adopting this system would rename, merge, overwrite, or reinterpret
existing durable state, summarize the conflict and ask before migration. Do
not create a parallel task system as a workaround.

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

## Change The Task System

Keep this skill as the one detailed runtime source.

When changing behavior:

1. Update the applicable section in `SKILL.md` or this reference.
2. Keep exact task structures in `task-templates.md`.
3. Search active package and distribution files for stale duplicates or
   conflicting rules.
4. Update navigation or installation documentation only when it is in scope.
5. Do not create a parallel protocol or second task skill.

## Structural Validation

After migration or cleanup, confirm:

- exactly one canonical `TODO.md` exists;
- only allowed project task statuses remain;
- open tasks, dates, placements, and available proof were preserved;
- closed tasks removed from `TODO.md` exist exactly once in
  `archive/tasks/YYYY-MM.md`;
- no empty archive was created;
- references resolve;
- no task rule depends on external project instructions or installation
  location;
- project task statuses did not change Codex runtime states;
- unrelated project instructions and task data remain intact;
- UTF-8 and Markdown are readable.

## Isolated Behavior Test

Use temporary copies, never live task files. Run equivalent scenarios with a
globally available skill and a project-local skill when validating
installation independence.

Minimum scenarios:

1. A short self-contained request creates no `TODO.md`.
2. "Add this for later" creates `TODO.md` when absent and adds one `pending`
   task in `Later` without creating an archive.
3. Unfinished authorized project work is captured at a natural checkpoint.
4. Unfinished discussion without started project work creates no task.
5. Starting work moves the task to `Active`, sets `in_progress`, creates one
   `[~]` item, and gives `Current Action` and `Next` different meanings.
6. A real blocker sets `blocked`, preserves progress, names the unblock
   condition, and removes a false current action.
7. An open task without evidence omits `Proof`.
8. A request to mark work `done` without real proof does not archive it as
   completed.
9. Verified closure writes and reads back the archive before removing the task
   from temporary `TODO.md`.
10. Simulated archive-write failure leaves the task in temporary `TODO.md`.
11. Repeated closure does not create a duplicate archive record.
12. Cancellation records a reason and does not require proof of completion.
13. An ambiguous existing task system remains unchanged and produces a clear
   question.
14. Routine task operations create no additional approval pause.
15. Project task updates do not change Codex goal, plan, session, or execution
   states.
16. Unrelated open tasks remain unchanged.

Report only the demonstrated level:

- `implemented`
- `structurally validated`
- `behavior smoke-tested`
- `live-tested`

Do not infer a higher level from a lower one.
