"""Read exact immutable snapshots and export reusable data without credentials."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Mapping

from .storage import ArtifactIntegrityError
from .compare import _collection_plan_matches_snapshot


class SnapshotStore:
    """Read existing evidence without taking ownership or migrating its schema."""

    def __init__(self, directory: Path | str):
        self.directory = Path(directory).resolve()
        database = self.directory / "state.sqlite3"
        if not database.is_file():
            raise FileNotFoundError(database)
        self.raw_directory = self.directory / "raw"
        self._db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
        self._db.row_factory = sqlite3.Row

    def __enter__(self) -> "SnapshotStore":
        return self

    def __exit__(self, *_: object) -> None:
        self._db.close()

    def artifact_metadata(self, artifact_id: str) -> dict[str, object]:
        row = self._db.execute(
            "SELECT request_fingerprint,sha256,byte_count,relative_path "
            "FROM raw_artifacts WHERE id=?", (artifact_id,),
        ).fetchone()
        if row is None:
            raise ArtifactIntegrityError("snapshot references missing raw artifact")
        return dict(row)

    def read_raw(self, artifact_id: str) -> bytes:
        row = self.artifact_metadata(artifact_id)
        path = (self.raw_directory / row["relative_path"]).resolve()
        if not path.is_relative_to(self.raw_directory.resolve()):
            raise ArtifactIntegrityError("artifact path escaped raw directory")
        try:
            body = path.read_bytes()
        except FileNotFoundError as error:
            raise ArtifactIntegrityError("raw artifact is missing") from error
        if len(body) != row["byte_count"] or _digest_bytes(body) != row["sha256"]:
            raise ArtifactIntegrityError("raw artifact digest mismatch")
        return body


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _has_topvisor_schema(db: sqlite3.Connection) -> bool:
    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name IN ('topvisor_jobs', 'topvisor_job_phrases', 'topvisor_result_pages')",
    ).fetchall()
    return len(rows) == 3


def read_topvisor_job(store: SnapshotStore, job_id: str) -> dict[str, object]:
    """Verify and read a Topvisor job and its raw artifacts in read-only mode."""
    db = store._db
    if not _has_topvisor_schema(db):
        raise KeyError(job_id)
    row = db.execute(
        "SELECT * FROM topvisor_jobs WHERE id=?", (job_id,),
    ).fetchone()
    if row is None:
        raise KeyError(job_id)
    keywords_json = row["keywords_json"]
    qualifiers_json = row["qualifiers_json"]
    if (_digest(keywords_json) != row["keywords_sha256"]
            or _digest(qualifiers_json) != row["qualifiers_sha256"]):
        raise ArtifactIntegrityError("Topvisor job payload digest mismatch")
    keywords = json.loads(keywords_json)
    qualifiers = json.loads(qualifiers_json)
    phrase_rows = db.execute(
        "SELECT p.position, p.keyword, p.canonical_id, c.normalized_text AS normalized_phrase "
        "FROM topvisor_job_phrases p JOIN canonical_phrases c ON c.id=p.canonical_id "
        "WHERE p.job_id=? ORDER BY p.position",
        (job_id,),
    ).fetchall()
    if [item["keyword"] for item in phrase_rows] != keywords:
        raise ArtifactIntegrityError("Topvisor job phrase table does not match keywords digest")
    pages = [dict(item) for item in db.execute(
        "SELECT region_key, searcher_key, frequency_type, page_offset, page_limit, "
        "artifact_id, batch_id, row_count, recorded_at_utc "
        "FROM topvisor_result_pages WHERE job_id=? "
        "ORDER BY region_key, searcher_key, frequency_type, page_offset",
        (job_id,),
    ).fetchall()]
    checked_artifacts: set[str] = set()
    for artifact_id in (
        row["estimate_artifact_id"],
        row["submit_artifact_id"],
        row["last_task_artifact_id"],
        *(page["artifact_id"] for page in pages),
    ):
        if artifact_id is not None and str(artifact_id) not in checked_artifacts:
            store.read_raw(str(artifact_id))
            checked_artifacts.add(str(artifact_id))
    run_state_row = db.execute(
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


def read_topvisor_snapshot_evidence(
    store: SnapshotStore, snapshot_id: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Read verified Topvisor jobs and keyword outcomes (including 0 vs unknown) for a snapshot."""
    db = store._db
    if not _has_topvisor_schema(db):
        return [], []
    job_ids = [
        str(row["id"])
        for row in db.execute(
            "SELECT id FROM topvisor_jobs WHERE snapshot_id=? ORDER BY created_at_utc, id",
            (snapshot_id,),
        ).fetchall()
    ]
    jobs = [read_topvisor_job(store, job_id) for job_id in job_ids]
    if not jobs:
        return [], []
    rows = db.execute(
        "SELECT j.id AS job_id, j.remote_task_id, j.snapshot_id, "
        "p.region_key, p.searcher_key, p.frequency_type, p.page_offset, "
        "o.id AS observation_id, o.canonical_id, c.normalized_text AS normalized_phrase, "
        "o.raw_phrase AS observed_phrase, o.rank, "
        "m.id AS measurement_id, m.kind, m.value, m.unit, m.context_json, "
        "b.id AS batch_id, b.parser_version, b.normalization_version, "
        "a.id AS raw_artifact_id, a.sha256 AS raw_sha256, a.received_at_utc "
        "FROM topvisor_jobs j "
        "JOIN topvisor_result_pages p ON p.job_id=j.id "
        "JOIN parse_batches b ON b.id=p.batch_id "
        "JOIN raw_artifacts a ON a.id=b.artifact_id "
        "JOIN observations o ON o.batch_id=b.id "
        "JOIN canonical_phrases c ON c.id=o.canonical_id "
        "LEFT JOIN measurements m ON m.batch_id=b.id AND m.observation_id=o.id "
        "AND m.kind='topvisor_volume' "
        "WHERE j.snapshot_id=? "
        "ORDER BY c.normalized_text, p.region_key, p.searcher_key, p.frequency_type, "
        "j.created_at_utc, o.id",
        (snapshot_id,),
    ).fetchall()
    records: list[dict[str, object]] = []
    checked_artifacts: set[str] = set()
    for row in rows:
        artifact_id = str(row["raw_artifact_id"])
        if artifact_id not in checked_artifacts:
            store.read_raw(artifact_id)
            checked_artifacts.add(artifact_id)
        has_value = row["value"] is not None
        records.append({
            "job_id": row["job_id"],
            "remote_task_id": row["remote_task_id"],
            "snapshot_id": row["snapshot_id"],
            "canonical_id": row["canonical_id"],
            "normalized_phrase": row["normalized_phrase"],
            "observed_phrase": row["observed_phrase"],
            "rank": row["rank"],
            "region_key": row["region_key"],
            "searcher_key": row["searcher_key"],
            "frequency_type": row["frequency_type"],
            "status": "measured" if has_value else "unknown",
            "kind": row["kind"] if has_value else None,
            "value": row["value"] if has_value else None,
            "unit": row["unit"] if has_value else None,
            "context": json.loads(row["context_json"]) if row["context_json"] is not None else None,
            "observation_id": row["observation_id"],
            "measurement_id": row["measurement_id"],
            "batch_id": row["batch_id"],
            "parser_version": row["parser_version"],
            "normalization_version": row["normalization_version"],
            "raw_artifact_id": artifact_id,
            "raw_sha256": row["raw_sha256"],
            "received_at_utc": row["received_at_utc"],
        })
    return jobs, records


