"""Typed semantic data contracts. Operational work belongs to roadmap stage 2."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Mapping


_SECRET_FIELD_PARTS = (
    "authorization", "apikey", "token", "secret", "password", "credential",
    "folderid", "cookie",
)


def _check_json_value(value: object, *, path: str = "") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        raise ValueError(f"floating provider option is not supported: {path}")
    if isinstance(value, list):
        for index, item in enumerate(value):
            _check_json_value(item, path=f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError(f"provider option key must be nonempty text: {path}")
            folded = "".join(char for char in key.casefold() if char.isalnum())
            if any(part in folded for part in _SECRET_FIELD_PARTS):
                raise ValueError(f"credential or account ID field is not allowed: {path}.{key}")
            _check_json_value(item, path=f"{path}.{key}")
        return
    raise ValueError(f"unsupported provider option type: {path}")


def canonical_json(value: object) -> str:
    _check_json_value(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def strict_json_object(raw: str) -> dict[str, object]:
    try:
        value = json.loads(raw, object_pairs_hook=_no_duplicate_keys)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("expected a JSON object") from error
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def _text(name: str, value: object, *, optional: bool = False) -> None:
    if optional and value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")


@dataclass(frozen=True)
class SemanticRequest:
    """Only result-affecting, nonsecret semantics; transport settings stay elsewhere.

    provider_options_json retains any provider-specific result options in the
    fingerprint. New top-level fields require an explicit contract change.
    """

    provider: str
    operation: str
    api_version: str
    adapter_version: str
    phrase: str | None = None
    regions: tuple[str, ...] = ()
    devices: tuple[str, ...] = ()
    locale: str | None = None
    period: str | None = None
    from_date: str | None = None
    to_date: str | None = None
    result_limit: int | None = None
    account_context: str | None = None
    provider_options_json: str = "{}"
    schema_version: int = 1

    def __post_init__(self) -> None:
        for name in ("provider", "operation", "api_version", "adapter_version"):
            _text(name, getattr(self, name))
        for name in ("phrase", "locale", "period", "from_date", "to_date"):
            _text(name, getattr(self, name), optional=True)
        for name in ("regions", "devices"):
            values = getattr(self, name)
            if isinstance(values, str):
                raise ValueError(f"{name} must be a sequence")
            values = tuple(values)
            for item in values:
                _text(name, item)
            object.__setattr__(self, name, values)
        if self.result_limit is not None and (
            isinstance(self.result_limit, bool)
            or not isinstance(self.result_limit, int)
            or self.result_limit <= 0
        ):
            raise ValueError("result_limit must be a positive integer")
        if isinstance(self.schema_version, bool) or not isinstance(self.schema_version, int) or self.schema_version <= 0:
            raise ValueError("schema_version must be a positive integer")
        if self.account_context is not None:
            _text("account_context", self.account_context)
            if not self.account_context.startswith(("alias:", "sha256:")):
                raise ValueError("account_context must be an alias or digest, not a raw account/folder ID")
        options = strict_json_object(self.provider_options_json)
        object.__setattr__(self, "provider_options_json", canonical_json(options))

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> SemanticRequest:
        allowed = {
            "provider", "operation", "api_version", "adapter_version", "phrase",
            "regions", "devices", "locale", "period", "from_date", "to_date",
            "result_limit", "account_context", "provider_options", "schema_version",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown semantic request fields: {sorted(unknown)}")
        missing = {"provider", "operation", "api_version", "adapter_version"} - set(value)
        if missing:
            raise ValueError(f"missing semantic request fields: {sorted(missing)}")
        options = value.get("provider_options", {})
        if not isinstance(options, dict):
            raise ValueError("provider_options must be an object")
        data = {key: item for key, item in value.items() if key != "provider_options"}
        data["provider_options_json"] = canonical_json(options)
        return cls(**data)  # type: ignore[arg-type]

    def descriptor(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "provider": self.provider,
            "operation": self.operation,
            "api_version": self.api_version,
            "adapter_version": self.adapter_version,
            "phrase": self.phrase,
            "regions": list(self.regions),
            "devices": list(self.devices),
            "locale": self.locale,
            "period": self.period,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "result_limit": self.result_limit,
            "account_context": self.account_context,
            "provider_options": json.loads(self.provider_options_json),
        }


@dataclass(frozen=True)
class RawResponse:
    status_code: int
    body: bytes
    headers: Mapping[str, str] = field(default_factory=dict)
    received_at_utc: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.status_code, bool) or not isinstance(self.status_code, int) or not 100 <= self.status_code <= 599:
            raise ValueError("status_code must be an HTTP status")
        if not isinstance(self.body, bytes):
            raise ValueError("body must be bytes")
        if not isinstance(self.headers, Mapping):
            raise ValueError("headers must be a mapping")
        _text("received_at_utc", self.received_at_utc, optional=True)
        if self.received_at_utc is not None:
            try:
                timestamp = datetime.fromisoformat(self.received_at_utc)
            except ValueError as error:
                raise ValueError("received_at_utc must be an ISO timestamp") from error
            if timestamp.utcoffset() != timedelta(0):
                raise ValueError("received_at_utc must include a UTC offset")


@dataclass(frozen=True)
class ParsedObservation:
    phrase: str
    channel: str
    rank: int | None = None

    def __post_init__(self) -> None:
        _text("phrase", self.phrase)
        _text("channel", self.channel)
        if self.rank is not None and (
            isinstance(self.rank, bool) or not isinstance(self.rank, int) or self.rank <= 0
        ):
            raise ValueError("rank must be a positive integer")


@dataclass(frozen=True)
class ParsedMeasurement:
    kind: str
    value: Decimal
    unit: str
    observation_index: int | None = None
    context_json: str = "{}"

    def __post_init__(self) -> None:
        _text("kind", self.kind)
        _text("unit", self.unit)
        if isinstance(self.value, bool):
            raise ValueError("measurement value cannot be boolean")
        try:
            decimal = Decimal(str(self.value))
        except (InvalidOperation, ValueError) as error:
            raise ValueError("measurement value must be decimal") from error
        if not decimal.is_finite():
            raise ValueError("measurement value must be finite")
        object.__setattr__(self, "value", decimal)
        if self.observation_index is not None and (
            isinstance(self.observation_index, bool)
            or not isinstance(self.observation_index, int)
            or self.observation_index < 0
        ):
            raise ValueError("observation_index must be nonnegative")
        context = strict_json_object(self.context_json)
        object.__setattr__(self, "context_json", canonical_json(context))


@dataclass(frozen=True)
class ParsedDiscoveryEdge:
    observation_index: int
    relation: str
    origin_kind: str
    origin_ref: str

    def __post_init__(self) -> None:
        if isinstance(self.observation_index, bool) or not isinstance(self.observation_index, int) or self.observation_index < 0:
            raise ValueError("observation_index must be nonnegative")
        for name in ("relation", "origin_kind", "origin_ref"):
            _text(name, getattr(self, name))


@dataclass(frozen=True)
class ParseResult:
    kind: str  # data or valid_empty; parser errors are exceptions, never empty.
    observations: tuple[ParsedObservation, ...] = ()
    measurements: tuple[ParsedMeasurement, ...] = ()
    discovery_edges: tuple[ParsedDiscoveryEdge, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in {"data", "valid_empty"}:
            raise ValueError("parse kind must be data or valid_empty")
        for name, expected in (
            ("observations", ParsedObservation),
            ("measurements", ParsedMeasurement),
            ("discovery_edges", ParsedDiscoveryEdge),
        ):
            values = tuple(getattr(self, name))
            if not all(isinstance(item, expected) for item in values):
                raise ValueError(f"{name} contains an invalid item")
            object.__setattr__(self, name, values)
        if self.kind == "valid_empty" and (self.observations or self.measurements or self.discovery_edges):
            raise ValueError("valid_empty cannot contain data")
        if self.kind == "data" and not (self.observations or self.measurements):
            raise ValueError("data result must contain an observation or measurement")
        size = len(self.observations)
        for item in (*self.measurements, *self.discovery_edges):
            index = item.observation_index
            if index is not None and index >= size:
                raise ValueError("observation_index is outside parsed observations")
