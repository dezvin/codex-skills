#!/usr/bin/env python3
"""Validate and reversibly group native Codex search discoveries.

The helper is deliberately mechanical: it performs no network access, page
reading, relevance scoring, semantic deduplication, or evidence judgment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import unquote_plus, urlsplit


SCHEMA_VERSION = "1.0"
SEARCH_PURPOSES = {"primary", "repeat", "verify", "contrarian"}
TRACKING_KEYS = {
    "dclid",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "msclkid",
}
REQUIRED_FIELDS = {
    "research_question",
    "query",
    "search_purpose",
    "search_round",
    "search_surface",
    "search_outcome",
    "searched_at",
    "raw_url",
}
OPTIONAL_FIELDS = {
    "title_if_returned",
    "snippet_if_returned",
    "native_rank_if_returned",
    "resolved_url",
    "accepted_canonical_url",
    "metadata_if_returned",
}
ALLOWED_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS


class ValidationError(ValueError):
    """Raised when the explicit input package violates the helper contract."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_id(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def require_string(record: dict[str, Any], field: str, location: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{location}.{field} must be a non-empty string")
    return value


def validate_url(value: str, location: str) -> None:
    try:
        parts = urlsplit(value)
        _ = parts.port
    except ValueError as exc:
        raise ValidationError(f"{location} is not a valid URL: {exc}") from exc
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValidationError(f"{location} must be an absolute http or https URL")
    if parts.username is not None or parts.password is not None:
        raise ValidationError(f"{location} must not contain user credentials")


def remove_tracking_query(query: str) -> tuple[str, list[str]]:
    if not query:
        return "", []

    kept: list[str] = []
    removed: list[str] = []
    for segment in query.split("&"):
        encoded_key = segment.split("=", 1)[0]
        key = unquote_plus(encoded_key).lower()
        if key.startswith("utm_") or key in TRACKING_KEYS:
            removed.append(key)
        else:
            kept.append(segment)
    return "&".join(kept), removed


def normalize_url(value: str) -> dict[str, Any]:
    """Return a conservative working key and reversible mechanical reasons."""

    validate_url(value, "url")
    parts = urlsplit(value)
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower().rstrip(".")
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValidationError(f"url contains an invalid internationalized host: {exc}") from exc

    reasons = ["scheme_excluded_from_working_key"]
    if host.startswith("www."):
        host = host[4:]
        reasons.append("www_host_variant_removed")
    elif host.startswith("m."):
        host = host[2:]
        reasons.append("mobile_host_variant_removed")

    port = parts.port
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None
        reasons.append("default_port_removed")
    host_key = host if port is None else f"{host}:{port}"

    path = parts.path or "/"
    query, removed_tracking = remove_tracking_query(parts.query)
    if removed_tracking:
        reasons.append("tracking_parameters_removed")
    if parts.fragment:
        reasons.append("fragment_removed")

    working_key = f"{host_key}{path}"
    if query:
        working_key += f"?{query}"

    return {
        "working_url_key": working_key,
        "normalization_reasons": sorted(set(reasons)),
        "removed_tracking_parameters": sorted(set(removed_tracking)),
    }


def validate_discovery(raw: Any, index: int) -> dict[str, Any]:
    location = f"discoveries[{index}]"
    if not isinstance(raw, dict):
        raise ValidationError(f"{location} must be an object")

    missing = sorted(REQUIRED_FIELDS - raw.keys())
    unknown = sorted(raw.keys() - ALLOWED_FIELDS)
    if missing:
        raise ValidationError(f"{location} is missing required fields: {', '.join(missing)}")
    if unknown:
        raise ValidationError(f"{location} has unknown fields: {', '.join(unknown)}")

    record = dict(raw)
    for field in (
        "research_question",
        "query",
        "search_purpose",
        "search_surface",
        "search_outcome",
        "searched_at",
        "raw_url",
    ):
        require_string(record, field, location)

    if record["search_purpose"] not in SEARCH_PURPOSES:
        allowed = ", ".join(sorted(SEARCH_PURPOSES))
        raise ValidationError(f"{location}.search_purpose must be one of: {allowed}")
    if record["search_surface"] != "native_codex":
        raise ValidationError(f"{location}.search_surface must be 'native_codex' for this MVP helper")
    if isinstance(record["search_round"], bool) or not isinstance(record["search_round"], int):
        raise ValidationError(f"{location}.search_round must be an integer")
    if record["search_round"] < 1:
        raise ValidationError(f"{location}.search_round must be at least 1")

    validate_url(record["raw_url"], f"{location}.raw_url")

    for field in ("title_if_returned", "snippet_if_returned"):
        if field in record and not isinstance(record[field], str):
            raise ValidationError(f"{location}.{field} must be a string when supplied")
    if "native_rank_if_returned" in record:
        rank = record["native_rank_if_returned"]
        if isinstance(rank, bool) or not isinstance(rank, int) or rank < 1:
            raise ValidationError(f"{location}.native_rank_if_returned must be an integer >= 1")
    for field in ("resolved_url", "accepted_canonical_url"):
        if field in record:
            if not isinstance(record[field], str) or not record[field].strip():
                raise ValidationError(f"{location}.{field} must be a non-empty string when supplied")
            validate_url(record[field], f"{location}.{field}")
    if "metadata_if_returned" in record and not isinstance(record["metadata_if_returned"], dict):
        raise ValidationError(f"{location}.metadata_if_returned must be an object when supplied")

    return record


def attempt_basis(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "research_question": record["research_question"],
        "query": record["query"],
        "search_purpose": record["search_purpose"],
        "search_round": record["search_round"],
        "search_surface": record["search_surface"],
        "search_outcome": record["search_outcome"],
        "searched_at": record["searched_at"],
    }


