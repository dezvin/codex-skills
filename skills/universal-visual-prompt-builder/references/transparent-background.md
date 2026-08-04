# Transparent Background

## Table Of Contents

1. Purpose
2. Background Modes
3. Surface Routing
4. Subject Boundary
5. Effects And Shadows
6. ChatGPT Images Prompt Construction
7. Editing And Preservation
8. Repair
9. Readiness

## 1. Purpose

Control true transparent-background prompts, isolated assets, transparent
multi-part compositions, placement context, and preservation of transparent
regions.

Do not use this reference for ordinary scenes with an opaque or visible
background.

## 2. Background Modes

Use one of these modes only when background behavior matters.

`opaque_scene`

- render the requested environment or visible background;
- do not add transparency constraints.

`transparent_isolated_asset`

- render one isolated subject or tightly connected object group;
- keep all unused surrounding space transparent;
- do not create a scene, surface, panel, or ground plane.

`transparent_composition`

- render several intended parts as one foreground composition;
- keep unused space and intentional gaps between parts transparent;
- do not fill the gaps with haze, glow, color, scenery, or a connecting panel.

## 3. Surface Routing

Determine the target surface when it affects capability or wording.

`chatgpt_images`

- use direct natural-language instructions;
- request a true transparent background early;
- do not put API parameters or model configuration inside the image prompt.

`api_or_named_model`

- verify current transparency support before promising the result;
- keep API parameters outside the natural-language image prompt;
- if transparency is unsupported, state the limitation instead of simulating it.

`other_or_unknown`

- keep the prompt portable;
- request transparency in natural language;
- do not guarantee technical transparency;
- ask for the target generator only when its capability materially changes
  whether the task can succeed.

Do not maintain a permanent model-support matrix in this reference. Verify
fresh capabilities from current authoritative documentation when required.

## 4. Subject Boundary

Define what belongs to the foreground artwork:

- primary subject;
- attached parts;
- requested labels or decorative elements;
- subject-owned light, glow, smoke, steam, particles, or shadows.

Anything outside that boundary remains transparent unless explicitly requested.

Do not treat a webpage, slide, presentation, packaging mockup, or placement
color as part of the image merely because it was supplied for contrast.

## 5. Effects And Shadows

Allow an effect when it belongs to the requested subject.

Keep shadows compact and attached to the subject unless the user explicitly
requests a visible surface.

Keep glow, smoke, steam, particles, and similar effects local. They must not
expand into a surrounding atmospheric field or become a hidden background.

Do not prohibit a subject-owned effect merely because the output is
transparent.

## 6. ChatGPT Images Prompt Construction

For an isolated asset, begin with a task-specific form of:

```text
Create [subject] as isolated foreground artwork on a true transparent
background.
```

Add only the controls the task needs:

```text
Render only [subject boundary]. Keep all unused surrounding space transparent.
```

For several parts:

```text
Keep all unused space and intentional gaps between the separate parts
transparent.
```

For placement context:

```text
The image will later be placed on [placement context]. Use this information
only to ensure sufficient foreground contrast; do not render that color,
surface, or any other background.
```

For recurring background failures, use targeted exclusions:

```text
Do not add a visible backdrop, scene, wall, floor, horizon, rectangular panel,
checkerboard pattern, vignette, or atmospheric background field.
```

Do not append the entire exclusion list when the task does not need it.

Do not put these inside a ChatGPT Images prompt:

```text
alpha = 0
background="transparent"
output_format="png"
use a transparency-compatible model
```

## 7. Editing And Preservation

When editing an existing transparent image:

- state what changes;
- preserve all existing transparent regions unless the edit requires otherwise;
- do not fill transparent gaps with inferred scenery or background color;
- preserve the subject silhouette and edge treatment when they are locked;
- localize new effects to the edited subject or region.

## 8. Repair

If the result contains a colored panel, scene, floor, horizon, checkerboard,
or filled gaps:

1. preserve the useful subject;
2. remove the visible background rather than rebuilding unrelated details;
3. restate the subject boundary;
4. require unused space and intended gaps to remain transparent;
5. separate placement context from rendered content.

If glow, haze, or shadow forms a background:

1. keep only the portion that belongs to the subject;
2. localize it to the subject edge or immediate footprint;
3. remove the surrounding field or ground plane.

## 9. Readiness

Before returning the prompt, confirm:

- the target surface is known when capability support matters;
- the correct background mode is selected;
- the subject boundary is explicit;
- unused space and intended gaps remain transparent;
- placement context is not rendered;
- shadows and effects do not form a hidden background;
- no API parameters appear inside a ChatGPT Images prompt;
- unsupported capability is not presented as guaranteed.
