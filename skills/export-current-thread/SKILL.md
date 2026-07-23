---
name: export-current-thread
description: Use this skill only when the user explicitly invokes $export-current-thread or directly asks to export or save the current Codex thread, conversation, chat, or session as a local txt file. Create a compact readable export by default and offer a separate full command-and-result export only after the compact file is ready. Do not invoke implicitly for ordinary logging, summaries, handoffs, or unrelated file exports.
---

# Export Current Thread

Export the observable work from the current Codex thread to a persistent UTF-8
`.txt` file. Keep the default file readable: preserve messages and a
verifiable trace of tool activity without copying full commands, file contents,
or result bodies into it.

This skill is intentionally explicit-only because even a compact export can
contain private text, local paths, and project information.

## Procedure

1. Run the bundled script:

```powershell
python "$env:USERPROFILE\.codex\skills\export-current-thread\scripts\export_current_thread.py" --json
```

2. If `python` is unavailable but `py` exists, run:

```powershell
py "$env:USERPROFILE\.codex\skills\export-current-thread\scripts\export_current_thread.py" --json
```

3. Read the script result. It includes `ok`, `export_kind`, `output_path`,
   `thread_id`, `rollout_path`, event counts, byte and character counts, and a
   deterministic token estimate. Do not read the generated file unless the
   user's request also requires analyzing it.

4. Tell the user that the compact export is ready, link the file, and mention
   the optional full journal only after successful creation:

```markdown
Готово: компактный экспорт текущей ветки сохранён здесь:
[filename.txt](C:\absolute\path\filename.txt)

В нём есть сообщения и проверяемый журнал операций без тяжёлого содержимого
файлов и результатов. Если понадобится полный журнал команд и результатов
инструментов, могу отдельно сделать технический экспорт.
```

Do not ask the user to choose a variant before creating the compact export.
Do not create a second file automatically.

## Compact Export

The default export must:

- preserve user, assistant, and subagent messages in chronological order;
- preserve context-compaction markers;
- represent every supported tool call and result with its `Call ID`, tool name,
  known working directory, explicit targets or path mentions, target-coverage
  status, result status, exit code when deterministically available, content
  size, SHA-256, and source-record number;
- label target coverage as `exact`, `partial`, or `unknown`; never present
  literal path mentions from arbitrary code as a complete file list;
- omit full invocation bodies, executed code, file contents, patches, and
  textual result bodies;
- include the exact script path, thread ID, source rollout, and command needed
  to retrieve supported records matching one `Call ID`.

If an agent reading the compact file needs details, it must not infer omitted
content. Retrieve only the records matching the required call:

```powershell
python "<script-path-from-export>" `
  --thread-id "<thread-id>" `
  --extract-call "<call-id>" `
  --temporary `
  --json
```

Check `pair_complete` in the JSON result and the extracted file. When it is
`false`, read `missing_parts` as `call` or `result` and do not treat the
fragment as a complete operation record. This is a structural check only; it
does not classify the operation or compare files before and after it.

Read the returned file, then delete it:

```powershell
python "<script-path-from-export>" --cleanup "<output_path>" --json
```

If the source rollout is unavailable, inspect current authoritative files and
project state. If that is insufficient, ask for a full command-and-result
export.

## Full Technical Export

Create a full technical export only after the user explicitly asks for the
full journal of commands and tool results:

```powershell
python "$env:USERPROFILE\.codex\skills\export-current-thread\scripts\export_current_thread.py" --full --json
```

The full export preserves supported invocation and textual result bodies. It
is an explicit follow-up artifact, not an automatic fallback for a long or
complex thread.

## Shared Behavior

- Use `CODEX_THREAD_ID` as the current-thread source.
- Read only `$CODEX_HOME/sessions` or `%USERPROFILE%\.codex\sessions`, plus `archived_sessions` only when a requested thread is archived.
- Never edit, rewrite, normalize, or move original `rollout-*.jsonl` files.
- Save the `.txt` in the first active workspace root from the thread context.
- If no active workspace root is available, save the `.txt` on the user's Desktop.
- Use supported `response_item` records as the canonical source for messages and tool activity. Use only explicitly allowed non-duplicating `event_msg` metadata.
- Exclude system/developer messages, known Codex-injected user-content blocks,
  hidden reasoning, token telemetry, unknown internal record types, and
  explicitly typed binary content through deterministic code rules.
- Do not use a model to summarize, clean, reformat, select relevant fragments, redact heuristically, or deduplicate by textual similarity.
- Remove only structurally proven duplicates with the same event or call identifier. Preserve identical wording when it belongs to distinct events.
- Preserve large textual tool results only in the explicit full export or a
  requested single-call extraction. Replace known binary content with
  available type, size, MIME, path, URL, or identifier metadata.
- Write UTF-8 without BOM.

## Failure Handling

- If the current thread id is unavailable, do not guess. Tell the user that Codex did not expose `CODEX_THREAD_ID` and ask them to rerun from an active Codex thread or provide a thread id.
- If the rollout file cannot be found or verified, explain that the current thread log could not be matched.
- If the export succeeds, do not paste the transcript into chat; only link the generated file.
