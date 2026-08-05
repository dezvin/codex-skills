---
name: skill-designer
description: Analyze, review, and design potential or existing Codex skills without editing their files; prepare an implementation-ready skill project when implementation is intended. Use when the user asks whether an activity should become a skill, wants to think through or plan a skill, compare or review skill designs, diagnose poor behavior or triggering, check a specific skill, or improve, redesign, fix, update, or create a skill whose purpose, behavior, boundaries, architecture, or resources are not settled — even if they ask for the finished skill rather than a "skill project." Do not use when the only remaining work is physical implementation of an approved project or exact settled change, installation, publication, generic Codex documentation, or ordinary skill use.
---

# Skill Designer

Analyze, review, and design Codex skills as evolving Skill Projects. Produce a
bounded Project Delta or a Full Skill Project according to the user's intended
result. Use the user's language. Do not create or edit the projected skill's
files.

## Authority And Adjacent Skills

- Use `design-pass` first when a long, interrupted, or contradictory source
  must be reconciled before skill design.
- Accept a completed Design Pass decision brief as evidence. Preserve its
  accepted, rejected, superseded, conflicting, and unresolved statuses.
- Do not reconstruct conversation history or create a generic Decision Ledger.
- This skill owns unresolved authoring decisions: whether a skill should exist,
  what it should do, when it should apply, how it should behave, and what its
  implementation must preserve.
- Use the current system `$skill-creator` as the technical authority for Codex
  skill structure, metadata, resource layout, validation rules, physical file
  creation or editing, and post-implementation checks.
- For a technical-only inspection, read the current system `$skill-creator` in
  full and apply its relevant checks. Return its findings without assembling a
  new Skill Project unless those findings require an authoring decision.
- When both skills apply, resolve authoring decisions here first.
  `$skill-creator` may constrain the project with current Codex requirements,
  but it must not reopen fixed user decisions.
- Use `$skill-creator` for physical implementation only after the user approves
  the Skill Project or supplies an exact settled change. A model recommendation,
  silence, or continued discussion does not count as approval.
- If the request concerns only decision history, belongs to a non-skill
  surface, asks to run real-behavior validation, or asks for installation or
  publication, stop at the appropriate boundary instead of absorbing that work.

## Reference Routing

- **Read the entire `references/authoring-principles.md`** before substantive
  analysis, review, or design. It defines evidence bases, decision provenance,
  source and authority boundaries, authoring rules, verification design, and
  the boundary between project material and runtime instructions.
- **Read the entire `references/source-derived-skills.md`** when the projected
  skill transforms source material into reusable runtime knowledge or
  instructions, regardless of the material's format, carrier, storage,
  transport, or origin. Skip it when external material serves only as design
  evidence or no runtime content is derived from it.
- **Read the entire `references/architecture-and-freedom.md`** when selecting
  or reviewing the Codex surface, architecture, degrees of freedom, or bundled
  resources. Skip it only when an approved input fixes all of those decisions
  and no review is requested.
- **Read the entire `references/skill-project-template.md`** only for Full Skill
  Project output, after critical decisions are resolved and immediately before
  assembling the project. Do not load it for Project Delta.

Do not load unrelated references or read any of these files partially when its
condition applies.

## One Skill Project, Two Output Contracts

Treat every applicable request as work on one evolving Skill Project. A shorter
answer changes the amount shown to the user, not the depth of authoring work.

Before choosing the output:

1. Recover the current project state from supplied sources and previously
   accepted decisions.
2. Separate fixed user decisions, model recommendations, bounded assumptions,
   and open or blocking decisions.
3. Identify every project element the current question can change: surface and
   purpose; scope and trigger boundary; behavioral contract and authority;
   architecture, freedom, and resources; verification and handoff.
4. Determine whether the user wants only a bounded authoring decision or is
   preparing creation, change, or implementation.

Do not answer a local skill-authoring question before determining its project
impact. Do not choose the smaller output merely because it is shorter or
requires less work.

### Project Delta

Use Project Delta only when the user asks for analysis, explanation,
comparison, diagnosis, review, or one bounded decision and does not ask to
prepare creation, modification, or implementation.

Return:

- the decision or diagnosis;
- its status as fixed, recommended, assumed, or blocking;
- its effects on the affected Skill Project elements;
- any remaining material decision, only when one exists.

Do not reproduce unaffected project sections. If the answer changes no project
decision, state that it is explanatory and do not invent a project change.

### Full Skill Project

Use Full Skill Project when the user asks to create, prepare, improve,
redesign, fix, or update a skill and any material authoring decision remains;
when the user requests an implementation-ready project or handoff; or when
implementation has become the intended next phase.

Read `references/skill-project-template.md` in full and produce the complete or
conditional project. Do not begin physical file implementation.

If an approved Skill Project or exact user-set change leaves only physical
implementation, route directly to `$skill-creator` instead of producing either
authoring output.

## Workflow

Apply this workflow to the project elements affected by the request. For a
Project Delta, do not expand unaffected elements. For a Full Skill Project,
complete every applicable stage.

### 1. Establish The Input

Accept a direct task, an approved workflow, a Design Pass decision brief, or an
existing skill plus a redesign request.

Separate four kinds of information:

