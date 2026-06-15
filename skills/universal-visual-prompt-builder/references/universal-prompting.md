# Universal Prompting

## Table Of Contents

1. Purpose
2. Read When
3. Core Doctrine
4. Dual-Model Baseline
5. Build Triad
6. Task Interpretation
7. Subject Binding
8. Dominant Visual Idea
9. Build Order
10. Constraint Discipline
11. Style Control
12. Spatial Logic
13. Color Binding
14. Factual Grounding
15. Refactor And Adaptation
16. Common Failure Modes
17. What This File Must Not Do

## 1. Purpose

This reference gives the portable prompting core for `universal-visual-prompt-builder`.

Use it to make prompts clear, controlled, and task-shaped. It is not a style
book, not an example gallery, and not a replacement for the workflow and
boundaries in `SKILL.md`.

## 2. Read When

Read this file for any substantive prompt build when the universal layer is not already available in the current turn.

It is especially useful when:

- the visual task has several constraints;
- the prompt must be more reliable than a loose scene description;
- the input is a direct user brief;
- an existing prompt needs refactor or adaptation;
- subject binding, spatial logic, style control, or factual grounding matters.

## 3. Core Doctrine

A strong image prompt is a controlled visual instruction set.

It should:

- define the image clearly;
- reduce ambiguity;
- protect critical constraints;
- preserve user intent;
- prevent attribute bleeding;
- match the actual deliverable type;
- stay as short as the task allows.

Prefer:

- clear subjects;
- clear roles;
- clear spatial logic;
- clear hierarchy;
- explicit preservation rules when editing;
- operational wording over decorative wording.

Avoid:

- empty hype;
- vague intensifiers;
- uncontrolled style stacking;
- overloaded scenes;
- prompt keyword soup;
- decorative filler that does not change the result.

## 4. Dual-Model Baseline

Treat `GPT Image 2` and `Nano Banana 2` as one active modern baseline for
prompt construction. Use the useful prompting principles associated with both
models in every substantive build. Do not appoint either model as the default,
primary, backup, or fallback.

The shared baseline favors:

- clear natural-language instructions and complete sentences;
- structured briefs when layout, exact text, several objects, references, or
  interacting constraints need stronger control;
- exact quoted text with explicit hierarchy, placement, spacing, contrast, and
  clean zones;
- preserve-first edit instructions that state both the requested change and
  what must remain unchanged;
- explicit reference roles, priorities, targets, and non-transfer boundaries;
- iterative refinement of a useful result before an unnecessary rebuild;
- deliberate spatial reasoning for transformations, comparisons, diagrams,
  infographics, and other structure-heavy visuals;
- factual grounding requirements when real products, interfaces, events,
  locations, people, or data matter;
- an ambitious but controlled first pass rather than automatic
  oversimplification.

When the user names a target model or success depends on a model-specific
capability:

1. preserve the shared baseline;
2. rely only on confirmed capabilities of that model;
3. adapt only the model-dependent wording;
4. do not invent unsupported guarantees.

## 5. Build Triad

Before building a serious prompt, identify:

`locked_constraints`

- what must not drift;
- examples: identity, geometry, composition, layout, hierarchy, exact text, product shape, factual object identity.

`flexible_variables`

- what may vary without harming the task;
- examples: secondary background mood, micro-texture, non-critical props, crop looseness, minor atmosphere.

`success_criterion`

- what would make the result clearly successful;
- examples: headline is readable, product geometry stays exact, identity is consistent, diagram is structurally readable.

If the triad is unclear, the prompt will usually drift.

## 6. Task Interpretation

Identify what kind of visual problem this is before writing.

Common functional categories:

- scene generation;
- portrait or subject rendering;
- product visualization;
- poster, title card, thumbnail, or cover;
- slide or presentation visual;
- infographic, diagram, or UI-like visual;
- series, sequence, storyboard, or set;
- image edit;
- result refinement;
- prompt refactor;
- prompt adaptation.

If the deliverable type changes structure, layout, or polish expectations, name it explicitly in the prompt.

Examples:

- "Create a poster..."
- "Create a presentation slide..."
- "Create a vertical story visual..."
- "Create an infographic..."
- "Create a realistic UI mockup..."

## 7. Subject Binding

Bind important attributes to the correct object, person, zone, or frame.

Good binding:

- the product in the foreground has a matte black finish;
- the headline sits in the upper third;
- the right panel shows the final outcome;
- the woman on the left wears the red coat.

Weak binding:

- matte black, headline on top, right panel, red coat.

Weak binding causes:

- attribute bleeding;
- wrong role assignment;
- unstable object relationships;
- text or labels moving to the wrong zone;
- reference traits contaminating the wrong target.

