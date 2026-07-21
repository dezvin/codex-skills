---
name: export-current-thread
description: Use this skill only when the user explicitly invokes $export-current-thread or directly asks to export/save the current Codex thread, conversation, chat, or session transcript as a local txt file. Do not invoke implicitly for ordinary logging, summaries, handoffs, or file exports that are not the current Codex thread.
---

# Export Current Thread

Export the observable work from the current Codex thread to a persistent UTF-8 `.txt` file. This skill is intentionally explicit-only because the export may contain private text, local paths, commands, and complete textual tool output.

## Procedure

1. Run the bundled script:

```powershell
python "$env:USERPROFILE\.codex\skills\export-current-thread\scripts\export_current_thread.py" --json
```

2. If `python` is unavailable but `py` exists, run:

```powershell
py "$env:USERPROFILE\.codex\skills\export-current-thread\scripts\export_current_thread.py" --json
```

3. Read the script result. It includes `ok`, `output_path`, `thread_id`, `rollout_path`, event counts, byte and character counts, and a deterministic token estimate. Do not read the generated file unless the user's request also requires analyzing it.

4. Answer the user in plain language: say that the export is ready and link the file path. Use this shape:

```markdown
Готово: экспорт текущей ветки сохранён здесь: [filename.txt](C:\absolute\path\filename.txt)
```

## Behavior

- Use `CODEX_THREAD_ID` as the current-thread source.
- Read only `$CODEX_HOME/sessions` or `%USERPROFILE%\.codex\sessions`, plus `archived_sessions` only when a requested thread is archived.
- Never edit, rewrite, normalize, or move original `rollout-*.jsonl` files.
- Save the `.txt` in the first active workspace root from the thread context.
- If no active workspace root is available, save the `.txt` on the user's Desktop.
- Preserve supported user and assistant messages, tool calls, full textual tool results, subagent messages, and selected technical events in chronological order.
- Use supported `response_item` records as the canonical source for messages and tool activity. Use only explicitly allowed non-duplicating `event_msg` metadata.
- Exclude system/developer messages, hidden reasoning, token telemetry, unknown internal record types, and explicitly typed binary content through deterministic code rules.
- Do not use a model to summarize, clean, reformat, select relevant fragments, redact heuristically, or deduplicate by textual similarity.
- Remove only structurally proven duplicates with the same event or call identifier. Preserve identical wording when it belongs to distinct events.
- Preserve large textual tool results in full. Replace known binary content with available type, size, MIME, path, URL, or identifier metadata.
- Write UTF-8 without BOM.

## Failure Handling

- If the current thread id is unavailable, do not guess. Tell the user that Codex did not expose `CODEX_THREAD_ID` and ask them to rerun from an active Codex thread or provide a thread id.
- If the rollout file cannot be found or verified, explain that the current thread log could not be matched.
- If the export succeeds, do not paste the transcript into chat; only link the generated file.