def _attach_topvisor_to_phrases(
    phrases: list[dict[str, object]], records: list[dict[str, object]],
) -> None:
    by_canonical: dict[int, list[dict[str, object]]] = {}
    for item in records:
        by_canonical.setdefault(int(item["canonical_id"]), []).append(item)
    for phrase in phrases:
        existing = list(phrase.get("topvisor_measurements", []))
        existing.extend(by_canonical.get(int(phrase["canonical_id"]), []))
        phrase["topvisor_measurements"] = existing


def read_snapshot(store: SnapshotStore, snapshot_id: str) -> dict[str, object]:
    """Verify saved snapshot and raw references without any provider adapter."""
    db = store._db
    row = db.execute(
        "SELECT run_id,payload_json,sha256 FROM collection_snapshots WHERE id=?",
        (snapshot_id,),
    ).fetchone()
    if row is not None:
        if _digest(row["payload_json"]) != row["sha256"] or row["sha256"] != snapshot_id:
            raise ArtifactIntegrityError("collection snapshot digest mismatch")
        payload = json.loads(row["payload_json"])
        if payload["run_id"] != row["run_id"]:
            raise ArtifactIntegrityError("collection snapshot run mismatch")
        for request in payload["requests"]:
            metadata = store.artifact_metadata(request["raw_artifact_id"])
            if (metadata["sha256"] != request["raw_sha256"]
                    or metadata["request_fingerprint"] != request["fingerprint"]):
                raise ArtifactIntegrityError("collection raw reference mismatch")
            store.read_raw(request["raw_artifact_id"])
        jobs, tv_records = read_topvisor_snapshot_evidence(store, snapshot_id)
        _attach_topvisor_to_phrases(payload["phrases"], tv_records)
        return {
            "snapshot_id": snapshot_id,
            **payload,
            "topvisor_jobs": jobs,
            "topvisor_measurements": tv_records,
        }
    row = db.execute(
        "SELECT comparison_id,payload_json,sha256 FROM comparison_snapshots WHERE id=?",
        (snapshot_id,),
    ).fetchone()
    if row is None:
        raise KeyError(snapshot_id)
    if _digest(row["payload_json"]) != row["sha256"] or row["sha256"] != snapshot_id:
        raise ArtifactIntegrityError("comparison snapshot digest mismatch")
    payload = json.loads(row["payload_json"])
    members = db.execute(
        "SELECT position,topic,run_id,plan_sha256 FROM comparison_topics "
        "WHERE comparison_id=? ORDER BY position", (row["comparison_id"],),
    ).fetchall()
    if (payload["comparison_id"] != row["comparison_id"]
            or len(members) != len(payload["topics"])):
        raise ArtifactIntegrityError("comparison membership mismatch")
    comp_jobs, comp_records = read_topvisor_snapshot_evidence(store, snapshot_id)
    datasets = []
    for index, (topic, member) in enumerate(zip(payload["topics"], members)):
        if (topic["position"] != index or topic["topic"] != member["topic"]
                or topic["run_id"] != member["run_id"]
                or not _collection_plan_matches_snapshot(
                    db, str(member["run_id"]), str(member["plan_sha256"]),
                    str(topic["plan_sha256"]),
                )):
            raise ArtifactIntegrityError("comparison topic mapping mismatch")
        dataset = read_snapshot(store, topic["collection_snapshot_id"])
        if (dataset["run_id"] != member["run_id"] or dataset["topic"] != topic["topic"]
                or dataset["plan_sha256"] != topic["plan_sha256"]):
            raise ArtifactIntegrityError("comparison points to another run")
        if comp_records:
            _attach_topvisor_to_phrases(dataset["phrases"], comp_records)
        datasets.append(dataset)
    return {
        "snapshot_id": snapshot_id,
        **payload,
        "datasets": datasets,
        "topvisor_jobs": comp_jobs,
        "topvisor_measurements": comp_records,
    }


