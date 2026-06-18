#!/usr/bin/env python3
"""Export the current Codex thread transcript to a text file."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def codex_home() -> Path:
    raw = os.environ.get("CODEX_HOME")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".codex"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                records.append(obj)
    return records


def read_session_meta_id(path: Path) -> str | None:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if obj.get("type") == "session_meta":
                    payload = obj.get("payload") or {}
                    value = payload.get("id")
                    return str(value) if value else None
                return None
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
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

    filename_matches = [p for p in candidates if thread_id in p.name]
    for path in sorted(filename_matches, key=lambda p: p.stat().st_mtime, reverse=True):
        if read_session_meta_id(path) == thread_id:
            return path

    for path in sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True):
        if read_session_meta_id(path) == thread_id:
            return path

    raise FileNotFoundError(f"Could not find a verified rollout file for thread id {thread_id}")


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
                text = clean_user_message(raw_text) if role == "USER" else raw_text.strip()
                if text:
                    event_messages.append(
                        {
                            "role": role,
                            "text": text,
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
                text = clean_user_message(text) if role == "USER" else text
                fallback_messages.append(
                    {
                        "role": role,
                        "text": text,
                        "timestamp": str(obj.get("timestamp") or ""),
                    }
                )

    if event_messages:
        return event_messages, "event_msg"
    return fallback_messages, "response_item"


def latest_payload(records: list[dict[str, Any]], record_type: str) -> dict[str, Any] | None:
    for obj in reversed(records):
        if obj.get("type") == record_type and isinstance(obj.get("payload"), dict):
            return obj["payload"]
    return None


def first_workspace_root(records: list[dict[str, Any]]) -> Path | None:
    payload = latest_payload(records, "turn_context")
    if not payload:
        return None

    roots = payload.get("workspace_roots")
    if isinstance(roots, list):
        for raw in roots:
            if isinstance(raw, str) and raw.strip():
                path = Path(raw).expanduser()
                if path.exists() and path.is_dir():
                    return path
    return None


def git_root_from_cwd(records: list[dict[str, Any]]) -> Path | None:
    payload = latest_payload(records, "turn_context") or latest_payload(records, "session_meta")
    raw_cwd = payload.get("cwd") if payload else None
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
    if not value:
        return None
    path = Path(value)
    return path if path.exists() and path.is_dir() else None


def desktop_dir() -> Path:
    desktop = Path.home() / "Desktop"
    if desktop.exists() and desktop.is_dir():
        return desktop
    return Path.home()


def output_dir_for(records: list[dict[str, Any]], explicit: str | None) -> tuple[Path, str]:
    if explicit:
        path = Path(explicit).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path, "explicit"

    workspace = first_workspace_root(records)
    if workspace:
        return workspace, "workspace_root"

    git_root = git_root_from_cwd(records)
    if git_root:
        return git_root, "git_root"

    return desktop_dir(), "desktop"


def safe_filename(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return value or "thread"


def build_export_text(
    *,
    thread_id: str,
    rollout_path: Path,
    output_location: str,
    messages: list[dict[str, str]],
    source_format: str,
) -> str:
    lines: list[str] = [
        "Codex thread export",
        f"Thread ID: {thread_id}",
        f"Source: {rollout_path}",
        f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Output location: {output_location}",
        f"Message source: {source_format}",
        f"Messages: {len(messages)}",
        "",
    ]

    for msg in messages:
        role = msg["role"]
        timestamp = msg.get("timestamp") or ""
        header = f"========== {role}"
        if timestamp:
            header += f" {timestamp}"
        header += " =========="
        lines.extend([header, "", msg["text"], ""])

    return "\n".join(lines)


def export_thread(args: argparse.Namespace) -> dict[str, Any]:
    thread_id = args.thread_id or os.environ.get("CODEX_THREAD_ID")
    if not thread_id:
        raise RuntimeError("CODEX_THREAD_ID is not available; cannot safely identify the current Codex thread.")

    rollout_path = Path(args.rollout).expanduser() if args.rollout else find_rollout(thread_id, args.include_archived)
    if not rollout_path.exists():
        raise FileNotFoundError(f"Rollout file does not exist: {rollout_path}")

    records = read_jsonl(rollout_path)
    if not records:
        raise RuntimeError(f"No readable JSONL records found in {rollout_path}")

    meta_id = read_session_meta_id(rollout_path)
    if meta_id and meta_id != thread_id:
        raise RuntimeError(f"Rollout id mismatch: expected {thread_id}, got {meta_id}")

    messages, source_format = collect_messages(records)
    if not messages:
        raise RuntimeError(f"No user or Codex messages found in {rollout_path}")

    out_dir, out_location = output_dir_for(records, args.output_dir)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"codex-thread-export-{safe_filename(thread_id)}-{timestamp}.txt"
    output_path = out_dir / filename

    content = build_export_text(
        thread_id=thread_id,
        rollout_path=rollout_path,
        output_location=out_location,
        messages=messages,
        source_format=source_format,
    )
    output_path.write_text(content, encoding="utf-8", newline="\n")

    user_count = sum(1 for msg in messages if msg["role"] == "USER")
    codex_count = sum(1 for msg in messages if msg["role"] == "CODEX")

    return {
        "ok": True,
        "thread_id": thread_id,
        "rollout_path": str(rollout_path),
        "output_path": str(output_path),
        "output_location": out_location,
        "message_source": source_format,
        "message_count": len(messages),
        "user_message_count": user_count,
        "codex_message_count": codex_count,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the current Codex thread to a txt file.")
    parser.add_argument("--thread-id", help="Thread id to export. Defaults to CODEX_THREAD_ID.")
    parser.add_argument("--rollout", help="Specific rollout-*.jsonl file to read.")
    parser.add_argument("--output-dir", help="Directory for the txt export.")
    parser.add_argument("--include-archived", action="store_true", help="Also search archived_sessions.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON result.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = export_thread(args)
    except Exception as exc:  # noqa: BLE001 - command-line tool should report concise failures.
        error = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(error, ensure_ascii=False, indent=2))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Exported current Codex thread to: {result['output_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
