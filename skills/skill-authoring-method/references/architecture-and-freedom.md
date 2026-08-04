# Architecture And Freedom

Use this reference to choose the correct Codex surface, the skill architecture,
the degree of freedom for each action, and the minimum necessary resources.

## Codex Surface Map

Treat this as the maintained current map. Do not browse documentation on every
project merely to reconfirm it. Update this reference manually when Codex adds,
removes, or materially changes a surface.

| Surface | Use for |
| --- | --- |
| Prompt | A one-off condition for the current task or thread |
| `AGENTS.md` | Durable repository or subtree guidance, commands, conventions, and review expectations |
| `config.toml` | Codex settings such as model, sandbox, tools, MCP, hooks, or reasoning defaults |
| Memory | Retained context, facts, preferences, and useful continuity rather than a procedure |
| Skill | A reusable specialized activity with instructions, references, scripts, or assets |
| Plugin | A distributable bundle of skills and optional tools, MCP configuration, apps, hooks, or assets |
| MCP or connector | Authorized access to external data, services, or actions |
| Hook | Mechanical enforcement around tool calls, commands, edits, or lifecycle events |
| Automation | Scheduled, monitored, recurring, or follow-up execution |

Choose the smallest surface that actually provides the required persistence,
capability, and enforcement. Split mixed needs instead of forcing them into one
artifact. For example, put a reusable review method in a skill and enforce a
non-bypassable command restriction with a hook.

### Skill Fit

A skill is a good fit when the activity is reusable, specialized, and benefits
from procedural knowledge, reference material, deterministic helpers, or
output assets that should travel together.

A skill is a poor fit when the need is only a one-time instruction, a local
repository convention, retained context, a setting, scheduled execution,
mechanical enforcement, external access, or distribution packaging.

When a skill is not the right surface, recommend the right surface and stop.
Do not create a partial skill merely because the user used the word "skill."

## Architecture Patterns

Use these as starting models. Combine them only when different parts of the
activity genuinely need different structures. Define a custom architecture
when none fits without distortion.

### Sequential Workflow

Use when later actions depend on earlier outputs. Make ordering, dependencies,
validation points, stop conditions, and recovery explicit.

### Iterative Refinement

Use when quality improves through revision. Define the quality criteria and a
real exit condition so the agent neither stops arbitrarily nor loops forever.

### Context-Aware Selection

Use when the same goal requires different routes depending on observable input
conditions. Key every branch to evidence, not intuition.

### Domain Intelligence

Use when specialized rules or knowledge must shape decisions. Apply rules at
the point where they can prevent an error, not only during final review.

### Multi-Service Coordination

Use when state moves across services or tools. Define phase boundaries, data
handoffs, partial-failure behavior, and permission gates.

### Custom Architecture

Describe a custom structure in plain language when the standard patterns are
insufficient. State what each part produces, how parts interact, and what
proves completion. Do not invent a new name when a standard pattern already
fits.

## Degrees Of Freedom

Calibrate freedom per critical action by asking what happens if the agent is
wrong.

| Consequence and variability | Degree | Instruction form |
| --- | --- | --- |
| Fragile, dangerous, irreversible, or exact | Low | Fixed script, exact schema, narrow command, or explicit contract |
| Preferred route with legitimate variation | Medium | Algorithm, decision table, pseudocode, or parameterized helper |
| Several valid approaches requiring judgment | High | Principles, criteria, and examples |

Do not assign one degree to the whole skill. A single skill can combine a
low-freedom write operation with high-freedom analysis.

## Resource Decisions

Plan only resources that provide recurring runtime value:

- Keep essential routing, order, and critical rules in `SKILL.md`.
- Put detailed methods, domain knowledge, schemas, and variants in
  `references/` with directive loading conditions.
- Put fragile or repeatedly rewritten deterministic operations in `scripts/`.
- Put templates, images, fonts, boilerplate, or other output materials in
  `assets/`.
- Add `agents/openai.yaml` for current product metadata and invocation policy.

Do not create empty directories, passive reference catalogs, README files, or
resources that only document how the skill was authored.

## Architecture Check

Before accepting an architecture, verify:

- each stage or branch has an observable reason to exist;
- dependencies are ordered rather than implied;
- the design does not force a task into the five starting patterns;
- freedom decreases where consequences increase;
- scripts are justified by determinism or repeated code;
- references are loaded only where their knowledge is needed;
- the chosen surface, not just the skill structure, is correct.
