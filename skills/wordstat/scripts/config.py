"""Versioned local profile and strict reconstruction of saved collection plans.

Provider capacity and tariff are runtime configuration, not semantic constants.
The bounded profile is a conservative operating choice, not an optimum claim.
"""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from typing import Mapping

from .collect import PROVIDERS, CollectPlan
from .compare import ComparePlan
from .execution import CapacityBucket, RetryPolicy
from .frontier import FrontierPolicy
from .seed_probes import LLMProposalBatch, ProbeRule, SeedFamily
from .wordstat_gettop import GetTopTariff


PROFILE_VERSION = "bounded-stage10-v1"
GUIDED_PROFILE_VERSION = "guided-collection-v1"
PRICING_SOURCE = "https://aistudio.yandex.ru/ru/docs/search-api/pricing"


def _positive_env(env: Mapping[str, str], name: str, default: int) -> int:
    value = int(env.get(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be positive")
    return value


def capacity_buckets(env: Mapping[str, str] | None = None) -> dict[str, CapacityBucket]:
    env = os.environ if env is None else env
    wordstat_id = env.get("WORDSTAT_CAPACITY_BUCKET", "wordstat_primary")
    wordstat = CapacityBucket(
        wordstat_id, _positive_env(env, "WORDSTAT_CAPACITY_RPS", 10),
        _positive_env(env, "WORDSTAT_CAPACITY_HOURLY", 100), 3600,
    )
    suggest_rps = _positive_env(env, "WORDSTAT_SUGGEST_LOCAL_RPS", 1)
    suggest_limit = _positive_env(env, "WORDSTAT_SUGGEST_LOCAL_PER_MINUTE", 10)
    return {
        "yandex_wordstat": wordstat,
        **{source: CapacityBucket(source + "_local", suggest_rps, suggest_limit, 60)
           for source in PROVIDERS[1:]},
    }


def configured_tariff(env: Mapping[str, str] | None = None) -> GetTopTariff:
    env = os.environ if env is None else env
    price = env.get("WORDSTAT_TARIFF_RUB_PER_1000")
    checked = env.get("WORDSTAT_TARIFF_CHECKED_ON")
    if price is None or checked is None:
        raise ValueError("set WORDSTAT_TARIFF_RUB_PER_1000 and WORDSTAT_TARIFF_CHECKED_ON "
                         "from a checked official pricing snapshot")
    return GetTopTariff(Decimal(price), "RUB", date.fromisoformat(checked), PRICING_SOURCE)


def bounded_collect_plan(
    topic: str, family: SeedFamily | str, proposal: Mapping[str, object],
    *, tariff: GetTopTariff, buckets: Mapping[str, CapacityBucket],
    mask_rules: tuple[ProbeRule, ...] = (), max_probe_candidates: int = 32,
    max_observed_branches: int = 64,
) -> CollectPlan:
    """A small, explicit v1 profile; all cost/capacity inputs remain external."""
    if set(buckets) != set(PROVIDERS):
        raise ValueError("all four capacity buckets are required")
    batch = LLMProposalBatch.from_mapping(proposal, max_hypotheses=4, max_rules=0)
    attempt_budgets = {provider: 4 for provider in PROVIDERS}
    return CollectPlan(
        topic=topic, topic_family=SeedFamily(family), llm_proposal=batch,
        mask_rules=mask_rules, max_probe_candidates=max_probe_candidates,
        max_observed_branches=max_observed_branches,
        frontier_policy=FrontierPolicy(
            tranche_size=4, hard_max_requests=16, breadth_reserve=2,
            per_branch_cap=2, weak_max_new_unique=0, weak_min_rediscovered=1,
            weak_max_newly_supported_branches=0, weak_tranches_to_stop=5,
            version=PROFILE_VERSION,
        ),
        bucket_ids={provider: buckets[provider].id for provider in PROVIDERS},
        attempt_budgets=attempt_budgets,
        retry_policy=RetryPolicy(max_attempts=2, max_total_wait=5),
        wordstat_num_phrases=200, wordstat_regions=(), wordstat_devices=(),
        tariff=tariff,
        max_estimated_wordstat_cost=tariff.estimate(attempt_budgets["yandex_wordstat"]),
        version=PROFILE_VERSION, association_review_required=True,
    )


def guided_collect_plan(
    topic: str, family: SeedFamily | str, proposal: Mapping[str, object],
    *, tariff: GetTopTariff, buckets: Mapping[str, CapacityBucket],
    max_estimated_wordstat_cost: Decimal,
    mask_rules: tuple[ProbeRule, ...] = (), max_probe_candidates: int = 128,
    max_observed_branches: int = 256,
    attempt_budgets: Mapping[str, int] | None = None,
) -> CollectPlan:
    """Bounded operating policy for reviewed waves, independent of hourly quota.

    These safety limits are provisional operating choices, not calibrated
    optimum or a promise of semantic completeness. Existing runs retain their
    exact saved plans; changing provider capacity does not change this policy.
    """
    if set(buckets) != set(PROVIDERS):
        raise ValueError("all four capacity buckets are required")
    batch = LLMProposalBatch.from_mapping(proposal, max_hypotheses=32, max_rules=0)
    budgets = {provider: 64 for provider in PROVIDERS}
    if attempt_budgets is not None:
        if not set(attempt_budgets) <= set(PROVIDERS):
            raise ValueError("unknown provider in attempt budgets")
        budgets.update(attempt_budgets)
    return CollectPlan(
        topic=topic, topic_family=SeedFamily(family), llm_proposal=batch,
        mask_rules=mask_rules, max_probe_candidates=max_probe_candidates,
        max_observed_branches=max_observed_branches,
        frontier_policy=FrontierPolicy(
            tranche_size=8, hard_max_requests=sum(budgets.values()),
            breadth_reserve=2, per_branch_cap=4,
            weak_max_new_unique=0, weak_min_rediscovered=1,
            weak_max_newly_supported_branches=0, weak_tranches_to_stop=3,
            version=GUIDED_PROFILE_VERSION,
        ),
        bucket_ids={provider: buckets[provider].id for provider in PROVIDERS},
        attempt_budgets=budgets,
        retry_policy=RetryPolicy(max_attempts=2, max_total_wait=5),
        wordstat_num_phrases=200, wordstat_regions=("225",), wordstat_devices=(),
        tariff=tariff, max_estimated_wordstat_cost=max_estimated_wordstat_cost,
        version=GUIDED_PROFILE_VERSION, association_review_required=True,
    )


def collect_plan_from_descriptor(value: Mapping[str, object]) -> CollectPlan:
    """Recreate a saved plan exactly; reject unknown fields and drift."""
    required = {
        "version", "topic", "topic_family", "llm_proposal", "mask_rules",
        "max_probe_candidates", "max_observed_branches", "frontier_policy",
        "bucket_ids", "attempt_budgets", "retry_policy", "wordstat_num_phrases",
        "wordstat_regions", "wordstat_devices", "tariff", "max_estimated_wordstat_cost",
    }
    if set(value) not in (required, required | {"association_review_required"}):
        raise ValueError("saved collect plan has unknown or missing fields")
    model = value["llm_proposal"]
    # Saved descriptors carry a trusted origin marker. The model-input parser
    # deliberately rejects it, so verify and strip it before reconstruction.
    proposed_rules = model["proposed_rules"]
    if any(rule.get("origin") != "llm_proposed" for rule in proposed_rules):
        raise ValueError("saved model rule has invalid origin")
    proposal = LLMProposalBatch.from_mapping(
        {**model, "proposed_rules": [
            {key: item for key, item in rule.items() if key != "origin"}
            for rule in proposed_rules
        ]},
        max_hypotheses=max(1, len(model["hypotheses"])),
        max_rules=len(proposed_rules),
    )
    rules = tuple(ProbeRule(
        **{**rule, "values": tuple(rule["values"])}
    ) for rule in value["mask_rules"])
    tariff = value["tariff"]
    retry = value["retry_policy"]
    return CollectPlan(
        topic=value["topic"], topic_family=value["topic_family"],
        llm_proposal=proposal, mask_rules=rules,
        max_probe_candidates=value["max_probe_candidates"],
        max_observed_branches=value["max_observed_branches"],
        frontier_policy=FrontierPolicy(**value["frontier_policy"]),
        bucket_ids=value["bucket_ids"], attempt_budgets=value["attempt_budgets"],
        retry_policy=RetryPolicy(**{key: (int(item) if str(item).lstrip("-").isdigit()
                                          else float(item)) if key in {
            "base_delay", "max_delay", "max_total_wait"} else item
            for key, item in retry.items()}),
        wordstat_num_phrases=value["wordstat_num_phrases"],
        wordstat_regions=tuple(value["wordstat_regions"]),
        wordstat_devices=tuple(value["wordstat_devices"]),
        tariff=GetTopTariff(
            Decimal(tariff["price_per_1000"]), tariff["currency"],
            date.fromisoformat(tariff["checked_on"]), tariff["source_url"],
        ),
        max_estimated_wordstat_cost=Decimal(value["max_estimated_wordstat_cost"]),
        version=value["version"],
        association_review_required=value.get("association_review_required", False),
    )


def compare_plan_from_descriptor(value: Mapping[str, object]) -> ComparePlan:
    required = {"version", "max_llm_hypotheses", "max_llm_proposed_rules",
                "normalization_version", "probe_grammar_version", "collection_plans"}
    if set(value) != required:
        raise ValueError("saved compare plan has unknown or missing fields")
    plans = tuple(collect_plan_from_descriptor(item) for item in value["collection_plans"])
    return ComparePlan(plans, value["max_llm_hypotheses"],
                       value["max_llm_proposed_rules"], value["version"])
