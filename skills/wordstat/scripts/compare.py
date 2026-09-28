"""Compare independent collect runs under one bounded methodology.

The canonical datasets remain the exact one-topic collection snapshots. This
layer checks common allocations and records exposure gaps; it never interprets
which topic is commercially preferable or trims a longer collection.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Mapping

from .collect import PROVIDERS, CollectPlan, Collector
from .identity import NORMALIZATION_VERSION, normalize_phrase_v1
from .models import canonical_json
from .seed_probes import GRAMMAR_VERSION
from .storage import ArtifactIntegrityError, _now
from .wordstat_gettop import GetTopTariff


def _digest(encoded: str) -> str:
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _collection_plan_matches_snapshot(db, run_id: str, current_digest: str,
                                      snapshot_digest: str) -> bool:
    """Accept an older plan only through an intact extension chain for this run."""
    if current_digest == snapshot_digest:
        return True
    current = db.execute(
        "SELECT plan_json,plan_sha256 FROM collection_runs WHERE run_id=?", (run_id,),
    ).fetchone()
    if (current is None or current["plan_sha256"] != current_digest
            or _digest(current["plan_json"]) != current_digest):
        raise ArtifactIntegrityError("comparison current collection plan digest mismatch")
    if db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='collection_budget_extensions'",
    ).fetchone() is None:
        return False
    extensions = db.execute(
        "SELECT * FROM collection_budget_extensions WHERE run_id=? ORDER BY revision DESC", (run_id,),
    ).fetchall()
    expected = current_digest
    known = {current_digest}
    for revision, row in zip(range(len(extensions), 0, -1), extensions):
        if (row["revision"] != revision or row["new_plan_sha256"] != expected
                or _digest(row["new_plan_json"]) != row["new_plan_sha256"]
                or _digest(row["old_plan_json"]) != row["old_plan_sha256"]):
            raise ArtifactIntegrityError("collection budget extension digest chain mismatch")
        expected = row["old_plan_sha256"]
        known.add(expected)
    return snapshot_digest in known


def _common_method(plan: CollectPlan) -> dict[str, object]:
    """Exclude only topic-specific hypotheses and initial family assignment."""
    return {key: value for key, value in plan.descriptor().items()
            if key not in {"topic", "topic_family", "llm_proposal"}}


@dataclass(frozen=True)
class ComparePlan:
    """Same collection method and allocated maxima for two or more topics.

    LLM hypotheses are caller-provided. Their common upper bound is validated,
    but upstream model token use cannot be established by this collector.
    """

    collect_plans: tuple[CollectPlan, ...]
    max_llm_hypotheses: int
    max_llm_proposed_rules: int
    version: str = "compare-matched-allocation-v1"

    def __post_init__(self) -> None:
        plans = tuple(self.collect_plans)
        if len(plans) < 2 or not all(isinstance(item, CollectPlan) for item in plans):
            raise ValueError("compare needs at least two CollectPlan values")
        object.__setattr__(self, "collect_plans", plans)
        topics = [normalize_phrase_v1(item.topic) for item in plans]
        if len(set(topics)) != len(topics):
            raise ValueError("compare topics must be distinct after normalization")
        if (isinstance(self.max_llm_hypotheses, bool)
                or not isinstance(self.max_llm_hypotheses, int)
                or self.max_llm_hypotheses < 1):
            raise ValueError("max_llm_hypotheses must be a positive integer")
        if (isinstance(self.max_llm_proposed_rules, bool)
                or not isinstance(self.max_llm_proposed_rules, int)
                or self.max_llm_proposed_rules < 0):
            raise ValueError("max_llm_proposed_rules must be a nonnegative integer")
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("compare version is required")
        method = _common_method(plans[0])
        proposal = plans[0].llm_proposal
        common_input = json.loads(proposal.input_context_json)
        if common_input.get("topic") != plans[0].topic:
            raise ValueError("LLM input_context.topic must match its compare topic")
        common_input.pop("topic")
        for item in plans:
            if _common_method(item) != method:
                raise ValueError("compare requires the same grammar, policy and allocated budgets")
            candidate = item.llm_proposal
            if (candidate.model_id != proposal.model_id
                    or candidate.prompt_version != proposal.prompt_version
                    or candidate.stage != proposal.stage):
                raise ValueError("compare LLM proposal method differs")
            candidate_input = json.loads(candidate.input_context_json)
            if candidate_input.pop("topic", None) != item.topic or candidate_input != common_input:
                raise ValueError("compare LLM input contexts differ beyond the topic")
            if (len(candidate.hypotheses) > self.max_llm_hypotheses
                    or len(candidate.proposed_rules) > self.max_llm_proposed_rules):
                raise ValueError("compare LLM proposal exceeds shared allocated maximum")

    def descriptor(self) -> dict[str, object]:
        return {
            "version": self.version,
            "max_llm_hypotheses": self.max_llm_hypotheses,
            "max_llm_proposed_rules": self.max_llm_proposed_rules,
            "normalization_version": NORMALIZATION_VERSION,
            "probe_grammar_version": GRAMMAR_VERSION,
            "collection_plans": [item.descriptor() for item in self.collect_plans],
        }


class Comparer:
    """Durable, sequential orchestration of existing one-topic Collector runs."""

    def __init__(self, collector: Collector):
        if not isinstance(collector, Collector):
            raise TypeError("Collector is required")
        self.collector = collector
        self.db = collector.db

    def _runtime_context(self, plan: ComparePlan) -> dict[str, object]:
        contexts: list[dict[str, object]] = []
        for item in plan.collect_plans:
            self.collector._check_runtime(item)
            context = self.collector._adapter_context(item)
            for provider in PROVIDERS:
                # The phrase is the subject being compared, not a provider setting.
                context[provider] = {key: value for key, value in context[provider].items()
                                     if key != "phrase"}
            contexts.append(context)
        if any(item != contexts[0] for item in contexts[1:]):
            raise ValueError("compare provider contexts differ across topics")
        return contexts[0]

    def start(self, plan: ComparePlan) -> str:
        """Validate before any I/O, then bind independently resumable runs.

        An interruption during local setup may leave an unattached collect run;
        no provider request occurs until run() is called.
        """
        self._runtime_context(plan)
        runs = [self.collector.start(item) for item in plan.collect_plans]
        return self.attach_existing(plan, runs)

    def attach_existing(self, plan: ComparePlan, run_ids: list[str]) -> str:
        """Bind reviewed topic runs without issuing or repeating provider calls."""
        context = self._runtime_context(plan)
        if len(run_ids) != len(plan.collect_plans) or len(set(run_ids)) != len(run_ids):
            raise ValueError("compare needs one distinct saved run per topic")
        for run_id, item in zip(run_ids, plan.collect_plans):
            self.collector._collection(run_id, item)
        encoded = canonical_json(plan.descriptor())
        comparison_id = uuid.uuid4().hex
        with self.db:
            self.db.execute(
                "INSERT INTO comparison_runs VALUES (?,?,?,?,?)",
                (comparison_id, _now(), encoded, _digest(encoded), canonical_json(context)),
            )
            for position, (item, run_id) in enumerate(zip(plan.collect_plans, run_ids)):
                item_encoded = canonical_json(item.descriptor())
                self.db.execute(
                    "INSERT INTO comparison_topics VALUES (?,?,?,?,?)",
                    (comparison_id, position, item.topic, run_id, _digest(item_encoded)),
                )
        return comparison_id

    def _members(self, comparison_id: str, plan: ComparePlan) -> list[dict[str, object]]:
        context = self._runtime_context(plan)
        row = self.db.execute(
            "SELECT plan_json,plan_sha256,adapter_context_json FROM comparison_runs WHERE id=?",
            (comparison_id,),
        ).fetchone()
        if row is None:
            raise KeyError(comparison_id)
        encoded = canonical_json(plan.descriptor())
        if row["plan_json"] != encoded or row["plan_sha256"] != _digest(encoded):
            raise ValueError("comparison plan changed; resume needs the original plan")
        if row["adapter_context_json"] != canonical_json(context):
            raise ValueError("comparison provider context changed")
        members = [dict(item) for item in self.db.execute(
            "SELECT position,topic,run_id,plan_sha256 FROM comparison_topics "
            "WHERE comparison_id=? ORDER BY position", (comparison_id,),
        )]
        if len(members) != len(plan.collect_plans):
            raise ArtifactIntegrityError("comparison has an incomplete topic mapping")
        for position, (member, item) in enumerate(zip(members, plan.collect_plans)):
            item_encoded = canonical_json(item.descriptor())
            if (member["position"] != position or member["topic"] != item.topic
                    or member["plan_sha256"] != _digest(item_encoded)):
                raise ArtifactIntegrityError("comparison topic mapping differs from its plan")
        return members

    def run(self, comparison_id: str, plan: ComparePlan) -> dict[str, object]:
        """Resume each topic through Collector; one topic never consumes another's budget."""
        members = self._members(comparison_id, plan)
        if any(self.db.execute(
            "SELECT 1 FROM guided_collection_runs WHERE run_id=?", (member["run_id"],)
        ).fetchone() is not None for member in members):
            raise ValueError("guided compare topics must resume through their own checkpoints")
        collections = [
            self.collector.run(member["run_id"], item)
            for member, item in zip(members, plan.collect_plans)
        ]
        return self._freeze(comparison_id, plan, collections)

    def extend_budget(
        self, comparison_id: str, plan: ComparePlan, *, hard_max_requests: int | None = None,
        attempt_budgets: Mapping[str, int] | None = None,
        tariff: GetTopTariff | None = None,
        max_estimated_wordstat_cost: Decimal | None = None,
    ) -> ComparePlan:
        """Increase every topic's common allocation atomically, without acquisition.

        Run IDs, checkpoints and old snapshots remain intact. Natural semantic
        stops remain closed; only a stop caused by the allocated budget reopens.
        """
        members = self._members(comparison_id, plan)
        prepared = []
        for member, item in zip(members, plan.collect_plans):
            run_id = str(member["run_id"])
            prepared.append(self.collector._prepare_budget_extension(
                run_id, item, hard_max_requests=hard_max_requests,
                attempt_budgets=attempt_budgets, tariff=tariff,
                max_estimated_wordstat_cost=max_estimated_wordstat_cost,
                preserve_semantic_stop=True,
            ))
        updated = replace(plan, collect_plans=tuple(item[0] for item in prepared))
        self._runtime_context(updated)
        encoded = canonical_json(updated.descriptor())
        with self.db:
            for member, item, (new_item, previous, state) in zip(
                members, plan.collect_plans, prepared,
            ):
                run_id = str(member["run_id"])
                self.collector._apply_budget_extension(run_id, item, new_item, previous, state)
                self.db.execute(
                    "UPDATE comparison_topics SET plan_sha256=? WHERE comparison_id=? AND position=?",
                    (_digest(canonical_json(new_item.descriptor())), comparison_id, member["position"]),
                )
            self.db.execute(
                "UPDATE comparison_runs SET plan_json=?,plan_sha256=? WHERE id=?",
                (encoded, _digest(encoded), comparison_id),
            )
        return updated

    def snapshot(self, comparison_id: str, plan: ComparePlan) -> dict[str, object]:
        """Freeze current partial or complete topic datasets without new provider calls."""
        members = self._members(comparison_id, plan)
        collections = [
            self.collector.snapshot(member["run_id"], item)
            for member, item in zip(members, plan.collect_plans)
        ]
        return self._freeze(comparison_id, plan, collections)

    @staticmethod
    def _provider_diagnostics(collection: dict[str, object], plan: CollectPlan) -> list[dict[str, object]]:
        exposure = {item["provider"]: item for item in collection["provider_exposure"]}
        attempts = {item["provider"]: item for item in collection["provider_diagnostics"]}
        result = []
        for provider in PROVIDERS:
            shown = exposure.get(provider, {})
            used = attempts.get(provider, {})
            planned = int(shown.get("planned", 0))
            completed = int(shown.get("completed", 0))
            postponed = int(shown.get("missing", 0))
            remaining = int(shown.get("remaining", 0))
            unresolved_selected = int(shown.get("selected", 0))
            invalid = int(shown.get("invalid", 0))
            result.append({
                "provider": provider,
                "allocated_max_attempts": plan.attempt_budgets[provider],
                "planned_opportunities": planned,
                "attempted": int(used.get("attempted", 0)),
                "successful_attempts": int(used.get("success", 0)),
                "valid_empty_attempts": int(used.get("valid_empty", 0)),
                "failed_attempts": int(used.get("failed", 0)),
                "completed_requests": completed,
                "missing_exposure": postponed + unresolved_selected,
                "remaining_frontier": remaining,
                "unresolved_selected": unresolved_selected,
                "invalidated_opportunities": invalid,
            })
        return result

    def _freeze(self, comparison_id: str, plan: ComparePlan,
                collections: list[dict[str, object]]) -> dict[str, object]:
        if len(collections) != len(plan.collect_plans):
            raise ValueError("one exact collection snapshot per topic is required")
        topics = []
        for position, (item, collection) in enumerate(zip(plan.collect_plans, collections)):
            providers = self._provider_diagnostics(collection, item)
            topics.append({
                "position": position, "topic": item.topic,
                "topic_family": item.topic_family.value,
                "run_id": collection["run_id"],
                "collection_snapshot_id": collection["snapshot_id"],
                "plan_sha256": collection["plan_sha256"],
                "run_state": collection["run_state"],
                "provider_exposure": providers,
                "gaps": collection["gaps"],
                "phrase_count": len(collection["phrases"]),
                "observation_count": sum(len(phrase["observations"])
                                         for phrase in collection["phrases"]),
                "llm_hypotheses_used": len(item.llm_proposal.hypotheses),
                "llm_proposed_rules_used": len(item.llm_proposal.proposed_rules),
            })
        limited = any(
            topic["run_state"]["outcome"] != "success"
            or any(source["missing_exposure"] for source in topic["provider_exposure"])
            for topic in topics
        )
        encoded_plan = canonical_json(plan.descriptor())
        payload = {
            "comparison_id": comparison_id,
            "plan_sha256": _digest(encoded_plan),
            "methodology": _common_method(plan.collect_plans[0]),
            "provider_context": self._runtime_context(plan),
            "normalization_version": NORMALIZATION_VERSION,
            "probe_grammar_version": GRAMMAR_VERSION,
            "source_classes": list(PROVIDERS),
            "freshness_policy": "new_acquisition_per_topic_run",
            "max_llm_hypotheses": plan.max_llm_hypotheses,
            "max_llm_proposed_rules": plan.max_llm_proposed_rules,
            "llm_generation_exposure": "external_proposals; actual actions and tokens not measured",
            "comparability": "limited_by_missing_or_incomplete_exposure" if limited else "matched_method_and_allocation",
            "topics": topics,
        }
        encoded = canonical_json(payload)
        digest = _digest(encoded)
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO comparison_snapshots VALUES (?,?,?,?,?)",
                (digest, comparison_id, _now(), encoded, digest),
            )
        return self.read_snapshot(digest)

    def read_snapshot(self, snapshot_id: str) -> dict[str, object]:
        """Read the manifest and its exact, separately immutable topic datasets."""
        row = self.db.execute(
            "SELECT comparison_id,payload_json,sha256 FROM comparison_snapshots WHERE id=?",
            (snapshot_id,),
        ).fetchone()
        if row is None:
            raise KeyError(snapshot_id)
        if _digest(row["payload_json"]) != row["sha256"] or snapshot_id != row["sha256"]:
            raise ArtifactIntegrityError("comparison snapshot digest mismatch")
        payload = json.loads(row["payload_json"])
        members = [dict(item) for item in self.db.execute(
            "SELECT position,topic,run_id,plan_sha256 FROM comparison_topics "
            "WHERE comparison_id=? ORDER BY position", (row["comparison_id"],),
        )]
        if (payload["comparison_id"] != row["comparison_id"]
                or len(payload["topics"]) != len(members)):
            raise ArtifactIntegrityError("comparison snapshot membership mismatch")
        collections = []
        for position, (topic, member) in enumerate(zip(payload["topics"], members)):
            if (topic["position"] != position or topic["topic"] != member["topic"]
                    or topic["run_id"] != member["run_id"]
                    or not _collection_plan_matches_snapshot(
                        self.db, str(member["run_id"]), str(member["plan_sha256"]),
                        str(topic["plan_sha256"]),
                    )):
                raise ArtifactIntegrityError("comparison snapshot topic mapping mismatch")
            dataset = self.collector.read_snapshot(topic["collection_snapshot_id"])
            if (dataset["run_id"] != topic["run_id"]
                    or dataset["topic"] != topic["topic"]
                    or dataset["plan_sha256"] != topic["plan_sha256"]):
                raise ArtifactIntegrityError("comparison points to another collection dataset")
            collections.append(dataset)
        return {"snapshot_id": snapshot_id, **payload, "datasets": collections}
