#!/usr/bin/env python3
"""Export available user and Codex message text from a verified local task record."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


COVERAGE_WARNING = (
    "This export contains available user and Codex message text from the local task record. "
    "It may omit attachments, tool results, inspected files, and other runtime context."
)


def codex_home() -> Path:
    raw = os.environ.get("CODEX_HOME")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".codex"


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    invalid_line_count = 0
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                invalid_line_count += 1
                continue
            if isinstance(obj, dict):
                records.append(obj)
            else:
                invalid_line_count += 1
    return records, invalid_line_count


def session_meta_id(records: list[dict[str, Any]]) -> str | None:
    for obj in records:
        if obj.get("type") != "session_meta":
            continue
        payload = obj.get("payload") or {}
        value = payload.get("id")
        return str(value) if value else None
    return None


def rollout_roots(include_archived: bool) -> list[Path]:
    home = codex_home()
    roots = [home / "sessions"]
    if include_archived:
        roots.append(home / "archived_sessions")
    return [root for root in roots if root.exists()]


def find_rollout(thread_id: str, include_archived: bool) -> Path:
    candidates: list[Path] = []
    for root in rollout_roots(include_archived):
        candidates.extend(root.rglob("rollout-*.jsonl"))

    filename_matches = [path for path in candidates if thread_id in path.name]
    ordered = sorted(filename_matches, key=lambda path: path.stat().st_mtime, reverse=True)
    ordered.extend(
        path
        for path in sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)
        if path not in filename_matches
    )

    for path in ordered:
        try:
            records, _ = read_jsonl(path)
        except (OSError, UnicodeDecodeError):
            continue
        if session_meta_id(records) == thread_id:
            return path

    raise FileNotFoundError(f"Could not find a verified local task record for thread id {thread_id}")


def clean_user_message(text: str) -> str:
    marker = re.search(r"(?m)^## My request for Codex:\s*$", text)
    if marker:
        text = text[marker.end() :]
    return text.strip()


def collect_messages(records: list[dict[str, Any]]) -> tuple[list[dict[str, str]], str]:
    event_messages: list[dict[str, str]] = []
    fallback_messages: list[dict[str, str]] = []

    for obj in records:
        payload = obj.get("payload") or {}

        if obj.get("type") == "event_msg" and payload.get("type") in {"user_message", "agent_message"}:
            raw_text = payload.get("message")
            if isinstance(raw_text, str) and raw_text.strip():
                role = "USER" if payload.get("type") == "user_message" else "CODEX"
                value = clean_user_message(raw_text) if role == "USER" else raw_text.strip()
                if value:
                    event_messages.append(
                        {
                            "role": role,
                            "text": value,
                            "timestamp": str(obj.get("timestamp") or ""),
                        }
                    )

        if obj.get("type") == "response_item" and payload.get("type") == "message":
            role_value = payload.get("role")
            if role_value not in {"user", "assistant"}:
                continue
            parts: list[str] = []
            content = payload.get("content") or []
            if isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    value = item.get("text") or item.get("output_text")
                    if isinstance(value, str) and value.strip():
                        parts.append(value.strip())
            text = "\n".join(parts).strip()
            if text:
                role = "USER" if role_value == "user" else "CODEX"
                fallback_messages.append(
                    {
                        "role": role,
                        "text": clean_user_message(text) if role == "USER" else text,
                        "timestamp": str(obj.get("timestamp") or ""),
                    }
                )

    if event_messages:
        return event_messages, "event_msg"
    return fallback_messages, "response_item"


def output_dir_for(explicit: str | None) -> tuple[Path, str]:
    if explicit:
        path = Path(explicit).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path, "explicit"

    path = Path(tempfile.gettempdir()) / "codex-thread-exports"
    path.mkdir(parents=True, exist_ok=True)
    return path, "system_temp"


def build_export_text(
    *,
    messages: list[dict[str, str]],
    source_format: str,
    invalid_line_count: int,
) -> str:
    warning = COVERAGE_WARNING
    if invalid_line_count:
        warning += f" {invalid_line_count} unreadable record line(s) were skipped."

    lines: list[str] = [
        "Codex available message history export",
        f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Message source: {source_format}",
        f"Messages: {len(messages)}",
        f"Coverage: {warning}",
        "",
    ]

    for message in messages:
        header = f"========== {message['role']}"
        timestamp = message.get("timestamp") or ""
        if timestamp:
            header += f" {timestamp}"
        header += " =========="
        lines.extend([header, "", message["text"], ""])

    return "\n".join(lines)


def export_thread(args: argparse.Namespace) -> dict[str, Any]:
    thread_id = args.thread_id or os.environ.get("CODEX_THREAD_ID")
    if not thread_id:
        raise RuntimeError("CODEX_THREAD_ID is not available; cannot safely identify the current Codex task.")

    rollout_path = Path(args.rollout).expanduser() if args.rollout else find_rollout(thread_id, args.include_archived)
    if not rollout_path.exists():
        raise FileNotFoundError(f"Local task record does not exist: {rollout_path}")

    records, invalid_line_count = read_jsonl(rollout_path)
    if not records:
        raise RuntimeError(f"No readable JSONL records found in {rollout_path}")

    record_thread_id = session_meta_id(records)
    if not record_thread_id:
        raise RuntimeError("The local task record has no verifiable session metadata.")
    if record_thread_id != thread_id:
        raise RuntimeError(f"Task record id mismatch: expected {thread_id}, got {record_thread_id}")

    messages, source_format = collect_messages(records)
    if not messages:
        raise RuntimeError(f"No user or Codex messages found in {rollout_path}")

    out_dir, out_location = output_dir_for(args.output_dir)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    output_path = out_dir / f"codex-thread-export-{timestamp}.txt"
    content = build_export_text(
        messages=messages,
        source_format=source_format,
        invalid_line_count=invalid_line_count,
    )
    output_path.write_text(content, encoding="utf-8", newline="\n")

    user_count = sum(1 for message in messages if message["role"] == "USER")
    codex_count = sum(1 for message in messages if message["role"] == "CODEX")
    coverage_warning = COVERAGE_WARNING
    if invalid_line_count:
        coverage_warning += f" {invalid_line_count} unreadable record line(s) were skipped."

    return {
        "ok": True,
        "output_path": str(output_path),
        "output_location": out_location,
        "message_source": source_format,
        "message_count": len(messages),
        "user_message_count": user_count,
        "codex_message_count": codex_count,
        "skipped_invalid_records": invalid_line_count,
        "coverage_warning": coverage_warning,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export available Codex message history to a txt file.")
    parser.add_argument("--thread-id", help="Thread id to export. Defaults to CODEX_THREAD_ID.")
    parser.add_argument("--rollout", help="Specific verified rollout-*.jsonl file to read.")
    parser.add_argument("--output-dir", help="Explicit directory for the txt export. Defaults to system temp.")
    parser.add_argument("--include-archived", action="store_true", help="Also search archived sessions.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable JSON result.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = export_thread(args)
    except Exception as exc:  # noqa: BLE001 - CLI should return concise structured failures.
        error = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(error, ensure_ascii=False, indent=2))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Exported available Codex message history to: {result['output_path']}")
        print(result["coverage_warning"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