def read_report_context(store: SnapshotStore, snapshot: Mapping[str, object]) -> dict[str, object]:
    """Read current branch metadata separately from immutable dataset evidence."""
    db = store._db
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    result = {}
    for dataset in snapshot.get("datasets", (snapshot,)):
        run_id = dataset["run_id"]
        context: dict[str, object] = {"branches": [], "parents": [], "reviews": []}
        if "collection_runs" in tables:
            row = db.execute("SELECT plan_json,plan_sha256 FROM collection_runs WHERE run_id=?",
                             (run_id,)).fetchone()
            if row is not None:
                if _digest(row["plan_json"]) != row["plan_sha256"]:
                    raise ArtifactIntegrityError("current collection plan digest mismatch")
                context["plan"] = json.loads(row["plan_json"])
                context["plan_matches_snapshot"] = row["plan_sha256"] == dataset.get("plan_sha256")
        if "semantic_branches" in tables:
            context["branches"] = [dict(row) for row in db.execute(
                "SELECT id,label,family,transition_kind,state,state_reason,creation_reason "
                "FROM semantic_branches WHERE run_id=? ORDER BY created_at_utc,id", (run_id,),
            )]
        if "semantic_branch_parents" in tables:
            context["parents"] = [dict(row) for row in db.execute(
                "SELECT p.branch_id,p.parent_id FROM semantic_branch_parents p "
                "JOIN semantic_branches b ON b.id=p.branch_id WHERE b.run_id=? "
                "ORDER BY p.branch_id,p.parent_id", (run_id,),
            )]
        if "collection_association_reviews" in tables:
            context["reviews"] = [dict(row) for row in db.execute(
                "SELECT branch_id,revision,decision,reason FROM collection_association_reviews "
                "WHERE run_id=? ORDER BY branch_id,revision", (run_id,),
            )]
        if "guided_branch_reviews" in tables:
            context["reviews"].extend(dict(row) for row in db.execute(
                "SELECT branch_id,decision,reason FROM guided_branch_reviews "
                "WHERE run_id=? ORDER BY branch_id", (run_id,),
            ))
        result[run_id] = context
    return result


