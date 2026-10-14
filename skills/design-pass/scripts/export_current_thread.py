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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPORT_PREFIX = "codex-thread-export-"
ANTIGRAVITY_EXPORT_PREFIX = "antigravity-conversation-export-"
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
    del path  # A filename is only a discovery hint, never proof of thread identity.
    return session_meta_id(records)


def rollout_roots(include_archived: bool) -> list[Path]:
    roots = [codex_home() / "sessions"]
    if include_archived:
        roots.append(codex_home() / "archived_sessions")
    return [root for root in roots if root.exists()]


def record_time_bounds(records: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    timestamps = [str(record["timestamp"]) for record in records if record.get("timestamp")]
    if not timestamps:
        return None, None
    return timestamps[0], timestamps[-1]


def timestamp_sort_value(value: str | None) -> float:
    if not value:
        return math.inf
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except ValueError:
        return math.inf


def candidate_failure(path: Path, reason: str, **details: Any) -> dict[str, Any]:
    failure: dict[str, Any] = {"path": str(path), "reason": reason}
    failure.update({key: value for key, value in details.items() if value is not None})
    return failure


def rollout_source(
    path: Path,
    records: list[dict[str, Any]],
    invalid_line_count: int,
) -> dict[str, Any]:
    first_timestamp, last_timestamp = record_time_bounds(records)
    return {
        "path": path,
        "records": records,
        "invalid_line_count": invalid_line_count,
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
    }


def discover_rollouts(
    thread_id: str,
    include_archived: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[Path] = []
    for root in rollout_roots(include_archived):
        candidates.extend(root.rglob("rollout-*.jsonl"))

    sources: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for path in sorted(set(candidates), key=lambda item: str(item).casefold()):
        filename_match = filename_thread_id(path) == thread_id
        try:
            records, invalid_line_count = read_jsonl(path)
        except (OSError, UnicodeDecodeError) as exc:
            if filename_match:
                failures.append(candidate_failure(path, "read_error", detail=str(exc)))
            continue

        internal_thread_id = session_meta_id(records)
        if internal_thread_id != thread_id:
            if filename_match:
                failures.append(
                    candidate_failure(
                        path,
                        "thread_id_mismatch" if internal_thread_id else "missing_session_meta_thread_id",
                        observed_thread_id=internal_thread_id,
                    )
                )
            continue

        if not records:
            failures.append(candidate_failure(path, "no_readable_records"))
            continue

        source = rollout_source(path, records, invalid_line_count)
        sources.append(source)
        if invalid_line_count:
            failures.append(
                candidate_failure(
                    path,
                    "unreadable_jsonl_lines",
                    invalid_line_count=invalid_line_count,
                )
            )
        if source["first_timestamp"] is None:
            failures.append(candidate_failure(path, "missing_event_timestamp"))

    if not sources:
        raise FileNotFoundError(f"Could not find a verified Codex rollout for thread id {thread_id}")

    sources.sort(
        key=lambda source: (
            timestamp_sort_value(source["first_timestamp"]),
            str(source["path"]).casefold(),
        )
    )
    return sources, failures


def load_explicit_rollout(
    path: Path,
    thread_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not path.exists():
        raise FileNotFoundError(f"Rollout file does not exist: {path}")
    records, invalid_line_count = read_jsonl(path)
    if not records:
        raise RuntimeError(f"No readable JSONL records found in {path}")
    internal_thread_id = verified_thread_id(path, records)
    if internal_thread_id != thread_id:
        raise RuntimeError(
            f"Rollout id mismatch: expected {thread_id}, got {internal_thread_id or 'unverified'}"
        )
    failures: list[dict[str, Any]] = []
    if invalid_line_count:
        failures.append(
            candidate_failure(
                path,
                "unreadable_jsonl_lines",
                invalid_line_count=invalid_line_count,
            )
        )
    return [rollout_source(path, records, invalid_line_count)], failures


def merge_rollout_records(
    sources: list[dict[str, Any]],
    replayed_user_records: set[tuple[str, int]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for source_index, source in enumerate(sources, start=1):
        source_path = str(source["path"])
        for record in source["records"]:
            annotated = dict(record)
            annotated["_source_rollout"] = source_path
            annotated["_source_rollout_index"] = source_index
            key = (source_path, int(record.get("_source_line") or 0))
            if key in replayed_user_records:
                annotated["_collapse_replayed_user"] = True
            merged.append(annotated)
    return merged


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


def message_turn_id(payload: dict[str, Any]) -> str | None:
    metadata = payload.get("internal_chat_message_metadata_passthrough")
    if not isinstance(metadata, dict) or not metadata.get("turn_id"):
        return None
    return str(metadata["turn_id"])


def canonical_replay_body(record: dict[str, Any]) -> str | None:
    payload = record.get("payload")
    if (
        record.get("type") != "response_item"
        or not isinstance(payload, dict)
        or payload.get("type") != "message"
        or payload.get("role") != "user"
    ):
        return None
    body, _, _ = message_body(payload, omit_injected_user_parts=True)
    normalized = body.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    return normalized if normalized else None


def substantive_user_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if canonical_replay_body(record) is not None]


def turn_is_structurally_unfinished(
    records: list[dict[str, Any]],
    user_record: dict[str, Any],
) -> bool:
    payload = user_record.get("payload")
    if not isinstance(payload, dict):
        return False
    turn_id = message_turn_id(payload)
    if not turn_id:
        return False

    try:
        user_index = records.index(user_record)
    except ValueError:
        return False

    turn_was_observed = False
    for record in records:
        record_payload = record.get("payload")
        if not isinstance(record_payload, dict):
            continue
        if str(record_payload.get("turn_id") or "") == turn_id and (
            record.get("type") == "turn_context"
            or (
                record.get("type") == "event_msg"
                and record_payload.get("type") == "task_started"
            )
        ):
            turn_was_observed = True
            break
    if not turn_was_observed:
        return False

    for record in records[user_index + 1 :]:
        record_payload = record.get("payload")
        if not isinstance(record_payload, dict):
            continue
        if record.get("type") != "response_item" or record_payload.get("type") != "message":
            continue
        role = record_payload.get("role")
        if role == "user" and canonical_replay_body(record) is not None:
            return False
        if role != "assistant":
            continue
        phase = str(record_payload.get("phase") or "")
        assistant_turn_id = message_turn_id(record_payload)
        if phase == "final_answer":
            return False
        if assistant_turn_id == turn_id and phase not in {"commentary"}:
            return False
    return True


def begins_with_replayed_user_message(
    records: list[dict[str, Any]],
    expected_body: str,
) -> dict[str, Any] | None:
    for record in records:
        payload = record.get("payload")
        if record.get("type") != "response_item" or not isinstance(payload, dict):
            continue
        if payload.get("type") != "message":
            continue
        role = payload.get("role")
        if role == "user":
            body = canonical_replay_body(record)
            if body is None:
                continue
            return record if body == expected_body else None
        if role == "assistant":
            return None
    return None


def proven_rollout_replays(
    sources: list[dict[str, Any]],
) -> set[tuple[str, int]]:
    replayed: set[tuple[str, int]] = set()
    for previous, current in zip(sources, sources[1:]):
        previous_users = substantive_user_records(previous["records"])
        if not previous_users:
            continue
        previous_user = previous_users[-1]
        previous_body = canonical_replay_body(previous_user)
        if previous_body is None or not turn_is_structurally_unfinished(
            previous["records"], previous_user
        ):
            continue

        current_user = begins_with_replayed_user_message(current["records"], previous_body)
        if current_user is None:
            continue
        previous_payload = previous_user.get("payload")
        current_payload = current_user.get("payload")
        if not isinstance(previous_payload, dict) or not isinstance(current_payload, dict):
            continue
        previous_turn_id = message_turn_id(previous_payload)
        current_turn_id = message_turn_id(current_payload)
        if not previous_turn_id or not current_turn_id or previous_turn_id == current_turn_id:
            continue
        current_turn_observed = any(
            isinstance(record.get("payload"), dict)
            and str(record["payload"].get("turn_id") or "") == current_turn_id
            and (
                record.get("type") == "turn_context"
                or (
                    record.get("type") == "event_msg"
                    and record["payload"].get("type") == "task_started"
                )
            )
            for record in current["records"]
        )
        if not current_turn_observed:
            continue

        replayed.add(
            (
                str(current["path"]),
                int(current_user.get("_source_line") or 0),
            )
        )
    return replayed


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
    if full:
        if record.get("_source_rollout"):
            attrs["source_rollout"] = record["_source_rollout"]
        if record.get("_source_line"):
            attrs["source_line"] = record["_source_line"]
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
    attrs: dict[str, Any] = {}
    if full:
        if record.get("_source_rollout"):
            attrs["source_rollout"] = record["_source_rollout"]
        if record.get("_source_line"):
            attrs["source_line"] = record["_source_line"]
    return {
        "timestamp": str(record.get("timestamp") or ""),
        "label": f"TECHNICAL EVENT: {kind}" if full else "CONTEXT COMPACTED",
        "attrs": attrs,
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
            if record.get("_collapse_replayed_user"):
                flush_file_reads()
                events.append(
                    {
                        "timestamp": str(record.get("timestamp") or ""),
                        "label": "ROLLOUT RESUMED",
                        "attrs": {},
                        "body": "",
                        "kind": "rollout_resumed_marker",
                    }
                )
                included["rollout_resumed_marker"] += 1
                excluded["proven_replayed_user_message"] += 1
                continue
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
    rollout_paths: list[Path],
    coverage_status: str,
    candidate_failures: list[dict[str, Any]],
    first_event_timestamp: str | None,
    last_event_timestamp: str | None,
    message_count: int,
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
    source_lines = [f"Sources ({len(rollout_paths)}):"]
    source_lines.extend(f"- {path}" for path in rollout_paths)
    coverage_lines = [
        f"Coverage status: {coverage_status}",
        f"Messages: {message_count}",
        f"First event timestamp: {first_event_timestamp or 'unavailable'}",
        f"Last event timestamp: {last_event_timestamp or 'unavailable'}",
        *source_lines,
    ]
    if candidate_failures:
        coverage_lines.extend(
            [
                f"Candidate failures ({len(candidate_failures)}):",
                json.dumps(candidate_failures, ensure_ascii=False, indent=2, sort_keys=True),
            ]
        )

    if not full:
        lines = [
            "Codex conversation recovery transcript",
            f"Thread ID: {thread_id}",
            *coverage_lines,
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
        *coverage_lines,
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
    allowed_prefix = path.name.startswith(EXPORT_PREFIX) or path.name.startswith(ANTIGRAVITY_EXPORT_PREFIX)
    if path.parent != temp_root or not allowed_prefix or path.suffix != ".txt":
        raise RuntimeError(f"Refusing to delete a path outside the managed temporary export directory: {path}")
    if not path.exists():
        return {"ok": True, "deleted": False, "output_path": str(path), "reason": "already_missing"}
    path.unlink()
    return {"ok": True, "deleted": True, "output_path": str(path)}


def export_thread(args: argparse.Namespace) -> dict[str, Any]:
    thread_id = args.thread_id or os.environ.get("CODEX_THREAD_ID")
    if not thread_id:
        raise RuntimeError("CODEX_THREAD_ID is unavailable; the current Codex thread cannot be identified safely")

    explicit_rollout = bool(args.rollout)
    if explicit_rollout:
        sources, candidate_failures = load_explicit_rollout(
            Path(args.rollout).expanduser(),
            thread_id,
        )
        coverage_status = "single_rollout"
    else:
        sources, candidate_failures = discover_rollouts(thread_id, args.include_archived)
        coverage_status = "partial_thread" if candidate_failures else "complete_thread"

    replayed_user_records = proven_rollout_replays(sources)
    records = merge_rollout_records(sources, replayed_user_records)
    if not records:
        raise RuntimeError("No readable JSONL records found in the verified rollout set")

    rollout_paths = [Path(source["path"]) for source in sources]
    invalid_line_count = sum(int(source["invalid_line_count"]) for source in sources)
    first_event_timestamp, last_event_timestamp = record_time_bounds(records)

    extracted_call_id = args.extract_call
    full = bool(args.full or extracted_call_id)
    pair_complete: bool | None = None
    missing_parts: list[str] | None = None
    if extracted_call_id:
        events, included, excluded, pair_complete, missing_parts = collect_call_events(records, extracted_call_id)
    else:
        events, included, excluded = collect_events(records, full=full)
    if not events:
        raise RuntimeError("No supported observable work events found in the verified rollout set")
    message_count = sum(event["kind"] in {"message", "agent_message"} for event in events)

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
        rollout_paths=rollout_paths,
        coverage_status=coverage_status,
        candidate_failures=candidate_failures,
        first_event_timestamp=first_event_timestamp,
        last_event_timestamp=last_event_timestamp,
        message_count=message_count,
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
        "coverage_status": coverage_status,
        "rollout_count": len(rollout_paths),
        "rollout_paths": [str(path) for path in rollout_paths],
        "rollout_path": str(rollout_paths[0]) if len(rollout_paths) == 1 else None,
        "candidate_failures": candidate_failures,
        "first_event_timestamp": first_event_timestamp,
        "last_event_timestamp": last_event_timestamp,
        "message_count": message_count,
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
            "The export is partial because one or more rollout candidates could not be read or included."
            if coverage_status == "partial_thread"
            else (
                "This export intentionally covers one explicitly selected rollout, not the complete thread."
                if coverage_status == "single_rollout"
                else (
                    "The recovery transcript preserves messages and confirmed file-read markers in their "
                    "chronological positions. Other tool calls and all tool results are omitted; request a full "
                    "technical export when those details are required."
                    if not full
                    else "The export preserves supported observable work but deterministically excludes "
                    "system/developer messages, hidden reasoning, unknown internal records, and typed binary content."
                )
            )
        ),
    }
    if extracted_call_id:
        result["pair_complete"] = pair_complete
        result["missing_parts"] = missing_parts
    return result



ANTIGRAVITY_EXPORT_PREFIX = "antigravity-conversation-export-"


def antigravity_app_data_dir() -> Path:
    raw = os.environ.get("ANTIGRAVITY_APP_DATA_DIR")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".gemini" / "antigravity"


def antigravity_conversation_id(args: argparse.Namespace) -> str | None:
    if args.thread_id:
        return args.thread_id
    return os.environ.get("ANTIGRAVITY_CONVERSATION_ID")


def discover_antigravity_log(conv_id: str) -> tuple[Path, bool]:
    log_dir = antigravity_app_data_dir() / "brain" / conv_id / ".system_generated" / "logs"
    full_log = log_dir / "transcript_full.jsonl"
    compact_log = log_dir / "transcript.jsonl"
    if full_log.exists():
        return full_log, True
    if compact_log.exists():
        return compact_log, False
    raise FileNotFoundError(f"No transcript found for Antigravity conversation {conv_id} in {log_dir}")


def extract_antigravity_user_request(text: str) -> tuple[str, str | None]:
    context_summary = None
    summary_match = re.search(r"<CONTEXT_SUMMARY>(.*?)</CONTEXT_SUMMARY>", text, re.DOTALL)
    if summary_match:
        context_summary = summary_match.group(1).strip()

    req_match = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", text, re.DOTALL)
    if req_match:
        return req_match.group(1).strip(), context_summary

    cleaned = text
    if summary_match:
        cleaned = cleaned.replace(summary_match.group(0), "")

    strip_tags = [
        "ADDITIONAL_METADATA",
        "USER_SETTINGS_CHANGE",
        "SUBAGENT_NOTIFICATION",
        "identity",
        "user_rules",
        "skills",
        "subagents",
        "artifacts",
        "conversation_transcript",
    ]
    for tag in strip_tags:
        cleaned = re.sub(rf"<{tag}>.*?</{tag}>", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"<RULE\[.*?\]>.*?</RULE\[.*?\]>", "", cleaned, flags=re.DOTALL)
    return cleaned.strip(), context_summary


def collect_antigravity_events(
    records: list[dict[str, Any]],
    *,
    with_thinking: bool,
    full: bool,
) -> tuple[list[dict[str, Any]], Counter[str], Counter[str]]:
    events: list[dict[str, Any]] = []
    included: Counter[str] = Counter()
    excluded: Counter[str] = Counter()

    pending_file_reads: list[str] = []
    pending_url_reads: list[str] = []

    def flush_reads() -> None:
        if pending_file_reads:
            seen: set[str] = set()
            unique_paths: list[str] = []
            for p in pending_file_reads:
                norm = normalize_path_literal(p)
                if norm not in seen:
                    seen.add(norm)
                    unique_paths.append(norm)
            if len(unique_paths) == 1:
                events.append({"label": "FILE READ", "body": unique_paths[0], "timestamp": None, "attrs": {}})
            else:
                events.append({"label": "FILES READ", "body": "\n".join(f"- {p}" for p in unique_paths), "timestamp": None, "attrs": {}})
            included["file_read_marker"] += len(unique_paths)
            pending_file_reads.clear()

        if pending_url_reads:
            seen_u: set[str] = set()
            unique_urls: list[str] = []
            for u in pending_url_reads:
                u_str = u.strip().strip("\"'")
                if u_str not in seen_u:
                    seen_u.add(u_str)
                    unique_urls.append(u_str)
            if len(unique_urls) == 1:
                events.append({"label": "URL READ", "body": unique_urls[0], "timestamp": None, "attrs": {}})
            else:
                events.append({"label": "URLS READ", "body": "\n".join(f"- {u}" for u in unique_urls), "timestamp": None, "attrs": {}})
            included["url_read_marker"] += len(unique_urls)
            pending_url_reads.clear()

    for data in records:
        step_idx = data.get("step_index")
        step_type = str(data.get("type") or "")
        created_at = str(data.get("created_at") or "")

        if full:
            if step_type == "USER_INPUT":
                raw = str(data.get("content") or "")
                _, summary = extract_antigravity_user_request(raw)
                if summary:
                    events.append({"label": "CONTEXT COMPACTED: SUMMARY", "body": summary, "timestamp": created_at, "attrs": {"step": step_idx}})
                    included["context_compacted"] += 1
                events.append({"label": "USER MESSAGE", "body": raw, "timestamp": created_at, "attrs": {"step": step_idx}})
                included["user_message"] += 1
            elif step_type == "PLANNER_RESPONSE":
                if data.get("thinking"):
                    events.append({"label": "THINKING", "body": str(data["thinking"]), "timestamp": created_at, "attrs": {"step": step_idx}})
                    included["thinking"] += 1
                for tc in data.get("tool_calls", []):
                    tc_name = tc.get("name")
                    events.append({
                        "label": f"TOOL CALL: {tc_name}",
                        "body": json.dumps(tc.get("args", {}), ensure_ascii=False, indent=2),
                        "timestamp": created_at,
                        "attrs": {"step": step_idx},
                    })
                    included[f"tool_call:{tc_name}"] += 1
                if data.get("content"):
                    events.append({"label": "ASSISTANT MESSAGE", "body": str(data["content"]), "timestamp": created_at, "attrs": {"step": step_idx}})
                    included["assistant_message"] += 1
            elif step_type == "GENERIC":
                events.append({"label": "TOOL RESULT", "body": str(data.get("content") or ""), "timestamp": created_at, "attrs": {"step": step_idx}})
                included["tool_result"] += 1
            elif step_type == "SYSTEM_MESSAGE":
                events.append({"label": "SYSTEM MESSAGE", "body": str(data.get("content") or ""), "timestamp": created_at, "attrs": {"step": step_idx}})
                included["system_message"] += 1
            elif step_type == "ERROR_MESSAGE":
                events.append({"label": "ERROR MESSAGE", "body": str(data.get("error") or ""), "timestamp": created_at, "attrs": {"step": step_idx}})
                included["error_message"] += 1
            else:
                excluded[f"step_type:{step_type}"] += 1
            continue

        # Default Recovery Transcript mode
        if step_type == "USER_INPUT":
            flush_reads()
            raw = str(data.get("content") or "")
            clean_req, summary = extract_antigravity_user_request(raw)
            if summary:
                events.append({"label": "CONTEXT COMPACTED: SUMMARY", "body": summary, "timestamp": created_at, "attrs": {}})
                included["context_compacted"] += 1
            if clean_req:
                events.append({"label": "USER MESSAGE", "body": clean_req, "timestamp": created_at, "attrs": {}})
                included["user_message"] += 1
            else:
                excluded["empty_user_message"] += 1

        elif step_type == "PLANNER_RESPONSE":
            for tc in data.get("tool_calls", []):
                name = tc.get("name")
                args = tc.get("args", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        pass
                if name == "view_file":
                    p = args.get("AbsolutePath") or args.get("path")
                    if p:
                        pending_file_reads.append(str(p))
                elif name == "read_url_content":
                    u = args.get("Url") or args.get("url")
                    if u:
                        pending_url_reads.append(str(u))
                else:
                    excluded[f"tool_call:{name}"] += 1

            if with_thinking and data.get("thinking"):
                flush_reads()
                events.append({"label": "THINKING", "body": str(data["thinking"]).strip(), "timestamp": created_at, "attrs": {}})
                included["thinking"] += 1

            if data.get("content") and str(data["content"]).strip():
                flush_reads()
                events.append({"label": "ASSISTANT MESSAGE", "body": str(data["content"]).strip(), "timestamp": created_at, "attrs": {}})
                included["assistant_message"] += 1

        elif step_type == "SYSTEM_MESSAGE":
            content = str(data.get("content") or "")
            match = re.search(r"sender=([^\s]+)", content)
            if match:
                sender = match.group(1)
                if "/task-" in sender or sender.lower() == "system":
                    excluded["system_message_noise"] += 1
                else:
                    flush_reads()
                    sub_match = re.search(r"content=(.*)", content, re.DOTALL)
                    sub_body = sub_match.group(1).strip() if sub_match else content
                    events.append({"label": f"SUBAGENT MESSAGE (sender: {sender})", "body": sub_body, "timestamp": created_at, "attrs": {}})
                    included["subagent_message"] += 1
            else:
                excluded["system_message_noise"] += 1
        else:
            excluded[f"step_type:{step_type}"] += 1

    flush_reads()
    return events, included, excluded


def build_antigravity_export_text(
    conv_id: str,
    log_path: Path,
    events: list[dict[str, Any]],
    included: Counter[str],
    excluded: Counter[str],
    *,
    with_thinking: bool,
    full: bool,
) -> str:
    timestamp_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message_count = sum(1 for ev in events if "MESSAGE" in ev["label"])

    first_ts = next((ev["timestamp"] for ev in events if ev.get("timestamp")), None)
    last_ts = next((ev["timestamp"] for ev in reversed(events) if ev.get("timestamp")), None)

    title = "Antigravity conversation full technical export" if full else "Antigravity conversation recovery transcript"
    lines = [
        title,
        f"Conversation ID: {conv_id}",
        "Coverage status: complete_conversation",
        f"Messages: {message_count}",
        f"First event timestamp: {first_ts or 'unavailable'}",
        f"Last event timestamp: {last_ts or 'unavailable'}",
        f"Source log: {log_path}",
        f"Exported: {timestamp_now}",
    ]
    if not full:
        lines.extend([
            "Coverage: user, assistant, and subagent messages; context-compaction markers; "
            "and confirmed file/URL reads placed where they occurred.",
            f"Thinking reasoning blocks: {'included' if with_thinking else 'omitted'}.",
            "Repeated chunk reads are collapsed only within the same interval between messages. "
            "Other tool calls and raw tool outputs are omitted.",
            "System messages, task manager notifications, and IDE UI metadata blocks are excluded.",
            "No model-based summarization, relevance filtering, or semantic rewriting was applied.",
            f"Included event counts: {json.dumps(dict(included), ensure_ascii=False, sort_keys=True)}",
            "",
        ])
        for ev in events:
            lines.append(f"[{ev['label']}]")
            if ev.get("body"):
                lines.append(ev["body"])
            lines.append("")
    else:
        lines.extend([
            f"Events: {len(events)}",
            "Coverage: user and assistant messages, model thinking, all tool calls, raw tool results, "
            "subagent messages, and system notifications.",
            f"Included event counts: {json.dumps(dict(included), ensure_ascii=False, sort_keys=True)}",
            f"Excluded event counts: {json.dumps(dict(excluded), ensure_ascii=False, sort_keys=True)}",
            "",
        ])
        for idx, ev in enumerate(events, start=1):
            ts = f"[{ev['timestamp']}]" if ev.get("timestamp") else ""
            header = f"[{idx:06d}]{ts}[{ev['label']}]"
            attrs = ev.get("attrs", {})
            if attrs:
                header += " " + " ".join(f"{k}={v}" for k, v in attrs.items())
            lines.extend([header, ev.get("body", ""), ""])

    return "\n".join(lines)


def antigravity_persistent_output_dir(override: str | None = None) -> tuple[Path, str]:
    if override:
        path = Path(override).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path, "custom_output_dir"
    cwd = Path.cwd().resolve()
    if cwd.is_dir():
        return cwd, "workspace_root"
    desktop = Path.home() / "Desktop"
    if desktop.is_dir():
        return desktop, "desktop"
    return temporary_output_dir(), "system_temp"


def create_antigravity_output_path(conv_id: str, temporary: bool, output_dir: Path) -> Path:
    if temporary:
        descriptor, raw_path = tempfile.mkstemp(
            prefix=ANTIGRAVITY_EXPORT_PREFIX,
            suffix=".txt",
            dir=output_dir,
            text=True,
        )
        os.close(descriptor)
        return Path(raw_path)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return output_dir / f"{ANTIGRAVITY_EXPORT_PREFIX}{safe_filename(conv_id)}-{timestamp}.txt"


def export_antigravity_conversation(args: argparse.Namespace) -> dict[str, Any]:
    conv_id = antigravity_conversation_id(args)
    if not conv_id:
        raise RuntimeError("ANTIGRAVITY_CONVERSATION_ID is unavailable; the current Antigravity conversation cannot be identified safely")

    log_path, _ = discover_antigravity_log(conv_id)
    records, invalid_line_count = read_jsonl(log_path)
    if not records:
        raise RuntimeError(f"No readable JSONL records found in Antigravity log: {log_path}")

    full = bool(args.full)
    with_thinking = bool(args.with_thinking)
    events, included, excluded = collect_antigravity_events(records, with_thinking=with_thinking, full=full)
    if not events:
        raise RuntimeError("No supported observable conversation events found in the Antigravity log")

    message_count = sum(1 for ev in events if "MESSAGE" in ev["label"])
    first_ts = next((ev["timestamp"] for ev in events if ev.get("timestamp")), None)
    last_ts = next((ev["timestamp"] for ev in reversed(events) if ev.get("timestamp")), None)

    if args.temporary:
        if args.output_dir:
            raise RuntimeError("--output-dir cannot be combined with --temporary")
        out_dir = temporary_output_dir()
        out_location = "system_temp"
    else:
        out_dir, out_location = antigravity_persistent_output_dir(args.output_dir)

    output_path = create_antigravity_output_path(conv_id, args.temporary, out_dir)
    content = build_antigravity_export_text(
        conv_id=conv_id,
        log_path=log_path,
        events=events,
        included=included,
        excluded=excluded,
        with_thinking=with_thinking,
        full=full,
    )
    output_path.write_text(content, encoding="utf-8", newline="\n")
    byte_count = output_path.stat().st_size
    char_count = len(content)

    export_kind = "full" if full else ("transcript_with_thinking" if with_thinking else "transcript")
    return {
        "ok": True,
        "host": "antigravity",
        "temporary": bool(args.temporary),
        "export_kind": export_kind,
        "thread_id": conv_id,
        "conversation_id": conv_id,
        "coverage_status": "complete_conversation",
        "log_path": str(log_path),
        "first_event_timestamp": first_ts,
        "last_event_timestamp": last_ts,
        "message_count": message_count,
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
            "The recovery transcript preserves user, assistant, and subagent messages, context-compaction markers, "
            "and confirmed file/URL reads in chronological order. Other tool calls and raw tool outputs are omitted; "
            "request a full technical export when those details are required."
            if not full
            else "The full technical export preserves user and assistant messages, model thinking, all tool calls, "
            "raw tool results, subagent messages, and system notifications from the verified log."
        ),
    }


def detect_host(args: argparse.Namespace) -> str:
    if args.rollout:
        return "codex"
    if args.thread_id:
        conv_dir = antigravity_app_data_dir() / "brain" / args.thread_id / ".system_generated" / "logs"
        if conv_dir.exists():
            return "antigravity"
        return "codex"
    if os.environ.get("ANTIGRAVITY_CONVERSATION_ID") or os.environ.get("ANTIGRAVITY_AGENT"):
        return "antigravity"
    if os.environ.get("CODEX_THREAD_ID"):
        return "codex"
    return "unknown"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export observable work from the current Codex thread or Antigravity conversation.")
    parser.add_argument("--thread-id", help="Thread/conversation id; defaults to CODEX_THREAD_ID or ANTIGRAVITY_CONVERSATION_ID.")
    parser.add_argument("--rollout", help="Specific rollout JSONL file to verify and read (Codex only).")
    parser.add_argument("--output-dir", help="Persistent output directory override.")
    parser.add_argument("--temporary", action="store_true", help="Create a managed temporary export.")
    parser.add_argument("--cleanup", metavar="PATH", help="Delete one managed temporary export and exit.")
    parser.add_argument(
        "--with-thinking",
        action="store_true",
        help="Include model thinking blocks in Antigravity recovery transcript (Antigravity only).",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Include full sanitized tool invocation and result bodies instead of the default recovery transcript.",
    )
    parser.add_argument(
        "--extract-call",
        metavar="CALL_ID",
        help="Export supported sanitized tool records by Call ID (Codex only) and report whether the call/result pair is complete.",
    )
    parser.add_argument("--include-archived", action="store_true", help="Also search archived sessions (Codex only).")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable JSON result.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.cleanup and (args.full or args.extract_call or args.with_thinking):
            raise RuntimeError("--cleanup cannot be combined with --full, --extract-call, or --with-thinking")
        if args.full and args.extract_call:
            raise RuntimeError("--full cannot be combined with --extract-call")
        if args.cleanup:
            result = cleanup_export(args.cleanup)
        else:
            host = detect_host(args)
            if host == "antigravity":
                if args.extract_call:
                    raise RuntimeError("--extract-call is supported only for Codex rollouts")
                if args.include_archived:
                    raise RuntimeError("--include-archived is supported only for Codex sessions")
                result = export_antigravity_conversation(args)
            elif host == "codex":
                if args.with_thinking:
                    raise RuntimeError("--with-thinking is supported only for Antigravity conversations")
                result = export_thread(args)
            else:
                raise RuntimeError(
                    "Neither ANTIGRAVITY_CONVERSATION_ID nor CODEX_THREAD_ID is available; "
                    "the current session cannot be identified safely."
                )
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
