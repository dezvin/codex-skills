#!/usr/bin/env python3
"""Export observable Codex thread work without model-based preprocessing."""

from __future__ import annotations

import argparse
import hashlib
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
PATH_KEYS = {
    "cwd",
    "directory",
    "file",
    "file_path",
    "files",
    "folder",
    "output_dir",
    "output_path",
    "path",
    "paths",
    "root",
    "uri",
    "url",
    "workdir",
    "workspace",
    "workspace_root",
    "workspace_roots",
}
PATCH_PATH_RE = re.compile(
    r"^\*\*\* (?:Add|Update|Delete) File: (?P<path>.+?)\s*$",
    re.MULTILINE,
)
WINDOWS_PATH_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9_])([A-Z]:\\[^\"'`|<>\r\n;]+)"
)
FILE_URI_RE = re.compile(r"(?i)\b(file:///[^\s\"'`|<>]+)")
NESTED_TOOL_RE = re.compile(r"\btools\.([A-Za-z_][A-Za-z0-9_]*)\s*\(")
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


def content_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_json_string(value: str) -> Any | None:
    stripped = value.strip()
    if not stripped.startswith(("{", "[")):
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def normalize_path_literal(value: str) -> str:
    return value.strip().strip("\"'").replace("\\\\", "\\")


def structured_targets(value: Any, parent_key: str = "") -> set[str]:
    targets: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered in PATH_KEYS:
                if isinstance(child, str) and child.strip():
                    targets.add(normalize_path_literal(child))
                elif isinstance(child, list):
                    for item in child:
                        if isinstance(item, str) and item.strip():
                            targets.add(normalize_path_literal(item))
            targets.update(structured_targets(child, lowered))
        return targets
    if isinstance(value, list):
        for child in value:
            targets.update(structured_targets(child, parent_key))
        return targets
    if isinstance(value, str):
        parsed = parse_json_string(value)
        if parsed is not None:
            targets.update(structured_targets(parsed, parent_key))
    return targets


def literal_path_mentions(text: str) -> set[str]:
    normalized = text.replace("\\\\", "\\")
    paths = {normalize_path_literal(match.group(1)) for match in WINDOWS_PATH_RE.finditer(normalized)}
    paths.update(match.group(1) for match in FILE_URI_RE.finditer(normalized))
    return {path.rstrip(" ,)") for path in paths if path}


def patch_targets(text: str) -> set[str]:
    return {
        normalize_path_literal(match.group("path"))
        for match in PATCH_PATH_RE.finditer(text)
        if match.group("path").strip()
    }


def nested_tool_names(text: str) -> list[str]:
    return list(dict.fromkeys(match.group(1) for match in NESTED_TOOL_RE.finditer(text)))


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


def tool_target_metadata(kind: str, payload: dict[str, Any], body: str) -> dict[str, Any]:
    tool_name = str(payload.get("name") or "")
    exact: set[str] = set()
    mentioned: set[str] = set()
    coverage = "unknown"

    argument_key = "input" if kind == "custom_tool_call" else "arguments"
    raw_value = payload.get(argument_key, "")
    exact.update(structured_targets(raw_value))
    mentioned.update(literal_path_mentions(body))

    if tool_name == "apply_patch":
        exact.update(patch_targets(body))
        coverage = "exact" if exact else "unknown"
    elif exact or mentioned:
        coverage = "partial"

    mentioned.difference_update(exact)
    return {
        "exact_targets": sorted(exact, key=str.casefold),
        "mentioned_paths": sorted(mentioned, key=str.casefold),
        "target_coverage": coverage,
        "workdir": extract_workdir(raw_value),
        "nested_tools": nested_tool_names(body),
    }


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


def compact_call_body(kind: str, payload: dict[str, Any], full_body: str, source_line: int | None) -> str:
    metadata = tool_target_metadata(kind, payload, full_body)
    lines: list[str] = []
    if metadata["nested_tools"]:
        lines.append(f"Underlying tools: {', '.join(metadata['nested_tools'])}")
    if metadata["workdir"]:
        lines.append(f"Working directory: {metadata['workdir']}")
    if metadata["exact_targets"]:
        lines.append("Exact targets:")
        lines.extend(f"- {path}" for path in metadata["exact_targets"])
    if metadata["mentioned_paths"]:
        lines.append("Mentioned paths:")
        lines.extend(f"- {path}" for path in metadata["mentioned_paths"])
    lines.extend(
        [
            f"Target coverage: {metadata['target_coverage']}",
            f"Invocation characters: {len(full_body)}",
            f"Invocation SHA-256: {content_digest(full_body)}",
        ]
    )
    if source_line is not None:
        lines.append(f"Source record: {source_line}")
    lines.append("Invocation content omitted from compact export.")
    return "\n".join(lines)


def compact_result_body(full_body: str, source_line: int | None) -> str:
    status, exit_code = parse_result_status(full_body)
    lines = [f"Result status: {status}"]
    if exit_code is not None:
        lines.append(f"Exit code: {exit_code}")
    lines.extend(
        [
            f"Result characters: {len(full_body)}",
            f"Result SHA-256: {content_digest(full_body)}",
        ]
    )
    if source_line is not None:
        lines.append(f"Source record: {source_line}")
    lines.append("Result content omitted from compact export.")
    return "\n".join(lines)


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
    source_line = record.get("_source_line")
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
        if not full:
            body = compact_call_body(kind, payload, body, source_line)
    else:
        label = "TOOL RESULT"
        keys = ("id", "call_id") if full else ("call_id",)
        for key in keys:
            if payload.get(key) is not None:
                attrs[key] = payload[key]
        body, binary_count = render_value(payload.get("output", ""))
        if not full:
            body = compact_result_body(body, source_line)

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
        "label": f"TECHNICAL EVENT: {kind}",
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
    extractor_path: Path,
    extracted_call_id: str | None = None,
    pair_complete: bool | None = None,
    missing_parts: list[str] | None = None,
) -> str:
    if extracted_call_id:
        title = "Codex extracted tool records"
        coverage = f"the supported tool records matching Call ID {extracted_call_id}."
    elif full:
        title = "Codex full technical observable work export"
        coverage = (
            "user and assistant messages, supported tool calls and full textual tool results, "
            "subagent messages, and selected technical events from the verified local rollout."
        )
    else:
        title = "Codex compact observable work export"
        coverage = (
            "user and assistant messages, compact tool traces, subagent messages, and context-compaction "
            "markers from the verified local rollout."
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
    if not full:
        lines.extend(
            [
                "Tool invocation bodies and result bodies are omitted from this compact export.",
                "Do not infer omitted details. Use Call ID to retrieve the matching supported tool records when needed.",
                f"Detail extractor: {extractor_path}",
                "Retrieval command:",
                f'python "{extractor_path}" --thread-id "{thread_id}" --extract-call "<call_id>" --temporary --json',
                "After reading the extracted fragment, delete it with the script's --cleanup command.",
                "If the source rollout is unavailable, inspect current authoritative files and project state. "
                "If that is insufficient, request a full command-and-result export.",
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
        extractor_path=Path(__file__).resolve(),
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
        "export_kind": "call_details" if extracted_call_id else ("full" if full else "compact"),
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
                "The compact export preserves messages and a verifiable tool trace while omitting invocation "
                "and result bodies; retrieve a specific Call ID or request a full command-and-result export "
                "when those details are required."
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
        help="Include full sanitized tool invocation and result bodies instead of the default compact trace.",
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