def export_rows(snapshot: Mapping[str, object]) -> list[dict[str, object]]:
    """One CSV row per observation; measurements remain structured JSON in a cell."""
    datasets = snapshot.get("datasets", [snapshot])
    rows = []
    for dataset in datasets:
        for phrase in dataset["phrases"]:
            topvisor_json = json.dumps(
                phrase.get("topvisor_measurements", []), ensure_ascii=False, sort_keys=True,
            )
            for observation in phrase["observations"]:
                rows.append({
                    "snapshot_id": dataset["snapshot_id"], "run_id": dataset["run_id"],
                    "topic": dataset["topic"], "canonical_id": phrase["canonical_id"],
                    "normalized_phrase": phrase["normalized_phrase"],
                    "wordstat_frequency_status": phrase["wordstat_frequency"],
                    "observation_id": observation["observation_id"],
                    "original_phrase": observation["original_phrase"],
                    "channel": observation["channel"], "rank": observation["rank"],
                    "request_fingerprint": observation["request_fingerprint"],
                    "raw_artifact_id": observation["artifact_id"],
                    "parser_version": observation["parser_version"],
                    "normalization_version": observation["normalization_version"],
                    "request_json": json.dumps(observation["request"], ensure_ascii=False, sort_keys=True),
                    "discovery_edges_json": json.dumps(
                        observation["discovery_edges"], ensure_ascii=False, sort_keys=True,
                    ),
                    "measurements_json": json.dumps(
                        observation["measurements"], ensure_ascii=False, sort_keys=True,
                    ),
                    "topvisor_measurements_json": topvisor_json,
                })
    return rows


def _spreadsheet_safe(value: object) -> object:
    """Neutralize spreadsheet formulas in CSV; JSON remains the exact export."""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def export_snapshot(snapshot: Mapping[str, object], path: Path | str, *, format: str,
                    report_context: Mapping[str, object] | None = None) -> Path:
    """Atomic replacement of a user export; raw and immutable snapshots stay intact."""
    destination = Path(path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if format not in {"json", "csv", "html"}:
        raise ValueError("format must be json, csv or html")
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", delete=False,
        dir=destination.parent, prefix=destination.name + ".tmp-",
    )
    temporary = Path(handle.name)
    try:
        with handle:
            if format == "json":
                json.dump(snapshot, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            elif format == "html":
                from .report import build_report
                handle.write(build_report(snapshot, report_context=report_context))
            else:
                rows = export_rows(snapshot)
                fields = [
                    "snapshot_id", "run_id", "topic", "canonical_id", "normalized_phrase",
                    "wordstat_frequency_status", "observation_id", "original_phrase",
                    "channel", "rank", "request_fingerprint", "raw_artifact_id",
                    "parser_version", "normalization_version", "request_json",
                    "discovery_edges_json", "measurements_json", "topvisor_measurements_json",
                ]
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows({key: _spreadsheet_safe(value) for key, value in row.items()}
                                 for row in rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination
