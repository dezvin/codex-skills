#!/usr/bin/env python3
"""Export observable Codex thread work without model-based preprocessing."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


EXPORT_PREFIX = "codex-thread-export-"
TEMP_SUBDIR = "codex-thread-exports"
ALLOWED_RESPONSE_ITEMS = {
    "message",
    "custom_tool_call",
    "custom_tool_call_output",
    "function_call",
    "function_call_output",
    "agent_message",
}
FULL_TECHNICAL_EVENT_FIELDS = {
    "task_started": ("turn_id", "started_at", "model_context_window"),
    "task_complete": (
        "turn_id",
        "started_at",
        "completed_at",
        "duration_ms",
        "time_to_first_token_ms",
    ),
    "context_compacted": (),
    "sub_agent_activity": (
        "event_id",
        "agent_path",
        "agent_thread_id",
        "kind",
        "occurred_at_ms",
    ),
}
COMPACT_TECHNICAL_EVENT_FIELDS = {
    "context_compacted": (),
}
BINARY_TYPES = {
    "audio",
    "blob",
    "computer_screenshot",
    "file",
    "image",
    "input_audio",
    "input_file",
    "input_image",
    "output_audio",
    "output_file",
    "output_image",
    "screenshot",
    "video",
}
BINARY_MIME_PREFIXES = ("image/", "audio/", "video/")
BINARY_MIME_TYPES = {"application/octet-stream"}
REFERENCE_KEYS = (
    "file_id",
    "id",
    "mime_type",
    "mimeType",
    "name",
    "path",
    "size",
    "url",
)
READ_PATH_KEYS = {
    "file",
    "file_path",
    "files",
    "path",
    "paths",
    "uri",
}
WINDOWS_PATH_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9_])([A-Z]:\\[^\"'`|<>\r\n;]+)"
)
FILE_URI_RE = re.compile(r"(?i)\b(file:///[^\s\"'`|<>]+)")
DIRECT_FILE_READ_TOOLS = {
    "open_file",
    "read_file",
    "read_text_file",
    "view_image",
}
SHELL_TOOLS = {"exec_command", "shell_command"}
INJECTED_USER_PART_PREFIXES = (
    "<recommended_plugins>",
    "# AGENTS.md instructions",
    "<environment_context>",
)


def codex_home() -> Path:
    raw = os.environ.get("CODEX_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".codex"


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    invalid_line_count = 0
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                invalid_line_count += 1
                continue
            if isinstance(value, dict):
                value["_source_line"] = line_number
                records.append(value)
            else:
                invalid_line_count += 1
    return records, invalid_line_count


def session_meta_id(records: list[dict[str, Any]]) -> str | None:
    for record in records:
        if record.get("type") != "session_meta":
            continue
        payload = record.get("payload")
        if isinstance(payload, dict) and payload.get("id"):
            return str(payload["id"])
    return None


def filename_thread_id(path: Path) -> str | None:
    match = re.search(
        r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
        path.name,
    )
    return match.group(1) if match else None


def verified_thread_id(path: Path, records: list[dict[str, Any]]) -> str | None:
    return session_meta_id(records) or filename_thread_id(path)


def rollout_roots(include_archived: bool) -> list[Path]:
    roots = [codex_home() / "sessions"]
    if include_archived:
        roots.append(codex_home() / "archived_sessions")
    return [root for root in roots if root.exists()]


def find_rollout(thread_id: str, include_archived: bool) -> Path:
    candidates: list[Path] = []
    for root in rollout_roots(include_archived):
        candidates.extend(root.rglob("rollout-*.jsonl"))

    ordered = sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)
    filename_matches = [path for path in ordered if filename_thread_id(path) == thread_id]
    remaining = [path for path in ordered if path not in filename_matches]
    for path in [*filename_matches, *remaining]:
        try:
            records, _ = read_jsonl(path)
        except (OSError, UnicodeDecodeError):
            continue
        if verified_thread_id(path, records) == thread_id:
            return path
    raise FileNotFoundError(f"Could not find a verified Codex rollout for thread id {thread_id}")


def is_binary_node(value: dict[str, Any]) -> bool:
    node_type = str(value.get("type") or "").lower()
    mime = str(value.get("mime_type") or value.get("mimeType") or "").lower()
    if node_type in BINARY_TYPES:
        return True
    return mime.startswith(BINARY_MIME_PREFIXES) or mime in BINARY_MIME_TYPES


def binary_placeholder(value: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"binary_content": "omitted"}
    if value.get("type"):
        result["type"] = value["type"]
    for key in REFERENCE_KEYS:
        if key in value and isinstance(value[key], (str, int, float, bool)):
            result[key] = value[key]
    return result


def sanitize_binary(value: Any) -> tuple[Any, int]:
    if isinstance(value, dict):
        if is_binary_node(value):
            return binary_placeholder(value), 1
        cleaned: dict[str, Any] = {}
        removed = 0
        for key, child in value.items():
            next_value, count = sanitize_binary(child)
            cleaned[key] = next_value
            removed += count
        return cleaned, removed
    if isinstance(value, list):
        cleaned_items: list[Any] = []
        removed = 0
        for child in value:
            next_value, count = sanitize_binary(child)
            cleaned_items.append(next_value)
            removed += count
        return cleaned_items, removed
    if isinstance(value, str):
        if re.match(r"^data:(?:image|audio|video)/[^;,]+;base64,", value, re.IGNORECASE):
            mime = value[5 : value.find(";")]
            return {"binary_content": "omitted", "mime_type": mime}, 1
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, (dict, list)):
                cleaned, removed = sanitize_binary(parsed)
                if removed:
                    return cleaned, removed
    return value, 0


def render_value(value: Any) -> tuple[str, int]:
    cleaned, removed = sanitize_binary(value)
    if isinstance(cleaned, str):
        return cleaned, removed
    return json.dumps(cleaned, ensure_ascii=False, indent=2, sort_keys=True), removed


def parse_json_string(value: str) -> Any | None:
    stripped = value.strip()
    if not stripped.startswith(("{", "[")):
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def normalize_path_literal(value: str) -> str:
    normalized = value.strip().strip("\"'").replace("\\\\", "\\")
    if os.name == "nt" and not normalized.lower().startswith("file:///"):
        normalized = normalized.replace("/", "\\")
    return normalized[4:] if normalized.startswith("\\\\?\\") else normalized


def tool_argument_value(kind: str, payload: dict[str, Any]) -> Any:
    key = "input" if kind == "custom_tool_call" else "arguments"
    raw = payload.get(key, "")
    if isinstance(raw, str):
        parsed = parse_json_string(raw)
        return parsed if parsed is not None else raw
    return raw


def structured_read_paths(value: Any, parent_key: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in READ_PATH_KEYS:
                if isinstance(child, str) and child.strip():
                    paths.append(normalize_path_literal(child))
                elif isinstance(child, list):
                    for item in child:
                        if isinstance(item, str) and item.strip():
                            paths.append(normalize_path_literal(item))
            paths.extend(structured_read_paths(child, lowered))
        return paths
    if isinstance(value, list):
        for child in value:
            paths.extend(structured_read_paths(child, parent_key))
        return paths
    if isinstance(value, str):
        parsed = parse_json_string(value)
        if parsed is not None:
            paths.extend(structured_read_paths(parsed, parent_key))
    return paths


def literal_path_mentions(text: str) -> set[str]:
    normalized = text.replace("\\\\", "\\")
    paths = {normalize_path_literal(match.group(1)) for match in WINDOWS_PATH_RE.finditer(normalized)}
    paths.update(match.group(1) for match in FILE_URI_RE.finditer(normalized))
    return {path.rstrip(" ,)") for path in paths if path}


def quoted_literal_at(text: str, start: int) -> tuple[str | None, int]:
    if start >= len(text) or text[start] not in {"'", '"'}:
        return None, start
    quote = text[start]
    escaped = False
    for index in range(start + 1, len(text)):
        char = text[index]
        if char == quote and not escaped:
            raw = text[start + 1 : index]
            decoded: list[str] = []
            position = 0
            escapes = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", "'": "'", '"': '"'}
            while position < len(raw):
                if raw[position] == "\\" and position + 1 < len(raw):
                    next_char = raw[position + 1]
                    if next_char in escapes:
                        decoded.append(escapes[next_char])
                        position += 2
                        continue
                decoded.append(raw[position])
                position += 1
            return "".join(decoded), index + 1
        escaped = char == "\\" and not escaped
        if char != "\\":
            escaped = False
    return None, start


def named_string_literals(text: str, key: str) -> list[str]:
    values: list[str] = []
    pattern = re.compile(rf"\b{re.escape(key)}\s*:\s*")
    for match in pattern.finditer(text):
        value, _ = quoted_literal_at(text, match.end())
        if value is not None:
            values.append(value)
    return values


def powershell_literal_variables(command: str) -> dict[str, str]:
    variables: dict[str, str] = {}
    literal_pattern = re.compile(
        r"\$(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<quote>['\"])(?P<value>.*?)(?P=quote)",
        re.DOTALL,
    )
    for match in literal_pattern.finditer(command):
        value = match.group("value")
        if match.group("quote") == "'":
            value = value.replace("''", "'")
        variables[match.group("name").casefold()] = normalize_path_literal(value)

    join_pattern = re.compile(
        r"\$(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*Join-Path\s+"
        r"(?P<base>\$[A-Za-z_][A-Za-z0-9_]*|['\"][^'\"]+['\"])\s+"
        r"(?P<child>['\"][^'\"]+['\"])",
        re.IGNORECASE,
    )
    for match in join_pattern.finditer(command):
        base = resolve_powershell_path(match.group("base"), variables)
        child = resolve_powershell_path(match.group("child"), variables)
        if base and child:
            variables[match.group("name").casefold()] = str(Path(base) / child)
    return variables


def resolve_powershell_path(expression: str, variables: dict[str, str]) -> str | None:
    value = expression.strip().rstrip(",")
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1].strip()
    else:
        value = value.rstrip(")")
    join_match = re.fullmatch(
        r"Join-Path\s+(?P<base>\$[A-Za-z_][A-Za-z0-9_]*|['\"][^'\"]+['\"])\s+"
        r"(?P<child>\$[A-Za-z_][A-Za-z0-9_]*|['\"][^'\"]+['\"])",
        value,
        re.IGNORECASE,
    )
    if join_match:
        base = resolve_powershell_path(join_match.group("base"), variables)
        child = resolve_powershell_path(join_match.group("child"), variables)
        return str(Path(base) / child) if base and child else None
    if re.fullmatch(r"\$[A-Za-z_][A-Za-z0-9_]*", value):
        resolved = variables.get(value[1:].casefold())
        if resolved and resolved.casefold().startswith("$env:"):
            return resolve_powershell_path(resolved, {})
        return resolved
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = normalize_path_literal(value[1:-1])
    env_match = re.match(r"(?i)^\$env:(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?P<rest>.*)$", value)
    if env_match:
        base = os.environ.get(env_match.group("name"))
        return normalize_path_literal(base + env_match.group("rest")) if base else None
    if not value:
        return None
    return normalize_path_literal(value)


def argument_after_flag(text: str, flag: str) -> str | None:
    match = re.search(rf"(?i)(?<!\w)-{re.escape(flag)}\b", text)
    if not match:
        return None
    index = match.end()
    while index < len(text) and text[index].isspace():
        index += 1
    if index >= len(text):
        return None
    if text[index] in {"'", '"'}:
        _, end = quoted_literal_at(text, index)
        return text[index:end] if end > index else None
    if text[index] == "(":
        depth = 0
        quote: str | None = None
        escaped = False
        for end in range(index, len(text)):
            char = text[end]
            if quote:
                if char == quote and not escaped:
                    quote = None
                escaped = char == "\\" and not escaped
                if char != "\\":
                    escaped = False
                continue
            if char in {"'", '"'}:
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return text[index : end + 1]
        return None
    end = index
    while end < len(text) and not text[end].isspace() and text[end] not in ";|,":
        end += 1
    return text[index:end] or None


def existing_file_path(value: str, workdir: str | None) -> bool:
    if value.lower().startswith("file:///"):
        return True
    candidate = Path(value).expanduser()
    if not candidate.is_absolute() and workdir:
        candidate = Path(workdir).expanduser() / candidate
    try:
        return candidate.is_file()
    except OSError:
        return False


def shell_read_paths(command: str, workdir: str | None) -> list[str]:
    variables = powershell_literal_variables(command)
    paths: list[str] = []
    content_pattern = re.compile(
        r"(?is)\b(?:Get-Content|Select-String|gc)\b(?P<args>[^;\r\n|]*)"
    )
    for match in content_pattern.finditer(command):
        args = match.group("args")
        expression = argument_after_flag(args, "LiteralPath") or argument_after_flag(args, "Path")
        if expression:
            path = resolve_powershell_path(expression, variables)
            if path:
                paths.append(path)

    positional_pattern = re.compile(r"(?im)(?:^|[;|]\s*)(?:type|more)\s+(?P<arg>[^\s;|]+)")
    for match in positional_pattern.finditer(command):
        path = resolve_powershell_path(match.group("arg"), variables)
        if path:
            paths.append(path)

    rg_pattern = re.compile(r"(?im)(?:^|[;|]\s*)rg\b(?P<args>[^;\r\n|]*)")
    for match in rg_pattern.finditer(command):
        args = match.group("args")
        if re.search(r"(?i)(?:^|\s)--files(?:\s|$)", args):
            continue
        candidates = list(literal_path_mentions(args))
        for variable in re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", args):
            resolved = resolve_powershell_path(variable, variables)
            if resolved:
                candidates.append(resolved)
        for quote_match in re.finditer(r"(['\"])(?P<value>.*?)(?:\1)", args):
            candidates.append(normalize_path_literal(quote_match.group("value")))
        paths.extend(path for path in candidates if existing_file_path(path, workdir))

    return paths


def nested_direct_read_paths(body: str) -> list[str]:
    paths: list[str] = []
    tool_pattern = re.compile(
        rf"\btools\.(?:{'|'.join(sorted(DIRECT_FILE_READ_TOOLS))})\s*\(",
        re.IGNORECASE,
    )
    for match in tool_pattern.finditer(body):
        end = body.find(");", match.end())
        segment = body[match.end() : end if end >= 0 else len(body)]
        for key in READ_PATH_KEYS:
            paths.extend(named_string_literals(segment, key))
    return paths


def file_read_paths(kind: str, payload: dict[str, Any], body: str) -> list[str]:
    tool_name = str(payload.get("name") or "").casefold()
    base_tool_name = tool_name.rsplit("__", 1)[-1].rsplit(".", 1)[-1]
    raw_value = tool_argument_value(kind, payload)
    paths: list[str] = []
    if base_tool_name in DIRECT_FILE_READ_TOOLS:
        paths.extend(structured_read_paths(raw_value))

    commands: list[str] = []
    workdir = extract_workdir(raw_value)
    if isinstance(raw_value, dict) and base_tool_name in SHELL_TOOLS:
        command = raw_value.get("command")
        if isinstance(command, str):
            commands.append(command)
    elif base_tool_name == "exec":
        commands.extend(named_string_literals(body, "command"))
        nested_workdirs = named_string_literals(body, "workdir")
        if nested_workdirs:
            workdir = normalize_path_literal(nested_workdirs[0])
        paths.extend(nested_direct_read_paths(body))

    for command in commands:
        paths.extend(shell_read_paths(command, workdir))

    unique: list[str] = []
    seen: set[str] = set()
    for path in paths:
        normalized = normalize_path_literal(path)
        if any(char in normalized for char in "*?["):
            continue
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            unique.append(normalized)
    return unique


def extract_workdir(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("workdir", "cwd"):
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                return normalize_path_literal(raw)
        for child in value.values():
            found = extract_workdir(child)
            if found:
                return found
        return None
    if isinstance(value, list):
        for child in value:
            found = extract_workdir(child)
            if found:
                return found
        return None
    if not isinstance(value, str):
        return None

    parsed = parse_json_string(value)
    if parsed is not None:
        found = extract_workdir(parsed)
        if found:
            return found

    match = re.search(
        r"\b(?:workdir|cwd)\s*:\s*([\"'])(?P<value>(?:\\.|(?!\1).)*)\1",
        value,
        re.DOTALL,
    )
    return normalize_path_literal(match.group("value")) if match else None


def text_fragments(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for child in value:
            result.extend(text_fragments(child))
        return result
    if isinstance(value, dict):
        result = []
        for key, child in value.items():
            if key in {"text", "output_text", "error", "message", "stderr", "stdout"}:
                result.extend(text_fragments(child))
            elif isinstance(child, (dict, list)):
                result.extend(text_fragments(child))
        return result
    return []


def boolean_ok(value: Any) -> bool | None:
    if isinstance(value, dict):
        if isinstance(value.get("ok"), bool):
            return value["ok"]
        for child in value.values():
            found = boolean_ok(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = boolean_ok(child)
            if found is not None:
                return found
    return None


def parse_result_status(body: str) -> tuple[str, int | None]:
    parsed = parse_json_string(body)
    searchable = "\n".join(text_fragments(parsed)) if parsed is not None else body
    exit_match = re.search(
        r"(?im)^(?:Exit code|Process exited with code):\s*(-?\d+)\s*$",
        searchable,
    )
    if exit_match:
        exit_code = int(exit_match.group(1))
        return ("success" if exit_code == 0 else "failure"), exit_code

    ok = boolean_ok(parsed)
    if ok is not None:
        return ("success" if ok else "failure"), None
    return "recorded", None


def confirmed_tool_results(records: list[dict[str, Any]]) -> dict[str, bool]:
    confirmed: dict[str, bool] = {}
    for record in records:
        if record.get("type") != "response_item":
            continue
        payload = record.get("payload")
        if not isinstance(payload, dict) or payload.get("type") not in {
            "custom_tool_call_output",
            "function_call_output",
        }:
            continue
        call_id = str(payload.get("call_id") or "")
        if not call_id:
            continue
        body, _ = render_value(payload.get("output", ""))
        status, _ = parse_result_status(body)
        if status != "failure":
            confirmed[call_id] = True
        else:
            confirmed.setdefault(call_id, False)
    return confirmed


def file_read_event(paths: list[str], timestamp: str) -> dict[str, Any]:
    if len(paths) == 1:
        label = "FILE READ"
        body = paths[0]
    else:
        label = "FILES READ"
        body = "\n".join(f"- {path}" for path in paths)
    return {
        "timestamp": timestamp,
        "label": label,
        "attrs": {},
        "body": body,
        "kind": "file_read_marker",
    }


def message_body(
    payload: dict[str, Any],
    *,
    omit_injected_user_parts: bool = False,
) -> tuple[str, int, int]:
    content = payload.get("content")
    if not isinstance(content, list):
        text, removed = render_value(content if content is not None else "")
        return text, removed, 0

    parts: list[str] = []
    removed = 0
    injected_removed = 0
    for item in content:
        if isinstance(item, dict):
            if is_binary_node(item):
                text, count = render_value(item)
                parts.append(text)
                removed += count
                continue
            text_value = item.get("text")
            if not isinstance(text_value, str):
                text_value = item.get("output_text")
            if isinstance(text_value, str):
                if omit_injected_user_parts and text_value.lstrip().startswith(INJECTED_USER_PART_PREFIXES):
                    injected_removed += 1
                    continue
                parts.append(text_value)
                continue
        text, count = render_value(item)
        parts.append(text)
        removed += count
    return "\n\n".join(parts), removed, injected_removed


def event_key(kind: str, payload: dict[str, Any]) -> tuple[str, str] | None:
    identifier = payload.get("id")
    if not identifier and kind in {
        "custom_tool_call",
        "custom_tool_call_output",
        "function_call",
        "function_call_output",
    }:
        identifier = payload.get("call_id")
    if identifier:
        return kind, str(identifier)
    return None


def response_event(
    record: dict[str, Any],
    excluded: Counter[str],
    *,
    full: bool,
) -> dict[str, Any] | None:
    payload = record.get("payload")
    if not isinstance(payload, dict):
        excluded["malformed_response_item"] += 1
        return None
    kind = str(payload.get("type") or "")
    if kind not in ALLOWED_RESPONSE_ITEMS:
        excluded[f"response_item:{kind or 'unknown'}"] += 1
        return None

    timestamp = str(record.get("timestamp") or "")
    attrs: dict[str, Any] = {}
    body = ""
    binary_count = 0
    injected_count = 0
    label = kind.upper()

    if kind == "message":
        role = str(payload.get("role") or "")
        if role not in {"user", "assistant"}:
            excluded[f"message_role:{role or 'unknown'}"] += 1
            return None
        label = "USER MESSAGE" if role == "user" else "ASSISTANT MESSAGE"
        if full:
            attrs["message_id"] = payload.get("id")
        body, binary_count, injected_count = message_body(
            payload,
            omit_injected_user_parts=role == "user",
        )
    elif kind == "agent_message":
        label = "SUBAGENT MESSAGE"
        keys = ("id", "author", "recipient") if full else ("author", "recipient")
        for key in keys:
            if payload.get(key) is not None:
                attrs[key] = payload[key]
        body, binary_count, injected_count = message_body(payload)
    elif kind in {"custom_tool_call", "function_call"}:
        label = "TOOL CALL"
        keys = ("id", "call_id", "namespace", "name", "status") if full else ("call_id", "namespace", "name")
        for key in keys:
            if payload.get(key) is not None:
                attrs[key] = payload[key]
        argument_key = "input" if kind == "custom_tool_call" else "arguments"
        body, binary_count = render_value(payload.get(argument_key, ""))
    else:
        label = "TOOL RESULT"
        keys = ("id", "call_id") if full else ("call_id",)
        for key in keys:
            if payload.get(key) is not None:
                attrs[key] = payload[key]
        body, binary_count = render_value(payload.get("output", ""))

    if binary_count:
        excluded["binary_content_blocks"] += binary_count
    if injected_count:
        excluded["injected_user_content_parts"] += injected_count
    if kind == "message" and not body.strip() and injected_count:
        excluded["empty_after_injected_content_removal"] += 1
        return None
    return {
        "timestamp": timestamp,
        "label": label,
        "attrs": attrs,
        "body": body,
        "dedupe_key": event_key(kind, payload),
        "kind": kind,
    }


def technical_event(record: dict[str, Any], *, full: bool) -> dict[str, Any] | None:
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return None
    kind = str(payload.get("type") or "")
    fields = (
        FULL_TECHNICAL_EVENT_FIELDS.get(kind)
        if full
        else COMPACT_TECHNICAL_EVENT_FIELDS.get(kind)
    )
    if fields is None:
        return None
    selected = {key: payload[key] for key in fields if payload.get(key) is not None}
    body = json.dumps(selected, ensure_ascii=False, indent=2, sort_keys=True) if selected else ""
    return {
        "timestamp": str(record.get("timestamp") or ""),
        "label": f"TECHNICAL EVENT: {kind}" if full else "CONTEXT COMPACTED",
        "attrs": {},
        "body": body,
        "dedupe_key": None,
        "kind": f"event_msg:{kind}",
    }


def collect_events(
    records: list[dict[str, Any]],
    *,
    full: bool,
) -> tuple[list[dict[str, Any]], Counter[str], Counter[str]]:
    if not full:
        return collect_transcript_events(records)

    events: list[dict[str, Any]] = []
    excluded: Counter[str] = Counter()
    included: Counter[str] = Counter()
    seen: set[tuple[str, str]] = set()

    for record in records:
        outer_type = record.get("type")
        event: dict[str, Any] | None = None
        if outer_type == "response_item":
            event = response_event(record, excluded, full=full)
        elif outer_type == "event_msg":
            event = technical_event(record, full=full)
            if event is None:
                payload = record.get("payload")
                kind = payload.get("type") if isinstance(payload, dict) else "unknown"
                excluded[f"event_msg:{kind}"] += 1
        elif outer_type not in {"session_meta", "turn_context"}:
            excluded[f"record:{outer_type or 'unknown'}"] += 1

        if event is None:
            continue
        key = event.pop("dedupe_key")
        if key is not None and key in seen:
            excluded["structural_duplicates"] += 1
            continue
        if key is not None:
            seen.add(key)
        included[event["kind"]] += 1
        events.append(event)
    return events, included, excluded


def collect_transcript_events(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], Counter[str], Counter[str]]:
    events: list[dict[str, Any]] = []
    excluded: Counter[str] = Counter()
    included: Counter[str] = Counter()
    seen: set[tuple[str, str]] = set()
    confirmed_results = confirmed_tool_results(records)
    pending_paths: list[str] = []
    pending_keys: set[str] = set()
    pending_timestamp = ""

    def flush_file_reads() -> None:
        nonlocal pending_timestamp
        if not pending_paths:
            return
        event = file_read_event(pending_paths.copy(), pending_timestamp)
        events.append(event)
        included[event["kind"]] += 1
        pending_paths.clear()
        pending_keys.clear()
        pending_timestamp = ""

    for record in records:
        outer_type = record.get("type")
        if outer_type == "response_item":
            payload = record.get("payload")
            if not isinstance(payload, dict):
                excluded["malformed_response_item"] += 1
                continue
            kind = str(payload.get("type") or "")
            if kind in {"custom_tool_call", "function_call"}:
                call_id = str(payload.get("call_id") or "")
                argument_key = "input" if kind == "custom_tool_call" else "arguments"
                body, binary_count = render_value(payload.get(argument_key, ""))
                if binary_count:
                    excluded["binary_content_blocks"] += binary_count
                paths = file_read_paths(kind, payload, body)
                if paths and confirmed_results.get(call_id, False):
                    if not pending_timestamp:
                        pending_timestamp = str(record.get("timestamp") or "")
                    for path in paths:
                        key = path.casefold()
                        if key not in pending_keys:
                            pending_keys.add(key)
                            pending_paths.append(path)
                    included["confirmed_file_read_call"] += 1
                elif paths:
                    excluded["unconfirmed_file_read_call"] += 1
                else:
                    excluded["non_file_read_tool_call"] += 1
                continue
            if kind in {"custom_tool_call_output", "function_call_output"}:
                excluded["tool_result"] += 1
                continue
            event = response_event(record, excluded, full=False)
        elif outer_type == "event_msg":
            event = technical_event(record, full=False)
            if event is None:
                payload = record.get("payload")
                kind = payload.get("type") if isinstance(payload, dict) else "unknown"
                excluded[f"event_msg:{kind}"] += 1
        elif outer_type in {"session_meta", "turn_context"}:
            continue
        else:
            excluded[f"record:{outer_type or 'unknown'}"] += 1
            continue

        if event is None:
            continue
        key = event.pop("dedupe_key")
        if key is not None and key in seen:
            excluded["structural_duplicates"] += 1
            continue
        if key is not None:
            seen.add(key)
        flush_file_reads()
        included[event["kind"]] += 1
        events.append(event)

    flush_file_reads()
    return events, included, excluded


def call_records(records: list[dict[str, Any]], call_id: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for record in records:
        if record.get("type") != "response_item":
            continue
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        if str(payload.get("call_id") or "") != call_id:
            continue
        if payload.get("type") in {
            "custom_tool_call",
            "custom_tool_call_output",
            "function_call",
            "function_call_output",
        }:
            matches.append(record)
    return matches


def call_pair_status(records: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    record_types = {
        str(record.get("payload", {}).get("type") or "")
        for record in records
        if isinstance(record.get("payload"), dict)
    }
    missing_parts: list[str] = []
    if not record_types.intersection({"custom_tool_call", "function_call"}):
        missing_parts.append("call")
    if not record_types.intersection({"custom_tool_call_output", "function_call_output"}):
        missing_parts.append("result")
    return not missing_parts, missing_parts


def collect_call_events(
    records: list[dict[str, Any]],
    call_id: str,
) -> tuple[list[dict[str, Any]], Counter[str], Counter[str], bool, list[str]]:
    selected = call_records(records, call_id)
    if not selected:
        raise RuntimeError(f"No supported tool call or result found for Call ID {call_id}")
    pair_complete, missing_parts = call_pair_status(selected)

    events: list[dict[str, Any]] = []
    included: Counter[str] = Counter()
    excluded: Counter[str] = Counter()
    for record in selected:
        event = response_event(record, excluded, full=True)
        if event is None:
            continue
        event.pop("dedupe_key", None)
        included[event["kind"]] += 1
        events.append(event)
    if not events:
        raise RuntimeError(f"No exportable tool details found for Call ID {call_id}")
    return events, included, excluded, pair_complete, missing_parts


def latest_turn_context(records: list[dict[str, Any]], *, full: bool = True) -> dict[str, Any]:
    del full  # Context stays minimal even in full exports; developer policy is never export data.
    allowed = ("cwd", "workspace_roots", "current_date", "timezone")
    for record in reversed(records):
        if record.get("type") != "turn_context" or not isinstance(record.get("payload"), dict):
            continue
        payload = record["payload"]
        return {key: payload[key] for key in allowed if payload.get(key) is not None}
    return {}


def first_workspace_root(records: list[dict[str, Any]]) -> Path | None:
    roots = latest_turn_context(records).get("workspace_roots")
    if isinstance(roots, list):
        for raw in roots:
            if isinstance(raw, str) and raw.strip():
                path = Path(raw).expanduser()
                if path.exists() and path.is_dir():
                    return path
    return None


def git_root_from_context(records: list[dict[str, Any]]) -> Path | None:
    raw_cwd = latest_turn_context(records).get("cwd")
    if not isinstance(raw_cwd, str) or not raw_cwd.strip():
        return None
    cwd = Path(raw_cwd).expanduser()
    if not cwd.exists():
        return None
    try:
        completed = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = completed.stdout.strip()
    path = Path(value) if value else None
    return path if path and path.exists() and path.is_dir() else None


def persistent_output_dir(records: list[dict[str, Any]], explicit: str | None) -> tuple[Path, str]:
    if explicit:
        path = Path(explicit).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path, "explicit"
    workspace = first_workspace_root(records)
    if workspace:
        return workspace, "workspace_root"
    git_root = git_root_from_context(records)
    if git_root:
        return git_root, "git_root"
    desktop = Path.home() / "Desktop"
    return (desktop if desktop.is_dir() else Path.home()), "desktop"


def temporary_output_dir() -> Path:
    path = Path(tempfile.gettempdir()) / TEMP_SUBDIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return cleaned or "thread"


def build_export_text(
    *,
    thread_id: str,
    rollout_path: Path,
    events: list[dict[str, Any]],
    included: Counter[str],
    excluded: Counter[str],
    invalid_line_count: int,
    context: dict[str, Any],
    full: bool,
    extracted_call_id: str | None = None,
    pair_complete: bool | None = None,
    missing_parts: list[str] | None = None,
) -> str:
    if not full:
        lines = [
            "Codex conversation recovery transcript",
            f"Thread ID: {thread_id}",
            f"Source: {rollout_path}",
            f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "Coverage: user, assistant, and subagent messages; context-compaction markers; "
            "and confirmed file reads placed where they occurred.",
            "Repeated chunk reads are collapsed only within the same interval between messages. "
            "Other tool calls and all tool results are omitted.",
            "System/developer messages, hidden reasoning, injected environment blocks, token telemetry, "
            "unknown internal records, and typed binary content are excluded.",
            "No model-based summarization, relevance filtering, or semantic rewriting was applied.",
        ]
        if invalid_line_count:
            lines.append(f"Warning: unreadable JSONL lines skipped: {invalid_line_count}")
        if context:
            lines.extend(
                [
                    "Latest observable thread context:",
                    json.dumps(context, ensure_ascii=False, indent=2, sort_keys=True),
                ]
            )
        lines.append("")
        for event in events:
            lines.append(f"[{event['label']}]")
            if event["body"]:
                lines.append(event["body"])
            lines.append("")
        return "\n".join(lines)

    if extracted_call_id:
        title = "Codex extracted tool records"
        coverage = f"the supported tool records matching Call ID {extracted_call_id}."
    elif full:
        title = "Codex full technical observable work export"
        coverage = (
            "user and assistant messages, supported tool calls and full textual tool results, "
            "subagent messages, and selected technical events from the verified local rollout."
        )
    lines = [
        title,
        f"Thread ID: {thread_id}",
        f"Source: {rollout_path}",
        f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Events: {len(events)}",
        f"Coverage: {coverage}",
        "Excluded by deterministic record type: system/developer messages, hidden reasoning, "
        "token telemetry, unknown internal records, and explicitly typed binary content.",
        "No model-based summarization, relevance filtering, or semantic deduplication was applied.",
        f"Unreadable JSONL lines skipped: {invalid_line_count}",
        f"Included record counts: {json.dumps(dict(included), ensure_ascii=False, sort_keys=True)}",
        f"Excluded record counts: {json.dumps(dict(excluded), ensure_ascii=False, sort_keys=True)}",
    ]
    if extracted_call_id:
        if pair_complete is None or missing_parts is None:
            raise RuntimeError("Extracted call metadata is incomplete")
        lines.extend(
            [
                f"pair_complete: {str(pair_complete).lower()}",
                f"missing_parts: {', '.join(missing_parts) if missing_parts else 'none'}",
            ]
        )
    if context:
        lines.extend(
            [
                "Latest observable thread context:",
                json.dumps(context, ensure_ascii=False, indent=2, sort_keys=True),
            ]
        )
    lines.append("")

    for index, event in enumerate(events, start=1):
        header = f"[{index:06d}]"
        if event["timestamp"]:
            header += f"[{event['timestamp']}]"
        header += f"[{event['label']}]"
        attrs = event["attrs"]
        if attrs:
            attr_text = " ".join(
                f"{key}={json.dumps(value, ensure_ascii=False)}"
                for key, value in attrs.items()
                if value is not None
            )
            if attr_text:
                header += f" {attr_text}"
        lines.extend([header, event["body"], ""])
    return "\n".join(lines)


def create_output_path(thread_id: str, temporary: bool, output_dir: Path) -> Path:
    if temporary:
        descriptor, raw_path = tempfile.mkstemp(
            prefix=EXPORT_PREFIX,
            suffix=".txt",
            dir=output_dir,
            text=True,
        )
        os.close(descriptor)
        return Path(raw_path)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return output_dir / f"{EXPORT_PREFIX}{safe_filename(thread_id)}-{timestamp}.txt"


def cleanup_export(raw_path: str) -> dict[str, Any]:
    path = Path(raw_path).expanduser().resolve()
    temp_root = temporary_output_dir().resolve()
    if path.parent != temp_root or not path.name.startswith(EXPORT_PREFIX) or path.suffix != ".txt":
        raise RuntimeError(f"Refusing to delete a path outside the managed temporary export directory: {path}")
    if not path.exists():
        return {"ok": True, "deleted": False, "output_path": str(path), "reason": "already_missing"}
    path.unlink()
    return {"ok": True, "deleted": True, "output_path": str(path)}


def export_thread(args: argparse.Namespace) -> dict[str, Any]:
    thread_id = args.thread_id or os.environ.get("CODEX_THREAD_ID")
    if not thread_id:
        raise RuntimeError("CODEX_THREAD_ID is unavailable; the current Codex thread cannot be identified safely")

    rollout_path = Path(args.rollout).expanduser() if args.rollout else find_rollout(thread_id, args.include_archived)
    if not rollout_path.exists():
        raise FileNotFoundError(f"Rollout file does not exist: {rollout_path}")
    records, invalid_line_count = read_jsonl(rollout_path)
    if not records:
        raise RuntimeError(f"No readable JSONL records found in {rollout_path}")
    record_thread_id = verified_thread_id(rollout_path, records)
    if record_thread_id != thread_id:
        raise RuntimeError(f"Rollout id mismatch: expected {thread_id}, got {record_thread_id or 'unverified'}")

    extracted_call_id = args.extract_call
    full = bool(args.full or extracted_call_id)
    pair_complete: bool | None = None
    missing_parts: list[str] | None = None
    if extracted_call_id:
        events, included, excluded, pair_complete, missing_parts = collect_call_events(records, extracted_call_id)
    else:
        events, included, excluded = collect_events(records, full=full)
    if not events:
        raise RuntimeError(f"No supported observable work events found in {rollout_path}")

    if args.temporary:
        if args.output_dir:
            raise RuntimeError("--output-dir cannot be combined with --temporary")
        out_dir = temporary_output_dir()
        out_location = "system_temp"
    else:
        out_dir, out_location = persistent_output_dir(records, args.output_dir)
    output_path = create_output_path(thread_id, args.temporary, out_dir)
    content = build_export_text(
        thread_id=thread_id,
        rollout_path=rollout_path,
        events=events,
        included=included,
        excluded=excluded,
        invalid_line_count=invalid_line_count,
        context=latest_turn_context(records, full=full),
        full=full,
        extracted_call_id=extracted_call_id,
        pair_complete=pair_complete,
        missing_parts=missing_parts,
    )
    output_path.write_text(content, encoding="utf-8", newline="\n")
    byte_count = output_path.stat().st_size
    char_count = len(content)
    result = {
        "ok": True,
        "temporary": bool(args.temporary),
        "export_kind": "call_details" if extracted_call_id else ("full" if full else "transcript"),
        "extracted_call_id": extracted_call_id,
        "thread_id": thread_id,
        "rollout_path": str(rollout_path),
        "output_path": str(output_path),
        "output_location": out_location,
        "event_count": len(events),
        "included_record_counts": dict(included),
        "excluded_record_counts": dict(excluded),
        "skipped_invalid_records": invalid_line_count,
        "byte_count": byte_count,
        "character_count": char_count,
        "estimated_token_count": math.ceil(char_count / 4),
        "coverage_warning": (
            (
                "The recovery transcript preserves messages and confirmed file-read markers in their "
                "chronological positions. Other tool calls and all tool results are omitted; request a full "
                "technical export when those details are required."
                if not full
                else "The export preserves supported observable work but deterministically excludes "
                "system/developer messages, hidden reasoning, unknown internal records, and typed binary content."
            )
        ),
    }
    if extracted_call_id:
        result["pair_complete"] = pair_complete
        result["missing_parts"] = missing_parts
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export observable work from the current Codex thread.")
    parser.add_argument("--thread-id", help="Thread id; defaults to CODEX_THREAD_ID.")
    parser.add_argument("--rollout", help="Specific rollout JSONL file to verify and read.")
    parser.add_argument("--output-dir", help="Persistent output directory override.")
    parser.add_argument("--temporary", action="store_true", help="Create a managed temporary export.")
    parser.add_argument("--cleanup", metavar="PATH", help="Delete one managed temporary export and exit.")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Include full sanitized tool invocation and result bodies instead of the default recovery transcript.",
    )
    parser.add_argument(
        "--extract-call",
        metavar="CALL_ID",
        help="Export supported sanitized tool records by Call ID and report whether the call/result pair is complete.",
    )
    parser.add_argument("--include-archived", action="store_true", help="Also search archived sessions.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable JSON result.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.cleanup and (args.full or args.extract_call):
            raise RuntimeError("--cleanup cannot be combined with --full or --extract-call")
        if args.full and args.extract_call:
            raise RuntimeError("--full cannot be combined with --extract-call")
        result = cleanup_export(args.cleanup) if args.cleanup else export_thread(args)
    except Exception as exc:  # noqa: BLE001 - CLI must return concise structured failures.
        error = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(error, ensure_ascii=False, indent=2))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result.get("output_path", "Done"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
