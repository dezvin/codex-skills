---
name: handoff
description: >-
  Prepare a self-contained prompt or handoff file that transfers selected work
  and its necessary context to another chat or agent. Use when the user asks
  to continue elsewhere, brief another agent, update a handoff, or prepare a
  next-stage, scoped parallel, or review task for another recipient when it
  depends on accumulated work.
  Do not use for discussing or editing this skill, executing an incoming
  handoff, standalone prompts unrelated to accumulated work, ordinary summaries
  or status updates, TODO capture, transcript exports, implementation design,
  or native thread operations alone.
---

# Handoff

Transfer the minimum working state another chat or agent needs to perform the
selected task correctly. Return the form the user asked for: a self-contained
prompt, a handoff file with a short continuation prompt, or an update to an
existing handoff. Do not produce a chronological conversation summary.

A transfer request authorizes preparing the requested final output and, when
necessary, temporarily recovering relevant Codex or Antigravity history with the bundled
export script. It does not authorize transferring the whole conversation,
broadening the recipient's task, or expanding either agent's permissions.

## Confirm That A Transfer Is Being Requested

Apply this skill implicitly only when both are true:

1. the user asks to prepare work for another chat or agent, including
   continuation elsewhere, a next stage, a scoped parallel task, a review, or
   an updated handoff;
2. that recipient needs decisions, results, constraints, state, or other
   context accumulated in the current work.

The user does not need to say "handoff." A clear request such as "continue this
in a new chat" is sufficient when the current work has one identifiable scope.
An observation that the chat is long, slow, or nearing its context limit is not
by itself a request to prepare a transfer.

Do not activate the transfer workflow merely because the user mentions this
skill, asks to inspect or edit it, wants an ordinary summary or standalone
prompt, or asks to continue from an incoming handoff. A native request to open,
resume, fork, move, or navigate to a Codex thread belongs to the corresponding
thread operation unless the user also asks for a prepared transfer. Follow an
explicit instruction to work without this skill.

## Establish The Receiving Task And Scope

Determine first:

- what the recipient must do and what result should count as done;
- which selected task, project, stage, branch, or review is being transferred;
- what accumulated context is necessary for that task;
- which output form the user requested.

Use the focus named by the user. Otherwise infer it only when the current work
has one clear contour. If several plausible scopes would give the recipient
materially different tasks, ask one short question about what to transfer.

Select context according to the receiving task:

- for continuation of the same task, preserve current state, decisions,
  completed work, remaining work, and the correct resumption point;
- for a separated or parallel task, preserve its boundary, required grounds,
  dependencies, and expected return without importing unrelated project work;
- for a next stage, preserve the accepted output of the previous stage and the
  conditions that govern the new one;
- for an independent or blind review, preserve the subject, requirements, raw
  evidence, and authority boundary while withholding prior judgments, expected
  verdicts, and proposed fixes that would bias the requested independence;
- for delayed resumption, distinguish preserved state from facts that may need
  freshness verification;
- for another workspace, host, product, or person, include only sources the
  recipient can access and make unavailable dependencies explicit.

Do not use handoff preparation to design an unresolved implementation. When an
approved plan, design, specification, or durable source already exists, point
the recipient to it and preserve only the context needed to use it correctly.
Preparing a task for another agent does not launch that agent or send the task.

## Choose The Output Form

Follow the user's requested form before considering where files can be written:

- If the user asks for a prompt to copy, a result in chat, or no separate file,
  return one self-contained continuation prompt in chat. Do not create a final
  handoff file merely because a writable project root exists.
- If the user asks to save, create, or prepare a handoff file, create the file
  and return a short continuation prompt that points to it.
- If the user supplies an existing handoff and asks to update it, read it first
  and update that file in place.
- If the user asks generally to prepare a transfer without choosing a form,
  prefer a handoff file when the recipient can access it; otherwise return a
  self-contained prompt.

If the recipient cannot access local files, do not present a local path as a
usable source. Put the necessary context in the prompt or state which source
material the user must make available to the recipient.

An instruction not to create the final handoff file does not prohibit a
temporary recovery export. An explicit instruction not to write any files
does: in that case, use visible context and state any material coverage limit.

## Select The Best Available History

Use visible context when it is sufficient to recover the selected scope.

Use the bundled export when earlier relevant state may be missing
because of compaction, truncation, a long conversation, a visible mid-task
start, or a user request to recover an older part of the current thread or conversation.

Run the export only when all of these are true:

- the environment is Codex or Antigravity;
- `CODEX_THREAD_ID`, `ANTIGRAVITY_CONVERSATION_ID`, or a user-supplied current thread ID is available;
- Python can run the bundled script;
- matching session logs or rollout journals can be verified;
- the user has not prohibited all file writes.

Run from this skill directory:

```powershell
python .\scripts\export_current_thread.py --temporary --json
```

If `python` is unavailable but `py` exists:

```powershell
py .\scripts\export_current_thread.py --temporary --json
```

The script writes a temporary UTF-8 recovery transcript and returns its exact
`output_path`, size, estimated token count, `coverage_status`, temporal boundaries, `message_count`, and
coverage warning. The transcript header lists every source log or journal used. It
preserves supported user, assistant, and subagent messages,
context-compaction markers, and short confirmed file/URL-read markers at the points
where those reads occurred.
Repeated chunk reads are collapsed within one interval between messages. Other
tool calls and all tool results are omitted. It deterministically excludes
system/developer messages, known platform-injected user-content blocks, hidden
reasoning, unknown internal records, and typed binary content. It does not use
a model to summarize, clean, select relevant fragments, or rewrite text.

