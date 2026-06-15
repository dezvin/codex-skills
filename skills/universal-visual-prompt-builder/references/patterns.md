# Patterns

## Table Of Contents

1. Purpose
2. Read When
3. Guardrails
4. Motifs
5. Prompt Patterns
6. Repair Patterns
7. What This File Must Not Do

## 1. Purpose

This is a low-priority support reference for prompt checks, small control patterns, and repair wording.

It stores control logic, not a visual style canon and not a bank of production approaches.

## 2. Read When

Read this file only after:

- task type is clear;
- success criterion is clear;
- main prompt architecture is selected;
- a small control pattern or repair wording would materially help.

Use at most one pattern by default. Never use this file to choose the production approach.

## 3. Guardrails

Patterns cannot:

- override a valid brief;
- choose architecture;
- replace task-specific references;
- become default style;
- freeze creative range;
- turn every output into a template.

If a pattern only says "this looked good", do not use it.

## 4. Motifs

`MTF-001 Subject-first opening`

Use when prompt needs a strong anchor.

```text
Start with the main subject and its defining action or state before adding environment, style, and secondary detail.
```

`MTF-002 One dominant visual idea`

Use when the scene risks overload.

```text
Use one primary subject or one dominant visual idea, then demote supporting detail.
```

`MTF-003 Bound attribute ownership`

Use when several people, objects, or zones appear.

```text
Assign each important attribute to a named target: the left panel, the foreground product, the upper headline, Character A.
```

`MTF-004 Clean text zone`

Use when exact text matters.

```text
Reserve a clean, low-detail zone behind the text with high contrast and generous margins.
```

`MTF-005 Style direction without mechanism lock`

Use when a style direction risks becoming a repeated object bundle, scene habit, or production recipe.

```text
Apply the selected style direction through task-derived hierarchy, structure, constraints, and medium choices. Do not treat material/color logic, object set, scene type, palette pair, layout skeleton, surface treatment, or decorative motif as required identity unless it is task-derived.
```

## 5. Prompt Patterns

`PAT-001 Natural-language visual`

```text
Create [deliverable type if useful] showing [subject] [action/state] in [scene/structure]. Emphasize [dominant visual idea]. Use [selected style grammar] with [composition/framing]. Preserve [critical constraints].
```

`PAT-002 Structured poster`

```text
Create a poster with [headline] as the dominant text in [zone], [hero visual] as the main image, and [support element] in [zone]. Keep strong hierarchy, clean margins, high contrast text, and low-detail background behind typography.
```

`PAT-003 Slide cover`

```text
Create a clean presentation slide cover with a clear title zone, one restrained supporting subtitle, and one dominant visual structure. Use presentation-friendly spacing, stable hierarchy, and generous negative space.
```

`PAT-004 Infographic`

```text
Create a structured infographic with [number] clearly separated sections, short readable labels, consistent spacing, and a clear [top-to-bottom / left-to-right] reading path.
```

`PAT-005 Controlled edit`

```text
Replace ONLY [target] with [new state]. Preserve [identity / geometry / composition / lighting / layout]. Keep all unrelated areas unchanged.
```

`PAT-006 Multi-reference assignment`

```text
Use [reference A] for [target + control dimension] only. Use [reference B] for [target + control dimension] only. Do not transfer [excluded traits] between references.
```

`PAT-007 Series frame`

```text
Preserve task-derived style core, readability, hierarchy, and sequence logic.
For this item, use [current goal], [archetype], and vary [dimensions] so it does
not repeat adjacent scene grammar, visual mechanism, text-image formula, or
rendering recipe.
```

## 6. Repair Patterns

`RPR-001 Identity drift`

```text
Preserve the subject's recognizable likeness, facial structure, and proportions. Reduce unrelated style transfer. Improve only [defect].
```

`RPR-002 Text readability`

```text
Keep the layout and concept. Improve text legibility only: simplify the background behind the text, increase contrast, preserve exact wording, and keep generous spacing.
```

`RPR-003 Composition drift`

```text
Keep the original composition, framing, and camera angle. Change only [target change].
```

`RPR-004 Default mechanism drift`

```text
Remove the recurring production bundle or rendering recipe that is not
task-derived. Use [task-derived visual mechanism] as the main meaning carrier
while preserving only the relevant style principles needed for this task.
```

`RPR-005 Series monotony`

```text
Preserve declared brand, palette, material, lighting, rendering, typography,
and other visual-identity anchors together with readability, hierarchy, and
sequence logic. Change scene class, focal subject, composition skeleton,
camera distance, visual mechanism, text-image relationship, scale, density,
or other unlocked execution details.
```

## 7. What This File Must Not Do

This file must not:

- become a prompt template library that replaces reasoning;
- choose a production approach from a bank of motifs;
- define a project-specific visual system;
- override the task or reference contract;
- override exact user inputs;
- encourage repeated visual mechanisms or production bundles;
- hide major missing inputs behind a pattern.
