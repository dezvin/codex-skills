"""One-topic, bounded collection over the existing durable frontier and adapters.

The caller supplies model hypotheses and the explicit resource policy. The
native CLI and bounded starter profile are separate modules.
"""

from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Mapping, Sequence

from .execution import (
    CapacityBucket, CapacityUnavailable, ExecutionCore, Executor, OutcomeKind,
    RetryPolicy, RunBudgetExhausted,
)
from .frontier import FrontierPolicy, SemanticFrontier
from .identity import fingerprint, normalize_phrase_v1
from .models import SemanticRequest, canonical_json
from .seed_probes import (
    LLMProposalBatch, ProbePlan, ProbeRule, ProbeSeed, ProposalStage, SeedFamily,
    generate_probes,
)
from .storage import ArtifactIntegrityError, DataStore, _now
from .suggest import (
    PARSER_VERSION as SUGGEST_PARSER_VERSION, SuggestAdapter, SuggestSource, parse_suggest,
)
from .wordstat_gettop import (
    PARSER_VERSION as GETTOP_PARSER_VERSION, GetTopAdapter, GetTopTariff, parse_gettop,
)


PROVIDERS = (
    "yandex_wordstat", "yandex_suggest", "google_suggest", "youtube_suggest",
)


@dataclass(frozen=True)
class CollectPlan:
    """Versioned collection inputs with explicit resource and monetary maxima."""

    topic: str
    topic_family: SeedFamily
    llm_proposal: LLMProposalBatch
    mask_rules: tuple[ProbeRule, ...]
    max_probe_candidates: int
    max_observed_branches: int
    frontier_policy: FrontierPolicy
    bucket_ids: Mapping[str, str]
    attempt_budgets: Mapping[str, int]
    retry_policy: RetryPolicy
    wordstat_num_phrases: int
    wordstat_regions: tuple[str, ...]
    wordstat_devices: tuple[str, ...]
    tariff: GetTopTariff
    max_estimated_wordstat_cost: Decimal
    version: str = "collect-one-topic-v1-provisional"
    association_review_required: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.association_review_required, bool):
            raise TypeError("association_review_required must be boolean")
        if not isinstance(self.topic, str) or not self.topic.strip():
            raise ValueError("topic is required")
        object.__setattr__(self, "topic_family", SeedFamily(self.topic_family))
        if (self.llm_proposal.topic != self.topic
                or self.llm_proposal.stage != ProposalStage.INITIALIZATION
                or not self.llm_proposal.hypotheses):
            raise ValueError("a nonempty initialization proposal for this topic is required")
        rules = tuple(self.mask_rules)
        if not all(isinstance(rule, ProbeRule) for rule in rules):
            raise TypeError("mask_rules must contain ProbeRule values")
        if len({rule.id for rule in rules}) != len(rules):
            raise ValueError("duplicate mask rule ID")
        proposed = {rule.id: rule for rule in self.llm_proposal.proposed_rules}
        if any(rule.origin == "llm_proposed" and proposed.get(rule.id) != rule for rule in rules):
            raise ValueError("model-proposed mask must belong to the saved proposal")
        object.__setattr__(self, "mask_rules", rules)
        if (isinstance(self.max_probe_candidates, bool) or not isinstance(self.max_probe_candidates, int)
                or self.max_probe_candidates < 1 or isinstance(self.max_observed_branches, bool)
                or not isinstance(self.max_observed_branches, int) or self.max_observed_branches < 0):
            raise ValueError("probe and branch limits must be explicit nonnegative integers")
        if not isinstance(self.frontier_policy, FrontierPolicy):
            raise TypeError("frontier_policy is required")
        if self.frontier_policy.hard_max_requests < len(PROVIDERS):
            raise ValueError("run maximum must allow a probe from each source")
        if set(self.bucket_ids) != set(PROVIDERS) or set(self.attempt_budgets) != set(PROVIDERS):
            raise ValueError("all four source budgets and capacity bucket IDs are required")
        if len(set(self.bucket_ids.values())) != len(PROVIDERS):
            raise ValueError("v1 requires a separate configured bucket for each source")
        if any(not isinstance(value, str) or not value.strip() for value in self.bucket_ids.values()):
            raise ValueError("capacity bucket IDs must be nonempty")
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 1
               for value in self.attempt_budgets.values()):
            raise ValueError("attempt budgets must be positive integers")
        if not isinstance(self.retry_policy, RetryPolicy):
            raise TypeError("retry_policy is required")
        if (isinstance(self.wordstat_num_phrases, bool) or not isinstance(self.wordstat_num_phrases, int)
                or not 1 <= self.wordstat_num_phrases <= 2000):
            raise ValueError("wordstat_num_phrases must be 1..2000")
        object.__setattr__(self, "wordstat_regions", tuple(self.wordstat_regions))
        object.__setattr__(self, "wordstat_devices", tuple(self.wordstat_devices))
        ceiling = Decimal(str(self.max_estimated_wordstat_cost))
        if not ceiling.is_finite() or ceiling < 0:
            raise ValueError("monetary ceiling must be nonnegative")
        if self.tariff.estimate(self.attempt_budgets["yandex_wordstat"]) > ceiling:
            raise ValueError("estimated Wordstat attempt budget exceeds monetary ceiling")
        object.__setattr__(self, "max_estimated_wordstat_cost", ceiling)
        # Reject an overgrown initial grammar before creating a run or issuing requests.
        seeds = (ProbeSeed(self.topic, self.topic_family, "topic", "topic:preflight"),
                 *self.llm_proposal.seeds("preflight"))
        generate_probes(ProbePlan(seeds, rules, self.max_probe_candidates))

    def descriptor(self) -> dict[str, object]:
        result = {
            "version": self.version, "topic": self.topic,
            "topic_family": self.topic_family.value,
            "llm_proposal": self.llm_proposal.descriptor(),
            "mask_rules": [rule.descriptor() for rule in self.mask_rules],
            "max_probe_candidates": self.max_probe_candidates,
            "max_observed_branches": self.max_observed_branches,
            "frontier_policy": self.frontier_policy.descriptor(),
            "bucket_ids": dict(self.bucket_ids),
            "attempt_budgets": dict(self.attempt_budgets),
            "retry_policy": {
                "max_attempts": self.retry_policy.max_attempts,
                "base_delay": str(self.retry_policy.base_delay),
                "max_delay": str(self.retry_policy.max_delay),
                "max_total_wait": str(self.retry_policy.max_total_wait),
                "retry_provider_5xx": self.retry_policy.retry_provider_5xx,
            },
            "wordstat_num_phrases": self.wordstat_num_phrases,
            "wordstat_regions": list(self.wordstat_regions),
            "wordstat_devices": list(self.wordstat_devices),
            "tariff": {
                "price_per_1000": str(self.tariff.price_per_1000),
                "currency": self.tariff.currency,
                "checked_on": self.tariff.checked_on.isoformat(),
                "source_url": self.tariff.source_url,
            },
            "max_estimated_wordstat_cost": str(self.max_estimated_wordstat_cost),
        }
        # Keep existing stage-7/9 run identities unchanged when the review gate
        # is disabled, so their saved plans remain resumable after migration.
        if self.association_review_required:
            result["association_review_required"] = True
        return result


