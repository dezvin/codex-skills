---
name: design-pass
description: Use this skill when the user provides a preflight brief, Decision Ledger, or resolved preflight package and asks to turn it into a design pass, implementation-ready design, architecture/design brief, or handoff before implementation. Use for mapping confirmed decisions and post-preflight answers into requirements, selected views, affected surfaces, implementation guidance, verification checks, and readiness status across Codex skills, LLM workflows, business, marketing, content, education, operations, methodology, research, visual, and code work. Do not use for raw discussion summarization, preflight consolidation, direct implementation, file editing, deployment checks, CI checks, ordinary critique, or deciding unresolved choices without marking them for confirmation.
---

# Design Pass

Convert a preflight package into a handoff-ready design for a separate implementation run. Here "implementation-ready" means ready to hand off, not permission for this skill run to execute.

This is not preflight. This is not implementation. This is not an ordinary task plan.

## Core Contract

- Default mode: read-only, answer-only design.
- Write the user-facing result in the user's language, including headings, status labels, and the implementation command.
- Use the provided preflight brief, Decision Ledger, and post-preflight user answers as the primary evidence.
- If no preflight brief or Decision Ledger is provided, stop and ask the user to provide one or to run `$preflight` first. Do not synthesize a fake preflight from raw conversation memory.
- Treat later explicit user answers after preflight as higher-priority input. Do not treat assistant suggestions as accepted decisions unless the user confirmed them.
- Do not edit files, create project artifacts, implement changes, run deployment checks, or execute the implementation handoff unless the current user explicitly asks for that separate action.
- Treat implementation-ready as handoff-ready: the current design-pass run prepares the next implementer, but does not become the implementer.
- Inspect project files only when they are provided, named, or clearly necessary for a responsible design pass. Use inspection for understanding, not modification.
- Do not force-fit the task into a known domain or view pack. If no preset fits, synthesize custom views from the task profile and explain why.
- Always produce an implementation handoff and readiness status. The handoff tells the next agent what to do; it is not permission for this skill run to do it.

## Required Inputs

Identify:

1. Target implementation task.
2. Preflight brief or Decision Ledger.
3. Post-preflight user answers or clarifications, if any.
4. Constraints, non-goals, and rejected options.
5. Optional project, system, audience, workflow, or file context.
6. Intended implementer, such as Codex, another AI agent, a person, or a team.

If the target task is missing, ask for it. If the preflight is missing, ask for it before continuing.

## Procedure

1. Read `references/design-pass-method.md`.
2. Validate that the input contains a real preflight brief, Decision Ledger, or explicit preflight-derived package.
3. Merge post-preflight user answers into the preflight status model without rewriting the original preflight.
4. Convert accepted and clearly resolved items into explicit design requirements. Convert rejected and superseded items into guardrails and non-goals.
5. Build the Task Profile: domain, output artifact, actors, change surface, quality criteria, failure modes, and implementation mode.
6. Select views from core views, relevant presets, and custom synthesis. Explain the selection.
7. Inspect current project or source context only when needed and allowed.
8. Build the layered design from context to implementation details and verification.
9. Build the Design Diff: current or before state -> target after state.
10. Build the Traceability & Impact Map. This is mandatory.
11. Record key design decisions in an ADR-like table when meaningful.
12. Add Acceptance Examples when scenarios materially clarify success or failure.
13. Produce the implementation handoff and ready-to-use command for the next agent.
14. Finish with a readiness check: `yes`, `no`, or `conditional`.

## Output Contract

Include the full core structure:

```markdown
# Design Pass: <task>

## 1. Brief Conclusion
## 2. Sources And Input Status
## 3. Resolved Preflight Summary
## 4. Design Requirements And Guardrails
## 5. Task Profile
## 6. Selected Views And Rationale
## 7. Design
## 8. Design Diff
## 9. Traceability And Impact Map
## 10. Key Design Decisions
## 11. Risks And Tradeoffs
## 12. Acceptance Examples
## 13. Implementation Handoff
## 14. Ready-To-Use Implementation Command
## 15. Readiness Check
```

Rules:

- Translate headings and labels into the user's language.
- Do not create irrelevant view sections just because a preset was partially selected.
- If evidence is missing, say what is missing instead of inventing it.
- If readiness is `conditional`, list exactly what must be confirmed or provided first.
- If readiness is `no`, explain the blocker and the nearest useful next step.
- If readiness is `conditional` or `no`, the ready-to-use command must not ask the next agent to implement the full design. It must ask the next agent to resolve named blockers, inspect named context, or obtain named confirmations first.
- Include Acceptance Examples when they help test behavior, quality, or edge cases. If examples would be artificial, say that the verification checks are sufficient instead of inventing examples.
- If implementation would be risky without reading specific files, list those files in the handoff instead of guessing their contents.

## Readiness Status

Use:

- `yes` only when the design is coherent, critical decisions are confirmed, affected surfaces are clear enough, checks are defined, and the handoff is actionable.
- `conditional` when implementation is possible only after named confirmations, bounded assumptions, or file/context reads.
- `no` when the preflight is missing, the target task is unclear, critical decisions conflict, or the design would require inventing important choices.
