# Task Templates

Use these exact structures when creating, repairing, closing, or cancelling
project tasks. Placeholder text is structural only; never copy it into real
task data.

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

Status: pending
Created: YYYY-MM-DD
Updated: YYYY-MM-DD

###### Goal

- <what should become true>

###### Current Action

- <required only while Status is in_progress>

###### Items

- [ ] pending: <remaining item>
- [~] in_progress: <current item>
- [!] blocked: <blocked item> — reason: <short reason>
- [x] done: <recently completed item, only until progress is compacted>
- [-] cancelled: <cancelled item> — reason: <short reason>

###### Progress

- <optional compact summary of completed work, maximum 1-3 bullets>

###### Done When

- <acceptance condition>

###### Proof

- <minimal evidence available while the task remains open>

###### Next

- <next action>
```

For a full task in `Active`, required fields are `Status`, `Created`, `Updated`,
`Goal`, `Items`, `Done When`, `Proof`, and `Next`. `Current Action` is required
only while the task is `in_progress`. `Progress` is optional.

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

- <first useful action>
```

Expand the task to the full open-task structure when work begins or when the
extra fields become necessary.

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

- <minimal evidence>

#### Files / Artifacts

- `<path-or-artifact>`

#### Follow-up

- <new TODO task, or "None">
```

Create the monthly archive lazily on the first real closure for that month.
When appending to an existing file, reuse its existing date-group structure.

## Cancelled Archive Record

Use the archive format with `Status: cancelled` and replace `Result` with:

```md
#### Cancellation Reason

- <why the task was cancelled>
```

Proof is optional for cancellation unless it materially explains the final
state.

## Field Rules

- `Goal`: the state that should become true.
- `Current Action`: one concrete action being performed now.
- `Items`: current and remaining work, not a historical checklist.
- `Progress`: at most one to three compact completed results.
- `Done When`: acceptance condition.
- `Proof`: evidence already available while the task is open.
- `Next`: the next useful action.
- `Constraints`, `Risks`, `Open Questions`, and `Decisions`: add only when
  future continuation genuinely needs them.

Use only these statuses:

- `pending`
- `in_progress`
- `blocked`
- `done`
- `cancelled`

Knowledge labels such as fact, observation, hypothesis, decision, risk, noise,
or verified result are not task statuses.