def choose_group_target(record: dict[str, Any]) -> tuple[str, list[str], int]:
    if "accepted_canonical_url" in record:
        return record["accepted_canonical_url"], ["accepted_canonical_url_supplied"], 0
    if "resolved_url" in record:
        return record["resolved_url"], ["resolved_url_supplied"], 1
    scheme = urlsplit(record["raw_url"]).scheme.lower()
    return record["raw_url"], [], 2 if scheme == "https" else 3


def build_output(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValidationError("top-level input must be an object")
    unknown_top = sorted(payload.keys() - {"schema_version", "discoveries"})
    if unknown_top:
        raise ValidationError(f"top-level input has unknown fields: {', '.join(unknown_top)}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValidationError(f"schema_version must be '{SCHEMA_VERSION}'")
    discoveries = payload.get("discoveries")
    if not isinstance(discoveries, list):
        raise ValidationError("discoveries must be an array")

    validated = [validate_discovery(item, index) for index, item in enumerate(discoveries)]
    basis_counts = Counter(canonical_json(record) for record in validated)
    basis_seen: Counter[str] = Counter()

    records: list[dict[str, Any]] = []
    attempts_by_id: dict[str, dict[str, Any]] = {}
    groups: dict[str, dict[str, Any]] = {}

    for record in validated:
        attempt = attempt_basis(record)
        search_attempt_id = stable_id("sa", attempt)
        attempts_by_id[search_attempt_id] = {"search_attempt_id": search_attempt_id, **attempt}

        record_basis = canonical_json(record)
        basis_seen[record_basis] += 1
        occurrence = basis_seen[record_basis]
        discovery_base_id = stable_id("disc", record)
        discovery_id = f"{discovery_base_id}_{occurrence:03d}"

        target_url, relation_reasons, preference_rank = choose_group_target(record)
        normalized_target = normalize_url(target_url)
        normalized_raw = normalize_url(record["raw_url"])
        working_key = normalized_target["working_url_key"]
        document_id = stable_id("doc", working_key)

        reasons = set(relation_reasons)
        reasons.update(normalized_target["normalization_reasons"])
        if target_url != record["raw_url"]:
            reasons.add("explicit_target_used_for_grouping")
        if normalized_raw["working_url_key"] == working_key and target_url != record["raw_url"]:
            reasons.add("raw_and_explicit_target_share_working_key")

        output_record: dict[str, Any] = {
            "discovery_id": discovery_id,
            "search_attempt_id": search_attempt_id,
            "document_id": document_id,
            **record,
            "working_url_key": working_key,
            "group_target_url": target_url,
            "url_group_reasons": sorted(reasons),
        }
        if normalized_raw["removed_tracking_parameters"]:
            output_record["removed_tracking_parameters"] = normalized_raw[
                "removed_tracking_parameters"
            ]
        records.append(output_record)

        group = groups.setdefault(
            document_id,
            {
                "document_id": document_id,
                "working_url_key": working_key,
                "members": [],
                "url_group_reasons": set(),
                "preferred_candidates": [],
            },
        )
        group["members"].append(
            {
                "discovery_id": discovery_id,
                "search_attempt_id": search_attempt_id,
                "raw_url": record["raw_url"],
            }
        )
        group["url_group_reasons"].update(reasons)
        group["preferred_candidates"].append((preference_rank, target_url, discovery_id))

    finalized_groups: list[dict[str, Any]] = []
    for group in groups.values():
        candidates = sorted(group.pop("preferred_candidates"), key=lambda item: (item[0], item[1], item[2]))
        group["preferred_candidate_url"] = candidates[0][1]
        group["members"] = sorted(group["members"], key=lambda item: item["discovery_id"])
        reasons = set(group["url_group_reasons"])
        if len(group["members"]) > 1:
            reasons.add("multiple_discoveries_share_working_key")
        group["url_group_reasons"] = sorted(reasons)
        finalized_groups.append(group)

    duplicate_input_records = sum(count - 1 for count in basis_counts.values() if count > 1)
    return {
        "schema_version": SCHEMA_VERSION,
        "search_attempts": sorted(attempts_by_id.values(), key=lambda item: item["search_attempt_id"]),
        "records": sorted(records, key=lambda item: item["discovery_id"]),
        "url_groups": sorted(finalized_groups, key=lambda item: item["document_id"]),
        "stats": {
            "input_discoveries": len(validated),
            "distinct_search_attempts": len(attempts_by_id),
            "url_groups": len(finalized_groups),
            "exact_duplicate_input_records_preserved": duplicate_input_records,
        },
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and reversibly group native Codex search discoveries."
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="UTF-8 JSON input file. Omit to read JSON from stdin.",
    )
    parser.add_argument("--pretty", action="store_true", help="Indent JSON output.")
    return parser.parse_args(argv)


def read_payload(input_path: str | None) -> Any:
    if input_path:
        text = Path(input_path).read_text(encoding="utf-8-sig")
    else:
        text = sys.stdin.buffer.read().decode("utf-8-sig")
    if not text.strip():
        raise ValidationError("input JSON is empty")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(
            f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        output = build_output(read_payload(args.input))
    except (OSError, UnicodeError, ValidationError) as exc:
        error = {"error": "normalization_failed", "message": str(exc)}
        print(json.dumps(error, ensure_ascii=False), file=sys.stderr)
        return 2

    print(
        json.dumps(
            output,
            ensure_ascii=False,
            sort_keys=True,
            indent=2 if args.pretty else None,
            separators=None if args.pretty else (",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
