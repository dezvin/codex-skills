# Authoring Principles

Use these principles when converting a recurring activity into a skill project.
They govern evidence, instruction design, resource boundaries, and the content
that may enter the projected runtime skill.

## Establish A Real Basis

Classify the activity before authoring:

### Observed Recurring Work

Use actual tasks, artifacts, failures, pauses, corrections, or repeated manual
effort as evidence. State what the agent currently misses or performs
inconsistently. A scripted baseline is not required for this method.

### Designed And Owner-Approved Workflow

Treat a new workflow as implementation-ready when its purpose, actors, inputs,
decisions, exceptions, authority, and finished result are sufficiently defined
and its owner has approved that design. Lack of historical runs does not make
the project provisional.

Record separately that real-use validation has not happened. Keep that status
in the project and handoff, not in the projected runtime instructions.

### Hypothetical Or Underspecified Workflow

Treat a workflow as conditional when material roles, inputs, decisions,
exceptions, permissions, or completion criteria remain unresolved. Name the
specific blockers instead of calling the whole idea vague.

## Preserve Decision Provenance

Keep these categories distinct:

- **Fixed:** explicitly set by the user or an authoritative source.
- **Recommended:** selected by this method using the available evidence.
- **Assumed:** a bounded choice made to keep the design coherent.
- **Open or blocking:** a decision that can materially change the project.

Do not infer acceptance from silence, continued discussion, or an assistant's
earlier wording. When a Design Pass is supplied, preserve its statuses rather
than reconstructing them.

## Make Description A Discovery Contract

Put what the skill does and when it should or should not be used in the YAML
`description`. Front-load the main use case and meaningful trigger terms.
Include adjacent negative cases when they protect routing.

Keep process order, implementation steps, and resource-loading instructions in
the body. A description that narrates the workflow can cause the body to be
skipped.

## Keep `SKILL.md` As A Working Map

Keep essential routing, dependencies, decisions, and critical safeguards in
`SKILL.md`. Move detailed methods, variants, schemas, and examples into
references. Link every reference from the point where it becomes necessary and
state whether to read it fully.

Avoid passive end-of-file reference lists. They announce files without causing
the agent to load them.

## Match Instruction Form To Failure

| Observed failure | Strong form |
| --- | --- |
| The agent knows a rule but violates it under pressure | Direct prohibition plus closure of realistic rationalizations |
| The output has the wrong shape | Positive output contract describing the required result |
| A required element is omitted | Required field or slot in the structure being produced |
| Behavior depends on context | Conditional keyed to an observable predicate |
| A fragile operation varies between runs | Deterministic script or exact algorithm |

Do not fix a shaping problem with an expanding list of prohibitions. Do not
write exemptions such as "unless useful." Express a real exception as its own
observable branch.

## Explain Critical Instructions

For a critical instruction, provide only the explanation needed to prevent
unsafe improvisation:

- **Action:** what to do.
- **Key point:** what error to watch for.
- **Why:** what practical loss the instruction prevents.

Do not turn every obvious step into a lesson. Explanations earn their space by
changing behavior at an edge case.

## Check At The Point Of Risk

Place a short check immediately before or after the action that can fail. Use a
script or schema when the property is deterministic. Do not rely on a generic
quality section at the end of a long workflow.

## Use One Term Per Concept

Choose one term for each working object and keep it stable across `SKILL.md`,
references, scripts, schemas, and output templates. Add a small glossary only
when several domain terms would otherwise collide.

## Remove Inactive Text

For each section ask: "What agent action changes because of this text?" Delete
or relocate text that has no answer. Replace rubbery language such as "as
needed" with an observable condition.

Keep secrets, tokens, environment values, user-specific absolute paths, author
history, and setup diaries out of runtime instructions. Create no README,
CHANGELOG, or auxiliary authoring documentation inside a skill.

## Check Dependencies Before Dependent Actions

When a projected workflow requires a tool, file, permission, connection, or
credential, design a preflight before the first dependent action. Stop or route
explicitly when a critical dependency is absent. Do not let the agent silently
invent a substitute.

Keep detailed environment commands in a reference when they would bloat the
main map.

## Separate Project Material From Runtime Material

Keep these in the skill project and implementation handoff only:

- evidence and decision provenance;
- implementation readiness;
- real-use validation status;
- Design Diff;
- authoring history and implementation notes;
- plans for future testing.

Put only reusable execution instructions, required knowledge, resources,
runtime checks, permission gates, and observable branches into the projected
skill.

If a project limitation changes runtime behavior, translate it into the actual
operational rule. For example, write "request approval before the first live
send" when approval is required; do not write that the workflow was designed
theoretically and has not been tested.

## Keep Claims Honest

Distinguish:

- designed;
- approved;
- implemented;
- structurally validated;
- exercised on a real task;
- behaviorally validated;
- installed or published.

This method can establish the first two states and prepare the third. It does
not prove the later states through eval automation.

## Authoring Check

Before handoff, verify that:

- the activity basis is explicit;
- user decisions and model recommendations remain distinguishable;
- every instruction has an observable behavioral purpose;
- every resource belongs to runtime rather than authoring history;
- exceptions are observable branches rather than nuance clauses;
- checks sit near the risks they control;
- the project does not claim evidence it has not produced.
