# Series And Sets

## Table Of Contents

1. Purpose
2. Read When
3. Core Distinction
4. Series Continuity Rules
5. Variable Dimensions
6. Per-Frame Or Per-Card Archetype
7. Sequence Prompt Rules
8. Set Item Rules
9. Adjacent Context
10. Controlled Variants
11. Anti-Repetition Check
12. Failure Modes
13. What This File Must Not Do

## 1. Purpose

This reference protects visual continuity without accidentally repeating the
same scene, layout, object, visual mechanism, text-image formula, or production
recipe across a series.

## 2. Read When

Read this file for:

- visual sequences;
- multi-frame prompt sets;
- card-like prompt sets;
- storyboard;
- campaign visuals;
- controlled visual sets;
- any task where "same style" could be confused with "same scene".

## 3. Core Distinction

Continuity is not scene repetition.

Continuity should preserve:

- task-derived style core or active visual identity;
- explicitly declared brand, palette, material, lighting, surface, rendering,
  and typography anchors;
- reading discipline and hierarchy;
- text legibility and typographic function when relevant;
- sequence attention logic;
- role clarity for each frame/card;
- task-fit and success criterion.

Continuity should not automatically preserve:

- same workspace;
- same hero object;
- same composition skeleton;
- same camera angle or distance;
- same text placement;
- same visual mechanism;
- same storytelling mechanism;
- incidental execution details that were never declared or shown to be part of
  the shared visual identity.

## 4. Series Continuity Rules

Continuity must preserve user-declared or reference-established anchors,
including brand, palette, materiality, lighting, surface treatment, rendering
style, and typography when they define the set.

Continuity may also preserve:

- hierarchy discipline;
- typographic tone;
- density level;
- selected style grammar;
- output polish;
- task-derived style core;
- reading path;
- sequence logic.

Do not freeze these unless explicitly requested, reference-established, or
task-derived:

- fixed workspace;
- repeated layout template;
- repeated hero object;
- repeated visual mechanism;
- fixed camera;
- fixed scene class;
- repeated rendering default.

Vary a shared visual anchor only when it is not locked and the current item's
role clearly benefits from the change.

## 5. Variable Dimensions

Useful axes of variation:

- scene class;
- environment type;
- focal subject;
- main object;
- composition family;
- camera angle;
- camera distance;
- text placement;
- visual mechanism;
- human presence;
- abstraction level;
- object scale;
- background density;
- process stage;
- relationship between text and image.

Adjacent frames or cards should differ on at least two or three axes unless template repetition is explicitly requested.

## 6. Per-Frame Or Per-Card Archetype

Each frame/card should have its own visual role.

Possible role examples:

- hero;
- explainer;
- process;
- detail;
- result;
- contrast;
- threshold;
- absence;
- object-led frame;
- scene-led frame;
- interface-led frame;
- diagram-led frame.

Do not treat the examples as a menu. Keep each item's goal and visual archetype
distinct.

## 7. Sequence Prompt Rules

For each sequence frame, preserve:

- exact requested in-image text;
- requested format;
- set continuity rules;
- current item goal;
- current item archetype;
- variable dimensions for this frame;
- adjacent frame context when provided;
- success condition.

Do not:

- rewrite exact text;
- generate story/content strategy;
- repeat the same layout skeleton across all frames by default;
- infer missing adjacent-frame differences from memory;
- ignore frame-level distinction.

If distinction is insufficient, stop and ask for the missing item-level goal
or visual distinction in the user's language.

## 8. Set Item Rules

For each card-like or set item prompt, preserve:

- exact requested in-image text;
- requested format or ratio;
- item-specific goal;
- item archetype;
- variable dimensions for this item;
- adjacent item context;
- success condition.

Do not:

- edit exact text;
- invent missing order or sequence logic;
- write captions;
- make every item the same text-left / visual-right template unless requested.

If distinction is insufficient, stop and ask for the missing item-level goal
or visual distinction in the user's language.

## 9. Adjacent Context

Use adjacent context to avoid repeated scene grammar and repeated production approach.

Check whether current frame/card repeats the previous or next one in:

- workspace type;
- hero object;
- composition skeleton;
- camera angle;
- camera distance;
- text placement;
- visual mechanism;
- depth behavior;
- lighting behavior.

If repetition is intended, make the template logic explicit. If not, vary the frame/card while preserving style.

## 10. Controlled Variants

Controlled variants are not stories or carousels.

Use when:

- one semantic focus remains;
- each variant changes only allowed dimensions;
- there is no story progression, card sequence, or swipe logic.

Output may include:

- `variant_id`;
- `distinction_note`;
- `image_prompt`.

If variants form a sequence, require item-level goals and use the sequence
rules above. If the user is asking to invent the surrounding content strategy
rather than image prompts, explain that the request is outside this skill.

## 11. Anti-Repetition Check

Before returning a series prompt, check:

- what stays invariant;
- what changes in this specific frame/card;
- whether current visual role is distinct;
- whether the frame/card differs by visual archetype or variable dimensions, not only by topic;
- whether declared brand, palette, material, lighting, rendering, and
  typography anchors remain stable;
- whether series continuity rules have accidentally become a scene skeleton;
- whether text placement is repeated for a reason;
- whether the visual mechanism is repeated for a reason;
- whether style continuity has frozen a production bundle or execution default.

If template repetition is not explicitly allowed, do not repeat the same scene skeleton, rendering default, or production-style recipe by default.

## 12. Failure Modes

Scene monotony:

- vary scene class, focal subject, camera distance, and visual mechanism.

Layout numbness:

- preserve typographic quality but vary zone structure and text-image relationship.

Production bundle repetition:

- keep style continuity but change the object, structure, or action carrying meaning.

Execution sameness:

- preserve declared visual-identity anchors, task-derived style core,
  readability, and sequence logic; vary scene, composition, focal subject,
  camera, text-image relationship, scale, density, or other unlocked execution
  details.

False consistency:

- distinguish legitimate shared visual anchors from repeated workspace,
  repeated panels, repeated hero objects, repeated layouts, or an incidental
  rendering recipe.

Under-specified frame:

- stop rather than invent frame-level differences.

## 13. What This File Must Not Do

This file must not:

- invent story, carousel, campaign, or publication content;
- rewrite exact text;
- choose sequence order without user-provided goals;
- turn variants into a hidden sequence;
- enforce a repeated template unless the input asks for it;
- override exact user constraints or reference contracts.
