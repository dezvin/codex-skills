# Artifact Profiles

Read only the section matching the current artifact when its type changes what must be preserved or removed. These profiles set preservation priorities; they are not mandatory templates.

## Model answer

Preserve the direct answer, facts needed to support it, material caveats, conditions that change the conclusion, and the next action when one is required.

Remove repeated questions, generic openings, narration of the response, optional background, generic reassurance, repeated conclusions, and unrequested next steps. Lead with the result. Add explanation only when it changes understanding, trust, or action.

## Instruction, prompt, or policy

Preserve triggers, actions, order, authority, prohibitions, exceptions, decision rules, dependencies, stop conditions, outputs, and verification.

Remove philosophy, generic advice, authoring history, repeated rules, broad rationale, obvious examples, and instructions already enforced or owned elsewhere.

## Skill or agent instruction file

Preserve discovery scope, essential workflow, critical boundaries, reference-loading conditions, failure handling, and result checks.

Keep the entrypoint as a working map. Move substantial conditional detail to a directly linked reference only when it will not be loaded for ordinary tasks. Do not duplicate detailed rules across the entrypoint and references.

When textual comparison cannot establish behavioral equivalence, test representative triggers, exclusions, stop conditions, modes, ownership boundaries, and outputs.

## Multiple source artifacts

When combining sources, preserve their distinct contributions. Ask which source controls when the output cannot safely represent a material conflict.

Keep separate artifacts when combining them would mix incompatible audiences, authority, lifecycle, evidence, or operational roles.

## Decision or design document

Preserve the current decision, requirements, grounds that control it, consequences, rejected options that protect scope, unresolved conflicts, and verification.

Remove conversation chronology, superseded detail with no current consequence, repeated summaries, ceremonial sections, and implementation history that does not affect the current design.

## Reference or knowledge document

Preserve independently useful facts, definitions, distinctions, evidence boundaries, navigation, and enough context for later correct use.

Remove repeated syntheses and multiple explanations of the same concept. Do not compress away distinctions merely because they fit under one broader label.

## Raw, source, or archive material

Preserve original wording, order, provenance, uncertainty, contradictions, omissions, and drafting traces when they are evidence or the artifact's subject. Remove them only when they are operational noise rather than source content.

Preserve the relationship between a claim and the source, date, qualification, or confidence that controls how it may be used.

## Handoff or status artifact

Preserve the objective, current verified state, completed work, changed artifacts, open questions, blockers, authority boundary, and next safe action.

Remove the full conversation retelling, finished intermediate reasoning, routine command logs, discarded branches with no current consequence, and generic encouragement.

## Code, configuration, or technical artifact

Preserve required behavior, public interfaces, boundary validation, security, data integrity, compatibility explicitly required now, and the smallest relevant verification.

Prefer reuse, native or standard capabilities, installed dependencies, and the smallest correct change. Remove speculative extensibility, one-use abstractions, wrappers without value, duplicate configuration, future scaffolding, and unrelated cleanup. Do not golf code or remove validation at trust boundaries.

## Structured result

Preserve required fields, types, semantics, identifiers, evidence, and error state.

Remove duplicated prose and fields with no consumer. Keep the validation needed by the receiving workflow.
