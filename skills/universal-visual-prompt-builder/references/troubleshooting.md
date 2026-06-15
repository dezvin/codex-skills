# Troubleshooting

## Table Of Contents

1. Purpose
2. Read When
3. Doctrine
4. Local Vs Structural Failure
5. Repair Ladder
6. Dominant Failure Mode
7. When To Refine
8. When To Rebuild
9. Multi-Pass Rescue
10. Common Failure Modes
11. Default Drift
12. Repair Questions
13. What This File Must Not Do

## 1. Purpose

This reference helps diagnose weak, drifting, unstable, or partially correct image results and choose the smallest useful repair.

## 2. Read When

Read this file when:

- the user reports a weak result;
- a refinement request arrives;
- a failure mode is named;
- the prompt fails readiness checks;
- default drift remains after initial assembly;
- a repair pass is needed.

Do not use troubleshooting preemptively for every first prompt.

## 3. Doctrine

When an output is weak, do not immediately regenerate everything.

First determine:

1. what already works;
2. what specifically failed;
3. whether the failure is local or structural;
4. what smallest correction can fix the dominant problem.

Good repair preserves working parts.

## 4. Local Vs Structural Failure

Local failure:

- limited defect in an otherwise useful result;
- examples: one hand, one label, text contrast, small object, background clutter.

Structural failure:

- whole image logic is wrong;
- examples: wrong subject dominance, broken layout, wrong reading path, identity collapse, competing styles, no stable focal logic.

Use local correction for local failure.

Use rebuild or stronger architecture only for structural failure.

## 5. Repair Ladder

Step 1: tighten one weak constraint.

Step 2: add one preservation rule.

Step 3: split into passes if one prompt is overloaded.

Step 4: rebuild with stronger architecture only if the concept or structure is wrong.

Do not jump to maximum structure too early.

## 6. Dominant Failure Mode

Fix the defect that most harms usefulness.

Examples:

- unreadable headline matters more than color mood in a poster;
- lost likeness matters more than background detail in a portrait;
- wrong product geometry matters more than cinematic atmosphere;
- broken reading path matters more than texture richness in an infographic.

## 7. When To Refine

Use refinement when:

- result is close;
- main structure works;
- concept is correct;
- only visible defects remain.

Refinement should say:

- what to preserve;
- what to improve;
- what not to redesign.

## 8. When To Rebuild

Rebuild when:

- concept is wrong;
- layout architecture is wrong;
- main subject is wrong;
- no stable focal logic exists;
- style goals conflict structurally;
- preservation failed at the whole-image level;
- prompt architecture is too weak for the task.

Rebuilding is justified only when local correction would leave the core unstable.

## 9. Multi-Pass Rescue

Use multi-pass strategy when one task mixes several difficult demands:

- identity + tiny text + strict branding;
- dense infographic + exact labels;
- product geometry + environment swap;
- UI-like layout + readable text;
- character consistency across a series.

Typical order:

1. structure;
2. preservation;
3. readability;
4. polish.

## 10. Common Failure Modes

Identity drift:

- strengthen likeness and separate identity from style/pose references.

Composition drift:

- preserve framing, camera angle, and zone structure.

Text unreadable:

- simplify background, improve contrast, increase negative space, strengthen exact text.

Layout collapse:

- use zone-based or panel-based structure.

Overloaded scene:

- reduce primary elements and restore one focal idea.

Style collision:

- choose a dominant style and demote secondary influence.

Weak product fidelity:

- protect geometry, silhouette, material, and scale.

Reference collision:

- define reference contracts and non-transfer boundaries.

Over-editing:

- use selective change wording and protect unchanged regions.

Set monotony:

- preserve declared brand, palette, material, lighting, rendering, typography,
  and other visual-identity anchors together with readability, hierarchy, and
  sequence logic;
- vary scene class, focal object, composition skeleton, camera distance, visual
  mechanism, and text-image formula.

## 11. Default Drift

Default drift appears when a prompt falls into a familiar production bundle not derived from the task.

Identify the bundle only from the explicit user input, provided references, existing prompt, edit target, or repeated pattern inside the current task. Do not import examples from another client or another visual system.

The bundle may be a repeated:

- environment class;
- object set;
- material set;
- color pairing;
- lighting mood;
- layout skeleton;
- composition family;
- visual mechanism;
- text-image formula;
- decorative motif;
- rendering default treated as identity.

Treat default drift as present only when:

- the prompt relies on a recurring style, object, scene, or production bundle;
- that bundle is not derived from the task's visual mechanism, structure
  decision, attention/composition logic, hard constraints, reference contract,
  or item-specific distinctions;
- removing that bundle would not damage the visual decision.

Do not treat an explicitly declared or reference-established series anchor as
drift merely because it repeats. Treat palette, materiality, light, surface
treatment, atmosphere, or production style as drift only when it is neither
locked nor task-derived and functions as an incidental repeated recipe.

Do not count it as drift when the familiar mechanism truly carries meaning. A document can be valid for a document-checking task; a card can be valid for a checking-card task; an interface layer can be valid for an interface task. The prompt must make that role explicit.

Repair:

1. preserve visual goal, exact text, hard constraints, references, and success criterion;
2. return to the actual visual decision;
3. choose a visual mechanism derived from the task;
4. change scale, composition family, abstraction, human trace, absence, threshold, comparison, process state, or object detail;
5. reduce decorative style and non-task-derived execution details.

If the drift cannot be repaired honestly after one pass, explain which visual
decision remains unresolved and ask the user for that decision in ordinary
language.

## 12. Repair Questions

Ask internally:

1. What is the single most damaging defect?
2. Is the failure local or structural?
3. What already works?
4. What must be preserved?
5. Which constraint is too weak?
6. Would one repair pass solve it?
7. Does the prompt need tightening, restructuring, simplification, or a hard stop?
8. In a series, am I preserving style continuity or accidentally preserving scene grammar?

## 13. What This File Must Not Do

This file must not:

- create ritual complexity;
- repair five things at once by default;
- rebuild close results unnecessarily;
- use troubleshooting as a first-pass prompt method;
- override exact task constraints.
