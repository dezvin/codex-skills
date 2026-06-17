---
name: export-current-thread
description: Use this skill only when the user explicitly invokes $export-current-thread or directly asks to export/save the current Codex thread, conversation, chat, or session transcript as a local txt file. Do not invoke implicitly for ordinary logging, summaries, handoffs, or file exports that are not the current Codex thread.
---

# Export Current Thread

Export the current Codex thread transcript to a UTF-8 `.txt` file. This skill is intentionally explicit-only because thread exports may contain private text, local paths, commands, and tool output.

## Procedure

1. Run the bundled script:

```powershell
python "$env:USERPROFILE\.codex\skills\export-current-thread\scripts\export_current_thread.py" --json
```

2. If `python` is unavailable but `py` exists, run:

```powershell
py "$env:USERPROFILE\.codex\skills\export-current-thread\scripts\export_current_thread.py" --json
```

3. Read the script result. It includes `ok`, `output_path`, `thread_id`, `rollout_path`, and message counts.

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
- Prefer visible `event_msg` records. Use `response_item` messages only as a fallback when visible records are absent.
- Write UTF-8 without BOM.

## Failure Handling

- If the current thread id is unavailable, do not guess. Tell the user that Codex did not expose `CODEX_THREAD_ID` and ask them to rerun from an active Codex thread or provide a thread id.
- If the rollout file cannot be found or verified, explain that the current thread log could not be matched.
- If the export succeeds, do not paste the transcript into chat; only link the generated file.
