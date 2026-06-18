# Design Pass Method

Use this method after receiving a preflight brief, Decision Ledger, or resolved preflight package. The goal is to create a traceable, handoff-ready design for a separate implementation run, not to summarize the conversation or execute the work.

## Contents

- Evidence Boundary
- Input Package
- Status Merge
- Design Requirements And Guardrails
- Task Profile
- View Selection
- View Library
- Custom View Synthesis
- Layered Design
- Design Diff
- Traceability And Impact Map
- Key Design Decisions
- Acceptance Examples
- Implementation Handoff
- Ready-To-Use Implementation Command
- Readiness Check
- Failure Modes

## Evidence Boundary

Use the preflight package as the main evidence source. It may be incomplete or stale, but it is still the user's selected decision memory.

Treat post-preflight user answers as an overlay over the preflight:

```text
preflight decision memory + later explicit user answers = design input package
```

Do not treat an assistant proposal as accepted unless the user explicitly confirmed it. Do not smooth over rejected, superseded, or conflicting items.

If current project files are inspected, treat them as evidence about current state. If they are not inspected, describe file-level impacts as expected or to be verified, not as confirmed facts.

## Input Package

Build an input package before designing:

```text
1. Preflight brief or Decision Ledger
2. Answers to open questions after preflight
3. Target implementation task
4. Constraints, non-goals, and rejected options
5. Optional current system, project, audience, or workflow context
6. Intended implementer
```

If the preflight is absent, stop. Ask for it or ask the user to run `$preflight` first.

## Status Merge

Do not rewrite the preflight. Add an overlay table:

```markdown
| Preflight item | Later user answer | Updated status | Design implication |
| --- | --- | --- | --- |
```

Use user-facing labels in the user's language. Keep these status meanings stable:

- accepted: confirmed by user or preflight evidence;
- rejected: explicitly excluded;
- superseded: replaced by a later user decision;
- proposed: suggested but not accepted;
- deferred: intentionally postponed;
- resolved: answered after preflight;
- still open: not answered;
- needs confirmation: plausible but not proven;
- conflict: unresolved contradiction;
- unknown: insufficient evidence.

Later explicit user decisions override earlier uncertain or conflicting items. Later assistant suggestions do not override earlier accepted decisions.

`resolved` is an overlay status for a post-preflight question that has been answered. It does not automatically mean `accepted`. Convert a resolved answer into an accepted design requirement only when the answer clearly commits to that choice.

## Design Requirements And Guardrails

Convert input status into design constraints before selecting views or designing:

```markdown
| ID | Source | Requirement / guardrail | Type | Design consequence |
| --- | --- | --- | --- | --- |
```

Use:

- requirement: from accepted decisions and clearly committed resolved answers;
- guardrail: from rejected, superseded, or explicitly forbidden options;
- non-goal: from things the implementation must not attempt;
- confirmation gate: from still open, conflicting, or unclear items.

Do not convert every resolved answer into a requirement. A resolved answer can simply close a question, narrow scope, or create a confirmation gate.

## Task Profile

Classify the task by useful traits, not by one rigid label:

```markdown
| Trait | Current profile |
| --- | --- |
| Domain | code, skill, LLM workflow, marketing, content, education, business process, research, document, visual design, hybrid, or custom |
| Output artifact | skill, prompt, text, process, file, plan, document, campaign, course, code, visual system, etc. |
| Actors | user, reader, client, team, Codex, AI agent, operator, learner, developer, etc. |
| Change surface | files, instructions, process, channel, message, offer, document structure, behavior, data flow, roles, etc. |
| Quality criteria | what makes the result useful and acceptable |
| Failure modes | how the implementation can fail |
| Implementation mode | who or what will implement it |
```

This profile drives view selection. Do not use "non-dev" as a final category; it is too broad.

## View Selection

Select views in three layers:

```text
Core Views -> Relevant Preset Views -> Custom Views if needed
```

Rules:

- Use only views that help the next implementation.
- If a preset only partially fits, use only the relevant views.
- If no preset fits, synthesize custom views from the task profile.
- Include a rationale table:

```markdown
| View | Source | Why needed |
| --- | --- | --- |
| Context View | core | Explains where the solution lives and why it matters |
| Custom: Conflict Scenario View | custom | The task depends on behavior under conflict |
```

