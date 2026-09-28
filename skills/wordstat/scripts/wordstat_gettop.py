"""Official Yandex Wordstat REST GetTop adapter (no semantic collection policy).

Contract: https://aistudio.yandex.ru/ru/docs/search-api/api-ref/Wordstat/getTop
The configured price and capacity are dated external inputs, never API constants.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal

from .execution import ExecutionCore, Executor, OutcomeKind, RetryPolicy, TransportFailure
from .identity import fingerprint
from .models import (
    ParseResult, ParsedDiscoveryEdge, ParsedMeasurement, ParsedObservation,
    RawResponse, SemanticRequest, canonical_json, strict_json_object,
)


ENDPOINT = "https://searchapi.api.cloud.yandex.net/v2/wordstat/topRequests"
PARSER_VERSION = "yandex-wordstat-gettop-rest-v2"
ADAPTER_VERSION = "gettop-rest-v1"
_DEVICES = {"DEVICE_ALL", "DEVICE_DESKTOP", "DEVICE_PHONE", "DEVICE_TABLET"}
_MAX_INT64 = 2**63 - 1


@dataclass(frozen=True)
class GetTopCredentials:
    auth_type: str
    secret: str = field(repr=False)
    folder_id: str = field(repr=False)

    def __post_init__(self) -> None:
        if self.auth_type not in {"api_key", "iam_token"}:
            raise ValueError("auth_type must be api_key or iam_token")
        if not self.secret or not self.secret.strip() or not self.folder_id or not self.folder_id.strip():
            raise ValueError("GetTop requires a credential and folder ID")

    @classmethod
    def from_environment(cls, env: Mapping[str, str] | None = None) -> GetTopCredentials:
        env = os.environ if env is None else env
        api_key = env.get("WORDSTAT_API_KEY")
        iam_token = env.get("WORDSTAT_IAM_TOKEN")
        if bool(api_key) == bool(iam_token):
            raise ValueError("set exactly one Wordstat API key or IAM token")
        folder_id = env.get("WORDSTAT_FOLDER_ID")
        if not folder_id:
            raise ValueError("WORDSTAT_FOLDER_ID is required")
        return cls("api_key" if api_key else "iam_token", api_key or iam_token or "", folder_id)

    @property
    def account_context(self) -> str:
        # The actual folder ID is used on the wire but never enters the semantic descriptor.
        return "sha256:" + hashlib.sha256(self.folder_id.encode("utf-8")).hexdigest()

    @property
    def redactions(self) -> tuple[bytes, bytes]:
        return self.secret.encode("utf-8"), self.folder_id.encode("utf-8")


@dataclass(frozen=True)
class GetTopTariff:
    """Operator-supplied pricing snapshot for estimated cost, not actual billing."""

    price_per_1000: Decimal
    currency: str
    checked_on: date
    source_url: str

    def __post_init__(self) -> None:
        price = Decimal(str(self.price_per_1000))
        if (not price.is_finite() or price < 0 or not isinstance(self.checked_on, date)
                or not self.currency.strip() or not self.source_url.strip()):
            raise ValueError("invalid dated GetTop tariff")
        object.__setattr__(self, "price_per_1000", price)

    def estimate(self, request_count: int) -> Decimal:
        if isinstance(request_count, bool) or not isinstance(request_count, int) or request_count < 0:
            raise ValueError("request_count must be a nonnegative integer")
        return self.price_per_1000 * Decimal(request_count) / Decimal(1000)


def _count(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an int64 decimal")
    if isinstance(value, str):
        if not value or not value.isascii() or not value.isdecimal():
            raise ValueError(f"{name} must be an int64 decimal string")
        count = int(value)
    elif isinstance(value, int):
        count = value  # Some REST implementations may use a JSON integer.
    else:
        raise ValueError(f"{name} must be an int64 decimal")
    if not 0 <= count <= _MAX_INT64:
        raise ValueError(f"{name} is outside nonnegative int64")
    return count


def _phrase_rows(value: object, channel: str, origin: str) -> tuple[
    list[ParsedObservation], list[ParsedMeasurement], list[ParsedDiscoveryEdge]
]:
    if not isinstance(value, list):
        raise ValueError(f"{channel} must be a list")
    observations: list[ParsedObservation] = []
    measurements: list[ParsedMeasurement] = []
    edges: list[ParsedDiscoveryEdge] = []
    for rank, item in enumerate(value, start=1):
        if not isinstance(item, dict) or not isinstance(item.get("phrase"), str) or not item["phrase"].strip():
            raise ValueError(f"{channel}[{rank}] has no valid phrase")
        count = _count(item.get("count"), f"{channel}[{rank}].count")
        observations.append(ParsedObservation(item["phrase"], channel, rank))
        measurements.append(ParsedMeasurement(
            "wordstat_gettop_phrase_count", Decimal(count), "queries_last_30_days",
            rank - 1, canonical_json({"channel": channel, "count_json_type": type(item["count"]).__name__}),
        ))
        edges.append(ParsedDiscoveryEdge(rank - 1, "discovered_from", "semantic_request", origin))
    return observations, measurements, edges


def parse_gettop(raw: bytes, request: SemanticRequest) -> ParseResult:
    """Keep channels distinct; a count-only reply retains its measurement."""
    if request.provider != "yandex_wordstat" or request.operation != "GetTop":
        raise ValueError("wrong semantic request for GetTop parser")
    payload = strict_json_object(raw.decode("utf-8"))
    if payload == {}:
        return ParseResult("valid_empty")  # Observed live for rare GetTop requests.
    total = _count(payload.get("totalCount"), "totalCount")
    origin = fingerprint(request)
    # Live REST replies can omit both empty arrays while retaining totalCount.
    # Explicit null is still malformed; omission is not a measured zero count.
    result_obs, result_measure, result_edges = _phrase_rows(payload.get("results", []), "gettop.results", origin)
    assoc_obs, assoc_measure, assoc_edges = _phrase_rows(payload.get("associations", []), "gettop.associations", origin)
    offset = len(result_obs)
    associations_measure = [
        ParsedMeasurement(item.kind, item.value, item.unit, item.observation_index + offset,
                          item.context_json)
        for item in assoc_measure
    ]
    associations_edges = [
        ParsedDiscoveryEdge(item.observation_index + offset, item.relation,
                            item.origin_kind, item.origin_ref)
        for item in assoc_edges
    ]
    total_measure = ParsedMeasurement(
        "wordstat_gettop_total_count", Decimal(total), "queries_last_30_days",
        None, canonical_json({"basis": "contains_all_keywords_any_order",
                              "count_json_type": type(payload["totalCount"]).__name__}),
    )
    return ParseResult(
        "data", tuple(result_obs + assoc_obs),
        tuple([total_measure] + result_measure + associations_measure),
        tuple(result_edges + associations_edges),
    )


class GetTopAdapter:
    def __init__(
        self, credentials: GetTopCredentials, *, timeout_seconds: float = 15.0,
        transport: Callable[[urllib.request.Request, float], RawResponse] | None = None,
    ):
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.credentials = credentials
        self.timeout_seconds = timeout_seconds
        self.transport = transport or self._http_transport

    def semantic_request(
        self, phrase: str, *, num_phrases: int,
        regions: tuple[str, ...] = (), devices: tuple[str, ...] = (),
    ) -> SemanticRequest:
        if not isinstance(phrase, str) or not phrase.strip() or len(phrase) > 400:
            raise ValueError("GetTop phrase must contain 1–400 characters")
        if isinstance(num_phrases, bool) or not isinstance(num_phrases, int) or not 1 <= num_phrases <= 2000:
            raise ValueError("num_phrases must be 1–2000")
        if (isinstance(regions, str) or isinstance(devices, str)
                or len(regions) > 100 or len(devices) > 3
                or any(not isinstance(region, str) or not region.strip() for region in regions)
                or any(device not in _DEVICES for device in devices)):
            raise ValueError("invalid GetTop region/device filters")
        return SemanticRequest(
            "yandex_wordstat", "GetTop", "v2", ADAPTER_VERSION, phrase=phrase,
            regions=tuple(regions), devices=tuple(devices), result_limit=num_phrases,
            account_context=self.credentials.account_context,
        )

    def request_body(self, request: SemanticRequest) -> dict[str, object]:
        if (request.provider, request.operation, request.api_version, request.adapter_version) != (
            "yandex_wordstat", "GetTop", "v2", ADAPTER_VERSION,
        ) or request.account_context != self.credentials.account_context or request.schema_version != 1:
            raise ValueError("request does not belong to this GetTop adapter/context")
        if request.locale is not None or request.period is not None or request.from_date is not None \
                or request.to_date is not None or request.provider_options_json != "{}":
            raise ValueError("unsupported GetTop request field")
        if request.phrase is None or request.result_limit is None:
            raise ValueError("phrase and numPhrases must be explicit")
        # Validate persisted descriptors as well as newly built ones.
        self.semantic_request(request.phrase, num_phrases=request.result_limit,
                              regions=request.regions, devices=request.devices)
        body: dict[str, object] = {
            "phrase": request.phrase,
            "numPhrases": request.result_limit,
            "folderId": self.credentials.folder_id,
        }
        if request.regions:
            body["regions"] = list(request.regions)
        if request.devices:
            body["devices"] = list(request.devices)
        return body

    def send(self, request: SemanticRequest) -> RawResponse:
        payload = json.dumps(self.request_body(request), ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8")
        scheme = "Api-Key" if self.credentials.auth_type == "api_key" else "Bearer"
        wire_request = urllib.request.Request(
            ENDPOINT, data=payload, method="POST",
            headers={"Authorization": f"{scheme} {self.credentials.secret}",
                     "Content-Type": "application/json"},
        )
        return self.transport(wire_request, self.timeout_seconds)

    @staticmethod
    def _http_transport(request: urllib.request.Request, timeout: float) -> RawResponse:
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return RawResponse(
                    response.status, response.read(), dict(response.headers.items()),
                    datetime.now(timezone.utc).isoformat(),
                )
        except urllib.error.HTTPError as response:
            with response:
                return RawResponse(
                    response.code, response.read(), dict(response.headers.items()),
                    datetime.now(timezone.utc).isoformat(),
                )
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            # A timeout after sending a paid request is ambiguous without provider reconciliation.
            raise TransportFailure() from error

    def execute(
        self, core: ExecutionCore, run_id: str, logical_key: str, *,
        phrase: str, num_phrases: int, bucket_id: str,
        tariff: GetTopTariff, max_estimated_cost: Decimal,
        regions: tuple[str, ...] = (), devices: tuple[str, ...] = (),
        policy: RetryPolicy | None = None,
    ) -> tuple[str, OutcomeKind]:
        policy = policy or RetryPolicy()
        ceiling = Decimal(str(max_estimated_cost))
        if not ceiling.is_finite() or ceiling < 0:
            raise ValueError("max_estimated_cost must be nonnegative")
        if tariff.estimate(policy.max_attempts) > ceiling:
            raise ValueError("estimated GetTop retry ceiling exceeds allowed cost")
        request = self.semantic_request(
            phrase, num_phrases=num_phrases, regions=regions, devices=devices,
        )
        work_id = core.create_work(run_id, logical_key, request, bucket_id)
        outcome = Executor(core, policy=policy).execute(
            work_id, self.send, parse_gettop, parser_version=PARSER_VERSION,
            redactions=self.credentials.redactions,
        )
        return work_id, outcome
