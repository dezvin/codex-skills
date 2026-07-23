---
name: handoff
description: >-
  Create or update a compact, portable handoff of selected ongoing work and a
  continuation prompt for a fresh chat or agent. Use when the user wants to
  transfer a specific task, project, recent work segment, or active work contour
  without making the next agent reread the conversation. When relevant Codex
  history may have fallen outside visible context, recover it with the bundled
  Codex-only temporary export before writing the handoff. Do not use for an
  ordinary summary or status update, a full transcript export, durable TODO
  capture, implementation design, continuation in the same chat, or native
  thread resume, fork, or transfer.
---

# Handoff

Transfer the minimum working state a fresh agent needs to continue the selected
work correctly. Do not produce a chronological conversation summary.

The user's handoff request authorizes creating the final handoff artifact and,
when necessary, temporarily reading the current Codex thread through the
bundled export script. It does not authorize transferring the whole
conversation or broadening the next agent's permissions.

## Establish The Transfer Scope

Determine what must continue before choosing a history source:

- a specific task;
- a specific project;
- the latest bounded segment of work;
- the full active work contour.

Use the focus named by the user. Otherwise infer one only when the current work
has a single clear contour. If several tasks, projects, or plausible boundaries
would produce materially different handoffs, ask one short question about what
to transfer.

Exclude unrelated work even when it appears in the same chat or export.

## Select The Best Available History

Use visible context when it is sufficient to recover the selected scope.

Use the bundled Codex-only export when earlier relevant state may be missing
because of compaction, truncation, a long conversation, a visible mid-task
start, or a user request to recover an older part of the current thread.

Run the export only when all of these are true:

- the environment is Codex;
- `CODEX_THREAD_ID` or a user-supplied current thread ID is available;
- Python can run the bundled script;
- the matching Codex rollout can be verified.

Run from this skill directory:

```powershell
python .\scripts\export_current_thread.py --temporary --json
```

If `python` is unavailable but `py` exists:

```powershell
py .\scripts\export_current_thread.py --temporary --json
```

The script writes a temporary compact UTF-8 `.txt` and returns its exact
`output_path`, size, estimated token count, and coverage warning. It preserves
supported user, assistant, and subagent messages plus a verifiable tool trace
with Call IDs, known paths, status, result size and hash, and source-record
references. It omits invocation bodies, executed code, file contents, and
result bodies. It deterministically excludes system/developer messages, known
Codex-injected user-content blocks, hidden reasoning, unknown internal
records, and typed binary content. It does not use a model to summarize,
clean, select relevant fragments, or deduplicate text.

If the export can responsibly fit in the available context, read it as
evidence for the already selected transfer scope. Do not add a preliminary
model pass for relevance selection. If it cannot fit, ask the user whether to
narrow the scope, read the file in chunks with the additional context cost, or
continue from visible context.

Do not infer omitted tool details. Retrieve the supported records matching one
`Call ID` only when they are material to the selected transfer scope, such as
a failed operation, irreversible change, or check that cannot be responsibly
established from current authoritative files:

```powershell
python .\scripts\export_current_thread.py `
  --extract-call "<call_id>" `
  --temporary `
  --json
