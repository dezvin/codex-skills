#!/usr/bin/env python3
"""Check or install the bundled adaptive-research custom agents for Codex or Antigravity."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tomllib


EXPECTED_CODEX = {
    "research-worker.toml": ("research-worker", "gpt-6-luna"),
    "research-analyst.toml": ("research-analyst", "gpt-6-sol"),
    "research-escalation.toml": ("research-escalation", "gpt-5.6-sol"),
}

EXPECTED_ANTIGRAVITY = {
    "research-worker.md": (
        "research-worker",
        "flash",
        "eager",
        ["search_web", "read_url_content", "view_file", "run_command"],
    ),
    "research-analyst.md": (
        "research-analyst",
        "inherit",
        "off",
        ["read_url_content", "view_file"],
    ),
    "research-escalation.md": (
        "research-escalation",
        "pro",
        "off",
        ["read_url_content", "view_file"],
    ),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_host(requested: str) -> str:
    if requested in ("codex", "antigravity"):
        return requested
    if any(k.startswith("ANTIGRAVITY_") for k in os.environ):
        return "antigravity"
    return "codex"


def codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME", "").strip()
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def antigravity_home() -> Path:
    configured = os.environ.get("ANTIGRAVITY_CONFIG_HOME", "").strip()
    return (
        Path(configured).expanduser()
        if configured
        else Path.home() / ".gemini" / "config"
    )


def validate_codex_template(
    path: Path, expected_name: str, expected_model: str
) -> list[str]:
    errors: list[str] = []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        return [f"cannot parse UTF-8 TOML: {exc}"]

    for field in ("name", "description", "developer_instructions"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            errors.append(f"{field} must be a non-empty string")
    if data.get("name") != expected_name:
        errors.append(f"name must be {expected_name!r}")
    if data.get("model") != expected_model:
        errors.append(f"model must be {expected_model!r}")
    if data.get("sandbox_mode") != "read-only":
        errors.append("sandbox_mode must be 'read-only'")
    return errors


def parse_simple_frontmatter(text: str) -> tuple[dict[str, object], str] | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        return None

    meta: dict[str, object] = {}
    current_list_key: str | None = None
    for raw_line in lines[1:end_idx]:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current_list_key is not None:
            items = meta.setdefault(current_list_key, [])
            if isinstance(items, list):
                items.append(stripped[2:].strip().strip("\"'"))
            continue
        current_list_key = None
        if ":" not in stripped:
            return None
        key, val = stripped.split(":", 1)
        key = key.strip()
        val = val.strip()
        if not val:
            meta[key] = []
            current_list_key = key
        elif val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            meta[key] = (
                [item.strip().strip("\"'") for item in inner.split(",") if item.strip()]
                if inner
                else []
            )
        else:
            is_quoted = (val.startswith('"') and val.endswith('"')) or (
                val.startswith("'") and val.endswith("'")
            )
            if not is_quoted and ": " in val:
                return None
            meta[key] = val[1:-1] if is_quoted else val

    body = "\n".join(lines[end_idx + 1 :]).strip()
    return meta, body


def validate_antigravity_template(
    path: Path,
    expected_name: str,
    expected_model: str,
    expected_policy: str,
    expected_tools: list[str],
) -> list[str]:
    errors: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"cannot read UTF-8 Markdown: {exc}"]

    parsed = parse_simple_frontmatter(text)
    if parsed is None:
        return ["missing or invalid YAML frontmatter"]
    meta, body = parsed

    if not isinstance(meta.get("name"), str) or meta.get("name") != expected_name:
        errors.append(f"name must be {expected_name!r}")
    if not isinstance(meta.get("description"), str) or not str(meta["description"]).strip():
        errors.append("description must be a non-empty string")
    if meta.get("mainAgent") != "false":
        errors.append("mainAgent must be false")
    if meta.get("subagent") != "true":
        errors.append("subagent must be true")
    if meta.get("model") != expected_model:
        errors.append(f"model must be {expected_model!r}")
    if meta.get("commandExecutionPolicy") != expected_policy:
        errors.append(f"commandExecutionPolicy must be {expected_policy!r}")
    if meta.get("tools") != expected_tools:
        errors.append(f"tools must be {expected_tools!r}")
    if not body:
        errors.append("markdown body (system instructions) must be non-empty")
    return errors


def inspect(source_dir: Path, target_dir: Path, host: str) -> dict[str, object]:
    matching: list[str] = []
    missing: list[str] = []
    conflicts: list[str] = []
    invalid_sources: dict[str, list[str]] = {}
    source_bytes: dict[str, bytes] = {}

    filenames = (
        list(EXPECTED_ANTIGRAVITY.keys())
        if host == "antigravity"
        else list(EXPECTED_CODEX.keys())
    )

    for filename in filenames:
        source = source_dir / filename
        if not source.is_file():
            invalid_sources[filename] = ["bundled template is missing"]
            continue
        if host == "antigravity":
            exp_name, exp_model, exp_policy, exp_tools = EXPECTED_ANTIGRAVITY[filename]
            errors = validate_antigravity_template(
                source, exp_name, exp_model, exp_policy, exp_tools
            )
        else:
            exp_name, exp_model = EXPECTED_CODEX[filename]
            errors = validate_codex_template(source, exp_name, exp_model)
        if errors:
            invalid_sources[filename] = errors
            continue
        try:
            source_bytes[filename] = source.read_bytes()
        except OSError as exc:
            invalid_sources[filename] = [f"cannot read bundled template: {exc}"]
            continue

        target = target_dir / filename
        if not target.exists():
            missing.append(filename)
        elif not target.is_file():
            conflicts.append(filename)
        else:
            try:
                target_bytes = target.read_bytes()
            except OSError:
                conflicts.append(filename)
                continue
            if sha256(target_bytes) == sha256(source_bytes[filename]):
                matching.append(filename)
            else:
                conflicts.append(filename)

    if invalid_sources:
        status = "invalid_source"
    elif conflicts:
        status = "conflict"
    elif missing:
        status = "setup_required"
    else:
        status = "ready"

    return {
        "status": status,
        "host": host,
        "codex_home": str(target_dir.parent),
        "agent_home": str(target_dir.parent),
        "target_dir": str(target_dir),
        "matching": matching,
        "missing": missing,
        "conflicts": conflicts,
        "invalid_sources": invalid_sources,
        "source_bytes": source_bytes,
    }


def public_result(
    result: dict[str, object], installed: list[str] | None = None
) -> dict[str, object]:
    return {
        "status": result["status"],
        "host": result["host"],
        "codex_home": result["codex_home"],
        "agent_home": result["agent_home"],
        "target_dir": result["target_dir"],
        "matching": result["matching"],
        "missing": result["missing"],
        "conflicts": result["conflicts"],
        "invalid_sources": result["invalid_sources"],
        "installed": installed or [],
        "permission_required": result["status"] == "setup_required",
    }


def install_missing(
    source_dir: Path, target_dir: Path, before: dict[str, object], host: str
) -> tuple[dict[str, object], list[str]]:
    if before["status"] != "setup_required":
        return before, []

    target_dir_existed = target_dir.exists()
    target_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    try:
        source_bytes = before["source_bytes"]
        assert isinstance(source_bytes, dict)
        for filename in before["missing"]:
            assert isinstance(filename, str)
            target = target_dir / filename
            with target.open("xb") as handle:
                handle.write(source_bytes[filename])
                handle.flush()
                os.fsync(handle.fileno())
            created.append(target)
    except (OSError, KeyError) as exc:
        for path in reversed(created):
            try:
                path.unlink()
            except OSError:
                pass
        if not target_dir_existed:
            try:
                target_dir.rmdir()
            except OSError:
                pass
        raise RuntimeError(
            f"installation failed without overwriting existing files: {exc}"
        ) from exc

    after = inspect(source_dir, target_dir, host)
    installed = [path.name for path in created]
    if after["status"] != "ready":
        for path in reversed(created):
            try:
                path.unlink()
            except OSError:
                pass
        raise RuntimeError(
            "post-install verification failed; newly created files were rolled back"
        )
    return after, installed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Inspect without writing")
    mode.add_argument(
        "--install-missing", action="store_true", help="Install only absent bundled agents"
    )
    parser.add_argument(
        "--host",
        choices=("auto", "codex", "antigravity"),
        default="auto",
        help="Target host environment (default: auto)",
    )
    parser.add_argument(
        "--user-approved", action="store_true", help="Confirm explicit user permission"
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    return parser.parse_args()


def emit(payload: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload["status"])


def main() -> int:
    args = parse_args()
    host = detect_host(args.host)
    source_dir = Path(__file__).resolve().parent.parent / "assets" / "custom-agents"
    target_dir = (
        antigravity_home() / "agents" if host == "antigravity" else codex_home() / "agents"
    )
    before = inspect(source_dir, target_dir, host)

    if args.check:
        emit(public_result(before), args.json)
        return 2 if before["status"] == "invalid_source" else 0

    if not args.user_approved:
        payload = public_result(before)
        payload["error"] = "explicit user approval is required"
        emit(payload, args.json)
        return 3

    if before["status"] in {"conflict", "invalid_source"}:
        emit(public_result(before), args.json)
        return 2

    try:
        after, installed = install_missing(source_dir, target_dir, before, host)
    except RuntimeError as exc:
        payload = public_result(inspect(source_dir, target_dir, host))
        payload["error"] = str(exc)
        emit(payload, args.json)
        return 2

    emit(public_result(after, installed), args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
