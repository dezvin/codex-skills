# Task Templates

Use these exact structures when creating, repairing, closing, or cancelling
project tasks. Placeholder text is structural only; never copy it into real
task data.

## Contents

- Open task
- Future task
- Blocked task
- Archive file
- Cancelled archive record
- Field rules
- Status rules

## Open Task

```md
## Project: <project-name>

### Purpose

- <why this project exists>

### Area: <area-name>

#### Purpose

- <why this area exists>

#### Active

##### <task-name>

Status: in_progress
Created: YYYY-MM-DD
Updated: YYYY-MM-DD

###### Goal

- <what should become true>

###### Current Action

- <one concrete action being performed now>

###### Items

- [~] in_progress: <bounded current work item>
- [ ] pending: <remaining item>

###### Progress

- <optional compact completed result, maximum 1-3 bullets>

###### Done When

- <acceptance condition>

###### Proof

- <include this section only when real evidence is already available>

###### Next

- <action after Current Action or safe resumption point>
```

For a full task in `Active`, required fields are `Status`, `Created`, `Updated`,
`Goal`, `Items`, `Done When`, and `Next`. `Current Action` is required only
while the task is `in_progress`. `Progress` and `Proof` are optional.

When `Status: in_progress`, use exactly one `[~] in_progress` item. It names
the bounded part being advanced, while `Current Action` names the concrete
action happening now. `Next` must not repeat `Current Action`; it names the
following action or the safe resumption point after interruption.

Existing project-specific routing may extend this structure. Preserve useful
extensions during routine updates.

## Future Task

```md
#### Later

##### <future-task-name>

Status: pending
Created: YYYY-MM-DD
Updated: YYYY-MM-DD

###### Goal

- <what should become true later>

###### Next

- <first useful action when work begins>
```

Expand the task to the full open-task structure when work begins or when the
extra fields become necessary. A pending task does not need `Current Action`,
a `[~]` item, or `Proof`.

## Blocked Task

Use the full open-task structure with:

```md
Status: blocked

###### Items

- [!] blocked: <blocked item> — reason: <specific reason>
- [ ] pending: <remaining item>

###### Next

- <first safe action after the named unblock event or input>
```

Preserve meaningful completed work in `Progress`. Omit `Current Action` when
no action is actually being performed. Name the event, input, file, decision,
access grant, or external result that will unblock the task.

## Item Markers

Use only these item forms:

```md
- [ ] pending: <remaining item>
- [~] in_progress: <bounded current item>
- [!] blocked: <blocked item> — reason: <short reason>
- [x] done: <recently completed item, only until progress is compacted>
- [-] cancelled: <cancelled item> — reason: <short reason>
```

## Archive File

```md
# Task Archive — YYYY-MM

## YYYY-MM-DD

### <task-name>

Status: done
Project: <project-name>
Area: <area-name>
Created: YYYY-MM-DD
Closed: YYYY-MM-DD

#### Result

- <what changed>

#### Proof

- <real evidence that the work was performed>

#### Files / Artifacts

- `<path-or-artifact>`

#### Follow-up

- <new TODO task, or "None">
```

Create `archive/tasks/YYYY-MM.md` lazily on the first real closure for that
month. When appending to an existing file, reuse its existing date-group
structure. `Proof` is required for `done`; do not archive plans, promises, or
task existence as completed work.

## Cancelled Archive Record

Use the archive format with `Status: cancelled` and replace `Result` with:

```md
#### Cancellation Reason

- <why the task was cancelled>
```

The cancellation reason is required. `Proof` is optional unless it materially
explains the final state.

## Field Rules

- `Goal`: the state that should become true.
- `Items`: current and remaining bounded work, not a historical checklist.
- `[~] in_progress`: the one bounded work item currently being advanced.
- `Current Action`: one concrete action being performed now inside that item.
- `Next`: the action after `Current Action` or the safe resumption point.
- `Progress`: at most one to three compact completed results.
- `Done When`: the acceptance condition.
- `Proof`: real evidence already available; omit it from an open task until
  evidence exists.
- `Constraints`, `Risks`, `Open Questions`, and `Decisions`: add only when
  future continuation genuinely needs them.

## Status Rules

Use only these project task statuses:

- `pending`
- `in_progress`
- `blocked`
- `done`
- `cancelled`

These statuses belong only to the project task ledger. Do not use them to
change Codex goal, plan, session, or execution states. Knowledge labels such
as fact, observation, hypothesis, decision, risk, noise, or verified result
are not task statuses.
