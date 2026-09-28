"""Isolated Topvisor Tasks API boundary and durable bulk measurement workflow.

Topvisor never runs implicitly inside collect or compare. Paid submission
requires an explicit snapshot, verified price estimate, budget gate, and
durable local intent recorded before network dispatch.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from .execution import TransportFailure
from .models import (
    ParseResult, ParsedDiscoveryEdge, ParsedMeasurement, ParsedObservation,
    RawResponse, SemanticRequest, canonical_json, strict_json_object,
)
from .storage import DataStore


BASE_URL = "https://api.topvisor.com/v2/json"
PRICE_PATH = "/get/projects_2/tasks/volumes/price"
SUBMIT_PATH = "/add/projects_2/tasks/volumes"
TASKS_PATH = "/get/projects_2/tasks"
RESULTS_PATH = "/get/keywords_2/keywords"
REGIONS_PATH = "/get/system_2/common/regions"
TOPVISOR_ADAPTER_VERSION = "topvisor-tasks-v2"
TOPVISOR_PARSER_VERSION = "topvisor-keywords-v1"
YANDEX_FREQUENCY_TYPES = {
    1: "broad", 2: "quoted", 3: "quoted_fixed",
    5: "ordered", 6: "ordered_fixed",
}
_MAX_INT64 = 2**63 - 1


def _configured_opener() -> urllib.request.OpenerDirector | None:
    """Select the network route before dispatch; never retry a paid submit on route failure."""
    mode = os.environ.get("TOPVISOR_PROXY_MODE", "system").strip().lower()
    if mode == "system":
        return None
    if mode == "direct":
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))
    raise ValueError("TOPVISOR_PROXY_MODE must be system or direct")


class TopvisorProtocolError(ValueError):
    """The upstream response does not satisfy the checked contract."""


@dataclass(frozen=True)
class TopvisorCredentials:
    user_id: str = field(repr=False)
    api_key: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.user_id.strip() or not self.api_key.strip():
            raise ValueError("Topvisor user ID and API key are required")

    @classmethod
    def from_environment(cls, env: Mapping[str, str] | None = None) -> TopvisorCredentials:
        values = os.environ if env is None else env
        return cls(values.get("TOPVISOR_USER_ID", ""), values.get("TOPVISOR_API_KEY", ""))

    @property
    def account_context(self) -> str:
        return "sha256:" + hashlib.sha256(self.user_id.encode("utf-8")).hexdigest()

    @property
    def redactions(self) -> tuple[bytes, bytes]:
        return self.user_id.encode("utf-8"), self.api_key.encode("utf-8")


@dataclass(frozen=True)
class FrequencyQualifier:
    """One Yandex Wordstat frequency dimension in Topvisor Tasks."""

    region_key: int
    searcher_key: int
    frequency_type: int

    def __post_init__(self) -> None:
        for name in ("region_key", "searcher_key", "frequency_type"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.frequency_type not in YANDEX_FREQUENCY_TYPES:
            raise ValueError("unsupported Yandex frequency type")
        if self.searcher_key != 0:
            raise ValueError("Topvisor bulk Wordstat requires Yandex searcher_key=0")

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> FrequencyQualifier:
        if not isinstance(value, Mapping):
            raise ValueError("qualifier must be a mapping")
        allowed = {"region_key", "searcher_key", "type", "frequency_type"}
        if set(value) - allowed or ("type" in value and "frequency_type" in value):
            raise ValueError("invalid qualifier fields")
        freq_type = value.get("type", value.get("frequency_type"))
        return cls(
            int(value["region_key"]) if not isinstance(value.get("region_key"), bool) and isinstance(value.get("region_key"), int) else -1,
            int(value["searcher_key"]) if not isinstance(value.get("searcher_key"), bool) and isinstance(value.get("searcher_key"), int) else -1,
            int(freq_type) if not isinstance(freq_type, bool) and isinstance(freq_type, int) else -1,
        )

    def descriptor(self) -> dict[str, int]:
        return {
            "region_key": self.region_key,
            "searcher_key": self.searcher_key,
            "type": self.frequency_type,
        }


def _coerce_qualifier(item: FrequencyQualifier | Mapping[str, object]) -> FrequencyQualifier:
    if isinstance(item, FrequencyQualifier):
        return item
    return FrequencyQualifier.from_mapping(item)


def volume_payload(
    keywords: tuple[str, ...], qualifiers: tuple[FrequencyQualifier, ...],
) -> dict[str, object]:
    """Build the shared estimate/submit body without changing phrase spelling."""
    if not keywords or any(not isinstance(word, str) or not word.strip() for word in keywords):
        raise ValueError("nonempty keywords are required")
    if len(set(keywords)) != len(keywords):
        raise ValueError("duplicate keywords must be resolved before billing")
    if not qualifiers or len(set(qualifiers)) != len(qualifiers):
        raise ValueError("nonempty unique qualifiers are required")
    return {"keywords": list(keywords), "qualifiers": [item.descriptor() for item in qualifiers]}


def response_envelope(raw: bytes) -> dict[str, object]:
    """A 2xx HTTP response may still carry an API error or invalid payload."""
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TopvisorProtocolError("malformed Topvisor JSON") from error
    if not isinstance(value, dict):
        raise TopvisorProtocolError("Topvisor envelope must be an object")
    errors = value.get("errors")
    if errors is not None and not isinstance(errors, list):
        raise TopvisorProtocolError("Topvisor errors must be a list")
    if errors:
        raise TopvisorProtocolError("Topvisor API returned errors; inspect safe raw evidence")
    if "result" not in value or value["result"] is None:
        raise TopvisorProtocolError("Topvisor result is missing or null")
    return value


def _nonnegative_decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise TopvisorProtocolError(f"{label} must be a numeric or decimal string")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise TopvisorProtocolError(f"{label} is not a valid decimal") from error
    if not parsed.is_finite() or parsed < 0:
        raise TopvisorProtocolError(f"{label} must be a nonnegative finite decimal")
    return parsed


def _optional_utc_iso(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise TopvisorProtocolError("task_time_delete must be a string when present")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    elif " " in text and "T" not in text:
        text = text.replace(" ", "T", 1)
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as error:
        raise TopvisorProtocolError("task_time_delete is not a valid ISO timestamp") from error
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


def parse_price_estimate(raw: bytes) -> tuple[Decimal, str | None]:
    """Extract nonnegative monetary estimate and optional currency from price response."""
    result = response_envelope(raw)["result"]
    if isinstance(result, dict):
        currency = result.get("currency")
        if currency is not None and (not isinstance(currency, str) or not currency.strip()):
            raise TopvisorProtocolError("price currency must be nonempty text")
        for key in ("price", "sum", "total", "cost"):
            if key in result and result[key] is not None:
                return _nonnegative_decimal(result[key], f"result.{key}"), (
                    currency.strip() if isinstance(currency, str) else None
                )
        raise TopvisorProtocolError("price object does not contain a recognized price field")
    return _nonnegative_decimal(result, "result"), None


def _positive_task_id(value: object) -> int:
    if isinstance(value, bool):
        raise TopvisorProtocolError("task ID must be a positive integer")
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        value = int(value)
    if not isinstance(value, int) or value <= 0:
        raise TopvisorProtocolError("task ID must be a positive integer")
    return value


def parse_submitted_task(raw: bytes) -> tuple[int, str | None]:
    """Extract remote task ID and optional task_time_delete from submit response."""
    result = response_envelope(raw)["result"]
    if isinstance(result, list):
        if len(result) != 1:
            raise TopvisorProtocolError("submit result list must contain exactly one task entry")
        result = result[0]
    if isinstance(result, dict):
        raw_id = result.get("id", result.get("task_id"))
        task_id = _positive_task_id(raw_id)
        expires_at = _optional_utc_iso(result.get("task_time_delete"))
        return task_id, expires_at
    return _positive_task_id(result), None


def parse_task_entry(raw: bytes, task_id: int | None = None) -> tuple[int, str, int | str | None] | None:
    """Find an explicitly identified task; an account list cannot establish ownership."""
    if task_id is None:
        raise TopvisorProtocolError("explicit task ID is required; task ownership cannot be inferred")
    task_id = _positive_task_id(task_id)
    result = response_envelope(raw)["result"]
    if not isinstance(result, list):
        raise TopvisorProtocolError("task list must be an array")
    matched: list[tuple[int, str, int | str | None]] = []
    for item in result:
        if not isinstance(item, dict):
            raise TopvisorProtocolError("task entry must be an object")
        entry_id = _positive_task_id(item.get("id"))
        if entry_id != task_id:
            continue
        status = item.get("task_status")
        if status not in ("ongoing", "completed"):
            raise TopvisorProtocolError("unknown task status")
        time_delete = item.get("task_time_delete")
        if isinstance(time_delete, bool) or (isinstance(time_delete, int) and time_delete < 0):
            raise TopvisorProtocolError("task_time_delete seconds must be nonnegative")
        if isinstance(time_delete, int) or time_delete is None:
            expiry: int | str | None = time_delete
        else:
            expiry = _optional_utc_iso(time_delete)
        matched.append((entry_id, status, expiry))
    if not matched:
        return None
    if len(matched) > 1:
        raise TopvisorProtocolError("multiple tasks returned; explicit task ID is required")
    return matched[0]


def task_status(raw: bytes, task_id: int) -> str | None:
    """None means the task was not returned; this is not completion."""
    entry = parse_task_entry(raw, task_id)
    return entry[1] if entry is not None else None


def _volume_count(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise TopvisorProtocolError(f"{field_name} must be an integer")
    if isinstance(value, str):
        if not value or not value.isascii() or not value.isdecimal():
            raise TopvisorProtocolError(f"{field_name} must be a nonnegative integer string")
        count = int(value)
    elif isinstance(value, int):
        count = value
    else:
        raise TopvisorProtocolError(f"{field_name} must be an integer or null")
    if not 0 <= count <= _MAX_INT64:
        raise TopvisorProtocolError(f"{field_name} is outside nonnegative int64")
    return count


def parse_results_page(raw: bytes, request: SemanticRequest) -> ParseResult:
    """Parse /get/keywords_2/keywords rows while keeping 0 distinct from null/unknown."""
    if request.provider != "topvisor" or request.operation != "keywords":
        raise ValueError("wrong semantic request for Topvisor keywords parser")
    options = strict_json_object(request.provider_options_json)
    job_id = options.get("job_id")
    remote_task_id = options.get("remote_task_id")
    snapshot_id = options.get("snapshot_id")
    snapshot_kind = options.get("snapshot_kind")
    region_key = options.get("region_key")
    searcher_key = options.get("searcher_key")
    frequency_type = options.get("frequency_type")
    offset = options.get("offset", 0)
    if (not isinstance(job_id, str) or not job_id
            or isinstance(remote_task_id, bool) or not isinstance(remote_task_id, int) or remote_task_id <= 0
            or not isinstance(snapshot_id, str) or not snapshot_id
            or snapshot_kind not in {"collect", "compare"}
            or isinstance(region_key, bool) or not isinstance(region_key, int)
            or isinstance(searcher_key, bool) or not isinstance(searcher_key, int)
            or isinstance(frequency_type, bool) or not isinstance(frequency_type, int)
            or frequency_type not in YANDEX_FREQUENCY_TYPES
            or isinstance(offset, bool) or not isinstance(offset, int) or offset < 0):
        raise ValueError("incomplete Topvisor keywords request metadata")

    result = response_envelope(raw)["result"]
    if not isinstance(result, list):
        raise TopvisorProtocolError("Topvisor keywords result must be a list")
    if not result:
        return ParseResult("valid_empty")

    field_name = f"volume:{region_key}:{searcher_key}:{frequency_type}"
    observations: list[ParsedObservation] = []
    measurements: list[ParsedMeasurement] = []
    edges: list[ParsedDiscoveryEdge] = []
    context = canonical_json({
        "source": "topvisor",
        "job_id": job_id,
        "remote_task_id": remote_task_id,
        "snapshot_id": snapshot_id,
        "region_key": region_key,
        "searcher_key": searcher_key,
        "frequency_type": frequency_type,
        "frequency_label": YANDEX_FREQUENCY_TYPES[frequency_type],
    })
    for index, row in enumerate(result):
        if not isinstance(row, dict):
            raise TopvisorProtocolError("Topvisor keyword row must be an object")
        phrase = row.get("name")
        if not isinstance(phrase, str) or not phrase.strip():
            raise TopvisorProtocolError("Topvisor keyword row is missing 'name'")
        if field_name not in row:
            raise TopvisorProtocolError(f"Topvisor keyword row is missing '{field_name}'")
        observations.append(ParsedObservation(phrase, "topvisor.keywords", offset + index + 1))
        edges.append(ParsedDiscoveryEdge(
            index, "measured_from_snapshot", f"{snapshot_kind}_snapshot", snapshot_id,
        ))
        raw_volume = row[field_name]
        if raw_volume is not None:
            count = _volume_count(raw_volume, field_name)
            measurements.append(ParsedMeasurement(
                "topvisor_volume",
                Decimal(count),
                "searches_per_month",
                observation_index=index,
                context_json=context,
            ))
    return ParseResult(
        "data",
        tuple(observations),
        tuple(measurements),
        tuple(edges),
    )


class TopvisorReadClient:
    """Read-only contract checks. Paid submit must pass a durable budget gate elsewhere."""

    def __init__(self, credentials: TopvisorCredentials, *, timeout: float = 15.0):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.credentials = credentials
        self.timeout = timeout
        self._opener = _configured_opener()

    def request(self, path: str, payload: Mapping[str, object]) -> bytes:
        if path not in (PRICE_PATH, TASKS_PATH, RESULTS_PATH):
            raise ValueError("only read-only Topvisor methods are available")
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            BASE_URL + path, body, method="POST",
            headers={
                "Content-Type": "application/json",
                "User-Id": self.credentials.user_id,
                "Authorization": "bearer " + self.credentials.api_key,
            },
        )
        try:
            open_request = self._opener.open if self._opener is not None else urllib.request.urlopen
            with open_request(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            raise TopvisorProtocolError(f"Topvisor HTTP {error.code}") from error
        response_envelope(raw)
        return raw

    def estimate_raw(
        self, keywords: tuple[str, ...], qualifiers: tuple[FrequencyQualifier, ...],
    ) -> bytes:
        return self.request(PRICE_PATH, volume_payload(keywords, qualifiers))

    def regions_raw(self, search: str, *, country_code: str | None = None,
                    only_countries: bool = False) -> bytes:
        """Resolve provider geography through its read-only directory, not ID guessing."""
        if not isinstance(search, str) or not search.strip():
            raise ValueError("region search must be nonempty text")
        params = {"searcher_key": 0, "search": search.strip(),
                  "only_countries": str(bool(only_countries)).lower()}
        if country_code is not None:
            if len(country_code) != 2 or not country_code.isascii() or not country_code.isalpha():
                raise ValueError("country-code must be a two-letter ISO code")
            params["country_code"] = country_code.upper()
        request = urllib.request.Request(
            BASE_URL + REGIONS_PATH + "?" + urllib.parse.urlencode(params), method="GET",
            headers={"User-Id": self.credentials.user_id,
                     "Authorization": "bearer " + self.credentials.api_key},
        )
        try:
            open_request = self._opener.open if self._opener is not None else urllib.request.urlopen
            with open_request(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            raise TopvisorProtocolError(f"Topvisor HTTP {error.code}") from error
        response_envelope(raw)
        return raw

    def task_raw(self, task_id: int) -> bytes:
        if isinstance(task_id, bool) or not isinstance(task_id, int) or task_id <= 0:
            raise ValueError("task ID must be a positive integer")
        return self.request(TASKS_PATH, {
            "fields": ["id", "task_status", "task_time_delete"],
            "filters": [{"name": "id", "operator": "EQUALS", "values": [task_id]}],
        })

    def results_raw(self, task_id: int, qualifier: FrequencyQualifier, *, limit: int = 1000,
                    offset: int = 0) -> bytes:
        if isinstance(task_id, bool) or not isinstance(task_id, int) or task_id <= 0:
            raise ValueError("task ID must be a positive integer")
        if not 1 <= limit <= 10000 or offset < 0:
            raise ValueError("invalid result page")
        field_name = "volume:{region_key}:{searcher_key}:{type}".format(**qualifier.descriptor())
        return self.request(RESULTS_PATH, {
            "project_id": task_id, "fields": ["name", field_name],
            "limit": limit, "offset": offset,
        })


class TopvisorRunner:
    """Durable state machine for Topvisor bulk measurement over saved snapshots."""

    def __init__(
        self,
        store: DataStore,
        credentials: TopvisorCredentials,
        *,
        timeout_seconds: float = 15.0,
        transport: Callable[[urllib.request.Request, float], RawResponse] | None = None,
    ):
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.store = store
        self.credentials = credentials
        self.timeout_seconds = timeout_seconds
        self._opener = _configured_opener() if transport is None else None
        self.transport = transport or self._http_transport

    def _http_transport(self, request: urllib.request.Request, timeout: float) -> RawResponse:
        open_request = self._opener.open if self._opener is not None else urllib.request.urlopen
        try:
            with open_request(request, timeout=timeout) as response:
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
            raise TransportFailure() from error

    def _send(self, path: str, payload: Mapping[str, object]) -> RawResponse:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        wire = urllib.request.Request(
            BASE_URL + path,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "User-Id": self.credentials.user_id,
                "Authorization": "bearer " + self.credentials.api_key,
            },
        )
        return self.transport(wire, self.timeout_seconds)

    def _semantic_request(
        self,
        operation: str,
        *,
        regions: Sequence[str] = (),
        result_limit: int | None = None,
        options: Mapping[str, object],
    ) -> SemanticRequest:
        return SemanticRequest(
            provider="topvisor",
            operation=operation,
            api_version="v2",
            adapter_version=TOPVISOR_ADAPTER_VERSION,
            regions=tuple(regions),
            result_limit=result_limit,
            account_context=self.credentials.account_context,
            provider_options_json=canonical_json(dict(options)),
        )

    def create_job(
        self,
        snapshot_id: str,
        qualifiers: Sequence[FrequencyQualifier | Mapping[str, object]],
        *,
        phrases: Sequence[str] | None = None,
        max_cost: Decimal | str | int | None = None,
    ) -> dict[str, object]:
        coerced = tuple(_coerce_qualifier(item) for item in qualifiers)
        job_id = self.store.create_topvisor_job(
            snapshot_id, coerced, phrases=phrases, max_cost=max_cost,
        )
        return self.store.topvisor_job(job_id)

    def create_batched_jobs(
        self,
        snapshot_id: str,
        qualifiers: Sequence[FrequencyQualifier | Mapping[str, object]],
        *,
        phrases: Sequence[str] | None = None,
        max_phrases_per_job: int = 1000,
        max_cost_per_job: Decimal | str | int | None = None,
    ) -> list[dict[str, object]]:
        if isinstance(max_phrases_per_job, bool) or not isinstance(max_phrases_per_job, int) or max_phrases_per_job <= 0:
            raise ValueError("max_phrases_per_job must be a positive integer")
        coerced = tuple(_coerce_qualifier(item) for item in qualifiers)
        if phrases is None:
            _, snapshot_phrases = self.store._verified_snapshot_phrases(snapshot_id)
            target_phrases = [str(item["normalized_phrase"]) for item in snapshot_phrases]
        else:
            target_phrases = list(phrases)
        if not target_phrases:
            raise ValueError("snapshot contains no phrases to measure")
        jobs: list[dict[str, object]] = []
        for start in range(0, len(target_phrases), max_phrases_per_job):
            chunk = target_phrases[start:start + max_phrases_per_job]
            job_id = self.store.create_topvisor_job(
                snapshot_id, coerced, phrases=chunk, max_cost=max_cost_per_job,
            )
            jobs.append(self.store.topvisor_job(job_id))
        return jobs

    def estimate(self, job_id: str) -> dict[str, object]:
        """Call /get/projects_2/tasks/volumes/price, save raw, and record estimated cost."""
        job = self.store.topvisor_job(job_id)
        if job["state"] not in {"created", "estimated", "budget_blocked"}:
            raise ValueError(f"cannot estimate Topvisor job in state {job['state']}")
        qualifiers = tuple(_coerce_qualifier(item) for item in job["qualifiers"])
        keywords = tuple(str(word) for word in job["keywords"])
        payload = volume_payload(keywords, qualifiers)
        regions = sorted({str(item.region_key) for item in qualifiers})
        request = self._semantic_request(
            "price",
            regions=regions,
            options={
                "job_id": job_id,
                "snapshot_id": job["snapshot_id"],
                "keywords_sha256": job["keywords_sha256"],
                "qualifiers": [item.descriptor() for item in qualifiers],
            },
        )
        response = self._send(PRICE_PATH, payload)
        artifact_id = self.store.save_raw(
            str(job["run_id"]), request, response, redactions=self.credentials.redactions,
        )
        if not 200 <= response.status_code < 300:
            raise TopvisorProtocolError(f"Topvisor HTTP {response.status_code}")
        estimated_cost, currency = parse_price_estimate(response.body)
        return self.store.record_topvisor_estimate(
            job_id,
            estimated_cost=estimated_cost,
            artifact_id=artifact_id,
            currency=currency,
        )

    def submit(
        self,
        job_id: str,
        *,
        max_cost: Decimal | str | int | None = None,
    ) -> dict[str, object]:
        """Verify budget gate, record durable intent, and submit paid volume task."""
        job = self.store.topvisor_job(job_id)
        if job["state"] in {"created", "estimated", "budget_blocked"}:
            selection = self.store.plan_unknown_topvisor_measurements(
                str(job["snapshot_id"]), job["qualifiers"], phrases=job["keywords"],
            )
            if selection["skipped_known_pairs"] or selection["pending_pairs"]:
                raise ValueError("Topvisor measurement selection changed; plan only still-missing "
                                 "pairs or continue the existing remote job")
        if job["estimated_cost"] is None:
            job = self.estimate(job_id)
        job = self.store.record_topvisor_submit_intent(job_id, max_cost=max_cost)
        qualifiers = tuple(_coerce_qualifier(item) for item in job["qualifiers"])
        keywords = tuple(str(word) for word in job["keywords"])
        payload = volume_payload(keywords, qualifiers)
        regions = sorted({str(item.region_key) for item in qualifiers})
        request = self._semantic_request(
            "submit",
            regions=regions,
            options={
                "job_id": job_id,
                "snapshot_id": job["snapshot_id"],
                "keywords_sha256": job["keywords_sha256"],
                "qualifiers": [item.descriptor() for item in qualifiers],
            },
        )
        try:
            response = self._send(SUBMIT_PATH, payload)
        except TransportFailure:
            self.store.record_topvisor_submit_ambiguous(
                job_id, reason="submit_transport_failure",
            )
            raise
        except Exception:
            self.store.record_topvisor_submit_ambiguous(
                job_id, reason="submit_unexpected_interruption",
            )
            raise
        artifact_id = self.store.save_raw(
            str(job["run_id"]), request, response, redactions=self.credentials.redactions,
        )
        if not 200 <= response.status_code < 300:
            self.store.record_topvisor_submit_ambiguous(
                job_id, reason=f"submit_http_{response.status_code}",
            )
            raise TopvisorProtocolError(f"Topvisor HTTP {response.status_code}")
        try:
            remote_task_id, expires_at_utc = parse_submitted_task(response.body)
        except TopvisorProtocolError:
            self.store.record_topvisor_submit_ambiguous(
                job_id, reason="submit_protocol_error_after_dispatch",
            )
            raise
        return self.store.record_topvisor_submit_result(
            job_id,
            remote_task_id=remote_task_id,
            artifact_id=artifact_id,
            submitted_at_utc=response.received_at_utc,
            expires_at_utc=expires_at_utc,
        )

    def poll(
        self,
        job_id: str,
        *,
        remote_task_id: int | None = None,
    ) -> dict[str, object]:
        """Check a known task; keep an unknown submit unresolved without querying the account."""
        job = self.store.topvisor_job(job_id)
        if job["state"] not in {"intent_recorded", "ambiguous_submit", "submitted", "ongoing"}:
            raise ValueError(f"cannot poll Topvisor job in state {job['state']}")
        target_task_id = remote_task_id if remote_task_id is not None else job["remote_task_id"]
        if target_task_id is None:
            if job["state"] == "intent_recorded":
                return self.store.record_topvisor_submit_ambiguous(
                    job_id, reason="remote_task_id_required_for_recovery",
                )
            return job
        if isinstance(target_task_id, bool) or not isinstance(target_task_id, int) or target_task_id <= 0:
            raise ValueError("remote_task_id must be a positive integer")
        payload: dict[str, object] = {
            "fields": ["id", "task_status", "task_time_delete"],
            "filters": [{"name": "id", "operator": "EQUALS", "values": [target_task_id]}],
        }
        request = self._semantic_request(
            "tasks",
            options={
                "job_id": job_id,
                "remote_task_id": target_task_id,
            },
        )
        response = self._send(TASKS_PATH, payload)
        artifact_id = self.store.save_raw(
            str(job["run_id"]), request, response, redactions=self.credentials.redactions,
        )
        if not 200 <= response.status_code < 300:
            raise TopvisorProtocolError(f"Topvisor HTTP {response.status_code}")
        entry = parse_task_entry(response.body, target_task_id)
        if entry is None:
            return self.store.record_topvisor_task_status(
                job_id,
                task_status=None,
                artifact_id=artifact_id,
                remote_task_id=target_task_id,
                checked_at_utc=response.received_at_utc,
            )
        found_id, status, task_time_delete = entry
        if isinstance(task_time_delete, int):
            # The documented task-list field is remaining seconds, not an ISO timestamp.
            checked_at = datetime.fromisoformat(response.received_at_utc)
            calculated_expiry = checked_at + timedelta(seconds=task_time_delete)
            if job["expires_at_utc"] is not None:
                calculated_expiry = min(
                    calculated_expiry, datetime.fromisoformat(str(job["expires_at_utc"])),
                )
            expires_at_utc = calculated_expiry.isoformat()
        else:
            expires_at_utc = task_time_delete
        return self.store.record_topvisor_task_status(
            job_id,
            task_status=status,
            artifact_id=artifact_id,
            remote_task_id=found_id,
            expires_at_utc=expires_at_utc,
            checked_at_utc=response.received_at_utc,
        )

    def fetch(
        self,
        job_id: str,
        *,
        page_limit: int = 1000,
    ) -> dict[str, object]:
        """Poll if needed and download all result pages before 24-hour expiration."""
        if isinstance(page_limit, bool) or not isinstance(page_limit, int) or not 1 <= page_limit <= 10000:
            raise ValueError("page_limit must be between 1 and 10000")
        job = self.store.topvisor_job(job_id)
        if job["state"] == "completed":
            return job
        if job["state"] not in {"submitted", "ongoing"}:
            raise ValueError(f"cannot fetch results for Topvisor job in state {job['state']}")
        if job["remote_task_status"] != "completed":
            job = self.poll(job_id)
            if job["state"] == "expired_24h" or job["remote_task_status"] != "completed":
                return job

        remote_task_id = int(job["remote_task_id"])
        total_keywords = len(job["keywords"])
        for qual_dict in job["qualifiers"]:
            qualifier = _coerce_qualifier(qual_dict)
            existing_pages = {
                int(page["page_offset"]): int(page["row_count"])
                for page in job["pages"]
                if (
                    int(page["region_key"]) == qualifier.region_key
                    and int(page["searcher_key"]) == qualifier.searcher_key
                    and int(page["frequency_type"]) == qualifier.frequency_type
                )
            }
            offset = 0
            while True:
                if offset in existing_pages:
                    row_count = existing_pages[offset]
                else:
                    field_name = "volume:{region_key}:{searcher_key}:{type}".format(
                        **qualifier.descriptor(),
                    )
                    payload = {
                        "project_id": remote_task_id,
                        "fields": ["name", field_name],
                        "limit": page_limit,
                        "offset": offset,
                    }
                    request = self._semantic_request(
                        "keywords",
                        regions=(str(qualifier.region_key),),
                        result_limit=page_limit,
                        options={
                            "job_id": job_id,
                            "remote_task_id": remote_task_id,
                            "snapshot_id": job["snapshot_id"],
                            "snapshot_kind": job["snapshot_kind"],
                            "region_key": qualifier.region_key,
                            "searcher_key": qualifier.searcher_key,
                            "frequency_type": qualifier.frequency_type,
                            "offset": offset,
                        },
                    )
                    response = self._send(RESULTS_PATH, payload)
                    artifact_id = self.store.save_raw(
                        str(job["run_id"]),
                        request,
                        response,
                        redactions=self.credentials.redactions,
                    )
                    if not 200 <= response.status_code < 300:
                        raise TopvisorProtocolError(f"Topvisor HTTP {response.status_code}")
                    job = self.store.record_topvisor_result_page(
                        job_id,
                        qualifier=qualifier,
                        page_offset=offset,
                        page_limit=page_limit,
                        artifact_id=artifact_id,
                        parser=parse_results_page,
                        parser_version=TOPVISOR_PARSER_VERSION,
                    )
                    recorded = next(
                        page for page in job["pages"]
                        if (
                            int(page["region_key"]) == qualifier.region_key
                            and int(page["searcher_key"]) == qualifier.searcher_key
                            and int(page["frequency_type"]) == qualifier.frequency_type
                            and int(page["page_offset"]) == offset
                        )
                    )
                    row_count = int(recorded["row_count"])
                offset += row_count
                if row_count < page_limit or offset >= total_keywords:
                    break
        return self.store.complete_topvisor_job(job_id)

    def run(
        self,
        job_id: str,
        *,
        max_cost: Decimal | str | int | None = None,
        page_limit: int = 1000,
    ) -> dict[str, object]:
        """Advance a Topvisor job through estimate -> submit -> poll/fetch safely."""
        job = self.store.topvisor_job(job_id)
        if job["state"] == "created":
            job = self.estimate(job_id)
        if job["state"] in {"estimated", "budget_blocked"}:
            if max_cost is None and job["max_cost"] is None:
                return job
            if job["state"] == "budget_blocked" and max_cost is None:
                return job
            job = self.submit(job_id, max_cost=max_cost)
        if job["state"] in {"submitted", "ongoing"}:
            job = self.fetch(job_id, page_limit=page_limit)
        return job
