---
name: nearest-clarity
description: >-
  Use when continued work must advance through bounded iterations because the
  full route cannot yet be honestly planned: the user does not know what to do
  next among several viable directions, important inputs will emerge during
  execution, the current plan may be stale, or the nearest testable segment
  must be chosen without pretending the whole path is known. Do not use merely
  because a task is complex, strategic, risky, or multi-step, for ordinary
  prioritization by clear criteria, or when the route and done condition are
  already clear. Use standalone `zoom-out` for a one-time reframing,
  recommendation, or plan that can be completed in one pass. During iterative
  work, keep `nearest-clarity` as the parent and use `zoom-out` only through
  its internal transition.
---

# Nearest Clarity

Work through uncertainty without pretending that the whole route is already known.

## Internal Zoom Out

Keep `nearest-clarity` as the owner of the iterative workflow.

Use standalone `zoom-out` when the requested result is a one-time overview,
recommendation, or plan and no continued iterative workflow is needed.

At initial activation, invoke the global `zoom-out` skill as a dependent
operation only when the user explicitly asks to reframe the problem or the
current basis is confirmed stale. A request for a next step alone does not
require `zoom-out`.

When new knowledge changes the goal, constraints, dependencies, risks, success
criteria, or problem framing:

1. Invoke the global `zoom-out` skill as a dependent operation.
2. Apply its result to the target contour, decision map, and nearest segment.
3. Continue the `nearest-clarity` workflow from the updated basis.

Do not replace the parent workflow with standalone `zoom-out`.

If `zoom-out` is unavailable, do not claim that a full Zoom out was completed.
Stop before continuing on a stale basis and report the missing dependency.

## Choose Depth

- Use light mode for moderate uncertainty: target, constraint, nearest action, expected result.
- Use working mode for ordinary complex work: target contour, decision map, nearest segment, iteration, signal, next step.
- Use deep mode for strategic, expensive, high-risk, or long-running work. Read `references/method.md` before proceeding.

Do not turn a simple task into a methodology ritual.

## Establish The Work

1. State the target contour: why the work matters, what should become true, and what must not be lost.
2. Identify current sources, inputs, constraints, and approval boundaries.
3. Sketch a preliminary decision map: likely stages, forks, dependencies, risks, checks, and decisions that are too early to make.
4. Mark distant stages as provisional. Do not present them as a committed route.
5. Select the nearest clear segment that can be planned honestly.
6. Define the result that should exist when the nearest segment is complete.

Use this precision gradient:

```text
current iteration -> concrete
nearest segment -> working plan
later stages -> preliminary decision map
far horizon -> target contour
```

## Run An Iteration

Before acting:

1. Name the focus.
2. Name the evidence or input being used.
3. Name the expected signal: what should become clearer after the action.
4. Confirm that the action is inside current permissions and approval boundaries.

After acting:

1. State what was done.
2. Identify the actual signal.
3. Separate fact, observation, hypothesis, decision, risk, noise, and verified result.
4. State what remains unknown.
5. Choose the next transition.
6. Record only durable state when persistence is needed.

Keep user-facing updates concise. Do not expose hidden reasoning or create a long methodology report unless the user requests one.

## Choose The Transition

- If the signal does not change a decision, constraint, risk, order, or success criterion, treat it as noise or a bounded observation and continue.
- If the signal changes only the order or contents of current work, update the nearest segment.
- If the signal changes the goal, constraints, dependencies, risks, success criteria, or problem framing, use the global `zoom-out` skill before continuing.
- If the basis did not change, continue the nearest segment without a ritual review or another `zoom-out`.
- After the dependent `zoom-out`, update the affected working elements and continue under `nearest-clarity`.
- If the nearest segment produced its intended result, close it and select the next segment.
- If several iterations produce no useful signal, narrow the task or use `zoom-out`.

A Zoom out is complete only when it changes or confirms a concrete element of the work and makes the next step clearer.

## Handle Hypotheses

Treat a hypothesis as a testable assumption, not a decision or fact.

Use:

```text
We assume...
Because...
This matters because...
We can test it through...
If true, next...
If false, change...
```

Do not turn one successful case into a general rule. Use:

```text
test iteration -> observation -> hypothesis -> verification -> rule
```

## Respect Risk And Consent

Use the project's existing Gates and checkpoints.

Before risky or consequential actions that change documents, plans, money, public communication, project direction, obligations, or irreversible state:

1. Show the proposed action.
2. Explain the relevant consequence or risk.
3. Ask for explicit user confirmation.
4. Wait for a new user reply before executing.

Do not add an extra checkpoint for a small reversible action already directly requested by the user.

Use a test iteration only when analysis is insufficient, a small real-world probe is cheaper than a large wrong plan, and the user explicitly approves it.

## Integrate With TODO

The method controls movement through uncertainty. The project task system stores only durable state.

Using `TODO.md` as an information source does not make `manage-project-tasks`
the parent workflow. When the task is to choose a direction under genuine
uncertainty, keep `nearest-clarity` as the parent. Invoke
`manage-project-tasks` only if the resulting durable task state must be
persisted or reconstructed.

When work must survive the current session:

- use `Goal` for the target contour;
- use `Current Action` for the current iteration;
- keep `Items` limited to current and remaining work;
- use `Progress` for at most 1-3 meaningful results or signals;
- add `Constraints`, `Risks`, `Open Questions`, or `Decisions` only when needed for continuation;
- use `Proof` for available evidence;
- use `Next` for the next useful action.

Do not turn `TODO.md` into a reasoning transcript, signal journal, hypothesis dump, detailed decision map, or distant plan.

Knowledge labels do not replace the task statuses defined by the project.

## Keep Working State Minimal

Do not create signal logs, hypothesis lists, decision maps, state files,
progress files, or other working documents by default.

Create a separate artifact only when the work genuinely requires durable
structure outside the current task state or the user explicitly requests it.

## Finish A Pass

A good pass produces:

- one concrete result;
- an expected signal;
- an actual signal;
- an honest knowledge status;
- an updated nearest segment or decision map when needed;
- a clear next step;
- less uncertainty than before.

Use the final check:

```text
Is it now easier to choose the next correct step?
```

For detailed definitions, transition logic, failure modes, checklists, and examples, read `references/method.md`.
