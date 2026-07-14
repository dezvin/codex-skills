# Design Method

Use this method only after decision analysis has established the requirements, guardrails, and critical-question state. The goal is a traceable, handoff-ready design, not direct implementation.

## Contents

- Design Input
- Requirements And Guardrails
- Task Profile And Views
- Layered Design
- Traceability And Verification
- Optional Controls
- Implementation Handoff
- Ready-To-Use Command
- Readiness
- Failure Modes

## Design Input

Build the design input from:

```text
Decision Ledger or existing preflight
+ later explicit user answers
+ target task
+ constraints, non-goals, and rejected options
+ inspected current-state evidence when needed
= design input
```

An existing preflight is one possible source, not a prerequisite. Do not let current-state inspection rewrite what the user decided. Use it to verify feasibility and affected surfaces.

If a critical user choice is still open, return to the critical-question pause instead of inventing it. A bounded file or context inspection can remain a readiness condition when it does not change the core design.

## Requirements And Guardrails

Convert decision status into design constraints before choosing structure:

| ID | Source | Requirement or guardrail | Type | Design consequence |
| --- | --- | --- | --- | --- |

Use:

- **requirement** for accepted decisions and clearly committed later answers;
- **guardrail** for rejected, superseded, or explicitly forbidden directions;
- **non-goal** for work the implementation must not attempt;
- **confirmation gate** for remaining bounded uncertainty that must be resolved before a named action.

Do not turn every answered question into a requirement. An answer can narrow scope, close a branch, or establish a non-goal.

## Task Profile And Views

Build a Task Profile only when it improves view selection or handoff. Useful traits are:

- domain;
- output artifact;
- actors or affected people;
- change surface;
- quality criteria;
- characteristic failure modes;
- intended implementer.

Select only views that help implementation. Core candidates include context, outcome, scope, actors, artifact, workflow, traceability, quality, risk, handoff, and readiness.

Use relevant domain views when useful:

| Task signal | Candidate views |
| --- | --- |
| Codex skill or AI workflow | Behavior, Instruction Hierarchy, Input/Output Contract, Tool/File Safety, Eval |
| Marketing or copy | Audience, Offer, Channel, Message, Metrics, Tone |
| Learning product | Learner, Outcome, Curriculum, Practice, Assessment |
| Business process | Actors, Workflow, Handoff, Decision Points, Operational Risk |
| Research | Question, Sources, Evidence, Synthesis, Gaps |
| Document or methodology | Purpose, Concept Model, Structure, Usage, Review Checklist |
| Code | Components, Data Flow, File Impact, Tests, Rollback/Safety |
| Visual design | Audience, Layout, Visual System, Assets, Review Criteria |

Presets are hints, not a closed taxonomy. Synthesize a plainly named custom view when the task requires one. Do not show a view-selection rationale unless it explains a non-obvious choice.

## Layered Design

Design from broad purpose toward verification:

```text
Context -> Capabilities -> Structure -> Interactions
-> Implementation implications -> Verification
```

Use domain-appropriate language. Do not force software vocabulary onto business, marketing, education, research, content, or methodology work.

The design must make clear:

- what should be different after implementation;
- what is included and excluded;
- what parts or stages exist;
- how they interact over time;
- what the implementer must change or create;
- what evidence will prove success.

## Traceability And Verification

Traceability is always required, but its display can be compact:

```text
decision or answer
-> requirement or guardrail
-> affected surface
-> implementation implication
-> verification
```

Use a table when several mappings must be compared:

| ID | Source decision | Requirement | Affected surface | Implementation implication | Verification | Risk |
| --- | --- | --- | --- | --- | --- | --- |

Adapt "affected surface" to the domain: file or component, skill instruction or script, workflow step, audience or channel, document section, learner activity, source set, or another plainly named surface.

If a surface was not inspected, label it expected or to inspect. Do not present expected file impact as confirmed current state.

Define checks that match the task: tests, lint, structural validation, scenario review, source verification, review checklist, examples, or observable behavior.

## Optional Controls

Use these only when they materially improve the result:

- **Design Diff** for a useful before-to-after comparison.
- **Key Design Decisions** for consequential choices and rejected alternatives.
- **Acceptance Examples** for behavior, edge cases, prompts, procedures, policies, or user-facing quality.
- **Full Decision Ledger** for complex or audit-sensitive histories.
- **Task Profile and selected-view rationale** for hybrid or non-obvious work.

Do not create empty sections. Do not repeat the same decision across several tables without adding control or verification value.

## Implementation Handoff

Give the next implementer enough context to act without rereading the discussion:

- goal;
- scope and non-goals;
- artifacts or surfaces to change;
- safe order of work;
- constraints and guardrails;
- context or files to inspect first;
- checks or review criteria;
- stop conditions and named blockers.

Keep the handoff actionable and proportionate. A design pass is not permission to execute it.

## Ready-To-Use Command

Write a command in the user's language containing:

```text
Use the attached Design Pass as the source of truth.

Goal: ...
Boundaries: ...
Read first: ...
Implement: ...
Do not: ...
Verify: ...
Stop and ask if: ...
```

Adapt the wording to the task. When readiness is `conditional` or `no`, the command must request only the named inspection, confirmation, or blocker resolution—not full implementation.

## Readiness

Use:

- `yes` when the target is coherent, critical decisions are confirmed, affected surfaces are sufficiently understood, checks are concrete, and the handoff is actionable;
- `conditional` when named bounded inspections, confirmations, or assumptions must be resolved before implementation;
- `no` when evidence is insufficient, critical decisions conflict, the target is unclear, or responsible design would require inventing important choices.

For file-bound tasks, use `conditional` when uninspected current files could change the design itself. A `yes` status is still possible when remaining inspection is purely mechanical and cannot alter the confirmed design.

Before finishing, check that:

- requirements and guardrails were derived before the design;
- rejected and superseded choices still protect scope;
- traceability connects decisions to checks;
- critical uncertainty is not hidden;
- optional sections earn their space;
- the handoff and command match readiness;
- no implementation occurred during the design run.

## Failure Modes

Correct these failures before returning the design:

- requiring an existing preflight before starting;
- designing from general impressions without a Decision Ledger;
- treating a resolved question as automatic acceptance;
- losing rejected or superseded guardrails;
- forcing a developer-only structure onto another domain;
- treating preset views as mandatory sections;
- omitting traceability or concrete verification;
- producing the old fixed fifteen-section document regardless of task size;
- asking for full implementation when readiness is conditional or no;
- claiming readiness while critical choices remain unresolved;
- editing project files without a separate explicit implementation request.
