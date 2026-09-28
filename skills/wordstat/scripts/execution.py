"""Single-worker durable execution core. No provider adapters or semantic policy."""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from enum import StrEnum

from .identity import fingerprint
from .models import ParseResult, RawResponse, SemanticRequest
from .storage import ArtifactIntegrityError, DataStore, ParserFailure, _now


class OutcomeKind(StrEnum):
    SUCCESS_WITH_DATA = "success_with_data"
    SUCCESS_VALID_EMPTY = "success_valid_empty"
    TRANSPORT_ERROR = "transport_error"
    PROVIDER_ERROR = "provider_error"
    AUTH_OR_CONFIGURATION_ERROR = "auth_or_configuration_error"
    THROTTLED = "throttled"
    MALFORMED_RESPONSE = "malformed_response"
    AMBIGUOUS_EXTERNAL_OUTCOME = "ambiguous_external_outcome"


class WorkStateError(RuntimeError):
    pass


class CapacityUnavailable(RuntimeError):
    def __init__(self, retry_at: float, reason: str):
        super().__init__(reason)
        self.retry_at = retry_at
        self.reason = reason


class RunBudgetExhausted(RuntimeError):
    pass


class TransportFailure(RuntimeError):
    """Only `definitely_not_sent=True` allows an automatic retry."""

    def __init__(self, *, definitely_not_sent: bool = False):
        super().__init__("transport failure")
        self.definitely_not_sent = definitely_not_sent


@dataclass(frozen=True)
class CapacityBucket:
    id: str
    rps: int
    window_limit: int
    window_seconds: int = 3600

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("capacity bucket ID must be nonempty")
        for value in (self.rps, self.window_limit, self.window_seconds):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError("capacity limits must be positive integers")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    max_total_wait: float = 120.0
    retry_provider_5xx: bool = False

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.base_delay <= 0 or self.max_delay <= 0 or self.max_total_wait < 0:
            raise ValueError("invalid retry policy")

    def delay(
        self, kind: OutcomeKind, http_status: int | None, retry_after: str | None,
        *, attempt_number: int, already_waited: float, now: float,
        jitter: Callable[[], float],
    ) -> float | None:
        if attempt_number >= self.max_attempts:
            return None
        retryable = (
            kind in {OutcomeKind.THROTTLED, OutcomeKind.TRANSPORT_ERROR}
            or (kind == OutcomeKind.PROVIDER_ERROR and self.retry_provider_5xx
                and http_status is not None and 500 <= http_status <= 599)
        )
        if not retryable:
            return None
        random_fraction = jitter()
        if not 0 <= random_fraction <= 1:
            raise ValueError("jitter must return a value in [0, 1]")
        fallback = min(self.max_delay, self.base_delay * (2 ** (attempt_number - 1)))
        delay = fallback * (0.5 + random_fraction / 2)
        if retry_after is not None:
            parsed = parse_retry_after(retry_after, now)
            if parsed is not None:
                delay = max(delay, parsed)
        if already_waited + delay > self.max_total_wait:
            return None
        return delay


def parse_retry_after(value: str, now: float) -> float | None:
    try:
        seconds = float(value.strip())
        if seconds >= 0 and seconds < float("inf"):
            return seconds
        return None
    except ValueError:
        pass
    try:
        stamp = parsedate_to_datetime(value)
        if stamp.tzinfo is None:
            return None
        return max(0.0, stamp.timestamp() - now)
    except (TypeError, ValueError, OverflowError):
        return None


@dataclass(frozen=True)
class RecoveryReport:
    safe_intents: tuple[str, ...]
    ambiguous_attempts: tuple[int, ...]
    repairable_raw_attempts: tuple[int, ...]
    repaired_attempts: tuple[int, ...]
    orphan_artifacts: tuple[str, ...]
    integrity_errors: tuple[str, ...]


_RUN_OUTCOMES = {"success", "degraded_success", "incomplete", "failed"}
_RESUMABILITY = {
    "no_pending_work", "resumable_automatically", "after_capacity_available",
    "awaiting_provider", "requires_operator_decision", "terminal_unrecoverable",
}


