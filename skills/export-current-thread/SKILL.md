---
name: export-current-thread
description: Use this skill only when the user explicitly invokes $export-current-thread, /export-current-thread, or directly asks to export or save the current Codex thread or Antigravity conversation as a local txt file. Create a readable recovery transcript by default and offer a separate full command-and-result export only after the transcript is ready. Supports --with-thinking in Antigravity. Do not invoke implicitly for ordinary logging, summaries, handoffs, or unrelated file exports.
---

# Export Current Thread

Export the observable work from the current Codex thread or Antigravity conversation to a persistent UTF-8 `.txt` file. Keep the default file readable: preserve the conversation, context-compaction markers, and mark confirmed file/URL reads where they occurred, without copying other tool activity, thinking reasoning, or raw tool outputs into it.

This skill is intentionally explicit-only because even a recovery transcript can contain private text, local paths, and project information.

## Host Detection & Dual-Environment Support

The skill automatically detects its runtime environment via process environment variables:
- **Google Antigravity**: detected via `ANTIGRAVITY_CONVERSATION_ID` or `ANTIGRAVITY_AGENT`. Reads the conversation's canonical `transcript_full.jsonl` (or `transcript.jsonl`) under `~/.gemini/antigravity/brain/<id>/.system_generated/logs/`.
- **OpenAI Codex**: detected via `CODEX_THREAD_ID`. Discovers and merges verified session rollout files under `~/.codex/sessions/`.

## Procedure

1. Run the bundled script:

```powershell
python "<skill-directory>\scripts\export_current_thread.py" --json
```

Or run via the known platform paths:
- In Antigravity: `python "$env:USERPROFILE\.gemini\config\skills\export-current-thread\scripts\export_current_thread.py" --json`
- In Codex: `python "$env:USERPROFILE\.codex\skills\export-current-thread\scripts\export_current_thread.py" --json`

2. If `python` is unavailable but `py` exists, substitute `py`.

3. Read the script result. `ok` means only that the command completed. Check `coverage_status` separately, together with timestamps, `message_count`, `output_path`, event counts, and estimated token counts. Do not read the generated file into chat context unless the user explicitly asks to analyze it.

4. Link the generated file in chat using standard markdown with the `file:///` URI scheme:

```markdown
Готово: стенограмма текущей ветки сохранена здесь:
[filename.txt](file:///C:/absolute/path/filename.txt)

В ней сохранён разговор, а чтение файлов и URL отмечено в соответствующих местах.
Если понадобится полный журнал команд и результатов инструментов, могу отдельно
сделать технический экспорт.
```

Do not ask the user to choose a variant before creating the recovery transcript. Do not create a second file automatically.

If `coverage_status` is `partial_thread`, say that the created file is partial and name the unavailable candidates.

## Recovery Transcript (Default)

The default export must:

- preserve user, assistant, and subagent messages in chronological order;
- preserve context-compaction markers and their stored summary text;
- replace confirmed file-content reads with one short `FILE READ` or `FILES READ` marker at their chronological position between messages;
- replace confirmed URL reads with one short `URL READ` or `URLS READ` marker at their chronological position between messages;
- collapse repeated reads of the same file/URL within one uninterrupted interval between messages;
- omit every other tool call and raw tool output (commands, code patches, HTML dumps, console logs);
- omit model thinking reasoning blocks by default;
- exclude UI metadata injections (Antigravity's `<ADDITIONAL_METADATA>`, `<USER_SETTINGS_CHANGE>`, rules blocks; Codex's `<recommended_plugins>`, `<environment_context>`);
- save the `.txt` in the active workspace root (or Desktop if unavailable).

## Model Thinking Blocks (`--with-thinking`, Antigravity only)

When running under Antigravity and the user explicitly requests thinking reasoning blocks:

```powershell
python "<skill-directory>\scripts\export_current_thread.py" --with-thinking --json
```

This preserves model `[THINKING]` blocks alongside messages while still omitting raw tool execution payloads and noise. This flag is supported exclusively for Antigravity conversations.

## Full Technical Export (`--full`)

Create a full technical export only after the user explicitly asks for the full journal of commands and tool results:

```powershell
python "<skill-directory>\scripts\export_current_thread.py" --full --json
```

The full export preserves all supported tool calls, arguments, full textual tool results, thinking blocks, and technical events.

`--extract-call <CALL_ID>` remains available for Codex rollouts to inspect an isolated tool call and result pair.

## Shared Boundaries & Integrity

- Never edit, rewrite, normalize, or delete original log files (`transcript_full.jsonl`, `rollout-*.jsonl`).
- Do not use a model to summarize, clean, reformat, select relevant fragments, redact heuristically, or deduplicate by textual similarity. All filtering is 100% deterministic code.
- Write output UTF-8 without BOM with standard LF or system newlines.
- If the current thread/conversation ID cannot be identified, report an honest error and do not guess.
