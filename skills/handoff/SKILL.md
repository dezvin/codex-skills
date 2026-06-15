---
name: handoff
description: Create a compact continuation handoff and a ready-to-use prompt for a fresh Codex chat. Use when the user wants to preserve working state, continue in a new session, transfer ongoing work, or prepare another AI agent to resume without rereading the conversation.
---

# Handoff

Create two outputs:

1. A Markdown handoff file containing the minimum working state a fresh agent needs.
2. A complete continuation prompt the user can send with that file in a new Codex chat.

The handoff is not a chronological conversation summary. Preserve information whose loss could cause a wrong next action, violated constraint, reopened decision, or repeated work. Remove conversational prose, intermediate reasoning, repetition, stale branches, and detail already captured in durable artifacts.

## Determine focus and location

- If the user supplied a next-session focus, prioritize it. Otherwise infer the focus from the active task.
- Write the handoff and continuation prompt in the primary language of the current conversation unless the user requests another language.
- Derive a short, specific topic and normalize it to lowercase kebab-case for the filename.
- When the work belongs to a project, search upward from the current working directory and save the file in the nearest ancestor that represents the project root. Infer it from available project metadata, manifests, configuration, source layout, or repository markers.
- When the work is not project-based or no project root can be identified, use the operating system's temporary directory.
- Use `handoff-<topic>.md`.
- If the user provides an existing handoff path and asks to update, refresh, amend, or replace it, read that file first and update it in place. Do not create a numbered copy.
- When creating a new handoff, never overwrite an existing file. On conflict, use the first available numbered name: `handoff-<topic>-2.md`, `handoff-<topic>-3.md`, and so on.

## Write the handoff

Use only relevant sections and omit empty ones:

```markdown
# Handoff: <topic>

## Goal
## Current state
## Decisions and constraints
## Facts, assumptions, and verification
## Artifacts and sources of truth
## Work completed
## Remaining work
## Next action
## Suggested skills

## Open questions
## Blockers
## Failed attempts
## Do not redo
## Risks
```

Apply these rules:

- Make the goal and next action concrete.
- Preserve exact user requirements, constraints, accepted decisions, and rejected approaches that still matter.
- Include `Facts, assumptions, and verification` only when material uncertainty affects the next work. Within it, separate `Confirmed facts`, `Assumptions`, and `Must verify` so the next agent does not treat an inference as established fact.
- For non-development work, preserve only relevant domain context such as the audience, intended outcome, deliverable format, tone, channel, stakeholder constraints, accepted or rejected directions, and what makes the result useful.
- Distinguish completed work from remaining work.
- Record failed attempts only when they prevent repetition or explain the current state.
- Reference existing PRDs, plans, research, ADRs, issues, commits, diffs, and other artifacts by exact path or URL instead of duplicating them.
- For each important artifact, state briefly why it matters and identify the primary source of truth when useful.
- In `Suggested skills`, use only exact names of skills available in the current session. Explain briefly when and why each should be invoked. If the available skill list cannot be inspected, omit the section instead of inventing skill names. Do not add filler suggestions.
- Redact API keys, passwords, tokens, credentials, and other secrets. Omit unnecessary personal or private client data. Preserve necessary local paths and describe required secrets abstractly, such as "the API key is available in the environment."

## Generate the continuation prompt

After saving the handoff, create a fully populated, concise prompt optimized for Codex with GPT-5.5. Use an outcome-first contract: goal, current task, context, critical constraints, and a verifiable completion condition. Leave room for the agent to choose an efficient execution path.

Do not leave placeholders. Mention only the handoff and the few primary artifacts the next agent should read first.

For project work, use this shape:

```markdown
Continue the work from this handoff: @<absolute-handoff-path>.

## Goal
<desired outcome>

## Current task
<the concrete task to resume>

## Read first
1. @<absolute-handoff-path>
2. @<primary-artifact-path> - <why it matters>

## Critical constraints
- <only constraints that materially govern the work>
- Do not repeat work marked completed or listed under `Do not redo`.

## Done when
- <verifiable completion condition>

Read the handoff and listed sources of truth first, inspect the current project state, and then continue the work. Treat my messages and current source-of-truth artifacts as authoritative over stale handoff details. If sources conflict, identify the conflict and use the current evidence. Do not stop at summarizing the handoff or proposing a plan; execute the task unless I explicitly request planning only. Ask a question only when genuinely blocked and the answer cannot be safely discovered from the available context.
```

For projectless work, replace `@<absolute-path>` references with the names of files the user should attach to the new chat.

Use `/goal` only for long-running work with one durable objective and a verifiable stopping condition. Do not use it for open-ended research, loosely related tasks, or work that still needs problem framing.

## Return to the user

Return:

```text
Handoff saved: <absolute path>

Start the next Codex chat with this file attached and the following prompt:

<complete continuation prompt>
```

Before finishing, check that a fresh agent could understand the goal and constraints, locate the sources of truth, avoid repeating completed work, and begin the correct next action.