class ExecutionCore:
    """Durable work and attempt transitions on the stage-1 DataStore."""

    def __init__(self, store: DataStore, *, clock: Callable[[], float] = time.time):
        self.store = store
        self.db = store._db
        self.clock = clock

    def configure_bucket(self, bucket: CapacityBucket) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO capacity_buckets (id,rps,window_limit,window_seconds) VALUES (?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET rps=excluded.rps, "
                "window_limit=excluded.window_limit,window_seconds=excluded.window_seconds",
                (bucket.id, bucket.rps, bucket.window_limit, bucket.window_seconds),
            )

    def configure_run_budget(self, run_id: str, bucket_id: str, max_attempts: int) -> None:
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts <= 0:
            raise ValueError("run call budget must be a positive integer")
        with self.db:
            self.db.execute(
                "INSERT INTO run_budgets VALUES (?,?,?) ON CONFLICT(run_id,bucket_id) "
                "DO UPDATE SET max_attempts=excluded.max_attempts",
                (run_id, bucket_id, max_attempts),
            )

    def create_work(
        self, run_id: str, logical_key: str, request: SemanticRequest, bucket_id: str,
    ) -> str:
        if not logical_key.strip():
            raise ValueError("logical work key must be nonempty")
        request_id = fingerprint(request)
        descriptor = json.dumps(request.descriptor(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        work_id = hashlib.sha256(
            json.dumps([run_id, logical_key], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO semantic_requests VALUES (?,?)", (request_id, descriptor),
            )
            stored_descriptor = self.db.execute(
                "SELECT descriptor_json FROM semantic_requests WHERE fingerprint=?", (request_id,),
            ).fetchone()[0]
            if stored_descriptor != descriptor:
                raise WorkStateError("request fingerprint collision or descriptor drift")
            self.db.execute(
                "INSERT OR IGNORE INTO work_items "
                "(id,run_id,logical_key,request_fingerprint,bucket_id,state,created_at_utc) "
                "VALUES (?,?,?,?,?,'pending',?)",
                (work_id, run_id, logical_key, request_id, bucket_id, _now()),
            )
            row = self.db.execute(
                "SELECT id,request_fingerprint,bucket_id FROM work_items "
                "WHERE run_id=? AND logical_key=?", (run_id, logical_key),
            ).fetchone()
            if row is None or row["id"] != work_id or row["request_fingerprint"] != request_id or row["bucket_id"] != bucket_id:
                raise WorkStateError("logical work identity already belongs to a different request or bucket")
        return work_id

    def work(self, work_id: str) -> dict[str, object]:
        row = self.db.execute("SELECT * FROM work_items WHERE id=?", (work_id,)).fetchone()
        if row is None:
            raise KeyError(work_id)
        return dict(row)

    def reopen_failed(self, work_id: str, *, accept_ambiguous_risk: bool = False) -> None:
        """Explicitly requeue a classified failure; never silently replay an ambiguous call."""
        with self.db:
            work = self.work(work_id)
            if work["state"] not in {"failed", "ambiguous"}:
                raise WorkStateError("only failed or ambiguous work can be reopened")
            if work["state"] == "ambiguous" and not accept_ambiguous_risk:
                raise WorkStateError("ambiguous external outcome needs explicit risk acceptance")
            self.db.execute(
                "UPDATE work_items SET state='pending',retry_at=NULL WHERE id=?", (work_id,)
            )

    def attempts(self, work_id: str) -> list[dict[str, object]]:
        return [dict(row) for row in self.db.execute(
            "SELECT * FROM attempts WHERE work_id=? ORDER BY id", (work_id,),
        ).fetchall()]

    def request(self, work_id: str) -> SemanticRequest:
        row = self.db.execute(
            "SELECT r.descriptor_json FROM work_items w JOIN semantic_requests r "
            "ON r.fingerprint=w.request_fingerprint WHERE w.id=?", (work_id,),
        ).fetchone()
        if row is None:
            raise KeyError(work_id)
        return SemanticRequest.from_mapping(json.loads(row[0]))

    def reserve(self, work_id: str) -> int:
        now = self.clock()
        with self.db:
            work = self.work(work_id)
            if work["state"] not in {"pending", "retry_wait", "capacity_wait"}:
                raise WorkStateError(f"work is not eligible: {work['state']}")
            if work["retry_at"] is not None and now < work["retry_at"]:
                reason = "external_throttle" if work["state"] == "capacity_wait" else "retry_delay"
                raise CapacityUnavailable(float(work["retry_at"]), reason)
            bucket = self.db.execute(
                "SELECT * FROM capacity_buckets WHERE id=?", (work["bucket_id"],),
            ).fetchone()
            if bucket is None:
                raise WorkStateError("capacity bucket is not configured")
            budget = self.db.execute(
                "SELECT max_attempts FROM run_budgets WHERE run_id=? AND bucket_id=?",
                (work["run_id"], work["bucket_id"]),
            ).fetchone()
            if budget is None:
                raise WorkStateError("run call budget is not configured")
            used = self.db.execute(
                "SELECT COUNT(*) FROM attempts a JOIN work_items w ON w.id=a.work_id "
                "WHERE w.run_id=? AND a.bucket_id=? AND a.state!='abandoned_before_dispatch'",
                (work["run_id"], work["bucket_id"]),
            ).fetchone()[0]
            if used >= budget[0]:
                raise RunBudgetExhausted("run call budget is exhausted")
            if now < bucket["blocked_until"]:
                raise CapacityUnavailable(float(bucket["blocked_until"]), "external_throttle")
            for seconds, limit, label in (
                (1, bucket["rps"], "rps"),
                (bucket["window_seconds"], bucket["window_limit"], "window"),
            ):
                rows = self.db.execute(
                    "SELECT reserved_at FROM attempts WHERE bucket_id=? "
                    "AND state!='abandoned_before_dispatch' AND reserved_at>? "
                    "ORDER BY reserved_at", (work["bucket_id"], now - seconds),
                ).fetchall()
                if len(rows) >= limit:
                    raise CapacityUnavailable(float(rows[len(rows) - limit][0] + seconds), label)
            cursor = self.db.execute(
                "INSERT INTO attempts (work_id,bucket_id,reserved_at,state) VALUES (?,?,?,'reserved')",
                (work_id, work["bucket_id"], now),
            )
            self.db.execute(
                "UPDATE work_items SET state='reserved',retry_at=NULL WHERE id=?", (work_id,),
            )
            return int(cursor.lastrowid)

    def mark_dispatched(self, attempt_id: int) -> None:
        with self.db:
            row = self.db.execute("SELECT work_id,state FROM attempts WHERE id=?", (attempt_id,)).fetchone()
            if row is None or row["state"] != "reserved":
                raise WorkStateError("attempt is not reserved")
            self.db.execute(
                "UPDATE attempts SET state='dispatched',dispatched_at=? WHERE id=?",
                (self.clock(), attempt_id),
            )
            self.db.execute("UPDATE work_items SET state='dispatching' WHERE id=?", (row["work_id"],))

    def _attempt_context(self, attempt_id: int):
        row = self.db.execute(
            "SELECT a.*,w.run_id,w.request_fingerprint,w.id AS work_id FROM attempts a "
            "JOIN work_items w ON w.id=a.work_id WHERE a.id=?", (attempt_id,),
        ).fetchone()
        if row is None:
            raise KeyError(attempt_id)
        return row

    def save_response(
        self, attempt_id: int, response: RawResponse, *, redactions: Sequence[bytes],
    ) -> str:
        row = self._attempt_context(attempt_id)
        if row["state"] != "dispatched":
            raise WorkStateError("only dispatched attempts may receive raw")
        return self.store.save_raw(
            row["run_id"], self.request(row["work_id"]), response,
            redactions=redactions, attempt_id=attempt_id,
        )

    def finalize_raw(
        self, attempt_id: int, parser: Callable[[bytes, SemanticRequest], ParseResult],
        *, parser_version: str,
    ) -> OutcomeKind:
        row = self._attempt_context(attempt_id)
        if row["state"] != "dispatched":
            raise WorkStateError("attempt is not awaiting raw completion")
        artifact = self.db.execute(
            "SELECT id,status_code FROM raw_artifacts WHERE attempt_id=?", (attempt_id,),
        ).fetchone()
        if artifact is None:
            raise WorkStateError("no raw artifact is linked to attempt")
        self.store.read_raw(artifact["id"])
        status = artifact["status_code"]
        if status == 429:
            kind = OutcomeKind.THROTTLED
        elif status in (401, 403):
            kind = OutcomeKind.AUTH_OR_CONFIGURATION_ERROR
        elif not 200 <= status < 300:
            kind = OutcomeKind.PROVIDER_ERROR
        else:
            try:
                with self.db:
                    batch_id = self.store.parse_artifact(
                        artifact["id"], parser, parser_version=parser_version,
                        _within_transaction=True,
                    )
                    parsed_kind = self.db.execute(
                        "SELECT kind FROM parse_batches WHERE id=?", (batch_id,),
                    ).fetchone()[0]
                    kind = (
                        OutcomeKind.SUCCESS_VALID_EMPTY if parsed_kind == "valid_empty"
                        else OutcomeKind.SUCCESS_WITH_DATA
                    )
                    self._commit_outcome(attempt_id, row["work_id"], kind, status)
                return kind
            except ParserFailure:
                kind = OutcomeKind.MALFORMED_RESPONSE
        with self.db:
            self._commit_outcome(attempt_id, row["work_id"], kind, status)
        return kind

    def _commit_outcome(
        self, attempt_id: int, work_id: str, kind: OutcomeKind,
        status: int | None, detail_code: str | None = None,
    ) -> None:
        self.db.execute(
            "UPDATE attempts SET state='completed',outcome_kind=?,http_status=?,"
            "detail_code=?,completed_at=? WHERE id=?",
            (kind.value, status, detail_code, self.clock(), attempt_id),
        )
        state = "completed" if kind in {
            OutcomeKind.SUCCESS_WITH_DATA, OutcomeKind.SUCCESS_VALID_EMPTY,
        } else "failed"
        if kind == OutcomeKind.AMBIGUOUS_EXTERNAL_OUTCOME:
            state = "ambiguous"
        self.db.execute("UPDATE work_items SET state=? WHERE id=?", (state, work_id))
        if state == "completed":
            run_id = self.db.execute(
                "SELECT run_id FROM work_items WHERE id=?", (work_id,),
            ).fetchone()[0]
            pending = self.db.execute(
                "SELECT COUNT(*) FROM work_items WHERE run_id=? AND state!='completed'",
                (run_id,),
            ).fetchone()[0]
            if pending == 0:
                self.db.execute(
                    "UPDATE run_states SET pause_reason=NULL,resumability='no_pending_work',"
                    "updated_at_utc=? WHERE run_id=?", (_now(), run_id),
                )

    def record_failure(
        self, attempt_id: int, kind: OutcomeKind, *, detail_code: str | None = None,
    ) -> None:
        if kind not in {OutcomeKind.TRANSPORT_ERROR, OutcomeKind.AMBIGUOUS_EXTERNAL_OUTCOME}:
            raise ValueError("only non-HTTP failures may be recorded without raw")
        row = self._attempt_context(attempt_id)
        if row["state"] != "dispatched":
            raise WorkStateError("attempt is not dispatched")
        with self.db:
            self._commit_outcome(attempt_id, row["work_id"], kind, None, detail_code)

    def schedule_retry(self, work_id: str, *, retry_at: float) -> None:
        with self.db:
            work = self.work(work_id)
            if work["state"] != "failed":
                raise WorkStateError("only a failed work item can be retried automatically")
            self.db.execute(
                "UPDATE work_items SET state='retry_wait',retry_at=? WHERE id=?",
                (retry_at, work_id),
            )

    def defer_after_throttle(self, work_id: str, *, retry_at: float) -> None:
        with self.db:
            work = self.work(work_id)
            if work["state"] != "failed":
                raise WorkStateError("only a throttled failed attempt can be deferred")
            last = self.db.execute(
                "SELECT outcome_kind FROM attempts WHERE work_id=? ORDER BY id DESC LIMIT 1",
                (work_id,),
            ).fetchone()
            if last is None or last[0] != OutcomeKind.THROTTLED:
                raise WorkStateError("last attempt was not throttled")
            self.db.execute(
                "UPDATE work_items SET state='capacity_wait',retry_at=? WHERE id=?",
                (retry_at, work_id),
            )
        self.note_capacity_pause(work_id, "external_throttle")

    def throttle_bucket(self, bucket_id: str, until: float) -> None:
        with self.db:
            self.db.execute(
                "UPDATE capacity_buckets SET blocked_until=MAX(blocked_until,?) WHERE id=?",
                (until, bucket_id),
            )

    def set_run_state(
        self, run_id: str, *, outcome: str, semantic_stop: str,
        pause_reason: str | None, resumability: str,
    ) -> None:
        if outcome not in _RUN_OUTCOMES or resumability not in _RESUMABILITY:
            raise ValueError("invalid run outcome or resumability")
        if not semantic_stop.strip() or (pause_reason is not None and not pause_reason.strip()):
            raise ValueError("invalid semantic stop or pause reason")
        with self.db:
            cursor = self.db.execute(
                "UPDATE run_states SET outcome=?,semantic_stop=?,pause_reason=?,"
                "resumability=?,updated_at_utc=? WHERE run_id=?",
                (outcome, semantic_stop, pause_reason, resumability, _now(), run_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(run_id)

    def run_state(self, run_id: str) -> dict[str, object]:
        row = self.db.execute("SELECT * FROM run_states WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        result = dict(row)
        result["pending_work"] = self.db.execute(
            "SELECT COUNT(*) FROM work_items WHERE run_id=? AND state!='completed'", (run_id,),
        ).fetchone()[0]
        return result

    def note_capacity_pause(self, work_id: str, reason: str) -> None:
        work = self.work(work_id)
        previous = self.run_state(work["run_id"])
        pause = "retry_delay" if reason == "retry_delay" else "provider_capacity_unavailable"
        resumability = (
            "resumable_automatically" if reason == "retry_delay"
            else "after_capacity_available"
        )
        self.set_run_state(
            work["run_id"], outcome="incomplete",
            semantic_stop=previous["semantic_stop"], pause_reason=pause,
            resumability=resumability,
        )

    def diagnostics(self, run_id: str) -> list[dict[str, object]]:
        return [dict(row) for row in self.db.execute(
            "SELECT json_extract(r.descriptor_json,'$.provider') AS provider,"
            "COUNT(DISTINCT w.id) AS planned,"
            "COUNT(a.id) AS attempted,"
            "SUM(CASE WHEN a.outcome_kind='success_with_data' THEN 1 ELSE 0 END) AS success,"
            "SUM(CASE WHEN a.outcome_kind='success_valid_empty' THEN 1 ELSE 0 END) AS valid_empty,"
            "SUM(CASE WHEN a.outcome_kind IN ('transport_error','provider_error',"
            "'auth_or_configuration_error','throttled','malformed_response') THEN 1 ELSE 0 END) AS failed,"
            "SUM(CASE WHEN w.state!='completed' AND a.id IS NULL THEN 1 ELSE 0 END) AS never_attempted "
            "FROM work_items w JOIN semantic_requests r ON r.fingerprint=w.request_fingerprint "
            "LEFT JOIN attempts a ON a.work_id=w.id WHERE w.run_id=? "
            "GROUP BY provider ORDER BY provider", (run_id,),
        ).fetchall()]

    def recover(
        self,
        parser_resolver: Callable[[SemanticRequest], tuple[Callable[[bytes, SemanticRequest], ParseResult], str]] | None = None,
    ) -> RecoveryReport:
        safe: list[str] = []
        ambiguous: list[int] = []
        repairable: list[int] = []
        repaired: list[int] = []
        integrity: list[str] = []
        bad_artifacts: set[str] = set()
        for artifact in self.db.execute("SELECT id FROM raw_artifacts").fetchall():
            artifact_id = artifact["id"]
            try:
                self.store.read_raw(artifact_id)
            except ArtifactIntegrityError as error:
                bad_artifacts.add(artifact_id)
                integrity.append(f"artifact {artifact_id}: {error}")
        for row in self.db.execute(
            "SELECT a.id,a.work_id,a.state AS attempt_state,w.state AS work_state,"
            "raw.id AS artifact_id FROM attempts a JOIN work_items w ON w.id=a.work_id "
            "LEFT JOIN raw_artifacts raw ON raw.attempt_id=a.id ORDER BY a.id"
        ).fetchall():
            attempt_id = row["id"]
            artifact_id = row["artifact_id"]
            if artifact_id in bad_artifacts:
                continue
            if row["attempt_state"] == "reserved":
                if artifact_id is not None:
                    integrity.append(f"attempt {attempt_id}: raw exists before dispatch")
                    continue
                with self.db:
                    self.db.execute(
                        "UPDATE attempts SET state='abandoned_before_dispatch' WHERE id=?", (attempt_id,),
                    )
                    self.db.execute("UPDATE work_items SET state='pending' WHERE id=?", (row["work_id"],))
                safe.append(row["work_id"])
            elif row["attempt_state"] == "dispatched" and artifact_id is None:
                with self.db:
                    self._commit_outcome(
                        attempt_id, row["work_id"], OutcomeKind.AMBIGUOUS_EXTERNAL_OUTCOME,
                        None, "restart_without_raw",
                    )
                ambiguous.append(attempt_id)
            elif row["attempt_state"] == "dispatched" and artifact_id is not None:
                repairable.append(attempt_id)
                if parser_resolver is not None:
                    request = self.request(row["work_id"])
                    parser, version = parser_resolver(request)
                    self.finalize_raw(attempt_id, parser, parser_version=version)
                    repaired.append(attempt_id)
        referenced = {
            row[0] for row in self.db.execute("SELECT relative_path FROM raw_artifacts").fetchall()
        }
        quarantined: list[str] = []
        for path in self.store.raw_directory.rglob("*"):
            if not path.is_file() or path.suffix not in {".bin", ".tmp"}:
                continue
            relative = path.relative_to(self.store.raw_directory)
            if relative.as_posix() in referenced:
                continue
            destination = self.store.directory / "quarantine" / "raw" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                destination = destination.with_name(f"{uuid.uuid4().hex}-{destination.name}")
            os.replace(path, destination)
            quarantined.append(destination.relative_to(self.store.directory).as_posix())
        return RecoveryReport(
            tuple(safe), tuple(ambiguous), tuple(repairable), tuple(repaired),
            tuple(sorted(quarantined)), tuple(integrity),
        )


class Executor:
    """Bounded single-worker execution against an injected provider function."""

    def __init__(
        self, core: ExecutionCore, *, policy: RetryPolicy = RetryPolicy(),
        sleeper: Callable[[float], None] = time.sleep,
        jitter: Callable[[], float] = random.random,
    ):
        self.core = core
        self.policy = policy
        self.sleeper = sleeper
        self.jitter = jitter

    def execute(
        self, work_id: str, send: Callable[[SemanticRequest], RawResponse],
        parser: Callable[[bytes, SemanticRequest], ParseResult], *,
        parser_version: str, redactions: Sequence[bytes] = (),
        checkpoint: Callable[[str], None] | None = None,
    ) -> OutcomeKind:
        waited = 0.0
        while True:
            try:
                attempt_id = self.core.reserve(work_id)
            except CapacityUnavailable as blocked:
                self.core.note_capacity_pause(work_id, blocked.reason)
                delay = max(0.0, blocked.retry_at - self.core.clock())
                if delay <= 0 or waited + delay > self.policy.max_total_wait:
                    raise
                before = self.core.clock()
                self.sleeper(delay + 0.001)
                if self.core.clock() <= before:
                    raise
                waited += self.core.clock() - before
                continue
            if checkpoint:
                checkpoint("after_intent")
            self.core.mark_dispatched(attempt_id)
            request = self.core.request(work_id)
            try:
                response = send(request)
                if checkpoint:
                    checkpoint("after_external")
                if not isinstance(response, RawResponse):
                    raise TypeError("provider did not return RawResponse")
            except TransportFailure as error:
                kind = (
                    OutcomeKind.TRANSPORT_ERROR if error.definitely_not_sent
                    else OutcomeKind.AMBIGUOUS_EXTERNAL_OUTCOME
                )
                self.core.record_failure(attempt_id, kind, detail_code="transport")
                response = None
            except Exception:
                kind = OutcomeKind.AMBIGUOUS_EXTERNAL_OUTCOME
                self.core.record_failure(attempt_id, kind, detail_code="unexpected_after_dispatch")
                response = None
            if response is not None:
                try:
                    self.core.save_response(attempt_id, response, redactions=redactions)
                except Exception:
                    self.core.record_failure(
                        attempt_id, OutcomeKind.AMBIGUOUS_EXTERNAL_OUTCOME,
                        detail_code="raw_persistence_error",
                    )
                    return OutcomeKind.AMBIGUOUS_EXTERNAL_OUTCOME
                if checkpoint:
                    checkpoint("after_raw")
                kind = self.core.finalize_raw(attempt_id, parser, parser_version=parser_version)
                if checkpoint:
                    checkpoint("after_commit")
                retry_after = next(
                    (value for name, value in response.headers.items()
                     if name.lower() == "retry-after"), None,
                )
                status = response.status_code
            else:
                retry_after = None
                status = None
            if kind == OutcomeKind.AMBIGUOUS_EXTERNAL_OUTCOME:
                return kind
            attempt_number = len(self.core.attempts(work_id))
            delay = self.policy.delay(
                kind, status, retry_after, attempt_number=attempt_number,
                already_waited=waited, now=self.core.clock(), jitter=self.jitter,
            )
            if kind == OutcomeKind.THROTTLED:
                conservative_delay = delay if delay is not None else (
                    parse_retry_after(retry_after, self.core.clock()) if retry_after else None
                )
                resume_at = self.core.clock() + (
                    conservative_delay if conservative_delay is not None else self.policy.base_delay
                )
                self.core.throttle_bucket(
                    self.core.work(work_id)["bucket_id"], resume_at,
                )
                if delay is None:
                    self.core.defer_after_throttle(work_id, retry_at=resume_at)
            if delay is None:
                return kind
            self.core.schedule_retry(work_id, retry_at=self.core.clock() + delay)
            self.sleeper(delay)
            waited += delay
