---
name: universal-visual-prompt-builder
description: "Use this skill for standalone image-prompt creation, refactoring, model/style/format adaptation, image editing, reference-based prompting, weak-result repair, prompt sets, and controlled variants from a brief, idea, image, or existing prompt. Produces prompt text but does not generate images. Do not use when a separate project-specific visual workflow owns the request or when the primary deliverable is broader content rather than an image prompt."
---
# Universal Visual Prompt Builder

## Role

Create production-ready image-prompt text without depending on a repository,
client system, hidden project files, or another skill.

Own only the image-prompt layer. Do not generate the image, write surrounding
content, or invent a broader campaign, story, carousel, or publication plan.
When the current repository has a dedicated visual-system workflow that owns
the request, defer to that owner without assuming its name or contract.

## Supported Work

Handle:

- a direct brief or rough visual idea;
- improvement or refactoring of an existing prompt;
- adaptation to a different model, style, medium, format, ratio, or use case;
- generation or editing from one or more reference images;
- selective edits, annotated-region edits, and example-based transformations;
- repair of a weak generated result;
- a standalone set, sequence, or storyboard of image prompts when the user
  supplies the frame goals;
- controlled variants of one visual focus.

Do not turn a request for broader content strategy into an image-prompt task.
It is valid to create prompts for supplied story frames, cards, scenes, or
sequence goals; it is not valid to invent the content sequence itself.

## Source Priority

Use this order:

1. the user's explicit request;
2. supplied images, references, existing prompts, and edit targets;
3. exact in-image text, preservation requirements, and hard constraints;
4. intended use, deliverable type, ratio, medium, or target model when material;
5. explicit style direction;
6. the smallest relevant reference set from this skill;
7. patterns only as low-priority aids.

Resolve conflicts as follows:

- task function beats decorative style;
- exact quoted text cannot be rewritten;
- preservation requirements beat polish in edit tasks;
- reference roles and non-transfer boundaries beat broad visual blending;
- a named model may refine the prompt but cannot discard the shared
  `GPT Image 2` and `Nano Banana 2` prompt-building baseline.

## Working Modes

Classify the request as one or more of:

- `direct_visual_brief`;
- `existing_prompt_refactor`;
- `prompt_adaptation`;
- `image_or_reference_edit`;
- `result_refinement`;
- `controlled_variants`;
- `prompt_set_or_sequence`.

For an existing prompt, identify what works, what must survive, what is weak,
and what success now means. Rebuild only when the working core is structurally
wrong or the user explicitly requests a new direction.

For adaptation, preserve the portable core and change only what the new model,
format, style, ratio, medium, or use case requires.

For an edit, define what changes, what stays unchanged, the highest
preservation priority, and what each reference controls.

For refinement, preserve the useful result and repair the dominant defect
before considering a rebuild.

For variants or sets, distinguish shared invariants from allowed differences.
Do not disguise a missing sequence decision as visual variation.

## Workflow

1. Identify the working mode and intended deliverable.
2. Normalize only what matters:
   - visual goal;
   - subject, scene, structure, or edit operation;
   - deliverable type and visual role;
   - dominant visual idea or meaning carrier;
   - locked constraints;
   - flexible variables;
   - success criterion;
   - exact text;
   - format and ratio;
   - reference roles and non-transfer boundaries;
   - special risks.
3. Read `references/universal-prompting.md` for any substantive build.
4. Read only the additional references whose conditions below apply.
5. Ask a short clarification only when missing information materially changes
   the image, layout, edit target, preservation rule, reference assignment,
   exact text, format, or success criterion.
6. If ambiguity is minor, use a conservative assumption and continue.
7. Choose the simplest sufficient architecture:
   - compact natural language for one dominant visual idea;
   - a structured brief for strict layout, several objects, references, or
     interacting constraints;
   - JSON or pseudo-JSON only when the user asks for it or when strict zoning,
     repeatability, or automation materially benefits;
   - a reasoning-oriented instruction for transformations, rearrangements,
     comparisons, process visuals, or educational diagrams;
   - a controlled edit instruction for preservation-heavy work;
   - a per-item structure for a set or sequence.
8. Build from the task outward:
   - subject, function, or edit operation;
   - action, state, scene, or structure;
   - composition and attention hierarchy;
   - exact text and layout;
   - task-derived style direction;
   - format and crop constraints;
   - reference and preservation rules;
   - useful camera, light, material, or medium details;
   - hard constraints and targeted exclusions.
9. Run the readiness and anti-drift checks below.
10. Return the result using one of the output modes below.

Do not output the normalized working layer unless the user asks for analysis.

For every substantive build, use `GPT Image 2` and `Nano Banana 2` together as
one active prompt-building baseline. Neither model is the default or fallback.
If the user names a target model, preserve that choice and adapt only the
model-dependent details after verification.

