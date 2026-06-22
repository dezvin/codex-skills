# Source Roles

Before compressing or consolidating, identify what each document is doing.

## Common Roles

`current-truth`

The document currently governs behavior, decisions, rules, or navigation.

`source-raw`

Original material, notes, transcript, evidence, or rough source. Do not clean it into a final version unless the user asks.

`draft`

A possible future version. It may contain useful language but is not authority.

`history`

Decision history, old context, or past state. Keep only when it affects current use or the user wants history preserved.

`handoff`

Continuation state for another session or worker. Do not merge it into a working document without checking whether its job is still active.

`todo-status`

Open work, blockers, pending decisions, or status notes. Do not dissolve these into smooth prose.

`reference`

Background material used to understand or verify the current document.

`archive`

Kept for record. Usually not a current source of truth.

## Ownership Map

For multiple documents, produce a compact map:

```text
Document:
Role:
Owns:
Should contribute:
Should stay separate:
Risk:
```

If several documents own different truths, do not merge automatically. Ask what final document is needed.

## Conflicts

If documents disagree, handle conflicts by the role of the output:

- Working rule: put the conflict in the report and ask which rule wins.
- Research or raw synthesis: keep the conflict in the output if it is part of the content.
- Cleanup map: list the conflict and propose the next decision.

If the output role is unclear, state your best guess and ask with choices.