Use `core`, `preset`, or `custom` as the source.

## View Library

Core views, useful in most design passes:

- Context View: where the solution lives and why it matters.
- Outcome View: what should be different after implementation.
- Scope / Non-scope View: what is included and excluded.
- Actor / Stakeholder View: who uses, reads, executes, approves, or is affected.
- Artifact View: what will be created or changed.
- Workflow View: how the solution works over time.
- Traceability & Impact View: what each decision requires and affects.
- Quality / Acceptance View: how quality will be judged.
- Risk View: how the solution can fail.
- Implementation Handoff View: what the next implementer needs.
- Readiness View: whether implementation can safely start.

Preset view hints:

| Task signal | Useful views |
| --- | --- |
| Codex skill or AI agent | Behavior View, Instruction Hierarchy View, Input/Output Contract View, Tool/File Safety View, Eval View |
| Prompt or LLM workflow | Context Boundary View, Role/Behavior View, Failure Mode View, Evaluation Prompt View |
| Marketing | Audience View, Offer View, Channel View, Message View, Metrics View |
| Copywriting | Reader View, Promise View, Structure View, Tone View, Editing Criteria View |
| Learning product | Learner View, Learning Outcome View, Curriculum View, Practice View, Assessment View |
| Business process | Actor View, Workflow View, Handoff View, Decision Point View, Operational Risk View |
| Research | Research Question View, Source View, Evidence View, Synthesis View, Gap View |
| Document or methodology | Purpose View, Concept Model View, Structure View, Usage View, Review Checklist View |
| Code | Component View, Data Flow View, File Impact View, Test View, Rollback/Safety View |
| Visual design | Audience View, Layout View, Visual System View, Asset View, Review Criteria View |

These presets are accelerators, not a closed taxonomy.

## Custom View Synthesis

When a task is outside known presets, create custom views by asking:

| Question | Possible view |
| --- | --- |
| Who participates or is affected? | Actor View |
| What is created or changed? | Artifact View |
| Where will the change appear? | Impact View |
| How does it work over time? | Workflow View |
| What decisions control the result? | Decision View |
| How can it fail? | Risk / Failure View |
| How should quality be checked? | Quality View |
| Who will implement it? | Handoff View |
| What must not happen? | Guardrail View |

Name custom views plainly. The user should understand the view without learning a methodology.

## Layered Design

Design from broad context toward implementation detail:

```text
Context -> Capabilities -> Structure -> Interactions -> Implementation Details -> Verification
```

Use domain-appropriate words:

| Layer | Question | Code example | Non-code example |
| --- | --- | --- | --- |
| Context | Where does this live and why? | repo, feature, users | channel, course, workflow, audience |
| Capabilities | What must it be able to do? | export, parse, validate | explain, persuade, teach, route |
| Structure | What parts does it have? | files, modules, components | sections, stages, roles, messages |
| Interactions | How do parts connect? | calls, data flow, dependencies | handoffs, transitions, usage logic |
| Implementation Details | What must be done? | edits, tests, commands | templates, criteria, instructions |
| Verification | How is it checked? | tests, lint, manual check | review checklist, examples, acceptance criteria |

Do not force software terms onto business, marketing, content, education, or methodology work.

## Design Diff

Show the intended change in plain terms before the traceability table:

```markdown
| Current / before | Target / after | What must change | Verification |
| --- | --- | --- | --- |
```

Use domain-appropriate wording:

- code: current behavior -> target behavior;
- Codex skill: current instruction behavior -> desired instruction behavior;
- LLM workflow: current agent behavior -> target agent behavior;
- marketing: current funnel/message state -> target funnel/message state;
- document or methodology: current structure/meaning -> target structure/meaning;
- business process: current workflow -> target workflow.

Design Diff is not a file diff. It is a reader-facing control that shows what the implementation is supposed to change.

## Traceability And Impact Map

This section is mandatory. It connects preflight memory to implementation:

```text
Preflight decision or answer
-> Design requirement
-> Affected surface
-> Implementation implication
-> Verification check
```

Use a table:

```markdown
| ID | Source | Decision / requirement | Affected surface | Implementation implication | Verification | Risk |
| --- | --- | --- | --- | --- | --- | --- |
```

Adapt `Affected surface` to the domain:

- code: file, module, component, data flow, test;
- Codex skill: SKILL.md section, reference, script, eval, safety rule;
- LLM workflow: context boundary, role, input, output, failure mode;
- marketing: audience, offer, channel, message, metric;
- copywriting: text block, promise, tone, structure, review criterion;
- business process: actor, workflow step, handoff, decision point;
- education: learner path, module, practice, assessment;
- research: question, source set, evidence standard, synthesis step;
- custom task: name the affected surface in plain language.

If the affected file or surface is not verified, mark it as expected or to inspect.

## Key Design Decisions

Use an ADR-like table for important choices:

```markdown
| ID | Design decision | Why | Alternatives rejected | Consequences |
| --- | --- | --- | --- | --- |
```

Do not create separate ADR files. This is a design-pass section only.

## Acceptance Examples

Use Acceptance Examples when examples help test behavior, quality, edge cases, or user-facing fit. They are especially useful for Codex skills, prompts, LLM workflows, procedures, policies, content systems, and other tasks where the implementation must behave correctly across scenarios.

Use this table:

```markdown
| Scenario | Expected result | Should not do | Check |
| --- | --- | --- | --- |
```

Good examples should be concrete enough that the next agent can use them as evaluation prompts, review cases, or acceptance checks.

If examples would be artificial and add no control beyond the verification plan, say so briefly and rely on the verification checks instead. Do not invent decorative examples.

## Implementation Handoff

Give the next implementer enough guidance to act without rereading the whole discussion:

- goal;
- scope and non-goals;
- artifacts or surfaces to create or change;
- safe order of work;
- constraints and guardrails;
- required context or files to read;
- checks to run or review criteria to apply;
- stop conditions and questions that block implementation.

Keep it actionable, but do not turn it into a detailed step-by-step implementation if the design is not ready.

## Ready-To-Use Implementation Command

Write a user-facing command for the next Codex or AI-agent chat. Include:

- the goal;
- the attached or pasted design-pass artifact as context;
- minimum boundaries and constraints;
- files, sources, or artifacts to read first;
- what to implement;
- what not to do;
- verification requirements;
- when to stop and ask.

If readiness is `conditional` or `no`, do not ask the next agent to implement the full design. The command must ask the next agent to first resolve named blockers, inspect named files or context, or obtain named confirmations.

Template:

```markdown
Use the attached Design Pass as the source of truth.

Goal: <goal>
Task: <task>
Boundaries: <scope, non-goals, constraints>
Read first: <files, sources, artifacts, or "the Design Pass only">
Implement: <ready implementation surface>
Do not: <rejected or risky actions>
Verify: <checks or review criteria>
Stop and ask if: <blocking uncertainty>
```

Translate this command into the user's language.

## Readiness Check

Use two checks.

Coherence check:

- target task is clear;
- preflight decisions and post-preflight answers were merged;
- design requirements and guardrails were derived before design;
- rejected and superseded options are preserved;
- selected views fit the task profile;
- Design Diff shows the intended change;
- risks and checks are visible.

Implementation readiness check:

- no critical unresolved decision is hidden;
- affected surfaces are clear enough or explicitly marked for inspection;
- implementation boundaries are clear;
- quality checks are concrete;
- Acceptance Examples are included when they materially improve checking, or explicitly omitted when they would be artificial;
- handoff and command are actionable;
- this skill run did not implement the work.

Final status:

```text
Ready for implementation: yes / no / conditional
```

Use:

- yes: implementation can start within the stated boundaries;
- conditional: implementation can start only after named confirmations or file/context reads;
- no: a blocker prevents responsible implementation.

## Failure Modes

Reject or correct these before returning the design pass:

- creating another preflight instead of a design pass;
- turning the design pass into a direct implementation;
- treating open questions as accepted decisions;
- treating `resolved` as automatically accepted;
- skipping Design Requirements And Guardrails;
- ignoring user answers after preflight;
- losing rejected or superseded options;
- forcing a dev-only structure onto non-dev work;
- treating view packs as a closed menu;
- omitting Design Diff;
- omitting the Traceability & Impact Map;
- asking the next agent to implement the full design when readiness is conditional or no;
- writing a huge academic document instead of useful design;
- claiming readiness when critical choices are missing;
- editing files without explicit current-user instruction.