Interpret coverage before drafting the handoff:

- `complete_thread` or `complete_conversation` means the verified history of the
  current thread or conversation was assembled into one chronology.
- `partial_thread` means at least one candidate journal could not be included.
  Inspect `candidate_failures`; do not present the handoff as based on the full
  thread. If the missing portion could materially affect the transfer, stop and
  ask whether to continue from the identified partial history or use another
  source.
- `single_rollout` means the export intentionally covers only one explicitly
  selected journal. Never describe it as the complete thread.

If the export can responsibly fit in the available context, read it as evidence
for the already selected transfer scope. Do not add a preliminary model pass
for relevance selection. If it cannot fit, ask the user whether to narrow the
scope, read the file in chunks with the additional context cost, or continue
from visible context.

Do not infer omitted tool details. Prefer current files, Git state, and other
authoritative artifacts. If exact historical tool activity remains material
and cannot be established from current evidence, ask separately for permission
to create a full technical export:

```powershell
python .\scripts\export_current_thread.py --full --temporary --json
```

Apply the same coverage check to a full technical export; `--full` changes the
included technical detail, not the thread coverage. After the handoff is
complete, delete every temporary export with:

```powershell
python .\scripts\export_current_thread.py --cleanup "<output_path>" --json
```

Do not copy an export into `.handoffs`, attach it to the continuation prompt,
or present it as a source for the recipient. If cleanup fails, report the exact
remaining path. A file-read marker records only a supported confirmed content
read; it does not prove that the whole file was read. Inspect important current
artifacts directly when feasible.

Do not run this Codex script in ChatGPT, Claude, Gemini, or another environment
unless that environment's compatible history mechanism has been implemented
and verified independently. If reliable export is unavailable, use visible
context and label its coverage honestly. Do not reconstruct missing history
from vague memory.

## Establish Current Evidence

Inspect only the state that can change the receiving task. When relevant,
establish the project root, current Git branch and commit, modified and
untracked files, created artifacts, checks actually run, unfinished processes,
material errors, and exact paths or URLs of primary sources of truth.

Reference large plans, specifications, logs, diffs, research, and other durable
artifacts instead of copying them when the recipient can access those sources.
State briefly why each important artifact matters.

Treat the handoff as a compact snapshot. Current user messages and current
authoritative artifacts override stale handoff details.

## Preserve The Authorization Boundary

State the actual authority that applies to the receiving task: analysis,
design, drafting, in-scope local changes, a confirmation-gated action, or
another clearly established boundary.

Do not convert an earlier approval into reusable permission for external,
destructive, costly, privileged, or scope-expanding action. Do not treat an
assistant proposal as a user decision.

## Build Proportional Transfer Content

Make this meaning recoverable in either output form when it affects the task:

- the receiving task and observable done condition;
- the selected transfer scope and authority boundary;
- current state, completed work, and remaining work;
- accepted decisions, active constraints, and material rejected approaches;
- accessible sources of truth and relevant workspace state;
- facts, assumptions, unknowns, blockers, failed attempts, or risks that change
  the recipient's next action;
- the first required action or dependency when the evidence determines one.

Use only the sections needed for the transfer. Do not manufacture empty
headings, duplicate source documents, or include context merely because it is
available. Redact keys, passwords, tokens, credentials, and unnecessary
private data. Do not add a generic recommendation to use other skills.

Give the recipient enough freedom to perform the task. Preserve required order,
dependencies, verification, and stop conditions, but do not invent a detailed
implementation route or turn the transfer into step-by-step micromanagement.

## Write A Handoff File When Requested

When a project handoff file is the selected form, create:

```text
<project-root>/.handoffs/handoff-<topic>.md
```

Create `.handoffs` lazily on the first real file-based handoff. Do not edit
`AGENTS.md`, `.gitignore`, or another project file. Derive a short lowercase
kebab-case topic. For a new handoff, never overwrite an existing file; use
`-2`, `-3`, and so on. When work is not project-based, save a requested handoff
file in the operating system's temporary directory unless the user names a
different location.

A file may use this structure, omitting or combining sections whose meaning is
not needed:

```markdown
# Handoff: <topic>

Context coverage: <verified Codex history or visible context and its limit>

## Goal and done condition
## Transfer scope and authorization
## Current state
## Decisions and constraints
## Sources of truth
## Completed and remaining work
## First action
```

Add facts and assumptions, blockers, material failed attempts, or risks only
when they affect continuation.

## Generate The Continuation Prompt

For a file-based handoff, return a short, fully localized prompt that points to
the file without duplicating it:

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
version. Do not activate Codex planning or goal modes. Do not tell the
recipient to execute when the recorded authorization is analysis-only,
design-only, draft-only, or confirmation-gated.

For an inline handoff, return one self-contained prompt containing the
proportional transfer content directly. It may point to durable sources the
recipient can access, but must not depend on a newly created handoff file.

## Return To The User

For a created or updated file, return its absolute path and the complete short
continuation prompt. For an inline handoff, return only the complete
self-contained prompt plus any material note about unavailable sources or
coverage.

Before finishing, verify that a fresh recipient can identify the selected task,
understand current state and authority, find or receive the necessary sources,
avoid repeated work, and begin the correct work without invented
micromanagement. Also verify that any temporary export was deleted or report
its exact remaining path.
