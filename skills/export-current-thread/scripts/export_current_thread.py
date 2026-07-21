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
TECHNICAL_EVENT_FIELDS = {
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


def codex_home() -> Path:
    raw = os.environ.get("CODEX_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".codex"


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    invalid_line_count = 0
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                invalid_line_count += 1
                continue
            if isinstance(value, dict):
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


def message_body(payload: dict[str, Any]) -> tuple[str, int]:
    content = payload.get("content")
    if not isinstance(content, list):
        return render_value(content if content is not None else "")

    parts: list[str] = []
    removed = 0
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
                parts.append(text_value)
                continue
        text, count = render_value(item)
        parts.append(text)
        removed += count
    return "\n\n".join(parts), removed


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
    label = kind.upper()

    if kind == "message":
        role = str(payload.get("role") or "")
        if role not in {"user", "assistant"}:
            excluded[f"message_role:{role or 'unknown'}"] += 1
            return None
        label = "USER MESSAGE" if role == "user" else "ASSISTANT MESSAGE"
        attrs["message_id"] = payload.get("id")
        body, binary_count = message_body(payload)
    elif kind == "agent_message":
        label = "SUBAGENT MESSAGE"
        for key in ("id", "author", "recipient"):
            if payload.get(key) is not None:
                attrs[key] = payload[key]
        body, binary_count = message_body(payload)
    elif kind in {"custom_tool_call", "function_call"}:
        label = "TOOL CALL"
        for key in ("id", "call_id", "namespace", "name", "status"):
            if payload.get(key) is not None:
                attrs[key] = payload[key]
        argument_key = "input" if kind == "custom_tool_call" else "arguments"
        body, binary_count = render_value(payload.get(argument_key, ""))
    else:
        label = "TOOL RESULT"
        for key in ("id", "call_id"):
            if payload.get(key) is not None:
                attrs[key] = payload[key]
        body, binary_count = render_value(payload.get("output", ""))

    if binary_count:
        excluded["binary_content_blocks"] += binary_count
    return {
        "timestamp": timestamp,
        "label": label,
        "attrs": attrs,
        "body": body,
        "dedupe_key": event_key(kind, payload),
        "kind": kind,
    }


def technical_event(record: dict[str, Any]) -> dict[str, Any] | None:
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return None
    kind = str(payload.get("type") or "")
    fields = TECHNICAL_EVENT_FIELDS.get(kind)
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
) -> tuple[list[dict[str, Any]], Counter[str], Counter[str]]:
    events: list[dict[str, Any]] = []
    excluded: Counter[str] = Counter()
    included: Counter[str] = Counter()
    seen: set[tuple[str, str]] = set()

    for record in records:
        outer_type = record.get("type")
        event: dict[str, Any] | None = None
        if outer_type == "response_item":
            event = response_event(record, excluded)
        elif outer_type == "event_msg":
            event = technical_event(record)
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


def latest_turn_context(records: list[dict[str, Any]]) -> dict[str, Any]:
    allowed = (
        "turn_id",
        "cwd",
        "workspace_roots",
        "current_date",
        "timezone",
        "model",
        "collaboration_mode",
        "approval_policy",
    )
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
) -> str:
    lines = [
        "Codex observable work export",
        f"Thread ID: {thread_id}",
        f"Source: {rollout_path}",
        f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Events: {len(events)}",
        "Coverage: user and assistant messages, supported tool calls and full textual tool results, "
        "subagent messages, and selected technical events from the verified local rollout.",
        "Excluded by deterministic record type: system/developer messages, hidden reasoning, "
        "token telemetry, unknown internal records, and explicitly typed binary content.",
        "No model-based summarization, relevance filtering, or semantic deduplication was applied.",
        f"Unreadable JSONL lines skipped: {invalid_line_count}",
        f"Included record counts: {json.dumps(dict(included), ensure_ascii=False, sort_keys=True)}",
        f"Excluded record counts: {json.dumps(dict(excluded), ensure_ascii=False, sort_keys=True)}",
    ]
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

    events, included, excluded = collect_events(records)
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
        context=latest_turn_context(records),
    )
    output_path.write_text(content, encoding="utf-8", newline="\n")
    byte_count = output_path.stat().st_size
    char_count = len(content)
    return {
        "ok": True,
        "temporary": bool(args.temporary),
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
            "The export preserves supported observable work but deterministically excludes "
            "system/developer messages, hidden reasoning, unknown internal records, and typed binary content."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export observable work from the current Codex thread.")
    parser.add_argument("--thread-id", help="Thread id; defaults to CODEX_THREAD_ID.")
    parser.add_argument("--rollout", help="Specific rollout JSONL file to verify and read.")
    parser.add_argument("--output-dir", help="Persistent output directory override.")
    parser.add_argument("--temporary", action="store_true", help="Create a managed temporary export.")
    parser.add_argument("--cleanup", metavar="PATH", help="Delete one managed temporary export and exit.")
    parser.add_argument("--include-archived", action="store_true", help="Also search archived sessions.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable JSON result.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
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
