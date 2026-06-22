# Mode Selection

Choose the smallest safe mode. Do not turn a simple file edit into a methodology exercise, and do not treat a folder cleanup as a one-shot rewrite.

## Modes

`analyze-only`

Use for folders, live work areas, unclear scope, mixed document roles, or when the user asks what to do. Produce a short sprawl map and cleanup plan. Do not write files.

`dry-run`

Use when the user wants to see the likely result before writing. Show the proposed structure, source mapping, risks, and key fragments, not the whole future document unless the user asks.

`compress-one`

Use for one ordinary `.md` or `.txt` document with a clear function and low to moderate risk.

`compress-instructional-doc`

Use for one ordinary `.md` or `.txt` document that controls actions: process docs, rules, runbooks, approval notes, workflow instructions, or guardrails. Preserve behavior, not just meaning.

`merge-many`

Use for multiple documents that may become one or more consolidated documents. Always map source roles and ownership before drafting.

`cleanup-sources`

Use only after a consolidated document exists and the user separately confirms moving included source files into `00_Source_Documents`.

## Scope Signals

Small enough for one pass:

- one short file;
- clear function;
- low risk;
- no live work area;
- no conflicting sources;
- no external link repair.

Needs staged work:

- a folder;
- several documents with different roles;
- live work area;
- raw/source plus current rules;
- instructions, statuses, TODOs, or handoffs;
- many internal links;
- unclear final document role.

## Broad Scope Rule

If the user points to a folder, begin with a shallow inventory. Read file names, sizes, dates, headings, and obvious links. Read full contents only for likely candidates.

If the request is really a document-contour cleanup rather than a file merge, say that and start with `analyze-only`.

## Live Work Area

Treat an area as live when the user says work is in progress or local signals suggest active work. If the evidence is unclear, state the assumption and ask.

For live areas, use only `analyze-only` or `dry-run` in the current pass.