Avoid pronouns when several subjects, objects, or zones matter.

## 8. Dominant Visual Idea

Most prompts should have one dominant visual idea.

Default budget:

- one primary subject or focal idea;
- two to four secondary elements if truly needed;
- all other detail as supporting context.

This does not mean every visual must be minimal. It means the prompt should not treat five priorities as equally central unless the task requires that complexity.

For a prompt set, keep one dominant visual idea per item, but do not reuse the
same dominant idea, scene skeleton, or visual mechanism across the whole set by
default.

## 9. Build Order

Default build order:

1. subject or deliverable type;
2. action, state, or task function;
3. environment, scene, structure, or layout;
4. style, medium, or rendering mode;
5. composition, camera, aspect, or zones;
6. lighting, color, material, or mood;
7. technical, text, edit, or preservation constraints.

Front-load:

- subject identity;
- key action or state;
- strongest control constraint.

Avoid opening with:

- beautiful image of;
- stunning shot of;
- masterpiece render of;
- high quality image of.

## 10. Constraint Discipline

Prefer constraints that are:

- specific;
- positive by default;
- tied to a target;
- useful for the success criterion;
- not merely decorative.

Use exclusions only for real recurring failure risks.

Strong constraints:

- keep the headline readable and separated from the background;
- preserve the product silhouette and edge geometry;
- bind the blue accent only to the right-side annotation labels;
- use clean negative space around the title block.

Weak constraints:

- very high quality;
- beautiful professional composition;
- modern style;
- no bad details.

## 11. Style Control

Style must support the task.

When combining styles:

- name the dominant base style;
- name the secondary influence;
- define which traits each layer controls;
- remove style layers that compete with the success criterion.

Do not combine conflicting styles unless the hybrid is intentional and hierarchically defined.

Style signals should be translated into concrete prompt choices, not pasted as an abstract style manifesto.

## 12. Spatial Logic

Use explicit spatial anchors when more than one object, zone, label, or panel matters.

Useful anchors:

- foreground;
- background;
- upper third;
- lower third;
- left column;
- right sidebar;
- center band;
- top-to-bottom reading path;
- side-by-side comparison;
- three clearly separated panels.

When counts or relationships matter, state them directly.

## 13. Color Binding

Bind every exact color to a named object, object part, text role, or layout
zone. Do not leave a precise color floating without a target.

Use HEX only when precision materially matters, such as brand, product,
interface, or approved design colors.

Separate:

- base object color;
- lighting temperature;
- global color grade or mood.

Do not let lighting or grading silently replace an exact base color.

For a gradient, define the colors, direction or center-edge relationship, and
the region it controls.

Example:

```text
Use exact color #0F172A on the product body only. Preserve this base color
under the scene lighting. Use a background gradient from #111827 at the top to
#1F2937 at the bottom.
```

Do not invent exact brand colors when they are not supplied or confirmed.

## 14. Factual Grounding

For fact-sensitive visuals, keep the prompt close to externally confirmed details.

Do not invent:

- real product details;
- real interface structure;
- real person likeness;
- event-specific visual facts;
- location-specific features;
- exact brand marks;
- data in diagrams or infographics.

If factual grounding is missing and materially affects the visual, ask or stop.

## 15. Refactor And Adaptation

When given an existing prompt, do not rebuild from scratch by default.

First identify:

- what works;
- what must be preserved;
- what is weak;
- what the new success criterion is;
- whether the issue is wording, structure, layout, preservation, portability, or use-case fit.

Good refactor:

- preserves the original intent;
- removes filler;
- improves binding;
- clarifies layout;
- strengthens preservation;
- controls style collisions;
- adapts only what materially changes the result.

For adaptation, preserve the portable core and change only what the new format, model, style, ratio, or task requires.

## 16. Common Failure Modes

Vague subject:

- response: define subject, action, and main control constraint early.

Attribute bleeding:

- response: strengthen subject binding and reduce ambiguous pronouns.

Overloaded composition:

- response: reduce primary elements and restore one dominant idea.

Style collision:

- response: choose a dominant style and limit secondary influence.

Weak layout control:

- response: use zones, hierarchy, text placement, and negative space.

Weak edit control:

- response: separate edit target, preservation rules, and reference contracts.

Prompt bloat:

- response: remove decorative adjectives and repeated synonyms that do not control the result.

## 17. What This File Must Not Do

This file must not:

- replace the workflow or boundaries in `SKILL.md`;
- decide repository-specific routing;
- override exact user inputs;
- turn every prompt into a long structured brief;
- force camera, realism, layout, or ratio language when not useful;
- provide a fixed house style;
- replace task-specific child references.