```

Check `pair_complete`. If it is `false`, use `missing_parts` to identify
whether the call or result is absent and do not infer the missing side.

Prefer current files, Git state, and other authoritative artifacts over stale
historical tool output. After the handoff is complete, delete the compact
export and every extracted fragment with:

```powershell
python .\scripts\export_current_thread.py --cleanup "<output_path>" --json
```

Do not copy the export or extracted payloads into `.handoffs`, attach them to
the continuation prompt, or present them as sources for the next agent. If
cleanup fails, report the exact remaining path. The compact trace can identify
only explicit or literally mentioned paths from arbitrary code; it must label
that coverage as partial or unknown. Inspect important current artifacts
directly when feasible.

Do not run this Codex script in ChatGPT, Claude, Gemini, or another environment
unless that environment's compatible history mechanism has been implemented
and verified independently. If reliable export is unavailable, use visible
context and label its coverage honestly. Do not reconstruct missing history
from vague memory.

## Establish Current Evidence

Before writing a project handoff, inspect only the state that can change the
next action. When relevant, record:

- project root;
- current Git branch and commit;
- modified and untracked files;
- created artifacts;
- checks actually run and their results;
- unfinished processes or material errors;
- exact paths or URLs of primary sources of truth.

Reference large plans, specifications, logs, diffs, research, and other durable
artifacts instead of copying them. State briefly why each important artifact
matters.

Treat the handoff as a compact snapshot, not a source of truth. Current user
messages and current authoritative artifacts override stale handoff details.

## Preserve The Authorization Boundary

State what the next agent is authorized to do, such as:

- analyze and report without changes;
- design without implementation;
- draft without sending or publishing;
- make in-scope local changes and validate them;
- act only after a new confirmation;
- continue autonomously within a named safe boundary.

Do not convert an earlier approval into reusable permission for external,
destructive, costly, privileged, or scope-expanding action. Do not treat an
assistant proposal as a user decision.

## Write The Handoff

Write in the user's current human-facing language. Determine it from recent
direct user messages, not from source files, code, tool output, or exported
history. If the user mixes languages, use the dominant language of their
direct instructions. Preserve paths, commands, identifiers, field names, and
exact quoted strings as written.

Use this core structure:

```markdown
# Handoff: <topic>

Context coverage: <verified Codex history or visible context and its limit>

## Goal and done condition
## Transfer scope
## Current task and authorization
## Current state
## Decisions and constraints
## Sources of truth and workspace state
## Completed
## Remaining
## First action
```

Add only relevant conditional sections:

```markdown
## Facts, assumptions, and what to verify
## Blockers
## Do not redo
## Material failed attempts
## Risks
```

Apply these rules:

- Make the goal, done condition, and first action concrete.
- Preserve exact user requirements, accepted decisions, rejected approaches
  that still constrain the work, and material unknowns.
- Separate confirmed facts, user decisions, assumptions, and items that still
  require verification.
- Distinguish completed work from remaining work.
- Record failed attempts only when they prevent repetition or explain current
  state.
- Redact keys, passwords, tokens, credentials, and unnecessary private data.
- Do not add a generic section recommending other skills.

## Choose The Output Form

When a writable project root exists, create:

```text
<project-root>/.handoffs/handoff-<topic>.md
```

Create `.handoffs` lazily on the first real handoff. Do not edit `AGENTS.md`,
`.gitignore`, or another project file. Derive a short lowercase kebab-case
topic. If the user supplies an existing handoff path and asks to refresh it,
read it first and update it in place. For a new handoff, never overwrite an
existing file; use `-2`, `-3`, and so on.

When work is not project-based but file creation is available, save the file
in the operating system's temporary directory.

When the environment cannot create files, return one self-contained
continuation prompt containing all required handoff information. Do not claim
that a file was created. Keep the same scope, evidence status, authorization
boundary, and first action as the file-based form.

## Generate The Continuation Prompt

For a file-based handoff, return a short, fully localized prompt that points to
the handoff without duplicating it:

```markdown
Continue the work from @<absolute-handoff-path>.

Current task: <concrete task>.
Done when: <verifiable completion condition>.

Read the handoff and its sources of truth first, then inspect the current
state. Continue only within the recorded authorization boundary. Do not repeat
completed work. If the handoff conflicts with my newer messages or current
authoritative artifacts, identify the conflict and use the current evidence.
```

Translate the entire prompt into the user's language. Do not mention a model
version. Do not activate Codex planning or goal modes. Do not tell the next agent to execute
when the recorded authorization is analysis-only, design-only, draft-only, or
confirmation-gated.

## Return To The User

For a created file, return its absolute path and the complete short
continuation prompt. For an inline handoff, return the single self-contained
prompt and state that the environment could not create a file.

Before finishing, verify that a fresh agent can identify the selected work,
understand the current state and authority boundary, find current sources of
truth, avoid repeated work, and begin the correct first action. Also verify
that any temporary export was deleted or report its exact remaining path.