## Conditional References

- Read `references/universal-prompting.md` for every substantive prompt build,
  refactor, or adaptation.
- Read `references/editing-references.md` for base-image edits, reference
  images, identity preservation, annotated regions, transformation examples,
  text replacement, or close-result refinement.
- Read `references/text-layout.md` when exact in-image text, typography,
  posters, slides, infographics, diagrams, UI-like layouts, zones, hierarchy,
  or legibility matter.
- Read `references/series-and-sets.md` for standalone prompt sets, sequences,
  storyboards, campaigns, controlled variants, continuity, or anti-repetition.
- Read `references/format-ratio.md` when ratio, orientation, crop, carrier
  format, or platform shape materially affects the result.
- Read `references/realism-camera-materials.md` when realism, camera, light,
  materials, portraits, products, or believable environments matter.
- Read `references/troubleshooting.md` after a weak result, named failure mode,
  or failed readiness check.
- Read `references/patterns.md` only after task type, architecture, and success
  criterion are known and one compact pattern would help.

## Output

Use exactly one mode unless the user requests a specific machine-readable or
prompt-only format.

### Mode A - Clarify

Use when the task is not build-ready.

Return:

1. one short explanation of the practical gap in the user's language;
2. one to four short questions that are genuinely required;
3. optionally, one short recommendation about references or workflow.

Stop after the clarification. Do not include a speculative prompt.

### Mode B - Full Build

Use when the task is build-ready.

Return in this order:

1. `Анализ и стратегия` - one to three concise sentences in the user's
   language naming the request type, chosen architecture, critical controls,
   preservation priorities, success criterion, or multi-pass need. State the
   practical conclusion, not hidden reasoning or the full normalized layer.
2. `Готовый промпт` - the final English `image_prompt` in one fenced code
   block. Preserve exact quoted in-image text in its source language.
3. `Практический совет` - one concrete recommendation in the user's language
   about generation, references, refinement, or risk control.

Example prompt block:

```text
<final English image prompt>
```

For variants or prompt sets, keep the same Mode B wrapper, then give each item
a short identifier and distinction followed by its own fenced prompt block.

When the user explicitly requests JSON, YAML, a field named `image_prompt`, or
another machine-readable or prompt-only shape, use that requested structure
instead of the Mode B wrapper.

## Readiness And Anti-Drift

Before returning a prompt, confirm:

- the visual goal and success criterion are preserved;
- subject, action, and strongest constraint appear early;
- exact text is unchanged and protected by layout when necessary;
- important attributes are bound to named people, objects, regions, or zones;
- each reference has a clear target, control dimension, priority, and
  non-transfer boundary when needed;
- edit tasks state both the change and the protected remainder;
- style supports the task instead of replacing it;
- format and ratio support the composition and reading path;
- exact colors and gradients are bound to named objects, parts, or zones;
- variants or adjacent items differ on meaningful allowed dimensions;
- declared series anchors remain stable while item-level visual decisions vary;
- camera, realism, lighting, and material details improve control;
- no internal paths, hidden project state, private mechanics, or service labels
  appear in the prompt;
- the prompt contains no unused alternatives or decorative keyword soup.

Default drift is present when the prompt falls into a generic scene, object
bundle, style stack, palette, layout skeleton, or rendering recipe not derived
from the task.

Repair once:

1. restate the visual goal;
2. identify the task-derived visual mechanism;
3. remove generic filler;
4. strengthen composition, layout, edit, or reference boundaries;
5. retain only details that improve the expected result.

If one focused repair cannot resolve the drift, ask for the missing visual
decision instead of pretending the prompt is ready.

## Stop Rules

Stop and ask for input when:

- exact text is required but absent;
- reference assignments materially conflict or remain ambiguous;
- recognizable identity is required but no usable reference exists;
- annotated regions are not identifiable;
- constraints are mutually incompatible in one image;
- the requested model must support a capability that has not been established;
- a prompt set lacks the item-level goals needed to distinguish its members;
- the request belongs to a separate project-specific visual owner.

Explain the practical missing input in the user's language. Do not expose
repository-specific route labels or assume another skill exists.

## References

- `references/universal-prompting.md` - portable prompt doctrine and assembly.
- `references/editing-references.md` - edits, references, identity, annotated
  regions, example transformations, and refinement.
- `references/text-layout.md` - exact text, typography, hierarchy, and layouts.
- `references/series-and-sets.md` - prompt sets, continuity, and variation.
- `references/format-ratio.md` - ratio, orientation, crop, and extreme formats.
- `references/realism-camera-materials.md` - realism, camera, light, materials.
- `references/troubleshooting.md` - diagnosis and targeted repair.
- `references/patterns.md` - low-priority control and repair patterns.
