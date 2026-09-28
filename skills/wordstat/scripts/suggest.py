"""Three independent suggestion sources backed by one conservative transport/parser.

These endpoints are undocumented adapter snapshots, not official volume APIs.
The caller owns each source's capacity bucket and any collection policy.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

from .execution import ExecutionCore, Executor, OutcomeKind, RetryPolicy, TransportFailure
from .identity import fingerprint
from .models import (
    ParseResult, ParsedDiscoveryEdge, ParsedObservation, RawResponse,
    SemanticRequest, canonical_json,
)


PARSER_VERSION = "suggest-array-v1"
ADAPTER_VERSION = "suggest-snapshot-v1"


class SuggestSource(StrEnum):
    YANDEX = "yandex_suggest"
    GOOGLE = "google_suggest"
    YOUTUBE = "youtube_suggest"


_ENDPOINTS = {
    SuggestSource.YANDEX: "https://suggest.yandex.ru/suggest-ff.cgi",
    SuggestSource.GOOGLE: "https://suggestqueries.google.com/complete/search",
    SuggestSource.YOUTUBE: "https://suggestqueries.google.com/complete/search",
}


def _token(name: str, value: str) -> str:
    if not isinstance(value, str) or not value or not value.isascii() or not all(
        char.isalnum() or char == "-" for char in value
    ):
        raise ValueError(f"{name} must be a nonempty ASCII language/locale token")
    return value


@dataclass(frozen=True)
class SuggestContext:
    """Provider-specific hints; country is not a Wordstat region mapping."""

    language: str = "ru"
    country: str | None = "ru"
    yandex_requested_limit: int = 10

    def __post_init__(self) -> None:
        _token("language", self.language)
        if self.country is not None:
            _token("country", self.country)
        if (isinstance(self.yandex_requested_limit, bool)
                or not isinstance(self.yandex_requested_limit, int)
                or self.yandex_requested_limit <= 0):
            raise ValueError("yandex_requested_limit must be positive")


def _source(request: SemanticRequest) -> SuggestSource:
    try:
        source = SuggestSource(request.provider)
    except ValueError as error:
        raise ValueError("unknown Suggest provider") from error
    if (request.operation != "Suggest" or request.api_version != "undocumented"
            or request.adapter_version != ADAPTER_VERSION or request.schema_version != 1):
        raise ValueError("wrong Suggest request version or operation")
    return source


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def parse_suggest(raw: bytes, request: SemanticRequest) -> ParseResult:
    """Only the returned strings are observations; list order is not volume."""
    source = _source(request)
    if request.phrase is None:
        raise ValueError("Suggest request has no phrase")
    try:
        payload = json.loads(raw.decode("utf-8"), parse_constant=_reject_json_constant)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Suggest response is not UTF-8 JSON") from error
    if (not isinstance(payload, list) or len(payload) < 2
            or not isinstance(payload[0], str) or payload[0] != request.phrase
            or not isinstance(payload[1], list)):
        raise ValueError("Suggest response has an unexpected array shape or query echo")
    if not payload[1]:
        return ParseResult("valid_empty")
    observations: list[ParsedObservation] = []
    edges: list[ParsedDiscoveryEdge] = []
    origin = fingerprint(request)
    for index, item in enumerate(payload[1]):
        if not isinstance(item, str) or not item.strip() or "\ufffd" in item:
            raise ValueError(f"Suggest item {index + 1} is not a valid phrase")
        observations.append(ParsedObservation(item, source.value, index + 1))
        edges.append(ParsedDiscoveryEdge(index, "suggested_for", "semantic_request", origin))
    return ParseResult("data", tuple(observations), discovery_edges=tuple(edges))


class SuggestAdapter:
    """A single chosen endpoint variant for one independent provider."""

    def __init__(
        self, source: SuggestSource, *, context: SuggestContext = SuggestContext(),
        timeout_seconds: float = 12.0,
        transport: Callable[[urllib.request.Request, float], RawResponse] | None = None,
    ):
        self.source = SuggestSource(source)
        if not isinstance(context, SuggestContext):
            raise TypeError("context must be SuggestContext")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.context = context
        self.timeout_seconds = timeout_seconds
        self.transport = transport or self._http_transport

    def _options(self) -> dict[str, str]:
        if self.source == SuggestSource.YANDEX:
            return {
                "uil": self.context.language,
                "v": "4",
                "sn": str(self.context.yandex_requested_limit),
            }
        options = {"client": "firefox", "hl": self.context.language}
        if self.context.country is not None:
            options["gl"] = self.context.country
        if self.source == SuggestSource.YOUTUBE:
            options["ds"] = "yt"
        return options

    def semantic_request(self, phrase: str) -> SemanticRequest:
        if not isinstance(phrase, str) or not phrase.strip():
            raise ValueError("Suggest phrase must be nonempty")
        return SemanticRequest(
            self.source.value, "Suggest", "undocumented", ADAPTER_VERSION,
            phrase=phrase, locale=self.context.language,
            result_limit=(self.context.yandex_requested_limit
                          if self.source == SuggestSource.YANDEX else None),
            provider_options_json=canonical_json(self._options()),
        )

    def request_url(self, request: SemanticRequest) -> str:
        if _source(request) != self.source or request != self.semantic_request(request.phrase):
            raise ValueError("request does not belong to this Suggest adapter/context")
        params = dict(self._options())
        if self.source == SuggestSource.YANDEX:
            params = {"part": request.phrase, **params}
        else:
            params["q"] = request.phrase
        return _ENDPOINTS[self.source] + "?" + urllib.parse.urlencode(params)

    def send(self, request: SemanticRequest) -> RawResponse:
        wire_request = urllib.request.Request(
            self.request_url(request), method="GET",
            headers={"Accept": "application/json", "User-Agent": "wordstat-suggest/1"},
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
            raise TransportFailure() from error

    def execute(
        self, core: ExecutionCore, run_id: str, logical_key: str, *,
        phrase: str, bucket_id: str, policy: RetryPolicy | None = None,
    ) -> tuple[str, OutcomeKind]:
        request = self.semantic_request(phrase)
        work_id = core.create_work(run_id, logical_key, request, bucket_id)
        outcome = Executor(core, policy=policy or RetryPolicy(max_attempts=1)).execute(
            work_id, self.send, parse_suggest, parser_version=PARSER_VERSION,
        )
        return work_id, outcome
