---
name: export-current-thread
description: Use this skill only when the user explicitly invokes $export-current-thread or directly asks to export or save the current Codex thread, conversation, chat, or session as a local txt file. Create a readable recovery transcript by default and offer a separate full command-and-result export only after the transcript is ready. Do not invoke implicitly for ordinary logging, summaries, handoffs, or unrelated file exports.
---

# Export Current Thread

Export the observable work from the current Codex thread to a persistent UTF-8
`.txt` file. Keep the default file readable: preserve the conversation and mark
confirmed file reads where they occurred, without copying other tool activity
or tool results into it.

This skill is intentionally explicit-only because even a recovery transcript can
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

4. Tell the user that the recovery transcript is ready, link the file, and mention
   the optional full journal only after successful creation:

```markdown
Готово: стенограмма текущей ветки сохранена здесь:
[filename.txt](C:\absolute\path\filename.txt)

В ней сохранён разговор, а чтение файлов отмечено в соответствующих местах.
Если понадобится полный журнал команд и результатов инструментов, могу отдельно
сделать технический экспорт.
```

Do not ask the user to choose a variant before creating the recovery transcript.
Do not create a second file automatically.

## Recovery Transcript

The default export must:

- preserve user, assistant, and subagent messages in chronological order;
- preserve context-compaction markers;
- replace confirmed file-content reads with one short `FILE READ` or `FILES
  READ` marker at their chronological position between messages;
- collapse repeated chunk reads of the same path within one interval between
  messages, but show the path again if it is read in a later interval;
- omit every other tool call and every tool result, including commands, Call
  IDs, hashes, statuses, line ranges, and source-record metadata;
- keep the verified thread ID and source rollout path so a later full technical
  export can be created while that rollout still exists.

A file-read marker means that a supported operation accessed that file's
content and returned without a detected failure. It does not certify that every
line was read. Do not infer file reads from a path mention, directory listing,
write, patch, hash, or other non-content operation.

## Full Technical Export

Create a full technical export only after the user explicitly asks for the
full journal of commands and tool results:

```powershell
python "$env:USERPROFILE\.codex\skills\export-current-thread\scripts\export_current_thread.py" --full --json
```

The full export preserves supported invocation and textual result bodies. It
is an explicit follow-up artifact, not an automatic fallback for a long or
complex thread.

`--extract-call <CALL_ID>` remains available for a Call ID already known from a
full technical export or another verified source. Check `pair_complete` and
`missing_parts`, then delete temporary fragments with `--cleanup`.

## Shared Behavior

- Use `CODEX_THREAD_ID` as the current-thread source.
- Read only `$CODEX_HOME/sessions` or `%USERPROFILE%\.codex\sessions`, plus `archived_sessions` only when a requested thread is archived.
- Never edit, rewrite, normalize, or move original `rollout-*.jsonl` files.
- Save the `.txt` in the first active workspace root from the thread context.
- If no active workspace root is available, save the `.txt` on the user's Desktop.
- Use supported `response_item` records as the canonical source for messages,
  confirmed file reads, and full technical activity. Use only explicitly
  allowed non-duplicating `event_msg` metadata.
- Exclude system/developer messages, known Codex-injected user-content blocks,
  hidden reasoning, token telemetry, unknown internal record types, and
  explicitly typed binary content through deterministic code rules.
- Do not use a model to summarize, clean, reformat, select relevant fragments, redact heuristically, or deduplicate by textual similarity.
- Remove only structurally proven duplicate messages. In the recovery
  transcript, additionally collapse repeated paths only inside one uninterrupted
  file-reading interval between messages.
- Preserve large textual tool results only in the explicit full export or a
  requested single-call extraction. Replace known binary content with
  available type, size, MIME, path, URL, or identifier metadata.
- Write UTF-8 without BOM.

## Failure Handling

- If the current thread id is unavailable, do not guess. Tell the user that Codex did not expose `CODEX_THREAD_ID` and ask them to rerun from an active Codex thread or provide a thread id.
- If the rollout file cannot be found or verified, explain that the current thread log could not be matched.
- If the export succeeds, do not paste the transcript into chat; only link the generated file.
