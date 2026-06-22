# Iterative Cleanup

Large document cleanup must move through bounded passes. Do not pretend the whole route is already known.

## Precision Gradient

Use this gradient:

```text
current pass -> concrete
nearest segment -> working plan
later cleanup -> provisional
far horizon -> target contour
```

## First Pass For Folders

For a folder or broad contour:

1. Make a shallow inventory.
2. Identify likely clusters and duplicates.
3. Identify live-area risk.
4. Map candidate source roles.
5. Propose the nearest safe cleanup segment.
6. Stop before writing unless the user explicitly approves a small segment.

Output:

```text
short sprawl map + cleanup plan + next safe action
```

## Run One Segment

Before acting, state:

- focus;
- files included;
- expected signal;
- write/move boundary.

After acting or dry-running, state:

- what became clearer;
- what remains uncertain;
- whether the next segment changed;
- what should happen next.

## Stop Or Reframe

Stop and ask when:

- the output document role is unclear;
- source ownership conflicts;
- a live contour is detected;
- a candidate cannot be validated;
- several passes produce no clearer next step;
- the requested action would turn cleanup into system redesign.

## Small Tasks

One pass is acceptable for one short low-risk file with a clear function and no source-role conflict.

Do not add extra methodology ceremony to simple work.
