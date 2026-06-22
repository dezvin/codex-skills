---
name: grill-me
description: Stress-test a plan, design, or non-dev creation task by asking one high-leverage question at a time until the important decision branches are resolved. Use when the user wants to be grilled, challenge a plan, expose hidden assumptions, clarify scope, audience, desired outcome, risks, ownership, user-facing behavior, work shape, what to trust when inputs conflict, readiness before preflight/design-pass/implementation, or the smallest useful test. Do not use for exhaustive questionnaires, fixed domain menus, low-level implementation defaults, cosmetic details, ordinary feedback, or decisions that can be safely handled by reasonable defaults.
---

# Grill Me

Stress-test the user's plan without wasting their attention. The goal is not to ask about everything. The goal is to resolve the important branches that change the plan, risk, scope, behavior, ownership, outcome, or next step.

## Core Contract

- Ask one question at a time.
- Ask only high-leverage questions: the answer must change a meaningful decision.
- For each question, explain why it matters and provide your recommended answer.
- Write user-facing questions and summaries in the user's language.
- Do not ask the user to translate technical terms. Turn internal concepts into concrete situations.
- For non-dev or creation work, infer the work shape before choosing what to ask.
- Do not classify the work into a fixed domain and do not present a domain menu.
- Synthesize the important decision surfaces from the work shape, then ask about one surface at a time.
- For obvious, reversible, conventional, or low-risk details, choose a reasonable default and record it in the next summary instead of asking.
- If an answer can be found from named or clearly relevant files, inspect read-only instead of asking. Keep inspection narrow and do not broaden into repository exploration unless the question truly cannot be answered responsibly without it. Do not edit files.
- Ask the user only for decisions that change meaning, risk, ownership, or behavior. Do not make the user approve the agent's mechanical work.
- Stop or zoom out when the questions become too granular, repetitive, or visibly irritating.

## Inputs To Establish

Identify as much as the user provided:

1. The plan, design, idea, or decision being tested.
2. What should exist if the work succeeds.
3. The intended outcome or change.
4. The audience, users, implementer, or affected people.
5. Constraints, boundaries, and non-goals.
6. Why the plan is expected to work.
7. What assumptions must be true.
8. What would make the plan risky, expensive, irreversible, or hard to undo.
9. Who can make or confirm the decision.
10. Whether the next step is `preflight`, `design-pass`, implementation, research, or another conversation.

If the plan is too vague to grill, ask one framing question first.

## Work Shape Before Domain

Do not adapt by choosing a domain label. Adapt by inferring the shape of the work:

- What is being created or decided?
- Who will use it, judge it, implement it, or be affected by it?
- What should change because this exists?
- What is inside the boundary, outside the boundary, or dangerous to include now?
- Why should this approach work?
- What must be true for it to work?
- How could it fail, and what would make that failure expensive?
- Who owns the decision or has the final say?
- What is the smallest useful test, example, draft, or probe that would show progress?

These are lenses, not a checklist. Do not ask through every lens mechanically. Use them to find the next high-impact branch.

## Decision Surface Synthesis

Before asking, silently identify 1-3 decision surfaces. A decision surface is a place where the user's answer changes the result, risk, scope, ownership, readiness, or user-facing behavior.

Prioritize the surface with the highest practical leverage right now. Prefer surfaces that determine:

- the desired outcome rather than only the visible output;
- the primary audience or affected people;
- boundaries and non-goals;
- the success criterion;
- the structure of the thing being created;
- the causal logic behind why it should work;
- a critical assumption;
- a likely failure mode;
- the decision owner;
- the next step or smallest useful test;
- what must not be done.

If no surface is worth the user's attention, default, inspect, or stop.

## Question Worthiness Filter

Before asking, silently check whether the answer would change one or more of:

- purpose or success criteria;
- audience or affected people;
- scope or non-goals;
- architecture or structure;
- responsibility or ownership;
- user-facing behavior or audience fit;
- desired outcome or change;
- causal logic;
- a critical assumption;
- what to trust when inputs conflict;
- safety, risk, reversibility, or cost of error;
- readiness for `preflight`, `design-pass`, or implementation;
- the smallest useful test or next step;
- what the agent should stop doing or must not do.

If the answer would not change any of these, do not ask. Choose a default, inspect the relevant source, or ignore the detail.

## What Not To Ask

Do not stop the user for:

- timestamp format;
- minor file naming;
- cosmetic phrasing;
- obvious extension behavior;
- reversible formatting;
- default folder labels when the convention is already clear;
- which domain category the task belongs to;
- taxonomy labels that do not change the work;
- implementation details that do not change risk, behavior, or scope.

If the user explicitly asks for exhaustive low-level review, you may go deeper. Otherwise protect the user's attention.

## How To Ask

Ask in plain working situations, not internal jargon.

Prefer:

```text
If the chat says one thing and the file says another, which should win?
My recommended answer: trust the current file for current state, but a later explicit user decision can override the rule to be changed.
```

Avoid:

```text
What is the source of truth?
```

Prefer:

```text
When we say "replace the file", do you mean fully rewrite it or update only the needed parts?
My recommended answer: update only the needed parts unless you explicitly say to rewrite the whole file.
```

Avoid:

```text
What is the replacement invariant?
```

Every question should include:

1. The question.
2. Why it matters.
3. Your recommended answer.
4. What will change if the user chooses differently.

For non-dev or creation work, phrase the question through a concrete work situation:

```text
When this exists, what should be different for the people affected by it?
My recommended answer: choose one primary change and treat everything else as support.
If you choose differently: the work can cover more ground, but the success criterion becomes blurrier.
```

Then wait for the user's answer before asking the next question.

## Ask, Default, Inspect, Or Stop

For each branch, choose one action:

- Ask: when the user must decide a meaningful branch.
- Default: when the detail is low-risk, conventional, or reversible.
- Inspect: when the answer is discoverable from provided, named, or clearly relevant files.
- Stop: when the remaining questions no longer change the plan enough to justify the user's attention.

Record defaults so the user can correct them later:

```markdown
Defaults I will assume:
- <default> because <reason>
```

## Checkpoints

After 5-7 high-impact questions for non-dev, non-tech, or creation work, after 7-10 high-impact questions for technical or design-heavy work, or earlier if the user shows fatigue, confusion, irritation, or says the questions are too granular, stop the interview and summarize:

```markdown
## Grill Checkpoint

Working shape:
- What is being created:
- Who it affects:
- Desired change:
- Important boundaries:

Decisions accepted:
- ...

Defaults I will assume:
- ...

Key assumptions:
- ...

Main risks:
- ...

Still worth asking:
- ...

Not worth asking:
- ...

Smallest useful test:
- ...

Recommended next question or next step:
- ...
```

If the user reacts with "too much", "too granular", "unclear", "stop", "this is noise", or similar, do not defend the previous question. Zoom out, summarize the useful state, and continue only with high-impact questions if the user wants to continue.

## Completion

End the grilling when:

- the important decision branches are resolved;
- the remaining details can safely be defaulted;
- the plan is ready for `preflight`, `design-pass`, implementation, or deliberate rejection;
- the user asks to stop.

Finish with:

```markdown
## Grill Result

Working shape:
- What is being created:
- Who it affects:
- Desired change:
- Important boundaries:

Decisions accepted:
- ...

Defaults assumed:
- ...

Key assumptions:
- ...

Remaining high-impact questions:
- ...

Risks still visible:
- ...

Decision owner:
- ...

Smallest useful test:
- ...

Readiness:
- ready for preflight / ready for design-pass / ready for implementation / need 1-2 more questions / better not start

Recommended next step:
- ...
```

Do not turn the result into a final design doc or implementation plan unless the user explicitly asks for that separate step.