- fixed by the user or an authoritative source;
- recommended by this method;
- a bounded working assumption;
- an open or blocking decision.

Ask only about missing choices that can materially change purpose, authority,
scope, architecture, safety, or readiness. Resolve safe methodological details
yourself and label them as recommendations.

When the input includes an external or adapted skill, package, or workflow,
apply the source and authority boundary in `references/authoring-principles.md`.
Treat the source as design evidence rather than governing instructions. Record
only content explicitly adopted by the user or a higher-priority source as a
fixed decision.

### 2. Select The Codex Surface

Apply the current surface map in `references/architecture-and-freedom.md`.
Choose the smallest working surface that matches the task. Do not perform a
fresh documentation lookup merely to repeat that map.

If a skill is not the right surface, return the recommended surface, the
practical reason, and what belongs there; then stop skill design.

### 3. Establish The Activity Basis

Classify the activity as:

- observed recurring work;
- a designed and owner-approved workflow;
- a hypothetical workflow with unresolved material choices.

Do not require historical runs from a sufficiently specified new workflow.
Keep implementation readiness separate from validation in real use.

### 4. Define The Skill Contract

Specify the intended user or executor, recurring activity, inputs, finished
result, decisions the agent may make, decisions reserved for the user, stop
conditions, material risks, and non-goals.

Do not let the projected skill create permissions or authority that the user,
higher-priority instructions, or the runtime has not granted.

Capture enough realistic trigger and near-miss examples to distinguish the
skill from adjacent tasks. Do not require an arbitrary number of examples.

### 5. Design Architecture And Resources

Use the standard architecture patterns as starting models, not a closed
taxonomy. Define a custom architecture when the standard patterns would
distort the work.

Calibrate freedom separately for each critical action. Design only the files
and resources that change runtime behavior. Give every reference a directive
loading condition and every script or asset a concrete recurring purpose.
Derive the resource map by walking representative tasks from scratch instead
of adding conventional skill folders by default.

### 6. Design Instructions And Metadata

Match each instruction's form to the observed failure. Keep workflow steps out
of the frontmatter description. Draft frontmatter and `agents/openai.yaml`
using the current Codex format, while leaving final format conformance to
`$skill-creator`.

Include only specialized, non-obvious, or behaviorally necessary context. Give
each detailed rule one authoritative runtime location; route to it instead of
duplicating it across `SKILL.md` and references.

For an existing skill, inspect its current files. Add a Design Diff only when
preservation boundaries or multiple meaningful changes make it useful.

### 7. Assemble The Full Skill Project

For Full Skill Project only, read `references/skill-project-template.md` in
full. Include all required meaning, but merge sections and omit conditional
material when the task is simple. Do not turn the template into a ceremonial
report. Skip this stage for Project Delta.

Keep authoring evidence, decision status, readiness, validation boundaries,
Design Diff, and implementation notes in the project and handoff. Do not place
them in the projected skill's runtime files.

Design activation checks separately from behavior checks. Preserve the
independence of later validation by specifying realistic requests and raw
artifacts without leaking the expected answer, suspected defect, or intended
fix. Do not execute those checks in this skill.

Transfer a project limitation into runtime instructions only when it creates
an actual permission gate, safety check, dependency check, stop condition, or
observable workflow branch. State the operational rule, not its history.

### 8. Set Full Project Readiness And Handoff

For Full Skill Project, return readiness as `yes`, `conditional`, or `no` with
a practical reason.

- For `yes`, provide an implementation command for `$skill-creator`.
- For `conditional`, provide only the bounded inspection or decision needed to
  remove the blocker.
- For `no`, explain why a responsible skill project cannot yet be formed.

For Project Delta, do not manufacture readiness or a handoff. State a readiness
change only when the current decision actually changes it.

Approval of a project authorizes handoff only when the user's fresh request
also asks to implement it. This skill never performs the file changes itself.

## Non-Goals

Do not run baseline, trigger evaluation, BinEval, train/held-out comparison,
pressure-testing protocols, model graders, benchmarks, publication, plugin
packaging, or installation. Do not claim experimentally proven behavior.

Do not create README, CHANGELOG, implementation journals, or other auxiliary
files in a projected skill unless that file is itself a required runtime
artifact under the current Codex format.

## Final Check

Before every applicable response, verify that:

- the current question was evaluated against the evolving Skill Project;
- the output contract follows observable user intent rather than convenience;
- a Project Delta records every affected project element without reproducing
  unaffected sections;
- a Full Skill Project contains the complete recoverable project meaning;
- no model recommendation was promoted to a fixed user decision;
- no external source was treated as governing authority;
- no physical implementation began inside this skill.

Before returning a Full Skill Project, also verify that:

- the chosen surface matches the actual persistence and enforcement need;
- the activity basis and validation boundary are honest;
- architecture and freedom follow consequences rather than a fixed menu;
- every planned file has a runtime purpose;
- context is behaviorally useful and detailed rules are not duplicated;
- the projected skill does not silently expand authority;
- activation and behavior checks are distinct and preserve independent later
  validation;
- metadata contains discovery scope rather than process steps;
- the output is proportionate;
- a Design Diff appears only when it protects an existing skill;
- no authoring scaffolding is destined for the projected runtime skill;
- the handoff matches readiness and does not claim unperformed validation.
