---
name: nearest-clarity
description: >-
  Use when continued work must advance through bounded iterations because
  decision-relevant information will emerge only during execution and the full
  route cannot yet be planned honestly. Trigger when several viable directions
  remain, the next segment depends on findings from current work, important
  constraints or inputs will appear during execution, or new evidence may
  invalidate the current basis. Keep a stable target contour, mark later stages
  as provisional, choose the nearest segment whose purpose and completion result
  can be defined now, and update only the affected layer after new evidence. Do
  not use merely because work is complex, strategic, risky, long-running, or
  multi-step; for ordinary prioritization with clear criteria; for a one-pass
  recommendation or reframing; or when the route and done condition are already
  clear.
---

# Nearest Clarity

Advance through genuine uncertainty without presenting the whole route as known.

## Establish The Navigation Frame

Always establish these layers before selecting the current action:

1. **Target contour**: why the work matters, what should become true, and what must not be lost.
2. **Nearest segment**: the bounded part of the route that can be planned honestly now.
3. **Segment completion result**: the result that closes the nearest segment.
4. **Current action**: the first concrete move inside the nearest segment.
5. **Provisional next segments or forks**: likely later work, dependencies, checks, or decisions that are still too early to commit.
6. **Far horizon**: the distant outcome or direction, without invented detail.
7. **Route-changing knowledge**: what new evidence could change the segment, order, constraints, or basis.

Use this precision gradient:

```text
current action -> concrete
nearest segment -> bounded working plan
next segments -> provisional route
far horizon -> target contour
```

Do not collapse the nearest segment into a renamed next action. A nearest segment has a purpose, a bounded body of work, a completion result, and a relationship to the provisional route. The current action is only its first move.

## Define The Nearest Segment

For the nearest segment, establish:

- why this segment is the right one to open now;
- what work belongs inside it;
- what must remain outside it for now;
- what result closes it;
- what should become clearer if the segment is exploratory;
- which provisional segment, fork, or decision it may open next.

Mark later stages honestly as provisional. Do not turn a plausible sequence into a committed route.

## Choose The Iteration Type

Use an execution iteration when the route is already clear:

```text
action -> output -> validation
```

Use an exploratory iteration when the action is meant to reduce uncertainty:

```text
action -> output -> new knowledge -> decision change
```

For an execution iteration, do not invent an expected signal. Define the output and validation instead.

For an exploratory iteration, distinguish:

- the output created, inspected, or changed;
- the knowledge expected from that output;
- the decision that the knowledge could change.

## Read The Result

After an iteration, separate:

- **output**: what was created, checked, or changed;
- **knowledge**: what the iteration actually revealed;
- **knowledge status**: fact, observation, hypothesis, risk, unknown, or verified result;
- **decision**: what changes in the work because of that knowledge.

Do not treat a decision as evidence. Do not turn one successful case into a rule. Use:

```text
test -> observation -> hypothesis -> verification -> rule
```

Keep internal classification out of the user-facing answer unless it helps the user judge the result or choose a direction.

## Update The Route

- If new knowledge does not change a decision, constraint, risk, order, or completion result, continue the nearest segment.
- If it changes only the contents or order of current work, update the nearest segment.
- If it changes the goal, constraints, dependencies, risks, completion criteria, or problem framing, rebuild the basis locally before continuing.
- If the nearest segment produced its completion result, close it and open the next honest segment.
- If repeated exploratory iterations do not reduce decision-relevant uncertainty, narrow the question or rebuild the basis.

To rebuild the basis locally, answer:

1. What changed?
2. Which previous assumption no longer holds?
3. Which goal, constraint, dependency, risk, or completion criterion is affected?
4. What remains valid?
5. Which provisional route elements must change?
6. What is now the nearest honestly plannable segment?

Do not invoke another skill for this transition.

## Answer Direction Questions

When the user asks what comes next, where to move, what stage opens now, or an equivalent direction question, always show:

```text
Target contour
Nearest segment and its completion result
First current action
Provisional next segments or forks
Far horizon
What could change the route
```

Show the navigation frame again after closing a segment, materially changing the route, or resuming the work. During ordinary intermediate updates, do not repeat an unchanged frame.

Keep the answer concise, but do not achieve brevity by removing navigation layers or reducing the segment to one action.

## Boundaries

- Do not attempt to enter or invoke Codex Plan mode. If the user already selected it, apply this method inside the active mode.
- Do not create signal logs, hypothesis lists, decision maps, state files, progress files, or other working artifacts by default.
- Create a separate artifact only when the work genuinely requires durable structure or the user explicitly requests it.
- Do not expose hidden reasoning or turn the method into a ceremonial report.

## Finish A Pass

A good pass produces:

- a concrete output or verified result;
- honest knowledge status where uncertainty remains;
- an updated nearest segment or locally rebuilt basis when needed;
- a clear first current action;
- a provisional view of what follows;
- less decision-relevant uncertainty than before.

Use the final check:

```text
Is the nearest segment clear?
Is its completion result defined?
Is its place in the provisional route visible?
Are later stages still marked as provisional rather than promised?
```

Read `references/method.md` when detailed definitions, transition logic, failure modes, or worked examples are needed.
