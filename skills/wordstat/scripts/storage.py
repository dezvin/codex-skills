"""SQLite state, immutable raw artifacts, and replayable derived data.

Provider I/O and semantic expansion policy live outside this layer.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from collections.abc import Callable, Mapping, Sequence
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .identity import NORMALIZATION_VERSION, fingerprint, normalize_phrase_v1
from .locking import StoreLock
from .models import ParseResult, RawResponse, SemanticRequest, canonical_json, strict_json_object
from .seed_probes import LLMProposalBatch, ProbePlan, ProbeBatch, generate_probes


SCHEMA_VERSION = 10
_TOPVISOR_FREQUENCY_TYPES = {1, 2, 3, 5, 6}
_SAFE_HEADER_NAMES = {"content-type", "date", "retry-after", "x-request-id", "x-yc-request-id"}

_SCHEMA = """
CREATE TABLE runs (
    id TEXT PRIMARY KEY,
    created_at_utc TEXT NOT NULL
);
CREATE TABLE semantic_requests (
    fingerprint TEXT PRIMARY KEY,
    descriptor_json TEXT NOT NULL
);
CREATE TABLE raw_artifacts (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    request_fingerprint TEXT NOT NULL REFERENCES semantic_requests(fingerprint),
    received_at_utc TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    safe_headers_json TEXT NOT NULL,
    relative_path TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL,
    byte_count INTEGER NOT NULL,
    redacted INTEGER NOT NULL CHECK (redacted IN (0, 1))
);
CREATE TABLE parse_batches (
    id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL REFERENCES raw_artifacts(id),
    parser_version TEXT NOT NULL,
    normalization_version TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('data', 'valid_empty')),
    parsed_at_utc TEXT NOT NULL,
    UNIQUE (artifact_id, parser_version, normalization_version)
);
CREATE TABLE canonical_phrases (
    id INTEGER PRIMARY KEY,
    normalization_version TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    UNIQUE (normalization_version, normalized_text)
);
CREATE TABLE observations (
    id INTEGER PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES parse_batches(id),
    canonical_id INTEGER NOT NULL REFERENCES canonical_phrases(id),
    raw_phrase TEXT NOT NULL,
    channel TEXT NOT NULL,
    rank INTEGER
);
CREATE TABLE measurements (
    id INTEGER PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES parse_batches(id),
    observation_id INTEGER REFERENCES observations(id),
    kind TEXT NOT NULL,
    value TEXT NOT NULL,
    unit TEXT NOT NULL,
    context_json TEXT NOT NULL
);
CREATE TABLE discovery_edges (
    id INTEGER PRIMARY KEY,
    observation_id INTEGER NOT NULL REFERENCES observations(id),
    relation TEXT NOT NULL,
    origin_kind TEXT NOT NULL,
    origin_ref TEXT NOT NULL
);
CREATE INDEX observations_batch ON observations(batch_id);
CREATE INDEX measurements_batch ON measurements(batch_id);
CREATE INDEX edges_observation ON discovery_edges(observation_id);
"""

_STAGE2_SCHEMA = """
CREATE TABLE run_states (
    run_id TEXT PRIMARY KEY REFERENCES runs(id),
    outcome TEXT NOT NULL DEFAULT 'incomplete',
    semantic_stop TEXT NOT NULL DEFAULT 'continuation_possible',
    pause_reason TEXT,
    resumability TEXT NOT NULL DEFAULT 'resumable_automatically',
    updated_at_utc TEXT NOT NULL
);
INSERT INTO run_states (run_id, updated_at_utc)
SELECT id, created_at_utc FROM runs;
CREATE TABLE capacity_buckets (
    id TEXT PRIMARY KEY,
    rps INTEGER NOT NULL CHECK (rps > 0),
    window_limit INTEGER NOT NULL CHECK (window_limit > 0),
    window_seconds INTEGER NOT NULL CHECK (window_seconds > 0),
    blocked_until REAL NOT NULL DEFAULT 0
);
CREATE TABLE run_budgets (
    run_id TEXT NOT NULL REFERENCES runs(id),
    bucket_id TEXT NOT NULL REFERENCES capacity_buckets(id),
    max_attempts INTEGER NOT NULL CHECK (max_attempts > 0),
    PRIMARY KEY (run_id, bucket_id)
);
CREATE TABLE work_items (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    logical_key TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL REFERENCES semantic_requests(fingerprint),
    bucket_id TEXT NOT NULL REFERENCES capacity_buckets(id),
    state TEXT NOT NULL,
    retry_at REAL,
    created_at_utc TEXT NOT NULL,
    UNIQUE (run_id, logical_key)
);
CREATE TABLE attempts (
    id INTEGER PRIMARY KEY,
    work_id TEXT NOT NULL REFERENCES work_items(id),
    bucket_id TEXT NOT NULL REFERENCES capacity_buckets(id),
    reserved_at REAL NOT NULL,
    dispatched_at REAL,
    completed_at REAL,
    state TEXT NOT NULL,
    outcome_kind TEXT,
    http_status INTEGER,
    detail_code TEXT
);
CREATE INDEX attempts_bucket_reserved ON attempts(bucket_id, reserved_at);
CREATE INDEX attempts_work ON attempts(work_id);
CREATE INDEX work_state ON work_items(state);
ALTER TABLE raw_artifacts ADD COLUMN attempt_id INTEGER REFERENCES attempts(id);
CREATE UNIQUE INDEX raw_attempt ON raw_artifacts(attempt_id) WHERE attempt_id IS NOT NULL;
"""

_STAGE5_SCHEMA = """
CREATE TABLE semantic_seed_batches (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    kind TEXT NOT NULL CHECK (kind IN ('llm_proposal', 'probe_generation')),
    parent_id TEXT REFERENCES semantic_seed_batches(id),
    created_at_utc TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    sha256 TEXT NOT NULL
);
CREATE INDEX semantic_seed_batches_run ON semantic_seed_batches(run_id, kind);
"""

_STAGE6_SCHEMA = """
CREATE TABLE semantic_branches (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    creation_key TEXT NOT NULL,
    transition_kind TEXT NOT NULL,
    origin_kind TEXT NOT NULL,
    origin_ref TEXT NOT NULL,
    family TEXT NOT NULL,
    label TEXT NOT NULL,
    creation_reason TEXT NOT NULL,
    state TEXT NOT NULL,
    state_reason TEXT,
    created_at_utc TEXT NOT NULL,
    UNIQUE (run_id, creation_key)
);
CREATE TABLE semantic_branch_parents (
    branch_id TEXT NOT NULL REFERENCES semantic_branches(id),
    parent_id TEXT NOT NULL REFERENCES semantic_branches(id),
    relation TEXT NOT NULL,
    PRIMARY KEY (branch_id, parent_id, relation)
);
CREATE TABLE semantic_branch_evidence (
    branch_id TEXT NOT NULL REFERENCES semantic_branches(id),
    observation_id INTEGER NOT NULL REFERENCES observations(id),
    role TEXT NOT NULL,
    PRIMARY KEY (branch_id, observation_id, role)
);
CREATE TABLE semantic_opportunities (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id),
    branch_id TEXT NOT NULL REFERENCES semantic_branches(id),
    provider TEXT NOT NULL,
    probe_family TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL REFERENCES semantic_requests(fingerprint),
    state TEXT NOT NULL,
    state_reason TEXT,
    outcome TEXT,
    tranche_number INTEGER,
    created_at_utc TEXT NOT NULL,
    UNIQUE (branch_id, probe_family, request_fingerprint)
);
CREATE INDEX semantic_opportunities_run_state ON semantic_opportunities(run_id, state);
CREATE INDEX semantic_opportunities_request ON semantic_opportunities(run_id, request_fingerprint);
CREATE TABLE semantic_frontier_policy (
    run_id TEXT PRIMARY KEY REFERENCES runs(id),
    policy_json TEXT NOT NULL,
    weak_tranches INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE semantic_tranches (
    run_id TEXT NOT NULL REFERENCES runs(id),
    number INTEGER NOT NULL,
    state TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    reviewed_at_utc TEXT,
    review_json TEXT,
    PRIMARY KEY (run_id, number)
);
CREATE TABLE semantic_tranche_requests (
    run_id TEXT NOT NULL,
    tranche_number INTEGER NOT NULL,
    request_fingerprint TEXT NOT NULL REFERENCES semantic_requests(fingerprint),
    selection_order INTEGER NOT NULL,
    phase TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (run_id, tranche_number, request_fingerprint),
    UNIQUE (run_id, request_fingerprint),
    UNIQUE (run_id, tranche_number, selection_order),
    FOREIGN KEY (run_id, tranche_number) REFERENCES semantic_tranches(run_id, number)
);
CREATE TABLE semantic_request_results (
    run_id TEXT NOT NULL REFERENCES runs(id),
    request_fingerprint TEXT NOT NULL REFERENCES semantic_requests(fingerprint),
    outcome TEXT NOT NULL,
    new_unique INTEGER NOT NULL,
    rediscovered INTEGER NOT NULL,
    newly_supported_branches INTEGER NOT NULL,
    completed_at_utc TEXT NOT NULL,
    PRIMARY KEY (run_id, request_fingerprint)
);
CREATE TABLE semantic_request_evidence (
    run_id TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    observation_id INTEGER NOT NULL REFERENCES observations(id),
    PRIMARY KEY (run_id, request_fingerprint, observation_id),
    FOREIGN KEY (run_id, request_fingerprint)
        REFERENCES semantic_request_results(run_id, request_fingerprint)
);
"""

_STAGE7_SCHEMA = """
CREATE TABLE collection_runs (
    run_id TEXT PRIMARY KEY REFERENCES runs(id),
    plan_json TEXT NOT NULL,
    plan_sha256 TEXT NOT NULL,
    adapter_context_json TEXT NOT NULL,
    proposal_batch_id TEXT REFERENCES semantic_seed_batches(id),
    probe_batch_id TEXT REFERENCES semantic_seed_batches(id),
    initialized INTEGER NOT NULL DEFAULT 0 CHECK (initialized IN (0, 1))
);
CREATE TABLE collection_disabled_providers (
    run_id TEXT NOT NULL REFERENCES collection_runs(run_id),
    provider TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (run_id, provider)
);
CREATE TABLE collection_branch_probes (
    branch_id TEXT PRIMARY KEY REFERENCES semantic_branches(id),
    batch_id TEXT NOT NULL REFERENCES semantic_seed_batches(id)
);
CREATE TABLE collection_snapshots (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES collection_runs(run_id),
    captured_at_utc TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    sha256 TEXT NOT NULL
);
CREATE INDEX collection_snapshots_run ON collection_snapshots(run_id, captured_at_utc);
"""

_STAGE8_SCHEMA = """
CREATE TABLE comparison_runs (
    id TEXT PRIMARY KEY,
    created_at_utc TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    plan_sha256 TEXT NOT NULL,
    adapter_context_json TEXT NOT NULL
);
CREATE TABLE comparison_topics (
    comparison_id TEXT NOT NULL REFERENCES comparison_runs(id),
    position INTEGER NOT NULL,
    topic TEXT NOT NULL,
    run_id TEXT NOT NULL UNIQUE REFERENCES collection_runs(run_id),
    plan_sha256 TEXT NOT NULL,
    PRIMARY KEY (comparison_id, position),
    UNIQUE (comparison_id, topic)
);
CREATE TABLE comparison_snapshots (
    id TEXT PRIMARY KEY,
    comparison_id TEXT NOT NULL REFERENCES comparison_runs(id),
    captured_at_utc TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    sha256 TEXT NOT NULL
);
CREATE INDEX comparison_snapshots_run ON comparison_snapshots(comparison_id, captured_at_utc);
"""

_STAGE10_SCHEMA = """
CREATE TABLE collection_association_reviews (
    branch_id TEXT NOT NULL REFERENCES semantic_branches(id),
    revision INTEGER NOT NULL CHECK (revision > 0),
    run_id TEXT NOT NULL REFERENCES collection_runs(run_id),
    decision TEXT NOT NULL CHECK (decision IN ('expand', 'uncertain', 'defer')),
    reason TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    review_version TEXT NOT NULL,
    input_sha256 TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    PRIMARY KEY (branch_id, revision)
);
CREATE INDEX collection_association_reviews_run ON collection_association_reviews(run_id);
"""

_STAGE11_SCHEMA = """
CREATE TABLE topvisor_jobs (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE REFERENCES runs(id),
    snapshot_id TEXT NOT NULL,
    snapshot_kind TEXT NOT NULL CHECK (snapshot_kind IN ('collect', 'compare')),
    keywords_json TEXT NOT NULL,
    keywords_sha256 TEXT NOT NULL,
    qualifiers_json TEXT NOT NULL,
    qualifiers_sha256 TEXT NOT NULL,
    max_cost TEXT,
    estimated_cost TEXT,
    currency TEXT,
    estimate_artifact_id TEXT REFERENCES raw_artifacts(id),
    state TEXT NOT NULL CHECK (state IN (
        'created', 'estimated', 'budget_blocked', 'intent_recorded',
        'ambiguous_submit', 'submitted', 'ongoing', 'completed',
        'expired_24h', 'failed'
    )),
    state_reason TEXT,
    remote_task_id INTEGER CHECK (remote_task_id IS NULL OR remote_task_id > 0),
    submit_artifact_id TEXT REFERENCES raw_artifacts(id),
    submitted_at_utc TEXT,
    expires_at_utc TEXT,
    last_task_artifact_id TEXT REFERENCES raw_artifacts(id),
    remote_task_status TEXT CHECK (remote_task_status IS NULL OR remote_task_status IN ('ongoing', 'completed')),
    completed_at_utc TEXT,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);
CREATE TABLE topvisor_job_phrases (
    job_id TEXT NOT NULL REFERENCES topvisor_jobs(id),
    position INTEGER NOT NULL CHECK (position >= 0),
    keyword TEXT NOT NULL,
    canonical_id INTEGER NOT NULL REFERENCES canonical_phrases(id),
    PRIMARY KEY (job_id, position),
    UNIQUE (job_id, keyword),
    UNIQUE (job_id, canonical_id)
);
CREATE TABLE topvisor_result_pages (
    job_id TEXT NOT NULL REFERENCES topvisor_jobs(id),
    region_key INTEGER NOT NULL,
    searcher_key INTEGER NOT NULL,
    frequency_type INTEGER NOT NULL,
    page_offset INTEGER NOT NULL CHECK (page_offset >= 0),
    page_limit INTEGER NOT NULL CHECK (page_limit > 0),
    artifact_id TEXT NOT NULL REFERENCES raw_artifacts(id),
    batch_id TEXT NOT NULL REFERENCES parse_batches(id),
    row_count INTEGER NOT NULL CHECK (row_count >= 0),
    recorded_at_utc TEXT NOT NULL,
    PRIMARY KEY (job_id, region_key, searcher_key, frequency_type, page_offset)
);
CREATE INDEX topvisor_jobs_snapshot ON topvisor_jobs(snapshot_id, created_at_utc);
CREATE INDEX topvisor_job_phrases_canonical ON topvisor_job_phrases(canonical_id);
"""

_BUDGET_EXTENSION_SCHEMA = """
CREATE TABLE collection_budget_extensions (
    run_id TEXT NOT NULL REFERENCES collection_runs(run_id),
    revision INTEGER NOT NULL CHECK (revision > 0),
    old_plan_json TEXT NOT NULL,
    old_plan_sha256 TEXT NOT NULL,
    new_plan_json TEXT NOT NULL,
    new_plan_sha256 TEXT NOT NULL,
    changed_at_utc TEXT NOT NULL,
    PRIMARY KEY (run_id, revision)
);
"""

_GUIDED_COLLECTION_SCHEMA = """
CREATE TABLE guided_collection_runs (
    run_id TEXT PRIMARY KEY REFERENCES runs(id),
    phase TEXT NOT NULL,
    scout_request_fingerprint TEXT NOT NULL REFERENCES semantic_requests(fingerprint),
    scout_work_id TEXT NOT NULL REFERENCES work_items(id),
    scout_context_json TEXT NOT NULL,
    checkpoint_json TEXT,
    updated_at_utc TEXT NOT NULL
);
CREATE TABLE guided_branch_reviews (
    run_id TEXT NOT NULL REFERENCES guided_collection_runs(run_id),
    branch_id TEXT NOT NULL REFERENCES semantic_branches(id),
    decision TEXT NOT NULL CHECK (decision IN ('expand', 'defer')),
    reason TEXT NOT NULL,
    checkpoint_sha256 TEXT NOT NULL,
    reviewed_at_utc TEXT NOT NULL,
    PRIMARY KEY (run_id, branch_id)
);
"""


class ArtifactIntegrityError(RuntimeError):
    """Stored raw is missing, outside the store, or different from its digest."""


class SchemaVersionError(RuntimeError):
    """The store needs a migration or belongs to another application."""


class ParserFailure(ValueError):
    """The saved response could not be interpreted by this parser version."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_timestamp(name: str, value: str | None) -> str:
    if value is None:
        return _now()
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be an ISO UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an ISO UTC timestamp") from error
    if parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must include a UTC offset")
    return value


def _decimal_text(name: str, value: object) -> str:
    if isinstance(value, bool):
        raise ValueError(f"{name} cannot be boolean")
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{name} must be a decimal value") from error
    if not decimal.is_finite() or decimal < 0:
        raise ValueError(f"{name} must be a nonnegative finite decimal")
    return str(decimal)


def _qualifier_descriptor(item: object) -> dict[str, int]:
    if hasattr(item, "descriptor") and callable(getattr(item, "descriptor")):
        raw = item.descriptor()
    elif isinstance(item, Mapping):
        raw = dict(item)
    else:
        raise ValueError("qualifier must be a mapping or FrequencyQualifier")
    if not isinstance(raw, Mapping):
        raise ValueError("qualifier descriptor must be a mapping")
    allowed = {"region_key", "searcher_key", "type", "frequency_type"}
    if set(raw) - allowed or ("type" in raw and "frequency_type" in raw):
        raise ValueError("invalid qualifier fields")
    region_key = raw.get("region_key")
    searcher_key = raw.get("searcher_key")
    frequency_type = raw.get("type", raw.get("frequency_type"))
    for label, number in (
        ("region_key", region_key),
        ("searcher_key", searcher_key),
        ("frequency_type", frequency_type),
    ):
        if isinstance(number, bool) or not isinstance(number, int) or number < 0:
            raise ValueError(f"{label} must be a nonnegative integer")
    if searcher_key not in (0, 1):
        raise ValueError("unsupported searcher key")
    if frequency_type not in _TOPVISOR_FREQUENCY_TYPES:
        raise ValueError("unsupported Yandex frequency type")
    return {
        "region_key": region_key,
        "searcher_key": searcher_key,
        "type": frequency_type,
    }


def _safe_headers(headers: object) -> dict[str, str]:
    result: dict[str, str] = {}
    for name, value in headers.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise ValueError("response header names and values must be text")
        lowered = name.lower()
        if lowered in _SAFE_HEADER_NAMES or lowered.startswith(("x-ratelimit-", "ratelimit-")):
            result[lowered] = value
    return result


class DataStore:
    """Single-process SQLite and raw store with OS-managed exclusive ownership."""

    def __init__(self, directory: Path | str):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self._owner = StoreLock(self.directory)
        self.raw_directory = self.directory / "raw"
        try:
            self.raw_directory.mkdir(exist_ok=True)
            self._db = sqlite3.connect(self.directory / "state.sqlite3")
            self._db.row_factory = sqlite3.Row
            self._db.execute("PRAGMA foreign_keys=ON")
            self._db.execute("PRAGMA synchronous=FULL")
            self._initialize_schema()
        except Exception:
            if hasattr(self, "_db"):
                self._db.close()
            self._owner.close()
            raise

    def _initialize_schema(self) -> None:
        version = self._db.execute("PRAGMA user_version").fetchone()[0]
        migrations = (
            _SCHEMA, _STAGE2_SCHEMA, _STAGE5_SCHEMA, _STAGE6_SCHEMA,
            _STAGE7_SCHEMA, _STAGE8_SCHEMA, _STAGE10_SCHEMA, _STAGE11_SCHEMA,
            _BUDGET_EXTENSION_SCHEMA, _GUIDED_COLLECTION_SCHEMA,
        )
        if version == 0:
            names = self._db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            if names:
                raise SchemaVersionError("unversioned nonempty SQLite database")
        if 0 <= version < SCHEMA_VERSION:
            script = "".join(migrations[version:])
            try:
                self._db.executescript(
                    f"BEGIN IMMEDIATE;\n{script}\nPRAGMA user_version={SCHEMA_VERSION};\nCOMMIT;"
                )
            except Exception:
                self._db.rollback()
                raise
        elif version != SCHEMA_VERSION:
            raise SchemaVersionError(f"unsupported store schema version: {version}")

    def close(self) -> None:
        try:
            self._db.close()
        finally:
            self._owner.close()

    def __enter__(self) -> DataStore:
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.close()

    def create_run(self) -> str:
        """Create a provenance anchor and an independent operational state."""
        run_id = uuid.uuid4().hex
        with self._db:
            self._db.execute("INSERT INTO runs VALUES (?, ?)", (run_id, _now()))
            self._db.execute(
                "INSERT INTO run_states (run_id, updated_at_utc) VALUES (?, ?)",
                (run_id, _now()),
            )
        return run_id

    def _save_seed_batch(
        self, run_id: str, kind: str, payload: dict[str, object],
        *, parent_id: str | None = None,
    ) -> str:
        if self._db.execute("SELECT 1 FROM runs WHERE id=?", (run_id,)).fetchone() is None:
            raise ValueError("run_id does not exist")
        if parent_id is not None:
            parent = self._db.execute(
                "SELECT run_id, kind FROM semantic_seed_batches WHERE id=?", (parent_id,)
            ).fetchone()
            if parent is None or parent["run_id"] != run_id or parent["kind"] != "llm_proposal":
                raise ValueError("parent must be an LLM proposal batch from the same run")
        if kind == "llm_proposal" and parent_id is not None:
            raise ValueError("LLM proposal cannot have a parent batch")
        encoded = canonical_json(payload)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        batch_id = uuid.uuid4().hex
        with self._db:
            self._db.execute(
                "INSERT INTO semantic_seed_batches VALUES (?, ?, ?, ?, ?, ?, ?)",
                (batch_id, run_id, kind, parent_id, _now(), encoded, digest),
            )
        return batch_id

    def save_llm_proposal(self, run_id: str, proposal: LLMProposalBatch) -> str:
        """Record a model proposal as a hypothesis, never an external observation."""
        if not isinstance(proposal, LLMProposalBatch):
            raise TypeError("proposal must be an LLMProposalBatch")
        return self._save_seed_batch(run_id, "llm_proposal", proposal.descriptor())

    def save_probe_generation(
        self, run_id: str, plan: ProbePlan, *, parent_id: str | None = None,
    ) -> tuple[str, ProbeBatch]:
        """Persist an explicit, one-pass plan and all origins before provider use."""
        if not isinstance(plan, ProbePlan):
            raise TypeError("plan must be a ProbePlan")
        for seed in plan.seeds:
            if seed.origin_kind != "observation":
                continue
            try:
                observation_id = int(seed.origin_ref)
            except ValueError:
                raise ValueError("observation seed reference must be an ID") from None
            source = self._db.execute(
                "SELECT o.raw_phrase FROM observations o "
                "JOIN parse_batches b ON b.id=o.batch_id "
                "JOIN raw_artifacts a ON a.id=b.artifact_id WHERE o.id=?",
                (observation_id,),
            ).fetchone()
            if source is None or source["raw_phrase"] != seed.phrase:
                raise ValueError("observation seed does not match its reference")
        if any(seed.origin_kind == "llm_hypothesis" for seed in plan.seeds) and parent_id is None:
            raise ValueError("LLM hypothesis seeds require their proposal batch parent")
        if parent_id is not None:
            parent = self.load_seed_batch(parent_id)
            if parent["run_id"] != run_id or parent["kind"] != "llm_proposal":
                raise ValueError("parent must be an LLM proposal batch from the same run")
            proposal = parent["payload"]
            hypotheses = proposal["hypotheses"]
            for seed in plan.seeds:
                if seed.origin_kind != "llm_hypothesis":
                    continue
                prefix = f"{parent_id}:"
                if not seed.origin_ref.startswith(prefix):
                    raise ValueError("LLM seed reference does not match parent batch")
                try:
                    index = int(seed.origin_ref[len(prefix):])
                    hypothesis = hypotheses[index]
                except (ValueError, IndexError):
                    raise ValueError("invalid LLM hypothesis reference") from None
                if index < 0 or seed.phrase != hypothesis["phrase"] or seed.family.value != hypothesis["family"]:
                    raise ValueError("LLM seed differs from its saved hypothesis")
            proposed_rules = {rule["id"]: rule for rule in proposal["proposed_rules"]}
            for rule in plan.rules:
                if rule.origin == "llm_proposed" and proposed_rules.get(rule.id) != rule.descriptor():
                    raise ValueError("model-proposed mask differs from its saved proposal")
        elif any(rule.origin == "llm_proposed" for rule in plan.rules):
            raise ValueError("model-proposed masks require their proposal batch parent")
        generated = generate_probes(plan)
        batch_id = self._save_seed_batch(
            run_id, "probe_generation",
            {"plan": plan.descriptor(), "result": generated.descriptor()},
            parent_id=parent_id,
        )
        return batch_id, generated

    def load_seed_batch(self, batch_id: str) -> dict[str, object]:
        row = self._db.execute(
            "SELECT id, run_id, kind, parent_id, created_at_utc, payload_json, sha256 "
            "FROM semantic_seed_batches WHERE id=?", (batch_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown semantic seed batch: {batch_id}")
        encoded = row["payload_json"]
        if hashlib.sha256(encoded.encode("utf-8")).hexdigest() != row["sha256"]:
            raise ArtifactIntegrityError("semantic seed batch digest mismatch")
        return {
            "id": row["id"], "run_id": row["run_id"], "kind": row["kind"],
            "parent_id": row["parent_id"], "created_at_utc": row["created_at_utc"],
            "payload": json.loads(encoded),
        }

    def save_raw(
        self,
        run_id: str,
        request: SemanticRequest,
        response: RawResponse,
        *,
        redactions: Sequence[bytes],
        attempt_id: int | None = None,
    ) -> str:
        """Persist sanitized response bytes before committing their metadata.

        Adapters must pass their current secrets and sensitive IDs as redactions.
        A crash before the SQLite insert may leave an orphan file; startup repair
        and intent semantics are specifically reserved for stage 2.
        """
        if self._db.execute("SELECT 1 FROM runs WHERE id=?", (run_id,)).fetchone() is None:
            raise ValueError("run_id does not exist")
        for secret in redactions:
            if not isinstance(secret, bytes) or not secret:
                raise ValueError("redactions must contain nonempty bytes")
        descriptor_json = json.dumps(
            request.descriptor(), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        if any(secret in descriptor_json.encode("utf-8") for secret in redactions):
            raise ValueError("semantic request descriptor contains a sensitive value")
        body = response.body
        for secret in redactions:
            body = body.replace(secret, b"[REDACTED]")
        redacted = body != response.body
        headers = _safe_headers(response.headers)
        for name, value in headers.items():
            encoded = value.encode("utf-8")
            for secret in redactions:
                encoded = encoded.replace(secret, b"[REDACTED]")
            sanitized = encoded.decode("utf-8")
            redacted = redacted or sanitized != value
            headers[name] = sanitized
        request_id = fingerprint(request)
        if attempt_id is not None:
            attempt = self._db.execute(
                "SELECT a.state, w.run_id, w.request_fingerprint FROM attempts a "
                "JOIN work_items w ON w.id=a.work_id WHERE a.id=?", (attempt_id,),
            ).fetchone()
            if (attempt is None or attempt["state"] != "dispatched"
                    or attempt["run_id"] != run_id
                    or attempt["request_fingerprint"] != request_id):
                raise ValueError("attempt is not dispatched for this run and request")
        artifact_id = uuid.uuid4().hex
        relative = Path(artifact_id[:2]) / f"{artifact_id}.bin"
        final_path = self.raw_directory / relative
        final_path.parent.mkdir(exist_ok=True)
        temporary = final_path.with_suffix(".tmp")
        with temporary.open("xb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, final_path)
        digest = hashlib.sha256(body).hexdigest()
        with self._db:
            self._db.execute(
                "INSERT OR IGNORE INTO semantic_requests VALUES (?, ?)",
                (request_id, descriptor_json),
            )
            stored = self._db.execute(
                "SELECT descriptor_json FROM semantic_requests WHERE fingerprint=?", (request_id,)
            ).fetchone()[0]
            if stored != descriptor_json:
                raise RuntimeError("semantic fingerprint collision or descriptor drift")
            self._db.execute(
                "INSERT INTO raw_artifacts "
                "(id, run_id, request_fingerprint, received_at_utc, status_code, "
                "safe_headers_json, relative_path, sha256, byte_count, redacted, attempt_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    artifact_id, run_id, request_id, response.received_at_utc or _now(),
                    response.status_code,
                    json.dumps(headers, ensure_ascii=False, sort_keys=True),
                    relative.as_posix(), digest, len(body), int(redacted), attempt_id,
                ),
            )
        return artifact_id

    def _artifact_row(self, artifact_id: str) -> sqlite3.Row:
        row = self._db.execute(
            "SELECT a.*, r.descriptor_json FROM raw_artifacts a "
            "JOIN semantic_requests r ON r.fingerprint=a.request_fingerprint WHERE a.id=?",
            (artifact_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown raw artifact: {artifact_id}")
        return row

    def read_raw(self, artifact_id: str) -> bytes:
        row = self._artifact_row(artifact_id)
        path = (self.raw_directory / row["relative_path"]).resolve()
        if not path.is_relative_to(self.raw_directory.resolve()):
            raise ArtifactIntegrityError("artifact path escaped raw directory")
        try:
            body = path.read_bytes()
        except FileNotFoundError as error:
            raise ArtifactIntegrityError("raw artifact is missing") from error
        if len(body) != row["byte_count"] or hashlib.sha256(body).hexdigest() != row["sha256"]:
            raise ArtifactIntegrityError("raw artifact digest mismatch")
        return body

    def artifact_metadata(self, artifact_id: str) -> dict[str, object]:
        row = self._artifact_row(artifact_id)
        return {
            "id": artifact_id,
            "run_id": row["run_id"],
            "request_fingerprint": row["request_fingerprint"],
            "request": json.loads(row["descriptor_json"]),
            "received_at_utc": row["received_at_utc"],
            "status_code": row["status_code"],
            "safe_headers": json.loads(row["safe_headers_json"]),
            "sha256": row["sha256"],
            "byte_count": row["byte_count"],
            "redacted": bool(row["redacted"]),
            "attempt_id": row["attempt_id"],
        }

    def parse_artifact(
        self,
        artifact_id: str,
        parser: Callable[[bytes, SemanticRequest], ParseResult],
        *,
        parser_version: str,
        normalization_version: str = NORMALIZATION_VERSION,
        normalizer: Callable[[str], str] = normalize_phrase_v1,
        _within_transaction: bool = False,
    ) -> str:
        """Append derived observations from durable raw without external I/O."""
        if not parser_version.strip() or not normalization_version.strip():
            raise ValueError("parser and normalization versions must be nonempty")
        if normalization_version != NORMALIZATION_VERSION and normalizer is normalize_phrase_v1:
            raise ValueError("new normalization version requires an explicit normalizer")
        row = self._artifact_row(artifact_id)
        body = self.read_raw(artifact_id)
        if not 200 <= row["status_code"] < 300:
            raise ValueError("HTTP error raw cannot be parsed as successful observations")
        existing = self._db.execute(
            "SELECT id FROM parse_batches WHERE artifact_id=? AND parser_version=? AND normalization_version=?",
            (artifact_id, parser_version, normalization_version),
        ).fetchone()
        if existing:
            return existing[0]
        request = SemanticRequest.from_mapping(json.loads(row["descriptor_json"]))
        try:
            parsed = parser(body, request)
            if not isinstance(parsed, ParseResult):
                raise ParserFailure("parser must return ParseResult; errors cannot become empty")
            normalized = [normalizer(item.phrase) for item in parsed.observations]
            for phrase in normalized:
                if not isinstance(phrase, str) or not phrase:
                    raise ParserFailure("normalizer returned an empty or invalid phrase")
        except ParserFailure:
            raise
        except Exception as error:
            raise ParserFailure(f"parser or normalizer raised {type(error).__name__}") from error
        batch_id = uuid.uuid4().hex
        with (nullcontext() if _within_transaction else self._db):
            self._db.execute(
                "INSERT INTO parse_batches VALUES (?, ?, ?, ?, ?, ?)",
                (batch_id, artifact_id, parser_version, normalization_version, parsed.kind, _now()),
            )
            observation_ids: list[int] = []
            for observation, canonical in zip(parsed.observations, normalized):
                self._db.execute(
                    "INSERT OR IGNORE INTO canonical_phrases (normalization_version, normalized_text) VALUES (?, ?)",
                    (normalization_version, canonical),
                )
                canonical_id = self._db.execute(
                    "SELECT id FROM canonical_phrases WHERE normalization_version=? AND normalized_text=?",
                    (normalization_version, canonical),
                ).fetchone()[0]
                cursor = self._db.execute(
                    "INSERT INTO observations (batch_id, canonical_id, raw_phrase, channel, rank) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (batch_id, canonical_id, observation.phrase, observation.channel, observation.rank),
                )
                observation_ids.append(cursor.lastrowid)
            for measurement in parsed.measurements:
                observation_id = (
                    observation_ids[measurement.observation_index]
                    if measurement.observation_index is not None else None
                )
                self._db.execute(
                    "INSERT INTO measurements (batch_id, observation_id, kind, value, unit, context_json) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        batch_id, observation_id, measurement.kind, str(measurement.value),
                        measurement.unit, measurement.context_json,
                    ),
                )
            for edge in parsed.discovery_edges:
                self._db.execute(
                    "INSERT INTO discovery_edges (observation_id, relation, origin_kind, origin_ref) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        observation_ids[edge.observation_index], edge.relation,
                        edge.origin_kind, edge.origin_ref,
                    ),
                )
        return batch_id

    def observations(self, batch_id: str) -> list[dict[str, object]]:
        rows = self._db.execute(
            "SELECT o.id, o.raw_phrase, o.channel, o.rank, c.normalized_text, "
            "c.normalization_version FROM observations o "
            "JOIN canonical_phrases c ON c.id=o.canonical_id WHERE o.batch_id=? ORDER BY o.id",
            (batch_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def measurements(self, batch_id: str) -> list[dict[str, object]]:
        rows = self._db.execute(
            "SELECT id, observation_id, kind, value, unit, context_json "
            "FROM measurements WHERE batch_id=? ORDER BY id", (batch_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def provenance(self, observation_id: int) -> dict[str, object]:
        row = self._db.execute(
            "SELECT o.raw_phrase, o.channel, o.rank, c.normalized_text, "
            "b.id AS batch_id, b.parser_version, b.normalization_version, "
            "a.id AS artifact_id, a.run_id, a.request_fingerprint, r.descriptor_json "
            "FROM observations o JOIN canonical_phrases c ON c.id=o.canonical_id "
            "JOIN parse_batches b ON b.id=o.batch_id "
            "JOIN raw_artifacts a ON a.id=b.artifact_id "
            "JOIN semantic_requests r ON r.fingerprint=a.request_fingerprint WHERE o.id=?",
            (observation_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown observation: {observation_id}")
        edges = self._db.execute(
            "SELECT relation, origin_kind, origin_ref FROM discovery_edges "
            "WHERE observation_id=? ORDER BY id", (observation_id,),
        ).fetchall()
        return {
            "observation_id": observation_id,
            "original_phrase": row["raw_phrase"],
            "canonical_phrase": row["normalized_text"],
            "channel": row["channel"],
            "rank": row["rank"],
            "parser_version": row["parser_version"],
            "normalization_version": row["normalization_version"],
            "batch_id": row["batch_id"],
            "artifact_id": row["artifact_id"],
            "run_id": row["run_id"],
            "request_fingerprint": row["request_fingerprint"],
            "request": json.loads(row["descriptor_json"]),
            "discovery_edges": [dict(edge) for edge in edges],
        }

    def _verified_snapshot_phrases(self, snapshot_id: str) -> tuple[str, list[dict[str, object]]]:
        row = self._db.execute(
            "SELECT run_id, payload_json, sha256 FROM collection_snapshots WHERE id=?",
            (snapshot_id,),
        ).fetchone()
        if row is not None:
            encoded = row["payload_json"]
            if hashlib.sha256(encoded.encode("utf-8")).hexdigest() != row["sha256"] or row["sha256"] != snapshot_id:
                raise ArtifactIntegrityError("collection snapshot digest mismatch")
            payload = json.loads(encoded)
            if payload.get("run_id") != row["run_id"]:
                raise ArtifactIntegrityError("collection snapshot run mismatch")
            for request in payload.get("requests", ()):
                artifact = self._artifact_row(request["raw_artifact_id"])
                if (artifact["sha256"] != request["raw_sha256"]
                        or artifact["request_fingerprint"] != request["fingerprint"]):
                    raise ArtifactIntegrityError("collection raw reference mismatch")
                self.read_raw(request["raw_artifact_id"])
            phrases: list[dict[str, object]] = []
            seen: set[int] = set()
            for item in payload.get("phrases", ()):
                canonical_id = item["canonical_id"]
                normalized_phrase = item["normalized_phrase"]
                stored = self._db.execute(
                    "SELECT normalized_text FROM canonical_phrases WHERE id=?",
                    (canonical_id,),
                ).fetchone()
                if stored is None or stored["normalized_text"] != normalized_phrase:
                    raise ArtifactIntegrityError("snapshot canonical phrase mismatch")
                if canonical_id not in seen:
                    seen.add(canonical_id)
                    phrases.append({
                        "canonical_id": canonical_id,
                        "normalized_phrase": normalized_phrase,
                    })
            phrases.sort(key=lambda entry: str(entry["normalized_phrase"]))
            return "collect", phrases

        row = self._db.execute(
            "SELECT comparison_id, payload_json, sha256 FROM comparison_snapshots WHERE id=?",
            (snapshot_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown snapshot: {snapshot_id}")
        encoded = row["payload_json"]
        if hashlib.sha256(encoded.encode("utf-8")).hexdigest() != row["sha256"] or row["sha256"] != snapshot_id:
            raise ArtifactIntegrityError("comparison snapshot digest mismatch")
        payload = json.loads(encoded)
        members = self._db.execute(
            "SELECT position, topic, run_id, plan_sha256 FROM comparison_topics "
            "WHERE comparison_id=? ORDER BY position",
            (row["comparison_id"],),
        ).fetchall()
        topics = payload.get("topics", ())
        if payload.get("comparison_id") != row["comparison_id"] or len(members) != len(topics):
            raise ArtifactIntegrityError("comparison membership mismatch")
        by_canonical: dict[int, dict[str, object]] = {}
        for index, (topic, member) in enumerate(zip(topics, members)):
            if (topic["position"] != index or topic["topic"] != member["topic"]
                    or topic["run_id"] != member["run_id"]
                    or topic["plan_sha256"] != member["plan_sha256"]):
                raise ArtifactIntegrityError("comparison topic mapping mismatch")
            kind, dataset_phrases = self._verified_snapshot_phrases(topic["collection_snapshot_id"])
            if kind != "collect":
                raise ArtifactIntegrityError("comparison member must be a collection snapshot")
            for phrase in dataset_phrases:
                by_canonical.setdefault(int(phrase["canonical_id"]), phrase)
        merged = sorted(by_canonical.values(), key=lambda entry: str(entry["normalized_phrase"]))
        return "compare", merged

    def _verified_job_artifact(self, run_id: str, artifact_id: str) -> sqlite3.Row:
        row = self._artifact_row(artifact_id)
        if row["run_id"] != run_id:
            raise ValueError("raw artifact belongs to a different run")
        if not 200 <= row["status_code"] < 300:
            raise ValueError("Topvisor operation requires an HTTP 2xx raw artifact")
        self.read_raw(artifact_id)
        return row

    def plan_unknown_topvisor_measurements(
        self, snapshot_id: str, qualifiers: Sequence[object], *,
        phrases: Sequence[str] | None = None,
    ) -> dict[str, object]:
        """Read verified evidence and plan only missing phrase × qualifier pairs."""
        from .exports import SnapshotStore, read_snapshot
        from .measurement_selection import select_unknown_measurements

        descriptors = [_qualifier_descriptor(item) for item in qualifiers]
        self._verified_snapshot_phrases(snapshot_id)
        with SnapshotStore(self.directory) as reader:
            snapshot = read_snapshot(reader, snapshot_id)
        return select_unknown_measurements(snapshot, descriptors, phrases=phrases)

    def create_topvisor_job(
        self,
        snapshot_id: str,
        qualifiers: Sequence[object],
        *,
        phrases: Sequence[str] | None = None,
        max_cost: Decimal | str | int | None = None,
    ) -> str:
        """Create an isolated Topvisor job over a verified immutable snapshot."""
        if not isinstance(snapshot_id, str) or not snapshot_id.strip():
            raise ValueError("snapshot_id must be nonempty text")
        if isinstance(qualifiers, (str, bytes)) or not isinstance(qualifiers, Sequence) or not qualifiers:
            raise ValueError("nonempty unique qualifiers are required")
        normalized_qualifiers = [_qualifier_descriptor(item) for item in qualifiers]
        qualifier_keys = [
            (item["region_key"], item["searcher_key"], item["type"])
            for item in normalized_qualifiers
        ]
        if len(set(qualifier_keys)) != len(qualifier_keys):
            raise ValueError("nonempty unique qualifiers are required")
        max_cost_text = _decimal_text("max_cost", max_cost) if max_cost is not None else None
        snapshot_kind, snapshot_phrases = self._verified_snapshot_phrases(snapshot_id)
        by_normalized = {
            str(item["normalized_phrase"]): int(item["canonical_id"])
            for item in snapshot_phrases
        }
        selected: list[tuple[str, int]] = []
        if phrases is None:
            for item in snapshot_phrases:
                selected.append((str(item["normalized_phrase"]), int(item["canonical_id"])))
        else:
            if isinstance(phrases, (str, bytes)) or not isinstance(phrases, Sequence) or not phrases:
                raise ValueError("phrases must be a nonempty sequence of strings")
            seen_canonical: set[int] = set()
            seen_keywords: set[str] = set()
            for raw_phrase in phrases:
                if not isinstance(raw_phrase, str) or not raw_phrase.strip():
                    raise ValueError("nonempty keywords are required")
                keyword = raw_phrase.strip()
                normalized = normalize_phrase_v1(keyword)
                if normalized not in by_normalized:
                    raise ValueError(f"phrase does not belong to snapshot: {keyword}")
                canonical_id = by_normalized[normalized]
                if keyword in seen_keywords or canonical_id in seen_canonical:
                    raise ValueError("duplicate keywords must be resolved before billing")
                seen_keywords.add(keyword)
                seen_canonical.add(canonical_id)
                selected.append((keyword, canonical_id))
        if not selected:
            raise ValueError("snapshot contains no phrases to measure")

        keywords = [keyword for keyword, _ in selected]
        keywords_json = canonical_json(keywords)
        keywords_sha256 = hashlib.sha256(keywords_json.encode("utf-8")).hexdigest()
        qualifiers_json = canonical_json(normalized_qualifiers)
        qualifiers_sha256 = hashlib.sha256(qualifiers_json.encode("utf-8")).hexdigest()
        job_id = uuid.uuid4().hex
        run_id = uuid.uuid4().hex
        now = _now()
        with self._db:
            self._db.execute("INSERT INTO runs VALUES (?, ?)", (run_id, now))
            self._db.execute(
                "INSERT INTO run_states (run_id, updated_at_utc) VALUES (?, ?)",
                (run_id, now),
            )
            self._db.execute(
                "INSERT INTO topvisor_jobs ("
                "id, run_id, snapshot_id, snapshot_kind, keywords_json, keywords_sha256, "
                "qualifiers_json, qualifiers_sha256, max_cost, estimated_cost, currency, "
                "estimate_artifact_id, state, state_reason, remote_task_id, submit_artifact_id, "
                "submitted_at_utc, expires_at_utc, last_task_artifact_id, remote_task_status, "
                "completed_at_utc, created_at_utc, updated_at_utc"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, 'created', NULL, NULL, NULL, "
                "NULL, NULL, NULL, NULL, NULL, ?, ?)",
                (
                    job_id, run_id, snapshot_id, snapshot_kind,
                    keywords_json, keywords_sha256, qualifiers_json, qualifiers_sha256,
                    max_cost_text, now, now,
                ),
            )
            for position, (keyword, canonical_id) in enumerate(selected):
                self._db.execute(
                    "INSERT INTO topvisor_job_phrases VALUES (?, ?, ?, ?)",
                    (job_id, position, keyword, canonical_id),
                )
        return job_id

    def topvisor_job(self, job_id: str) -> dict[str, object]:
        row = self._db.execute(
            "SELECT * FROM topvisor_jobs WHERE id=?", (job_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown Topvisor job: {job_id}")
        keywords_json = row["keywords_json"]
        qualifiers_json = row["qualifiers_json"]
        if (hashlib.sha256(keywords_json.encode("utf-8")).hexdigest() != row["keywords_sha256"]
                or hashlib.sha256(qualifiers_json.encode("utf-8")).hexdigest() != row["qualifiers_sha256"]):
            raise ArtifactIntegrityError("Topvisor job payload digest mismatch")
        keywords = json.loads(keywords_json)
        qualifiers = json.loads(qualifiers_json)
        phrase_rows = self._db.execute(
            "SELECT p.position, p.keyword, p.canonical_id, c.normalized_text AS normalized_phrase "
            "FROM topvisor_job_phrases p JOIN canonical_phrases c ON c.id=p.canonical_id "
            "WHERE p.job_id=? ORDER BY p.position",
            (job_id,),
        ).fetchall()
        if [item["keyword"] for item in phrase_rows] != keywords:
            raise ArtifactIntegrityError("Topvisor job phrase table does not match keywords digest")
        pages = [dict(item) for item in self._db.execute(
            "SELECT region_key, searcher_key, frequency_type, page_offset, page_limit, "
            "artifact_id, batch_id, row_count, recorded_at_utc "
            "FROM topvisor_result_pages WHERE job_id=? "
            "ORDER BY region_key, searcher_key, frequency_type, page_offset",
            (job_id,),
        ).fetchall()]
        run_state_row = self._db.execute(
            "SELECT outcome, semantic_stop, pause_reason, resumability, updated_at_utc "
            "FROM run_states WHERE run_id=?",
            (row["run_id"],),
        ).fetchone()
        return {
            "id": row["id"],
            "job_id": row["id"],
            "run_id": row["run_id"],
            "snapshot_id": row["snapshot_id"],
            "snapshot_kind": row["snapshot_kind"],
            "keywords": keywords,
            "keywords_sha256": row["keywords_sha256"],
            "qualifiers": qualifiers,
            "qualifiers_sha256": row["qualifiers_sha256"],
            "phrases": [dict(item) for item in phrase_rows],
            "max_cost": row["max_cost"],
            "estimated_cost": row["estimated_cost"],
            "currency": row["currency"],
            "estimate_artifact_id": row["estimate_artifact_id"],
            "state": row["state"],
            "state_reason": row["state_reason"],
            "remote_task_id": row["remote_task_id"],
            "submit_artifact_id": row["submit_artifact_id"],
            "submitted_at_utc": row["submitted_at_utc"],
            "expires_at_utc": row["expires_at_utc"],
            "last_task_artifact_id": row["last_task_artifact_id"],
            "remote_task_status": row["remote_task_status"],
            "completed_at_utc": row["completed_at_utc"],
            "created_at_utc": row["created_at_utc"],
            "updated_at_utc": row["updated_at_utc"],
            "pages": pages,
            "run_state": dict(run_state_row) if run_state_row is not None else None,
        }

    def record_topvisor_estimate(
        self,
        job_id: str,
        *,
        estimated_cost: Decimal | str | int,
        artifact_id: str,
        currency: str | None = None,
    ) -> dict[str, object]:
        """Save verified price estimate raw and compare against max_cost if already configured."""
        job = self.topvisor_job(job_id)
        if job["state"] not in {"created", "estimated", "budget_blocked"}:
            raise ValueError(f"cannot record estimate in state {job['state']}")
        if currency is not None and (not isinstance(currency, str) or not currency.strip()):
            raise ValueError("currency must be nonempty text when provided")
        cost_text = _decimal_text("estimated_cost", estimated_cost)
        self._verified_job_artifact(str(job["run_id"]), artifact_id)
        blocked = (
            job["max_cost"] is not None
            and Decimal(cost_text) > Decimal(str(job["max_cost"]))
        )
        state = "budget_blocked" if blocked else "estimated"
        reason = "estimated_cost_exceeds_max_cost" if blocked else None
        now = _now()
        with self._db:
            self._db.execute(
                "UPDATE topvisor_jobs SET estimated_cost=?, currency=?, estimate_artifact_id=?, "
                "state=?, state_reason=?, updated_at_utc=? WHERE id=?",
                (cost_text, currency, artifact_id, state, reason, now, job_id),
            )
            self._db.execute(
                "UPDATE run_states SET outcome='incomplete', pause_reason=?, resumability=?, "
                "updated_at_utc=? WHERE run_id=?",
                (
                    "budget_blocked" if blocked else None,
                    "requires_operator_decision" if blocked else "resumable_automatically",
                    now,
                    job["run_id"],
                ),
            )
        return self.topvisor_job(job_id)

    def record_topvisor_submit_intent(
        self,
        job_id: str,
        *,
        max_cost: Decimal | str | int | None = None,
    ) -> dict[str, object]:
        """Enforce budget ceiling and persist durable intent before paid submit dispatch."""
        job = self.topvisor_job(job_id)
        if job["state"] in {
            "intent_recorded", "ambiguous_submit", "submitted",
            "ongoing", "completed", "expired_24h",
        }:
            raise ValueError(f"paid submit intent is blocked in state {job['state']}")
        if job["estimated_cost"] is None or job["estimate_artifact_id"] is None:
            raise ValueError("price estimate is required before paid Topvisor submit")
        self._verified_job_artifact(str(job["run_id"]), str(job["estimate_artifact_id"]))
        ceiling_source = max_cost if max_cost is not None else job["max_cost"]
        if ceiling_source is None:
            raise ValueError("max_cost is required before paid Topvisor submit")
        ceiling_text = _decimal_text("max_cost", ceiling_source)
        now = _now()
        if Decimal(str(job["estimated_cost"])) > Decimal(ceiling_text):
            with self._db:
                self._db.execute(
                    "UPDATE topvisor_jobs SET max_cost=?, state='budget_blocked', "
                    "state_reason='estimated_cost_exceeds_max_cost', updated_at_utc=? WHERE id=?",
                    (ceiling_text, now, job_id),
                )
                self._db.execute(
                    "UPDATE run_states SET outcome='incomplete', pause_reason='budget_blocked', "
                    "resumability='requires_operator_decision', updated_at_utc=? WHERE run_id=?",
                    (now, job["run_id"]),
                )
            raise ValueError("estimated Topvisor cost exceeds max_cost")
        with self._db:
            self._db.execute(
                "UPDATE topvisor_jobs SET max_cost=?, state='intent_recorded', "
                "state_reason=NULL, updated_at_utc=? WHERE id=?",
                (ceiling_text, now, job_id),
            )
            self._db.execute(
                "UPDATE run_states SET outcome='incomplete', pause_reason=NULL, "
                "resumability='resumable_automatically', updated_at_utc=? WHERE run_id=?",
                (now, job["run_id"]),
            )
        return self.topvisor_job(job_id)

    def record_topvisor_submit_result(
        self,
        job_id: str,
        *,
        remote_task_id: int,
        artifact_id: str,
        submitted_at_utc: str | None = None,
        expires_at_utc: str | None = None,
    ) -> dict[str, object]:
        """Persist remote task ID and 24-hour expiration window after paid submit."""
        job = self.topvisor_job(job_id)
        if job["state"] not in {"intent_recorded", "ambiguous_submit"}:
            raise ValueError(f"cannot record submit result in state {job['state']}")
        if isinstance(remote_task_id, bool) or not isinstance(remote_task_id, int) or remote_task_id <= 0:
            raise ValueError("remote_task_id must be a positive integer")
        artifact = self._verified_job_artifact(str(job["run_id"]), artifact_id)
        submitted_at = _utc_timestamp(
            "submitted_at_utc",
            submitted_at_utc or str(artifact["received_at_utc"]),
        )
        if expires_at_utc is not None:
            expires_at = _utc_timestamp("expires_at_utc", expires_at_utc)
        else:
            expires_at = (datetime.fromisoformat(submitted_at) + timedelta(hours=24)).isoformat()
        if datetime.fromisoformat(expires_at) <= datetime.fromisoformat(submitted_at):
            raise ValueError("expires_at_utc must be after submitted_at_utc")
        now = _now()
        with self._db:
            self._db.execute(
                "UPDATE topvisor_jobs SET state='submitted', state_reason=NULL, "
                "remote_task_id=?, submit_artifact_id=?, submitted_at_utc=?, "
                "expires_at_utc=?, updated_at_utc=? WHERE id=?",
                (remote_task_id, artifact_id, submitted_at, expires_at, now, job_id),
            )
            self._db.execute(
                "UPDATE run_states SET outcome='incomplete', pause_reason=NULL, "
                "resumability='resumable_automatically', updated_at_utc=? WHERE run_id=?",
                (now, job["run_id"]),
            )
        return self.topvisor_job(job_id)

    def record_topvisor_submit_ambiguous(
        self,
        job_id: str,
        *,
        reason: str = "submit_transport_interrupted",
    ) -> dict[str, object]:
        """Block duplicate paid submission when dispatch succeeded or failed ambiguously."""
        job = self.topvisor_job(job_id)
        if job["state"] != "intent_recorded":
            raise ValueError(f"cannot mark ambiguous submit in state {job['state']}")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("ambiguous submit reason must be nonempty text")
        now = _now()
        with self._db:
            self._db.execute(
                "UPDATE topvisor_jobs SET state='ambiguous_submit', state_reason=?, "
                "updated_at_utc=? WHERE id=?",
                (reason.strip(), now, job_id),
            )
            self._db.execute(
                "UPDATE run_states SET outcome='incomplete', "
                "pause_reason='unresolved_ambiguous_side_effect', "
                "resumability='requires_operator_decision', updated_at_utc=? WHERE run_id=?",
                (now, job["run_id"]),
            )
        return self.topvisor_job(job_id)

    def reopen_ambiguous_topvisor_job(
        self,
        job_id: str,
        *,
        accept_ambiguous_cost_risk: bool = False,
        allow_duplicate_cost_risk: bool = False,
    ) -> dict[str, object]:
        """Allow operator-authorized retry only when duplicate-billing risk is explicitly accepted."""
        job = self.topvisor_job(job_id)
        if job["state"] not in {"intent_recorded", "ambiguous_submit"}:
            raise ValueError("only an ambiguous_submit or intent_recorded job can be reopened")
        if not (accept_ambiguous_cost_risk or allow_duplicate_cost_risk):
            raise ValueError("ambiguous Topvisor submit requires explicit duplicate-cost risk acceptance")
        now = _now()
        with self._db:
            self._db.execute(
                "UPDATE topvisor_jobs SET state='estimated', "
                "state_reason='reopened_after_ambiguous_submit', updated_at_utc=? WHERE id=?",
                (now, job_id),
            )
            self._db.execute(
                "UPDATE run_states SET outcome='incomplete', pause_reason=NULL, "
                "resumability='resumable_automatically', updated_at_utc=? WHERE run_id=?",
                (now, job["run_id"]),
            )
        return self.topvisor_job(job_id)

    def record_topvisor_task_status(
        self,
        job_id: str,
        *,
        task_status: str | None,
        artifact_id: str,
        remote_task_id: int | None = None,
        expires_at_utc: str | None = None,
        checked_at_utc: str | None = None,
    ) -> dict[str, object]:
        """Update remote task status, reconcile ambiguous submit, or mark 24-hour expiration."""
        job = self.topvisor_job(job_id)
        if job["state"] not in {"intent_recorded", "ambiguous_submit", "submitted", "ongoing"}:
            raise ValueError(f"cannot record task status in state {job['state']}")
        if task_status not in {None, "ongoing", "completed"}:
            raise ValueError("task_status must be 'ongoing', 'completed', or None")
        artifact = self._verified_job_artifact(str(job["run_id"]), artifact_id)
        checked_at = _utc_timestamp(
            "checked_at_utc",
            checked_at_utc or str(artifact["received_at_utc"]),
        )
        resolved_task_id = job["remote_task_id"]
        if remote_task_id is not None:
            if isinstance(remote_task_id, bool) or not isinstance(remote_task_id, int) or remote_task_id <= 0:
                raise ValueError("remote_task_id must be a positive integer")
            if resolved_task_id is not None and resolved_task_id != remote_task_id:
                raise ValueError("remote_task_id does not match saved job task ID")
            resolved_task_id = remote_task_id

        submitted_at = (
            str(job["submitted_at_utc"])
            if job["submitted_at_utc"] is not None
            else checked_at
        )
        if expires_at_utc is not None:
            expires_at = _utc_timestamp("expires_at_utc", expires_at_utc)
        elif job["expires_at_utc"] is not None:
            expires_at = str(job["expires_at_utc"])
        elif resolved_task_id is not None:
            expires_at = (datetime.fromisoformat(submitted_at) + timedelta(hours=24)).isoformat()
        else:
            expires_at = None

        now = _now()
        if task_status in {"ongoing", "completed"}:
            if resolved_task_id is None:
                raise ValueError("remote_task_id is required when task_status is present")
            with self._db:
                self._db.execute(
                    "UPDATE topvisor_jobs SET state='ongoing', state_reason=NULL, "
                    "remote_task_id=?, submitted_at_utc=?, expires_at_utc=?, "
                    "last_task_artifact_id=?, remote_task_status=?, updated_at_utc=? WHERE id=?",
                    (
                        resolved_task_id, submitted_at, expires_at,
                        artifact_id, task_status, now, job_id,
                    ),
                )
                self._db.execute(
                    "UPDATE run_states SET outcome='incomplete', pause_reason=NULL, "
                    "resumability='resumable_automatically', updated_at_utc=? WHERE run_id=?",
                    (now, job["run_id"]),
                )
            return self.topvisor_job(job_id)

        if expires_at is not None and datetime.fromisoformat(checked_at) >= datetime.fromisoformat(expires_at):
            with self._db:
                self._db.execute(
                    "UPDATE topvisor_jobs SET state='expired_24h', "
                    "state_reason='topvisor_task_expired_before_fetch', "
                    "last_task_artifact_id=?, updated_at_utc=? WHERE id=?",
                    (artifact_id, now, job_id),
                )
                self._db.execute(
                    "UPDATE run_states SET outcome='incomplete', "
                    "pause_reason='topvisor_task_expired_24h', "
                    "resumability='requires_operator_decision', updated_at_utc=? WHERE run_id=?",
                    (now, job["run_id"]),
                )
            return self.topvisor_job(job_id)

        if job["state"] == "intent_recorded":
            with self._db:
                self._db.execute(
                    "UPDATE topvisor_jobs SET state='ambiguous_submit', "
                    "state_reason='interrupted_submit_not_found_in_tasks', "
                    "last_task_artifact_id=?, updated_at_utc=? WHERE id=?",
                    (artifact_id, now, job_id),
                )
                self._db.execute(
                    "UPDATE run_states SET outcome='incomplete', "
                    "pause_reason='unresolved_ambiguous_side_effect', "
                    "resumability='requires_operator_decision', updated_at_utc=? WHERE run_id=?",
                    (now, job["run_id"]),
                )
            return self.topvisor_job(job_id)

        with self._db:
            self._db.execute(
                "UPDATE topvisor_jobs SET last_task_artifact_id=?, updated_at_utc=? WHERE id=?",
                (artifact_id, now, job_id),
            )
        return self.topvisor_job(job_id)

    def record_topvisor_result_page(
        self,
        job_id: str,
        *,
        qualifier: object,
        page_offset: int,
        page_limit: int,
        artifact_id: str,
        parser: Callable[[bytes, SemanticRequest], ParseResult],
        parser_version: str,
    ) -> dict[str, object]:
        """Parse and record one Topvisor keywords page into durable observations and measurements."""
        job = self.topvisor_job(job_id)
        if job["state"] not in {"submitted", "ongoing", "completed"}:
            raise ValueError(f"cannot record result page in state {job['state']}")
        if job["remote_task_id"] is None:
            raise ValueError("remote_task_id is required before recording results")
        qual = _qualifier_descriptor(qualifier)
        if qual not in job["qualifiers"]:
            raise ValueError("qualifier does not belong to this Topvisor job")
        if isinstance(page_offset, bool) or not isinstance(page_offset, int) or page_offset < 0:
            raise ValueError("page_offset must be a nonnegative integer")
        if isinstance(page_limit, bool) or not isinstance(page_limit, int) or page_limit <= 0:
            raise ValueError("page_limit must be a positive integer")
        self._verified_job_artifact(str(job["run_id"]), artifact_id)

        allowed_canonical = {int(item["canonical_id"]) for item in job["phrases"]}
        expected_context = {
            "source": "topvisor",
            "job_id": job_id,
            "remote_task_id": int(job["remote_task_id"]),
            "snapshot_id": str(job["snapshot_id"]),
            "region_key": qual["region_key"],
            "searcher_key": qual["searcher_key"],
            "frequency_type": qual["type"],
        }
        now = _now()
        with self._db:
            batch_id = self.parse_artifact(
                artifact_id,
                parser,
                parser_version=parser_version,
                _within_transaction=True,
            )
            obs_rows = self._db.execute(
                "SELECT id, canonical_id FROM observations WHERE batch_id=? ORDER BY id",
                (batch_id,),
            ).fetchall()
            for obs in obs_rows:
                if int(obs["canonical_id"]) not in allowed_canonical:
                    raise ParserFailure("Topvisor result phrase does not belong to job phrase set")
            obs_ids = {int(obs["id"]) for obs in obs_rows}
            for measurement in self.measurements(batch_id):
                if measurement["kind"] != "topvisor_volume":
                    raise ParserFailure("Topvisor measurement kind must be 'topvisor_volume'")
                if measurement["observation_id"] is None or int(measurement["observation_id"]) not in obs_ids:
                    raise ParserFailure("Topvisor measurement must reference a parsed observation")
                context = strict_json_object(str(measurement["context_json"]))
                for key, expected_value in expected_context.items():
                    if context.get(key) != expected_value:
                        raise ParserFailure(f"Topvisor measurement context mismatch on {key}")
            existing = self._db.execute(
                "SELECT artifact_id, batch_id, page_limit, row_count FROM topvisor_result_pages "
                "WHERE job_id=? AND region_key=? AND searcher_key=? AND frequency_type=? AND page_offset=?",
                (job_id, qual["region_key"], qual["searcher_key"], qual["type"], page_offset),
            ).fetchone()
            if existing is not None:
                if (existing["artifact_id"] != artifact_id
                        or existing["batch_id"] != batch_id
                        or existing["page_limit"] != page_limit):
                    raise ValueError("result page already recorded with different artifact or limit")
            else:
                self._db.execute(
                    "INSERT INTO topvisor_result_pages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        job_id, qual["region_key"], qual["searcher_key"], qual["type"],
                        page_offset, page_limit, artifact_id, batch_id, len(obs_rows), now,
                    ),
                )
            if job["state"] == "submitted":
                self._db.execute(
                    "UPDATE topvisor_jobs SET state='ongoing', updated_at_utc=? WHERE id=?",
                    (now, job_id),
                )
            else:
                self._db.execute(
                    "UPDATE topvisor_jobs SET updated_at_utc=? WHERE id=?",
                    (now, job_id),
                )
        return self.topvisor_job(job_id)

    def complete_topvisor_job(self, job_id: str) -> dict[str, object]:
        """Mark a Topvisor job completed once all qualifiers have verified local result pages."""
        job = self.topvisor_job(job_id)
        if job["state"] == "completed":
            return job
        if job["state"] not in {"submitted", "ongoing"}:
            raise ValueError(f"cannot complete Topvisor job in state {job['state']}")
        covered = {
            (int(page["region_key"]), int(page["searcher_key"]), int(page["frequency_type"]))
            for page in job["pages"]
        }
        required = {
            (int(qual["region_key"]), int(qual["searcher_key"]), int(qual["type"]))
            for qual in job["qualifiers"]
        }
        if covered != required:
            raise ValueError("cannot complete Topvisor job before all qualifiers have result pages")
        for page in job["pages"]:
            self._verified_job_artifact(str(job["run_id"]), str(page["artifact_id"]))
        now = _now()
        with self._db:
            self._db.execute(
                "UPDATE topvisor_jobs SET state='completed', state_reason=NULL, "
                "remote_task_status='completed', completed_at_utc=?, updated_at_utc=? WHERE id=?",
                (now, now, job_id),
            )
            self._db.execute(
                "UPDATE run_states SET outcome='success', semantic_stop='topvisor_completed', "
                "pause_reason=NULL, resumability='no_pending_work', updated_at_utc=? WHERE run_id=?",
                (now, job["run_id"]),
            )
        return self.topvisor_job(job_id)

    def topvisor_measurements_for_snapshot(self, snapshot_id: str) -> list[dict[str, object]]:
        """Read verified Topvisor measurements for a snapshot without mutating the snapshot."""
        self._verified_snapshot_phrases(snapshot_id)
        rows = self._db.execute(
            "SELECT j.id AS job_id, j.remote_task_id, j.snapshot_id, "
            "o.id AS observation_id, o.canonical_id, c.normalized_text AS normalized_phrase, "
            "o.raw_phrase AS observed_phrase, m.id AS measurement_id, m.kind, m.value, m.unit, "
            "m.context_json, b.id AS batch_id, b.parser_version, b.normalization_version, "
            "a.id AS raw_artifact_id, a.sha256 AS raw_sha256, a.received_at_utc "
            "FROM topvisor_jobs j "
            "JOIN topvisor_result_pages p ON p.job_id=j.id "
            "JOIN parse_batches b ON b.id=p.batch_id "
            "JOIN raw_artifacts a ON a.id=b.artifact_id "
            "JOIN observations o ON o.batch_id=b.id "
            "JOIN canonical_phrases c ON c.id=o.canonical_id "
            "JOIN measurements m ON m.batch_id=b.id AND m.observation_id=o.id "
            "WHERE j.snapshot_id=? AND m.kind='topvisor_volume' "
            "ORDER BY c.normalized_text, p.region_key, p.searcher_key, p.frequency_type, j.created_at_utc, m.id",
            (snapshot_id,),
        ).fetchall()
        results: list[dict[str, object]] = []
        checked_artifacts: set[str] = set()
        for row in rows:
            artifact_id = str(row["raw_artifact_id"])
            if artifact_id not in checked_artifacts:
                self.read_raw(artifact_id)
                checked_artifacts.add(artifact_id)
            context = strict_json_object(str(row["context_json"]))
            results.append({
                "measurement_id": row["measurement_id"],
                "job_id": row["job_id"],
                "remote_task_id": row["remote_task_id"],
                "snapshot_id": row["snapshot_id"],
                "canonical_id": row["canonical_id"],
                "normalized_phrase": row["normalized_phrase"],
                "observed_phrase": row["observed_phrase"],
                "region_key": context["region_key"],
                "searcher_key": context["searcher_key"],
                "frequency_type": context["frequency_type"],
                "kind": row["kind"],
                "value": row["value"],
                "unit": row["unit"],
                "context": context,
                "observation_id": row["observation_id"],
                "batch_id": row["batch_id"],
                "parser_version": row["parser_version"],
                "normalization_version": row["normalization_version"],
                "raw_artifact_id": artifact_id,
                "raw_sha256": row["raw_sha256"],
                "received_at_utc": row["received_at_utc"],
            })
        return results
