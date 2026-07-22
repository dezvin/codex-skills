---
name: grill-me
description: Conduct a deliberate one-question-at-a-time stress test of a plan, idea, or decision until no material user-owned decision remains unresolved. Use only when the user explicitly invokes $grill-me or directly asks to be grilled, interviewed, challenged, or questioned before proceeding. Do not use for ordinary feedback, fact gathering, exhaustive questionnaires, implementation, or decisions that can be handled through inspection, a reversible default, or a practical test.
---

# Grill Me

Clarify the decisions that only the user can make before the next stage. Do not try to eliminate every uncertainty or ask about every aspect of the work.

## Core Contract

- Ask one material question at a time and wait for the answer.
- Preserve explicit decisions already made in the current conversation. Do not ask them again.
- Derive decision branches from the actual work instead of following a domain menu or checklist.
- Give a brief recommended answer. Explain consequences or alternatives only when they are not obvious.
- Write questions, orientation, and the final result in the user's language.
- Inspect named or clearly relevant sources read-only when they can answer a factual question. Keep inspection narrow and do not edit files.
- Choose reasonable reversible defaults without asking, and record them for the final result.
- Stop when no material user-owned decision remains unresolved.
- Recommend a next stage when useful, but do not invoke another skill, activate a Codex mode, design, plan, or implement the work.

## Operating Loop

### 1. Establish The Current Decision

From the request and current conversation, identify:

- the plan, idea, decision, or proposed work being tested;
- the next decision or action this conversation is preparing;
- explicit user decisions already made;
- material constraints or boundaries already stated.

If the subject is too vague to derive a meaningful branch, ask one framing question. Do not start an intake survey.

Re-open an earlier answer only when new information conflicts with it, changes its meaning, or reveals ambiguity that would materially distort the next stage. State the reason briefly before asking again.

### 2. Derive A Material Branch

Do not work through predefined categories. Derive the decision map from the task.

A material branch exists when two plausible answers would lead to meaningfully different:

- outcomes or actions;
- commitments or boundaries;
- risks or costs of error;
- downstream stages.

Before asking, compare plausible answers to the candidate question. If they would not materially change what happens next, discard the question.

Choose the earliest unresolved branch with the greatest practical leverage. Do not ask a lower-level question while a higher-impact user decision still controls it.

### 3. Route The Uncertainty

Assign each material uncertainty to the correct resolver:

```text
User intent or commitment -> ask
Discoverable fact -> inspect
Reversible low-risk detail -> choose a default
Hypothesis answerable only in practice -> assign a test
Difference that does not change the work -> ignore
```

Only the first category becomes a question for the user. Do not turn missing facts, mechanical work, or testable hypotheses into preference questions.

### 4. Orient And Ask

Before every new question, show exactly one compact orientation line in the user's language. For Russian, use exactly:

```text
Решено: ... | Сейчас: ... | Остаётся: ...
```

For another language, translate these three labels without changing the one-line structure.

Keep it to one line. Do not show counters, predicted question totals, a separate start summary, or a multi-line checkpoint.

Then ask one naturally phrased question and give a concise recommendation:

```text
<one question>

I would choose: <recommendation and brief reason>.
```

Do not automatically add separate sections explaining why the question matters, every alternative, or what each choice changes. Add that context only when the user needs it to make the decision responsibly.

### 5. Update The Decision Map

After the answer:

- preserve the accepted decision;
- revise only branches affected by the answer;
- route newly exposed facts, defaults, and hypotheses correctly;
- select the next highest-leverage user-owned branch;
- finish instead of manufacturing another question when none remains.

Do not target a fixed number of questions. If the user becomes irritated, asks to stop, or says the process is too granular, stop questioning and return the compact result with remaining branches visible.

## Completion Gate

Before finishing, try to identify one unresolved user-owned branch that could:

- change the required outcome;
- materially change the boundary or commitment;
- make the current direction wrong or materially riskier;
- force the next agent or person to invent the user's intent.

If such a branch exists, ask it. If the remaining uncertainty belongs to inspection, a reversible default, or a practical test, route it there and finish.

Completion means:

> The next stage can proceed without inventing a material user decision.

It does not mean the work is technically feasible, commercially validated, researched, implemented, or verified.

## Final Result

Return a compact result only when the interview ends or the user stops it. Use only relevant sections and omit empty ones:

```markdown
## Grill Result

### Clarified decisions
- ...

### Working defaults
- ...

### To inspect or test
- ...

### Remaining user decisions
- ...

### Suitable next stage
...

### Decision clarity
User decisions are sufficient / insufficient for the next stage to proceed without inventing material user intent.
```

Recommend the suitable next stage without starting it. Do not claim readiness for implementation, technical feasibility, validation, or completion of the underlying work.

## Boundaries

- Do not use this skill for ordinary advice or feedback when the user did not explicitly request an interview.
- Do not turn it into an exhaustive questionnaire or a fixed domain flow.
- Do not create a design document, implementation plan, task system, state file, or handoff.
- Do not activate Codex planning or goal modes.
- Do not invoke `design-pass`, `zoom-out`, another skill, or implementation automatically.
- Do not make the user approve mechanical, conventional, reversible, or discoverable details.
