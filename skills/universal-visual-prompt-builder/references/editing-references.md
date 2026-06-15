# Editing And References

## Table Of Contents

1. Purpose
2. Read When
3. Editing Doctrine
4. Edit Routing
5. Preservation Priorities
6. Reference Contract
7. Identity References
8. Multi-Reference Workflows
9. Example-Based Transformation
10. Annotated Regions
11. Text Replacement
12. Refinement
13. Ambiguity Management
14. Failure Modes
15. Prompt Patterns
16. What This File Must Not Do

## 1. Purpose

This reference controls image edits, reference-based prompts, identity
preservation, multi-reference synthesis, example-based transformations,
annotated-region edits, and close-result refinement.

## 2. Read When

Read this file when:

- a base image exists;
- the task is edit, replace, remove, add, preserve, refine, or transform;
- reference images are provided;
- multiple references could contaminate one another;
- recognizable identity is required;
- typography, layout, composition, geometry, lighting, or identity must be preserved.

## 3. Editing Doctrine

Treat editing as controlled operation, not blind regeneration.

Always separate:

1. what changes;
2. what stays unchanged;
3. what has highest preservation priority.

Use the build triad:

- locked constraints;
- flexible variables;
- success criterion.

Classify the allowed edit scope when it affects preservation:

- `local` - one named region, object, or attribute may change;
- `bounded` - several named elements or one coherent layer may change;
- `broad redesign` - composition, environment, style, or multiple structural
  layers may change.

State the allowed scope in the prompt when over-editing is a material risk. If
the requested scope is unclear and different interpretations would change
preservation, ask before building.

If the base result is already close, prefer surgical refinement over full reconstruction.

## 4. Edit Routing

Region-aware surgical edit:

- one object, region, or attribute changes;
- everything else stays stable.

Single-reference edit:

- one image is the base source;
- identity, composition, or structure must be preserved.

Multi-reference identity synthesis:

- several images represent the same person or object;
- one stable identity/product representation is needed.

Mixed multi-reference workflow:

- references control different dimensions, such as identity, style, pose, outfit, lighting, composition, layout, material, or typography.

Example-based transformation:

- one image pair shows a transformation logic;
- that logic must apply to another base.

Refinement workflow:

- current result is close;
- a visible defect must be corrected without redesigning the concept.

## 5. Preservation Priorities

Common preservation targets:

- identity;
- facial structure;
- body proportions;
- pose;
- product geometry;
- logo silhouette;
- composition;
- camera angle;
- perspective;
- scene layout;
- lighting direction;
- shadow logic;
- typography hierarchy;
- text placement;
- material finish.

State highest-priority preservation first.

Priority examples:

- portrait edit: identity usually outranks background detail;
- product edit: geometry usually outranks atmosphere;
- poster localization: layout and hierarchy usually outrank decorative texture.

## 6. Reference Contract

For each materially important reference, define:

- `target` — which subject, object, region, or layout zone it controls;
- `control_dimension` — identity, geometry, pose, composition, lighting, material, typography, layout, color, etc.;
- `priority` — base, primary, support, or optional;
- `non_transfer_boundary` — what must not be borrowed.

Use one dominant control assignment per reference by default.

If one reference affects several dimensions, separate assignments explicitly.

Do not let a reference silently control everything.

## 7. Identity References

Use a likeness reference only when recognizable identity is part of the visual
goal. Do not make a referenced person the subject by default.

Determine:

- why recognizable identity is needed;
- how much face or body recognizability is required;
- which identity traits must remain stable;
- what expression, pose, clothing, or context may change;
- what the identity reference must not control.

Derive shot size, camera distance, framing, angle, pose, action, expression,
outfit, and relationship to the scene from the user's task and supplied
references. Do not let an identity sheet silently choose them.

Clean identity sheets are identity controls, not scene, style, outfit, lighting,
crop, or layout references.

Face reference controls:

- facial identity;
- facial structure;
- hair and facial hair if present;
- eyes;
- nose;
- mouth/lips when needed;
- expression within identity;
- moderate apparent age preservation unless the task changes age.

Body reference controls:

- body type;
- body proportions;
- posture;
- full-body silhouette;
- stance;
- natural bearing.

Non-transfer boundaries:

- do not copy reference-sheet grid or layout;
- do not copy crop structure;
- do not copy background or room;
- do not copy lighting setup;
- do not copy sheet composition;
- do not copy reference-sheet format;
- do not preserve outfit by default.

Define clothing from the target scene unless the user explicitly asks to keep the reference outfit.

Stable identity-adjacent accessories, such as signature glasses, piercings, or
distinctive jewelry, may be softly preserved when they materially support
recognizability or the user asks to keep them. Do not treat every accessory as
identity by default.

Protect recognizable identity without freezing expression, pose, clothing, or genre treatment unless exact fidelity is the task.

## 8. Multi-Reference Workflows

Mixed references must have explicit hierarchy:

1. base structural source;
2. named target for each support reference;
3. control dimension from each support reference;
4. what is borrowed;
5. what must not transfer.

Example:

```text
Use Image 1 as the base structural reference for composition. Use Image 2 for Character A identity only. Use Image 3 for global lighting only. Do not transfer outfit, pose, or background from the identity reference.
```

If reference assignments are unclear and materially affect the result, ask the user to label references or provide visible numbers.

## 9. Example-Based Transformation

Use this workflow when a source pair demonstrates a change and the user wants
the same transformation logic applied to another base image.

First infer:

1. what changed structurally;
2. what changed visually;
3. what stayed stable;
4. which transformation rule should transfer;
5. which properties of the new base must remain its own.

Then state the operation explicitly:

```text
Analyze the transformation from Image 1 to Image 2. Apply the same
transformation logic to Image 3 while preserving Image 3's identity, geometry,
composition, and any stated locked constraints.
```

Do not imitate only the surface style. Do not transfer a rule blindly when the
new base has incompatible geometry, different preservation priorities, or when
the example pair changed several dimensions that cannot be separated.

If the pair is ambiguous, ask which change is the intended transferable rule.

## 10. Annotated Regions

When boxes, circles, arrows, masks, color marks, or numbered regions identify
an edit:

- bind each instruction to the visible marker or region;
- define what changes inside it;
- define what remains unchanged outside it;
- remove temporary markers from the final image unless the user wants them;
- use one instruction per region when several precise edits are involved.

Example:

```text
Place the new sofa inside the blue rectangle. Remove the blue marker after the
edit. Preserve the rest of the room, camera position, lighting, and geometry.
```

If a marker is not identifiable, several markers overlap, or numbering is
missing, ask for labels or visible numbering before building the prompt.

## 11. Text Replacement

For text replacement, preserve:

- typography tone;
- placement;
- spacing;
- hierarchy;
- alignment;
- layout;
- overall composition.

Change only the text unless the user asks for layout redesign.

If replacement text is longer, allow line breaks or resizing only if explicitly stated or reasonably necessary.

## 12. Refinement

Use refinement when:

- result is close;
- main structure works;
- concept is correct;
- visible defects remain.

Refinement order:

1. preserve what already works;
2. identify dominant defect;
3. correct that defect surgically;
4. avoid redesign unless the concept is wrong.

Typical targets:

- face fidelity;
- hand anatomy;
- text clarity;
- typography spacing;
- lighting coherence;
- material realism;
- background cleanliness;
- product edge clarity;
- reflection control;
- layout alignment.

## 13. Ambiguity Management

Ask when:

- multiple references could define the same trait;
- identity vs pose vs style is unclear;
- marked areas have no labels;
- example pairs are mixed;
- upload order is ambiguous;
- reference contamination risk is high.

Recommend visible numeric labels when helpful.

If ambiguity is minor, proceed with a stated internal assumption.

## 14. Failure Modes

Identity drift:

- strengthen identity lock;
- reduce style pressure;
- separate identity reference from pose/style/outfit references.

Composition drift:

- preserve framing, camera angle, and layout;
- separate structural edit from stylistic polish.

Layout drift:

- preserve hierarchy, placement, spacing, and margins.

Over-editing:

- use "replace only" or "change only";
- protect unchanged areas.

Transformation drift:

- separate the transferable transformation rule from surface details;
- preserve the target base's own identity, geometry, and composition.

Marker leakage:

- bind the change to the marked region;
- require removal of temporary arrows, boxes, circles, masks, or labels.

Reference collision:

- assign one dominant control per reference;
- clarify base/support hierarchy;
- add non-transfer boundaries.

Reference-sheet drift:

- state identity-only role;
- exclude sheet grid, background, lighting, crop, and outfit transfer.

## 15. Prompt Patterns

Controlled replacement:

```text
Replace ONLY the [target object/region] with [new concept]. Preserve [identity / geometry / composition / camera angle / lighting / layout]. Keep all other aspects unchanged.
```

Attribute change:

```text
Change the [target object] to [new attribute]. Preserve the original [identity / structure / scene / composition].
```

Surgical refinement:

```text
Refine the existing image. Keep the composition and overall concept. Improve only [dominant failure mode]. Do not redesign the scene.
```

Example-based transformation:

```text
Analyze the transformation from Image 1 to Image 2, then apply the same
transformation logic to Image 3. Preserve Image 3's identity, geometry,
composition, and unrelated details.
```

Annotated-region edit:

```text
Change only the area marked [marker/number]. Preserve everything outside that
region. Remove the temporary marker after applying the edit.
```

## 16. What This File Must Not Do

This file must not:

- force long reference analysis into every edit;
- treat references as a style blender;
- invent recognizable likeness;
- copy reference-sheet layouts;
- preserve outfit, pose, or lighting from identity sheets by default;
- transfer an example transformation without identifying the actual rule;
- leave temporary edit markers in the final image by default;
- rebuild close results when targeted refinement is enough.