class Collector:
    """Single-worker orchestration; adapters may use real or injected transports."""

    def __init__(self, store: DataStore, gettop: GetTopAdapter,
                 suggests: Mapping[str, SuggestAdapter],
                 capacity_buckets: Mapping[str, CapacityBucket]):
        if set(suggests) != set(PROVIDERS[1:]) or set(capacity_buckets) != set(PROVIDERS):
            raise ValueError("all four source adapters and capacity buckets are required")
        for name, adapter in suggests.items():
            if not isinstance(adapter, SuggestAdapter) or adapter.source.value != name:
                raise ValueError("Suggest adapter/source mismatch")
        if not isinstance(gettop, GetTopAdapter):
            raise TypeError("GetTopAdapter is required")
        self.store = store
        self.db = store._db
        self.gettop = gettop
        self.suggests = dict(suggests)
        self.buckets = dict(capacity_buckets)
        self.core = ExecutionCore(store)
        self.frontier = SemanticFrontier(store)
        for bucket in self.buckets.values():
            self.core.configure_bucket(bucket)

    def start(self, plan: CollectPlan) -> str:
        self._check_runtime(plan)
        run_id = self.store.create_run()
        self.attach_existing(run_id, plan)
        return run_id

    def attach_existing(self, run_id: str, plan: CollectPlan) -> None:
        """Attach an approved plan to a durable scout run without replaying its call."""
        self._check_runtime(plan)
        if self.db.execute("SELECT 1 FROM runs WHERE id=?", (run_id,)).fetchone() is None:
            raise KeyError(run_id)
        encoded = canonical_json(plan.descriptor())
        context = self._adapter_context(plan)
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO collection_runs(run_id,plan_json,plan_sha256,adapter_context_json) "
                "VALUES (?,?,?,?)",
                (run_id, encoded, hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
                 canonical_json(context)),
            )
        self._initialize(run_id, plan)

    def _check_runtime(self, plan: CollectPlan) -> None:
        for provider in PROVIDERS:
            if self.buckets[provider].id != plan.bucket_ids[provider]:
                raise ValueError(f"capacity bucket mismatch for {provider}")
        self.gettop.semantic_request(
            plan.topic, num_phrases=plan.wordstat_num_phrases,
            regions=plan.wordstat_regions, devices=plan.wordstat_devices,
        )

    def _adapter_context(self, plan: CollectPlan) -> dict[str, object]:
        return {
            "yandex_wordstat": self.gettop.semantic_request(
                plan.topic, num_phrases=plan.wordstat_num_phrases,
                regions=plan.wordstat_regions, devices=plan.wordstat_devices,
            ).descriptor(),
            **{source: self.suggests[source].semantic_request(plan.topic).descriptor()
               for source in PROVIDERS[1:]},
        }

    def _collection(self, run_id: str, plan: CollectPlan) -> dict[str, object]:
        self._check_runtime(plan)
        row = self.db.execute("SELECT * FROM collection_runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        encoded = canonical_json(plan.descriptor())
        if (row["plan_json"] != encoded or row["plan_sha256"] !=
                hashlib.sha256(encoded.encode("utf-8")).hexdigest()):
            raise ValueError("collection plan changed; resume needs the original plan")
        if row["adapter_context_json"] != canonical_json(self._adapter_context(plan)):
            raise ValueError("provider adapter context changed during this run")
        return dict(row)

    def extend_budget(
        self, run_id: str, plan: CollectPlan, *, hard_max_requests: int | None = None,
        attempt_budgets: Mapping[str, int] | None = None,
        tariff: GetTopTariff | None = None,
        max_estimated_wordstat_cost: Decimal | None = None,
    ) -> CollectPlan:
        """Increase one saved run's allocation without rewriting earlier snapshots.

        This changes only budget fields. Execution remains a separate, explicit resume.
        """
        if self.db.execute(
            "SELECT 1 FROM comparison_topics WHERE run_id=? LIMIT 1", (run_id,),
        ).fetchone():
            raise ValueError("comparison topic budgets must remain matched; individual extension is forbidden")
        updated, previous, state = self._prepare_budget_extension(
            run_id, plan, hard_max_requests=hard_max_requests,
            attempt_budgets=attempt_budgets, tariff=tariff,
            max_estimated_wordstat_cost=max_estimated_wordstat_cost,
        )
        with self.db:
            self._apply_budget_extension(run_id, plan, updated, previous, state)
        return updated

    def _prepare_budget_extension(
        self, run_id: str, plan: CollectPlan, *, hard_max_requests: int | None = None,
        attempt_budgets: Mapping[str, int] | None = None,
        tariff: GetTopTariff | None = None,
        max_estimated_wordstat_cost: Decimal | None = None,
        preserve_semantic_stop: bool = False,
    ) -> tuple[CollectPlan, dict[str, object], dict[str, object]]:
        """Validate one allocation without writing; compare prepares every member first."""
        previous = self._collection(run_id, plan)
        if self.db.execute(
            "SELECT 1 FROM semantic_tranches WHERE run_id=? AND state='active' LIMIT 1", (run_id,),
        ).fetchone():
            raise ValueError("finish or recover the active tranche before extending the budget")
        state = self.core.run_state(run_id)
        allowed_stops = {"continuation_possible", "hard_run_budget_exhausted"}
        if preserve_semantic_stop:
            allowed_stops.update({"frontier_exhausted_under_current_grammar", "marginal_return_exhausted"})
        if state["semantic_stop"] not in allowed_stops:
            raise ValueError("budget extension cannot reopen a semantic stop")
        maximum = plan.frontier_policy.hard_max_requests if hard_max_requests is None else hard_max_requests
        budgets = dict(plan.attempt_budgets)
        if attempt_budgets is not None:
            if not set(attempt_budgets).issubset(PROVIDERS):
                raise ValueError("unknown provider in attempt budgets")
            budgets.update(attempt_budgets)
        if (isinstance(maximum, bool) or not isinstance(maximum, int)
                or maximum < plan.frontier_policy.hard_max_requests):
            raise ValueError("run request maximum cannot decrease")
        if any(isinstance(value, bool) or not isinstance(value, int)
               or value < plan.attempt_budgets[provider] for provider, value in budgets.items()):
            raise ValueError("provider attempt budget cannot decrease")
        if (maximum == plan.frontier_policy.hard_max_requests
                and budgets == dict(plan.attempt_budgets)):
            raise ValueError("budget extension must increase at least one limit")
        if maximum > sum(budgets.values()):
            raise ValueError("request maximum exceeds the sum of provider attempt budgets")
        selected = self.db.execute(
            "SELECT COUNT(*) FROM semantic_tranche_requests WHERE run_id=?", (run_id,),
        ).fetchone()[0]
        if state["semantic_stop"] == "hard_run_budget_exhausted" and maximum <= selected:
            raise ValueError("request maximum must exceed selected work to reopen this run")
        wordstat_grows = budgets["yandex_wordstat"] > plan.attempt_budgets["yandex_wordstat"]
        if wordstat_grows and (tariff is None or max_estimated_wordstat_cost is None):
            raise ValueError("a current tariff and explicit monetary ceiling are required for more Wordstat calls")
        ceiling = (plan.max_estimated_wordstat_cost if max_estimated_wordstat_cost is None
                   else Decimal(str(max_estimated_wordstat_cost)))
        if not ceiling.is_finite() or ceiling < plan.max_estimated_wordstat_cost:
            raise ValueError("monetary ceiling cannot decrease")
        chosen_tariff = plan.tariff if tariff is None else tariff
        if wordstat_grows and chosen_tariff.checked_on < plan.tariff.checked_on:
            raise ValueError("new Wordstat tariff cannot predate the saved tariff")
        updated = replace(
            plan, frontier_policy=replace(plan.frontier_policy, hard_max_requests=maximum),
            attempt_budgets=budgets, tariff=chosen_tariff,
            max_estimated_wordstat_cost=ceiling,
        )
        policy = self.db.execute(
            "SELECT policy_json FROM semantic_frontier_policy WHERE run_id=?", (run_id,),
        ).fetchone()
        old_policy = canonical_json(plan.frontier_policy.descriptor())
        if policy is not None and policy[0] != old_policy:
            raise ValueError("saved frontier policy differs from the current plan")
        return updated, previous, state

    def _apply_budget_extension(
        self, run_id: str, plan: CollectPlan, updated: CollectPlan,
        previous: Mapping[str, object], state: Mapping[str, object],
    ) -> None:
        """Apply a prevalidated allocation inside the caller's transaction."""
        budgets = updated.attempt_budgets
        new_policy = canonical_json(updated.frontier_policy.descriptor())
        encoded = canonical_json(updated.descriptor())
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        self.db.execute(
            "UPDATE semantic_frontier_policy SET policy_json=? WHERE run_id=?",
            (new_policy, run_id),
        )
        revision = self.db.execute(
            "SELECT COALESCE(MAX(revision),0)+1 FROM collection_budget_extensions WHERE run_id=?",
            (run_id,),
        ).fetchone()[0]
        self.db.execute(
            "INSERT INTO collection_budget_extensions VALUES (?,?,?,?,?,?,?)",
            (run_id, revision, previous["plan_json"], previous["plan_sha256"],
             encoded, digest, _now()),
        )
        self.db.execute(
            "UPDATE collection_runs SET plan_json=?,plan_sha256=? WHERE run_id=?",
            (encoded, digest, run_id),
        )
        for provider in PROVIDERS:
            self.db.execute(
                "INSERT INTO run_budgets(run_id,bucket_id,max_attempts) VALUES (?,?,?) "
                "ON CONFLICT(run_id,bucket_id) DO UPDATE SET max_attempts=excluded.max_attempts",
                (run_id, plan.bucket_ids[provider], budgets[provider]),
            )
            if budgets[provider] > plan.attempt_budgets[provider]:
                # A budget rejection happens before dispatch. Only that
                # classified gap may be reopened without paid-call risk.
                self.db.execute(
                    "DELETE FROM collection_disabled_providers "
                    "WHERE run_id=? AND provider=? AND reason='budget_blocked'",
                    (run_id, provider),
                )
                selected_numbers = [row[0] for row in self.db.execute(
                    "SELECT DISTINCT tranche_number FROM semantic_opportunities "
                    "WHERE run_id=? AND provider=? AND state='postponed' "
                    "AND outcome='budget_blocked' AND tranche_number IS NOT NULL",
                    (run_id, provider),
                )]
                self.db.execute(
                    "UPDATE semantic_opportunities SET "
                    "state=CASE WHEN tranche_number IS NULL THEN 'eligible' ELSE 'selected' END,"
                    "state_reason=NULL,outcome=NULL "
                    "WHERE run_id=? AND provider=? AND state='postponed' "
                    "AND outcome='budget_blocked'",
                    (run_id, provider),
                )
                for number in selected_numbers:
                    self.db.execute(
                        "UPDATE semantic_tranches SET state='active',review_json=NULL,"
                        "reviewed_at_utc=NULL WHERE run_id=? AND number=?",
                        (run_id, number),
                    )
        if state["semantic_stop"] == "hard_run_budget_exhausted":
            guided = self.db.execute(
                "SELECT phase FROM guided_collection_runs WHERE run_id=?", (run_id,),
            ).fetchone()
            awaiting_review = guided is not None and guided[0] != "wave_ready"
            self.db.execute(
                "UPDATE run_states SET outcome='incomplete',"
                "semantic_stop='continuation_possible',pause_reason=?,"
                "resumability=?,updated_at_utc=? WHERE run_id=?",
                (state["pause_reason"] if awaiting_review else None,
                 state["resumability"] if awaiting_review else "resumable_automatically",
                 _now(), run_id),
            )
        elif state["pause_reason"] == "run_budget_exhausted":
            self.db.execute(
                "UPDATE run_states SET outcome='incomplete',pause_reason=NULL,"
                "resumability='resumable_automatically',updated_at_utc=? WHERE run_id=?",
                (_now(), run_id),
            )

    def _seed_batch(self, run_id: str, plan: CollectPlan, row: Mapping[str, object]) -> str:
        if row["proposal_batch_id"]:
            return str(row["proposal_batch_id"])
        descriptor = canonical_json(plan.llm_proposal.descriptor())
        digest = hashlib.sha256(descriptor.encode("utf-8")).hexdigest()
        found = self.db.execute(
            "SELECT id FROM semantic_seed_batches WHERE run_id=? AND kind='llm_proposal' "
            "AND sha256=? ORDER BY created_at_utc LIMIT 1", (run_id, digest),
        ).fetchone()
        batch_id = found[0] if found else self.store.save_llm_proposal(run_id, plan.llm_proposal)
        with self.db:
            self.db.execute("UPDATE collection_runs SET proposal_batch_id=? WHERE run_id=?",
                            (batch_id, run_id))
        return batch_id

    def _initialize(self, run_id: str, plan: CollectPlan) -> None:
        row = self._collection(run_id, plan)
        for provider in PROVIDERS:
            self.core.configure_run_budget(
                run_id, plan.bucket_ids[provider], plan.attempt_budgets[provider]
            )
        if row["initialized"]:
            return
        proposal_id = self._seed_batch(run_id, plan, row)
        seeds = (ProbeSeed(plan.topic, plan.topic_family, "topic", f"topic:{run_id}"),
                 *plan.llm_proposal.seeds(proposal_id))
        probe_plan = ProbePlan(seeds, plan.mask_rules, plan.max_probe_candidates)
        if row["probe_batch_id"]:
            probe_id = str(row["probe_batch_id"])
            payload = self.store.load_seed_batch(probe_id)["payload"]
            if payload["plan"] != probe_plan.descriptor():
                raise ValueError("persisted probe plan differs")
            probes = payload["result"]["probes"]
        else:
            matching = next((candidate["id"] for candidate in self.db.execute(
                "SELECT id,payload_json FROM semantic_seed_batches "
                "WHERE run_id=? AND kind='probe_generation' AND parent_id=?",
                (run_id, proposal_id),
            ) if json.loads(candidate["payload_json"])["plan"] == probe_plan.descriptor()), None)
            if matching is not None:
                probe_id = matching
                probes = self.store.load_seed_batch(probe_id)["payload"]["result"]["probes"]
            else:
                probe_id, generated = self.store.save_probe_generation(
                    run_id, probe_plan, parent_id=proposal_id
                )
                probes = [item.descriptor() for item in generated.probes]
            with self.db:
                self.db.execute("UPDATE collection_runs SET probe_batch_id=? WHERE run_id=?",
                                (probe_id, run_id))
        branches: dict[str, str] = {}
        for family in dict.fromkeys(seed.family.value for seed in seeds):
            branch_id = self.frontier.create_branch(
                run_id, f"initial-family:{family}", transition_kind="initial_seed_family",
                origin_kind="topic", origin_ref=f"topic:{run_id}", family=family,
                label=family, reason="initial topic/seed family",
            )
            if self.frontier.branch(branch_id)["state"] == "proposed":
                self.frontier.set_branch_state(branch_id, "eligible")
            branches[family] = branch_id
        for probe in probes:
            families_for_probe = sorted({origin["seed_family"] for origin in probe["origins"]})
            for family in families_for_probe:
                branch_id = branches[family]
                probe_families = {"seed" if origin["rule_family"] is None else origin["rule_family"]
                                  for origin in probe["origins"] if origin["seed_family"] == family}
                for probe_family in sorted(probe_families):
                    for source in PROVIDERS[1:]:
                        self.frontier.add_opportunity(
                            run_id, branch_id, probe_family,
                            self.suggests[source].semantic_request(probe["phrase"]),
                        )
        topic_branch = branches[plan.topic_family.value]
        self.frontier.add_opportunity(
            run_id, topic_branch, "seed", self.gettop.semantic_request(
                plan.topic, num_phrases=plan.wordstat_num_phrases,
                regions=plan.wordstat_regions, devices=plan.wordstat_devices,
            ),
        )
        with self.db:
            self.db.execute("UPDATE collection_runs SET initialized=1 WHERE run_id=?", (run_id,))

    def _parser(self, request: SemanticRequest):
        if request.provider == "yandex_wordstat":
            return parse_gettop, GETTOP_PARSER_VERSION
        if request.provider in self.suggests:
            return parse_suggest, SUGGEST_PARSER_VERSION
        raise ValueError(f"unknown provider: {request.provider}")

    def _successful_batch(self, work_id: str, parser_version: str) -> str:
        row = self.db.execute(
            "SELECT pb.id FROM attempts a JOIN raw_artifacts raw ON raw.attempt_id=a.id "
            "JOIN parse_batches pb ON pb.artifact_id=raw.id WHERE a.work_id=? "
            "AND a.outcome_kind IN ('success_with_data','success_valid_empty') "
            "AND pb.parser_version=? ORDER BY a.id DESC LIMIT 1",
            (work_id, parser_version),
        ).fetchone()
        if row is None:
            raise ArtifactIntegrityError("completed work has no matching parsed raw artifact")
        return row[0]

    def _execute_selected(self, run_id: str, item: Mapping[str, object], plan: CollectPlan) -> None:
        if item["outcome"] is not None:
            return
        request_id = str(item["request_fingerprint"])
        opportunity = self.db.execute(
            "SELECT state FROM semantic_opportunities WHERE run_id=? AND request_fingerprint=? "
            "LIMIT 1", (run_id, request_id),
        ).fetchone()
        if opportunity is None or opportunity["state"] != "selected":
            return
        request = SemanticRequest.from_mapping(json.loads(item["descriptor_json"]))
        provider = request.provider
        disabled = self.db.execute(
            "SELECT reason FROM collection_disabled_providers WHERE run_id=? AND provider=?",
            (run_id, provider),
        ).fetchone()
        if disabled is not None:
            self.frontier.postpone_request(
                run_id, request_id, reason=f"provider disabled: {disabled[0]}", outcome="error"
            )
            return
        parser, parser_version = self._parser(request)
        adapter = self.gettop if provider == "yandex_wordstat" else self.suggests[provider]
        work_id = self.core.create_work(run_id, request_id, request, plan.bucket_ids[provider])
        state = self.core.work(work_id)["state"]
        if state == "completed":
            outcome = OutcomeKind.SUCCESS_WITH_DATA
        elif state in {"failed", "ambiguous"}:
            last = self.core.attempts(work_id)[-1]
            outcome = OutcomeKind(last["outcome_kind"])
        else:
            try:
                outcome = Executor(self.core, policy=plan.retry_policy).execute(
                    work_id, adapter.send, parser, parser_version=parser_version,
                    redactions=(self.gettop.credentials.redactions if provider == "yandex_wordstat" else ()),
                )
            except CapacityUnavailable as error:
                self.frontier.postpone_request(
                    run_id, request_id, reason=str(error), outcome="capacity_blocked"
                )
                with self.db:
                    self.db.execute(
                        "INSERT OR IGNORE INTO collection_disabled_providers VALUES (?,?,?)",
                        (run_id, provider, "capacity_blocked"),
                    )
                return
            except RunBudgetExhausted:
                self.frontier.postpone_request(
                    run_id, request_id, reason="run attempt budget exhausted", outcome="budget_blocked"
                )
                with self.db:
                    self.db.execute(
                        "INSERT OR IGNORE INTO collection_disabled_providers VALUES (?,?,?)",
                        (run_id, provider, "budget_blocked"),
                    )
                return
        if outcome in {OutcomeKind.SUCCESS_WITH_DATA, OutcomeKind.SUCCESS_VALID_EMPTY}:
            self.frontier.record_result(
                run_id, request_id, parse_batch_id=self._successful_batch(work_id, parser_version)
            )
        else:
            unresolved = ("ambiguous" if outcome == OutcomeKind.AMBIGUOUS_EXTERNAL_OUTCOME
                          else "capacity_blocked" if outcome == OutcomeKind.THROTTLED else "error")
            self.frontier.postpone_request(
                run_id, request_id, reason=outcome.value, outcome=unresolved,
            )
            with self.db:
                self.db.execute(
                    "INSERT OR IGNORE INTO collection_disabled_providers VALUES (?,?,?)",
                    (run_id, provider, outcome.value),
                )

    def _postpone_disabled_eligible(self, run_id: str) -> None:
        with self.db:
            self.db.execute(
                "UPDATE semantic_opportunities SET state='postponed',"
                "outcome=CASE (SELECT reason FROM collection_disabled_providers d "
                "WHERE d.run_id=semantic_opportunities.run_id AND d.provider=semantic_opportunities.provider) "
                "WHEN 'capacity_blocked' THEN 'capacity_blocked' "
                "WHEN 'throttled' THEN 'capacity_blocked' "
                "WHEN 'budget_blocked' THEN 'budget_blocked' ELSE 'error' END,"
                "state_reason='provider disabled for this run' "
                "WHERE run_id=? AND state='eligible' AND provider IN "
                "(SELECT provider FROM collection_disabled_providers WHERE run_id=?)",
                (run_id, run_id),
            )

    def _available_attempts(self, run_id: str, plan: CollectPlan) -> dict[str, int]:
        """Run allocation limits tranche selection before external reservations."""
        available = {}
        for provider in PROVIDERS:
            bucket_id = plan.bucket_ids[provider]
            used = self.db.execute(
                "SELECT COUNT(*) FROM attempts a JOIN work_items w ON w.id=a.work_id "
                "WHERE w.run_id=? AND a.bucket_id=? AND a.state!='abandoned_before_dispatch'",
                (run_id, bucket_id),
            ).fetchone()[0]
            available[provider] = max(0, plan.attempt_budgets[provider] - used)
        return available

    def association_review_batch(self, run_id: str, plan: CollectPlan) -> list[dict[str, object]]:
        """Compact, raw-backed candidate context for an external Codex reviewer."""
        self._collection(run_id, plan)
        if not plan.association_review_required:
            return []
        candidates = []
        rows = self.db.execute(
            "SELECT id,label,family,origin_ref FROM semantic_branches "
            "WHERE run_id=? AND transition_kind='wordstat_association' "
            "AND state='proposed' ORDER BY created_at_utc,id", (run_id,),
        ).fetchall()
        for row in rows:
            origin = self.store.provenance(int(row["origin_ref"]))
            parents = [item[0] for item in self.db.execute(
                "SELECT p.label FROM semantic_branch_parents x "
                "JOIN semantic_branches p ON p.id=x.parent_id "
                "WHERE x.branch_id=? ORDER BY p.id", (row["id"],),
            )]
            context = {
                "run_id": run_id, "branch_id": row["id"], "topic": plan.topic,
                "phrase": row["label"], "family": row["family"],
                "parent_branches": parents, "seed_phrase": origin["request"]["phrase"],
                "observation_id": origin["observation_id"],
                "channel": origin["channel"], "rank": origin["rank"],
                "raw_artifact_id": origin["artifact_id"],
            }
            candidates.append({**context, "input_sha256": hashlib.sha256(
                canonical_json(context).encode("utf-8")
            ).hexdigest()})
        return candidates

    def apply_association_reviews(
        self, run_id: str, plan: CollectPlan, decisions: Sequence[Mapping[str, object]],
        *, reviewer: str, review_version: str,
    ) -> None:
        """Accept one complete, versioned external assessment of pending branches."""
        pending = self.association_review_batch(run_id, plan)
        if not pending:
            raise ValueError("no pending association review")
        if any(not isinstance(value, str) or not value.strip()
               for value in (reviewer, review_version)):
            raise ValueError("reviewer and review_version are required")
        expected = {item["branch_id"]: item for item in pending}
        if (len(decisions) != len(expected)
                or any(not isinstance(item, Mapping) for item in decisions)
                or {item.get("branch_id") for item in decisions} != set(expected)):
            raise ValueError("review must cover each pending branch exactly once")
        for item in decisions:
            if set(item) != {"branch_id", "input_sha256", "decision", "reason"}:
                raise ValueError("invalid association review fields")
            if item["input_sha256"] != expected[item["branch_id"]]["input_sha256"]:
                raise ValueError("review input changed; refresh candidate batch")
            if item["decision"] not in {"expand", "uncertain", "defer"}:
                raise ValueError("invalid association review decision")
            if not isinstance(item["reason"], str) or not item["reason"].strip():
                raise ValueError("association review needs a reason")
        with self.db:
            for item in decisions:
                self.db.execute(
                    "INSERT INTO collection_association_reviews VALUES (?,?,?,?,?,?,?,?,?)",
                    (item["branch_id"], 1, run_id, item["decision"], item["reason"],
                     reviewer, review_version, item["input_sha256"], _now()),
                )
                updated = self.db.execute(
                    "UPDATE semantic_branches SET state=?,state_reason=? "
                    "WHERE id=? AND run_id=? AND state='proposed'",
                    ("eligible" if item["decision"] == "expand" else "postponed",
                     None if item["decision"] == "expand" else "association_review_deferred",
                     item["branch_id"], run_id),
                )
                if updated.rowcount != 1:
                    raise ValueError("association branch changed during review")
            self.db.execute(
                "UPDATE run_states SET pause_reason=NULL,resumability='resumable_automatically',"
                "updated_at_utc=? WHERE run_id=? AND pause_reason='awaiting_semantic_review'",
                (_now(), run_id),
            )

    def reconsider_association(
        self, run_id: str, plan: CollectPlan, branch_id: str, *,
        decision: str, reason: str, reviewer: str, review_version: str,
    ) -> None:
        """Promote or keep a deferred branch without erasing earlier judgments."""
        self._collection(run_id, plan)
        if decision not in {"expand", "uncertain", "defer"}:
            raise ValueError("invalid association review decision")
        if any(not isinstance(value, str) or not value.strip()
               for value in (reason, reviewer, review_version)):
            raise ValueError("review reason, reviewer and version are required")
        row = self.db.execute(
            "SELECT r.revision,r.decision,r.input_sha256,b.state,b.state_reason,b.transition_kind "
            "FROM collection_association_reviews r JOIN semantic_branches b "
            "ON b.id=r.branch_id WHERE r.branch_id=? AND r.run_id=? "
            "ORDER BY r.revision DESC LIMIT 1", (branch_id, run_id),
        ).fetchone()
        if (row is None or row["state"] != "postponed"
                or row["state_reason"] != "association_review_deferred"
                or row["decision"] not in {"defer", "uncertain"}
                or row["transition_kind"] != "wordstat_association"):
            raise ValueError("only a reviewed, deferred association may be reconsidered")
        with self.db:
            self.db.execute(
                "INSERT INTO collection_association_reviews VALUES (?,?,?,?,?,?,?,?,?)",
                (branch_id, row["revision"] + 1, run_id, decision, reason,
                 reviewer, review_version, row["input_sha256"], _now()),
            )
            self.db.execute(
                "UPDATE semantic_branches SET state=?,state_reason=? WHERE id=?",
                ("eligible" if decision == "expand" else "postponed",
                 None if decision == "expand" else "association_review_deferred",
                 branch_id),
            )

    def _expand_observed(self, run_id: str, plan: CollectPlan, *, hold_new: bool = False) -> None:
        """Bounded one-step-at-a-time snowball; evidence is retained even when not expanded."""
        rows = self.db.execute(
            "SELECT e.observation_id,o.canonical_id,o.raw_phrase,o.channel,o.rank,"
            "raw.request_fingerprint,r.descriptor_json "
            "FROM semantic_request_evidence e JOIN observations o ON o.id=e.observation_id "
            "JOIN parse_batches pb ON pb.id=o.batch_id "
            "JOIN raw_artifacts raw ON raw.id=pb.artifact_id "
            "JOIN semantic_requests r ON r.fingerprint=raw.request_fingerprint "
            "WHERE e.run_id=? ORDER BY e.observation_id", (run_id,),
        ).fetchall()
        first_by_canonical: dict[int, object] = {}
        for row in rows:
            first_by_canonical.setdefault(row["canonical_id"], row)
        # Interleave source channels so a long results list cannot occupy all
        # observed-branch slots before lateral associations and Suggest appear.
        by_channel: dict[str, deque[tuple[int, object]]] = {}
        for canonical_id, row in first_by_canonical.items():
            source_request = SemanticRequest.from_mapping(json.loads(row["descriptor_json"]))
            if normalize_phrase_v1(row["raw_phrase"]) == normalize_phrase_v1(source_request.phrase):
                continue
            by_channel.setdefault(row["channel"], deque()).append((canonical_id, row))
        balanced: list[tuple[int, object]] = []
        channel_order = [name for name in (
            "gettop.results", "yandex_suggest", "google_suggest",
            "gettop.associations", "youtube_suggest",
        ) if name in by_channel]
        channel_order.extend(sorted(set(by_channel) - set(channel_order)))
        while any(by_channel.values()):
            for channel in channel_order:
                if by_channel[channel]:
                    balanced.append(by_channel[channel].popleft())
        for canonical_id, row in balanced:
            key = f"observed-canonical:{canonical_id}"
            existing = self.db.execute(
                "SELECT id FROM semantic_branches WHERE run_id=? AND creation_key=?",
                (run_id, key),
            ).fetchone()
            if existing:
                branch_id = existing[0]
            else:
                count = self.db.execute(
                    "SELECT COUNT(*) FROM semantic_branches WHERE run_id=? "
                    "AND transition_kind IN ('observed_relation','wordstat_association')", (run_id,),
                ).fetchone()[0]
                if count >= plan.max_observed_branches and not hold_new:
                    continue
                source_request = SemanticRequest.from_mapping(json.loads(row["descriptor_json"]))
                if normalize_phrase_v1(row["raw_phrase"]) == normalize_phrase_v1(source_request.phrase):
                    continue
                parents = tuple(item[0] for item in self.db.execute(
                    "SELECT DISTINCT branch_id FROM semantic_opportunities "
                    "WHERE run_id=? AND request_fingerprint=? ORDER BY branch_id",
                    (run_id, row["request_fingerprint"]),
                ))
                family = (self.frontier.branch(parents[0])["family"] if parents
                          else plan.topic_family.value)
                transition = ("wordstat_association" if row["channel"] == "gettop.associations"
                              else "observed_relation")
                branch_id = self.frontier.create_branch(
                    run_id, key, transition_kind=transition, origin_kind="observation",
                    origin_ref=str(row["observation_id"]), family=family,
                    label=row["raw_phrase"], reason="first observed canonical phrase; provisional expansion order",
                    parents=parents, evidence_ids=(row["observation_id"],),
                )
            for other in rows:
                if other["canonical_id"] == canonical_id:
                    self.frontier.add_evidence(branch_id, other["observation_id"], role="reobserved")
            branch = self.frontier.branch(branch_id)
            if branch["state"] == "postponed" or (hold_new and branch["state"] == "proposed"):
                # Deferred branches stay visible without generating work. Remove
                # only unselected placeholders left by older uncertain reviews.
                if branch["state_reason"] == "association_review_deferred":
                    with self.db:
                        self.db.execute(
                            "DELETE FROM semantic_opportunities WHERE branch_id=? "
                            "AND state='eligible' AND tranche_number IS NULL", (branch_id,),
                        )
                continue
            if plan.association_review_required and branch["transition_kind"] == "wordstat_association":
                review = self.db.execute(
                    "SELECT decision FROM collection_association_reviews WHERE branch_id=? "
                    "ORDER BY revision DESC LIMIT 1",
                    (branch_id,),
                ).fetchone()
                if review is None or review["decision"] != "expand":
                    continue
            if branch["state"] == "proposed":
                self.frontier.set_branch_state(branch_id, "eligible")
            seed = ProbeSeed(branch["label"], SeedFamily(branch["family"]), "observation",
                             branch["origin_ref"])
            probe_plan = ProbePlan((seed,), plan.mask_rules, plan.max_probe_candidates)
            probe_row = self.db.execute(
                "SELECT batch_id FROM collection_branch_probes WHERE branch_id=?", (branch_id,)
            ).fetchone()
            if probe_row:
                generated = self.store.load_seed_batch(probe_row[0])["payload"]["result"]["probes"]
            else:
                parent_id = self._collection(run_id, plan)["proposal_batch_id"]
                matching = next((candidate["id"] for candidate in self.db.execute(
                    "SELECT id,payload_json FROM semantic_seed_batches "
                    "WHERE run_id=? AND kind='probe_generation' AND parent_id=?",
                    (run_id, parent_id),
                ) if json.loads(candidate["payload_json"])["plan"] == probe_plan.descriptor()), None)
                if matching is not None:
                    generated_id = matching
                    generated = self.store.load_seed_batch(generated_id)["payload"]["result"]["probes"]
                else:
                    generated_id, batch = self.store.save_probe_generation(
                        run_id, probe_plan, parent_id=parent_id
                    )
                    generated = [item.descriptor() for item in batch.probes]
                with self.db:
                    self.db.execute(
                        "INSERT OR IGNORE INTO collection_branch_probes VALUES (?,?)",
                        (branch_id, generated_id),
                    )
            for probe in generated:
                families = {"seed" if origin["rule_family"] is None else origin["rule_family"]
                            for origin in probe["origins"]}
                for probe_family in sorted(families):
                    for provider in PROVIDERS[1:]:
                        self.frontier.add_opportunity(
                            run_id, branch_id, probe_family,
                            self.suggests[provider].semantic_request(probe["phrase"]),
                        )
            self.frontier.add_opportunity(
                run_id, branch_id, "seed", self.gettop.semantic_request(
                    branch["label"], num_phrases=plan.wordstat_num_phrases,
                    regions=plan.wordstat_regions, devices=plan.wordstat_devices,
                ),
            )

    def run(self, run_id: str, plan: CollectPlan) -> dict[str, object]:
        """Resume an initialized one-topic run; no automatic retry of postponed work."""
        if self.db.execute(
            "SELECT 1 FROM guided_collection_runs WHERE run_id=?", (run_id,)
        ).fetchone() is not None:
            raise ValueError("guided run must be continued through guided checkpoints")
        self._initialize(run_id, plan)
        recovery = self.core.recover(self._parser)
        if recovery.integrity_errors:
            raise ArtifactIntegrityError("raw artifact integrity check failed")
        self._expand_observed(run_id, plan)
        while True:
            if self.frontier.status(run_id)["semantic_stop"] != "continuation_possible":
                break
            if self.association_review_batch(run_id, plan):
                self.core.set_run_state(
                    run_id, outcome="degraded_success", semantic_stop="continuation_possible",
                    pause_reason="awaiting_semantic_review", resumability="requires_operator_decision",
                )
                break
            self._postpone_disabled_eligible(run_id)
            number, selected = self.frontier.start_tranche(
                run_id, plan.frontier_policy,
                available_attempts=self._available_attempts(run_id, plan),
            )
            if number is None:
                # A per-provider attempt allocation can be exhausted before the
                # shared hard request maximum. Keep eligible semantic work visible
                # and classify this as an operational budget pause, not saturation.
                eligible_providers = {row[0] for row in self.db.execute(
                    "SELECT DISTINCT provider FROM semantic_opportunities "
                    "WHERE run_id=? AND state='eligible'", (run_id,),
                )}
                remaining = self._available_attempts(run_id, plan)
                if (eligible_providers and
                        all(remaining.get(provider, 0) == 0 for provider in eligible_providers)):
                    completed = self.db.execute(
                        "SELECT 1 FROM semantic_request_results WHERE run_id=? LIMIT 1",
                        (run_id,),
                    ).fetchone() is not None
                    self.core.set_run_state(
                        run_id, outcome="degraded_success" if completed else "incomplete",
                        semantic_stop="continuation_possible",
                        pause_reason="run_budget_exhausted",
                        resumability="requires_operator_decision",
                    )
                break
            for item in selected:
                self._execute_selected(run_id, item, plan)
            self._expand_observed(run_id, plan)
            self._postpone_disabled_eligible(run_id)
            self.frontier.review_tranche(run_id, number)
        return self.snapshot(run_id, plan)

    def retry_postponed(self, run_id: str, request_fingerprint: str, plan: CollectPlan,
                        *, accept_ambiguous_cost_risk: bool = False) -> None:
        """Explicitly resume one failed/capacity item, preserving paid-call ambiguity."""
        self._collection(run_id, plan)
        row = self.db.execute(
            "SELECT outcome,tranche_number FROM semantic_opportunities WHERE run_id=? "
            "AND request_fingerprint=? AND state='postponed' LIMIT 1",
            (run_id, request_fingerprint),
        ).fetchone()
        if row is None:
            raise ValueError("request is not postponed")
        if row["outcome"] == "ambiguous" and not accept_ambiguous_cost_risk:
            raise ValueError("ambiguous call needs explicit duplicate-cost risk acceptance")
        if (row["tranche_number"] is None and
                self.frontier.status(run_id)["semantic_stop"] != "continuation_possible"):
            raise ValueError("unselected work cannot resume after this run's semantic/budget stop")
        work = self.db.execute(
            "SELECT id,state FROM work_items WHERE run_id=? AND logical_key=?",
            (run_id, request_fingerprint),
        ).fetchone()
        if work is not None and work["state"] in {"failed", "ambiguous"}:
            self.core.reopen_failed(work["id"], accept_ambiguous_risk=accept_ambiguous_cost_risk)
        provider_row = self.db.execute(
            "SELECT json_extract(descriptor_json,'$.provider') FROM semantic_requests "
            "WHERE fingerprint=?", (request_fingerprint,),
        ).fetchone()
        if provider_row is not None:
            with self.db:
                self.db.execute(
                    "DELETE FROM collection_disabled_providers WHERE run_id=? AND provider=?",
                    (run_id, provider_row[0]),
                )
        if row["tranche_number"] is None:
            with self.db:
                self.db.execute(
                    "UPDATE semantic_opportunities SET state='eligible',state_reason=NULL,outcome=NULL "
                    "WHERE run_id=? AND request_fingerprint=? AND state='postponed'",
                    (run_id, request_fingerprint),
                )
        else:
            self.frontier.resume_request(
                run_id, request_fingerprint, accept_ambiguous_risk=accept_ambiguous_cost_risk
            )

    def snapshot(self, run_id: str, plan: CollectPlan) -> dict[str, object]:
        """Freeze exact observation IDs and source contexts; never synthesize zero counts."""
        collection = self._collection(run_id, plan)
        requests: list[dict[str, object]] = []
        phrases: dict[int, dict[str, object]] = {}
        for result in self.db.execute(
            "SELECT result.request_fingerprint,result.outcome,r.descriptor_json "
            "FROM semantic_request_results result JOIN semantic_requests r "
            "ON r.fingerprint=result.request_fingerprint WHERE result.run_id=? "
            "ORDER BY result.completed_at_utc,result.request_fingerprint", (run_id,),
        ).fetchall():
            provider = json.loads(result["descriptor_json"])["provider"]
            parser_version = (GETTOP_PARSER_VERSION if provider == "yandex_wordstat"
                              else SUGGEST_PARSER_VERSION)
            work = self.db.execute(
                "SELECT id FROM work_items WHERE run_id=? AND logical_key=?",
                (run_id, result["request_fingerprint"]),
            ).fetchone()
            if work is None:
                raise ArtifactIntegrityError("semantic result has no durable work")
            batch_id = self._successful_batch(work[0], parser_version)
            raw = self.db.execute(
                "SELECT a.id,a.sha256,a.received_at_utc,a.status_code,b.kind "
                "FROM parse_batches b JOIN raw_artifacts a ON a.id=b.artifact_id "
                "WHERE b.id=?", (batch_id,),
            ).fetchone()
            self.store.read_raw(raw["id"])
            measurements = self.store.measurements(batch_id)
            obs = self.store.observations(batch_id)
            requests.append({
                "fingerprint": result["request_fingerprint"], "request": json.loads(result["descriptor_json"]),
                "outcome": result["outcome"], "batch_id": batch_id, "parser_version": parser_version,
                "raw_artifact_id": raw["id"], "raw_sha256": raw["sha256"],
                "received_at_utc": raw["received_at_utc"], "http_status": raw["status_code"],
                "observation_ids": [item["id"] for item in obs],
                "request_measurements": [item for item in measurements if item["observation_id"] is None],
            })
            for observation in obs:
                details = self.store.provenance(observation["id"])
                canonical = self.db.execute(
                    "SELECT canonical_id FROM observations WHERE id=?", (observation["id"],)
                ).fetchone()[0]
                record = phrases.setdefault(canonical, {
                    "canonical_id": canonical, "normalized_phrase": observation["normalized_text"],
                    "observations": [], "wordstat_frequency": "unknown",
                })
                linked_measurements = [item for item in measurements
                                       if item["observation_id"] == observation["id"]]
                if any(item["kind"] == "wordstat_gettop_phrase_count" for item in linked_measurements):
                    record["wordstat_frequency"] = "measured"
                record["observations"].append({
                    **details, "measurements": linked_measurements,
                })
        gaps = [dict(row) for row in self.db.execute(
            "SELECT provider,request_fingerprint,outcome,state_reason FROM semantic_opportunities "
            "WHERE run_id=? AND state='postponed' ORDER BY provider,request_fingerprint",
            (run_id,),
        ).fetchall()]
        axes = self.core.run_state(run_id)
        if gaps:
            axes["outcome"] = "degraded_success" if requests else "incomplete"
            axes["resumability"] = ("requires_operator_decision" if any(
                gap["outcome"] in {"ambiguous", "budget_blocked"} for gap in gaps)
                else "after_capacity_available" if any(gap["outcome"] == "capacity_blocked" for gap in gaps)
                else "resumable_automatically")
        elif requests and axes["semantic_stop"] != "continuation_possible":
            axes["outcome"] = "success"
            axes["pause_reason"] = None
            axes["resumability"] = "no_pending_work"
        with self.db:
            self.db.execute(
                "UPDATE run_states SET outcome=?,pause_reason=?,resumability=?,updated_at_utc=? "
                "WHERE run_id=?", (axes["outcome"], axes["pause_reason"], axes["resumability"],
                                  _now(), run_id),
            )
        frontier_status = self.frontier.status(run_id)
        exposure = [dict(row) for row in self.db.execute(
            "SELECT provider,COUNT(DISTINCT request_fingerprint) AS planned,"
            "COUNT(DISTINCT CASE WHEN state='completed' THEN request_fingerprint END) AS completed,"
            "COUNT(DISTINCT CASE WHEN state='postponed' THEN request_fingerprint END) AS missing,"
            "COUNT(DISTINCT CASE WHEN state='selected' THEN request_fingerprint END) AS selected,"
            "COUNT(DISTINCT CASE WHEN state='invalid' THEN request_fingerprint END) AS invalid,"
            "COUNT(DISTINCT CASE WHEN state='eligible' THEN request_fingerprint END) AS remaining "
            "FROM semantic_opportunities WHERE run_id=? GROUP BY provider ORDER BY provider",
            (run_id,),
        ).fetchall()]
        payload = {
            "run_id": run_id, "topic": plan.topic, "plan_sha256": collection["plan_sha256"],
            "run_state": {name: axes[name] for name in ("outcome", "semantic_stop", "pause_reason", "resumability")},
            "frontier": frontier_status, "requests": requests,
            "phrases": sorted(phrases.values(), key=lambda item: item["normalized_phrase"]),
            "gaps": gaps, "provider_exposure": exposure,
            "provider_diagnostics": self.core.diagnostics(run_id),
            "association_review_pending": len(self.association_review_batch(run_id, plan)),
        }
        encoded = canonical_json(payload)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO collection_snapshots VALUES (?,?,?,?,?)",
                (digest, run_id, _now(), encoded, digest),
            )
        return {"snapshot_id": digest, **payload}

    def read_snapshot(self, snapshot_id: str) -> dict[str, object]:
        row = self.db.execute(
            "SELECT payload_json,sha256 FROM collection_snapshots WHERE id=?", (snapshot_id,)
        ).fetchone()
        if row is None:
            raise KeyError(snapshot_id)
        if hashlib.sha256(row["payload_json"].encode("utf-8")).hexdigest() != row["sha256"]:
            raise ArtifactIntegrityError("collection snapshot digest mismatch")
        return {"snapshot_id": snapshot_id, **json.loads(row["payload_json"])}
