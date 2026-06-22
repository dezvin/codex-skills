---
name: document-consolidator
description: Use this skill only when explicitly invoked as $document-consolidator to analyze document sprawl, compress Markdown/text documents, consolidate multiple documents into candidate or final documents, or plan cleanup without losing evidence, source roles, protected facts, rules, decisions, links, or unfinished work. Supports .md and .txt only. Do not use for skill files, prompt files, docx/pdf, ordinary copyediting, publication writing, code refactors, or implicit summarization.
---

# Document Consolidator

Use this skill to safely reduce document sprawl without destroying the work the documents perform.

The core rule is:

```text
Preserve the document's function first.
Improve structure second.
Compress language third.
```

This skill is explicit-only. If it was not invoked by name, do not assume it applies.

## Supported Work

- Analyze a folder or selected files and produce a short sprawl map plus cleanup plan.
- Compress one Markdown or plain-text document.
- Compress an instructional document, rule, runbook, or process note with stricter behavior preservation.
- Consolidate several documents into one or more new documents.
- Create a dry run showing structure, source mapping, risks, and key fragments without writing files.
- Move included source documents into `00_Source_Documents` only after separate confirmation.

Do not use this skill for:

- `SKILL.md` or skill-package compression;
- prompt files;
- `.docx`, `.pdf`, spreadsheets, slide decks, images, code, or generated data files;
- ordinary copyediting, post writing, summary writing, or style polish;
- broad project redesign disguised as document cleanup.

If a requested file is a skill or prompt file, stop and say this skill does not own that work.

## Reference Loading

Read only the references needed for the selected path:

- Read `references/mode-selection.md` first for every run.
- Read `references/source-roles.md` when more than one document is involved or a folder is being mapped.
- Read `references/compression.md` for `compress-one` and `compress-instructional-doc`.
- Read `references/consolidation.md` for `merge-many`, source movement, and source-link handling.
- Read `references/iterative-cleanup.md` for folders, live contours, large scopes, or unclear cleanup paths.
- Read `references/file-safety.md` before creating a candidate file, moving files, replacing files, or moving sources.
- Read `references/validation-and-findings.md` before checking a candidate, reporting losses, or deciding whether to stop.
- Read `references/output-templates.md` when presenting a map, dry run, confirmation request, findings, or final report.

## Workflow

1. Confirm explicit invocation and supported file type.
2. Identify the scope: selected files, one folder, or a proposed output path.
3. If the scope is broad, start with a shallow inventory: file names, sizes, dates, headings, and links. Do not read all content by default.
4. Select the mode from `references/mode-selection.md`.
5. Map each document's function, source role, currentness, and protected anchors.
6. If the task may write or move files, show the relevant map and ask for plain confirmation before writing.
7. For large or uncertain work, complete only the nearest safe segment. Do not pretend the whole cleanup can be planned in one pass.
8. Create a candidate version when writing is needed. Never overwrite the target directly.
9. Read the candidate back and validate against the original source material.
10. Ask for confirmation before final replacement or source movement.
11. Use the filesystem scripts for move/rename operations.
12. Report only the useful result, remaining risks, and next safe step. Do not create service-report files unless the user explicitly asks.

## Candidate And Replacement Rule

For any document replacement:

```text
target.md -> target.candidate.md
target.txt -> target.candidate.txt
target -> target.candidate
```

The target file must not be overwritten by writing content into it.

Required sequence:

1. Read the original file.
2. Create the candidate beside the original.
3. Read the candidate back.
4. Validate the candidate against protected anchors and source role.
5. Ask for replacement confirmation.
6. Move the original file to `_backup/<YYYY-MM-DD_HH-mm>/`.
7. Rename the candidate to the original name.
8. Read the final file back and verify encoding, links when relevant, and protected anchors.

All backup, replacement, and source moves must use filesystem move/rename operations, not model-mediated copy/rewrite.

Use:

- `scripts/document_fs_ops.ps1` on Windows/PowerShell.
- `scripts/document_fs_ops.sh` on macOS/Linux shells.

The scripts are for mechanical file operations only. The model remains responsible for reading, understanding, drafting, validating, and asking for approval.

## Confirmation Rules

Use human-facing language. Say `подтверждение записи`, not `Write-Lock`, unless the user asks for the technical label.

Ask only for decisions that change behavior, risk, scope, or files. Do not ask about obvious implementation details.

Before a write or move, show:

- what will be created, replaced, or moved;
- where backup will be;
- what will not be touched;
- what validation will run after the operation;
- allowed answers such as `да / поправить / остановиться`.

Do not treat tool approval, silence, or prior intent as confirmation.

## Safety Rules

- Evidence beats brevity.
- A valid result may be: "Do not compress this; the length is carrying necessary evidence or behavior."
- Do not collapse current truth, raw/source material, archived history, drafts, TODOs, handoffs, and rules into one file without mapping their roles first.
- Do not fix references outside selected files by default; report the risk instead.
- Do not invent validation scenarios. Derive them from the current documents.
- Do not preserve reasons for past decisions by default unless they are needed for current use or the user asks.
- Do not create README, CHANGELOG, proof files, service reports, or logs as part of ordinary operation.

## Output Style

Speak to the user in plain, practical language before technical details.

For Russian-speaking users, answer in Russian unless asked otherwise.

Keep service detail out of the main answer. Show file operations only when they were requested, are waiting for confirmation, or failed.
