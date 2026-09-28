"""Small native entry point for bounded collect/compare runs and exact exports."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from decimal import Decimal, InvalidOperation

from .collect import PROVIDERS, Collector
from .compare import ComparePlan, Comparer
from .config import (GUIDED_PROFILE_VERSION, PROFILE_VERSION,
                     bounded_collect_plan, guided_collect_plan, capacity_buckets,
                     collect_plan_from_descriptor, compare_plan_from_descriptor,
                     configured_tariff)
from .execution import TransportFailure
from .exports import SnapshotStore, export_snapshot, read_snapshot, read_topvisor_job, read_report_context
from .guided import GuidedCollector
from .locking import StoreBusyError
from .seed_probes import ProbeRule
from .storage import ArtifactIntegrityError, DataStore, ParserFailure
from .suggest import SuggestAdapter, SuggestContext, SuggestSource
from .topvisor import (FrequencyQualifier, TopvisorCredentials, TopvisorReadClient,
                       TopvisorRunner, response_envelope)
from .wordstat_gettop import GetTopAdapter, GetTopCredentials


def _json_file(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _runtime(store: DataStore) -> Collector:
    buckets = capacity_buckets()
    gettop = GetTopAdapter(GetTopCredentials.from_environment())
    context = SuggestContext()
    suggests = {source.value: SuggestAdapter(source, context=context)
                for source in SuggestSource}
    return Collector(store, gettop, suggests, buckets)


def _topvisor_runtime(store: DataStore) -> TopvisorRunner:
    return TopvisorRunner(store, TopvisorCredentials.from_environment())


def _parse_qualifier_arg(spec: str) -> FrequencyQualifier:
    parts = spec.split(":")
    if len(parts) != 3 or not all(part.isascii() and part.isdecimal() for part in parts):
        raise ValueError("qualifier must use REGION:SEARCHER:TYPE format, e.g. 213:0:1")
    return FrequencyQualifier(int(parts[0]), int(parts[1]), int(parts[2]))


def _topvisor_summary(job: dict[str, object]) -> dict[str, object]:
    return {
        "job_id": job["id"],
        "run_id": job["run_id"],
        "snapshot_id": job["snapshot_id"],
        "snapshot_kind": job["snapshot_kind"],
        "phrase_count": len(job["keywords"]),
        "qualifiers": job["qualifiers"],
        "max_cost": job["max_cost"],
        "estimated_cost": job["estimated_cost"],
        "currency": job["currency"],
        "state": job["state"],
        "state_reason": job["state_reason"],
        "remote_task_id": job["remote_task_id"],
        "remote_task_status": job["remote_task_status"],
        "submitted_at_utc": job["submitted_at_utc"],
        "expires_at_utc": job["expires_at_utc"],
        "completed_at_utc": job["completed_at_utc"],
        "page_count": len(job["pages"]),
        "run_state": job["run_state"],
    }


def _saved_plan(store: DataStore, run_id: str, *, compare: bool = False):
    table, column = ("comparison_runs", "id") if compare else ("collection_runs", "run_id")
    row = store._db.execute(
        f"SELECT plan_json FROM {table} WHERE {column}=?", (run_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"unknown {'comparison' if compare else 'run'} ID")
    value = json.loads(row["plan_json"])
    return compare_plan_from_descriptor(value) if compare else collect_plan_from_descriptor(value)


def _summary(snapshot: dict[str, object]) -> dict[str, object]:
    if "datasets" in snapshot:
        pending_by_run = {item["run_id"]: item.get("association_review_pending", 0)
                          for item in snapshot["datasets"]}
        return {
            "comparison_id": snapshot["comparison_id"], "snapshot_id": snapshot["snapshot_id"],
            "comparability": snapshot["comparability"],
            "topics": [{"topic": item["topic"], "run_id": item["run_id"],
                        "snapshot_id": item["collection_snapshot_id"],
                        "run_state": item["run_state"], "provider_exposure": item["provider_exposure"],
                        "association_review_pending": pending_by_run.get(item["run_id"], 0)}
                       for item in snapshot["topics"]],
        }
    return {
        "run_id": snapshot["run_id"], "snapshot_id": snapshot["snapshot_id"],
        "run_state": snapshot["run_state"], "phrase_count": len(snapshot["phrases"]),
        "association_review_pending": snapshot.get("association_review_pending", 0),
        "provider_exposure": snapshot["provider_exposure"], "gaps": snapshot["gaps"],
    }


def _attempt_budget_args(items: list[str]) -> dict[str, int]:
    budgets: dict[str, int] = {}
    for item in items:
        provider, separator, amount = item.partition("=")
        if not separator or not amount.isascii() or not amount.isdecimal():
            raise ValueError("attempt budget must use PROVIDER=COUNT")
        if provider not in PROVIDERS:
            raise ValueError("unknown provider in attempt budgets")
        if provider in budgets:
            raise ValueError("duplicate provider attempt budget")
        budgets[provider] = int(amount)
    return budgets


def _start_plan(args: argparse.Namespace):
    proposal = _json_file(args.proposal)
    if not isinstance(proposal, dict):
        raise ValueError("proposal file must contain one JSON object")
    mask_rules = ()
    if getattr(args, "mask_rules", None):
        raw_rules = _json_file(args.mask_rules)
        if not isinstance(raw_rules, list):
            raise ValueError("mask rules file must contain a JSON array")
        mask_rules = tuple(ProbeRule.from_mapping(item, origin="deterministic")
                           for item in raw_rules)
    is_guided = args.command == "guided"
    new_profile = is_guided and getattr(args, "profile", GUIDED_PROFILE_VERSION) == GUIDED_PROFILE_VERSION
    factory = guided_collect_plan if new_profile else bounded_collect_plan
    limits = _attempt_budget_args(args.attempt_budget)
    budget_args = ({"max_estimated_wordstat_cost": Decimal(args.max_estimated_wordstat_cost),
                    "attempt_budgets": limits}
                   if new_profile else {})
    plan = factory(
        args.topic, args.family, proposal,
        tariff=configured_tariff(), buckets=capacity_buckets(),
        mask_rules=mask_rules,
        max_probe_candidates=((128 if new_profile else 32) if args.max_probe_candidates is None
                              else args.max_probe_candidates),
        max_observed_branches=((256 if new_profile else 64) if args.max_observed_branches is None
                               else args.max_observed_branches),
        **budget_args,
    )
    regions = tuple(args.region or (("225",) if args.command == "guided" else ()))
    num_phrases = getattr(args, "num_phrases", None)
    if (args.max_requests is not None or limits
            or args.max_estimated_wordstat_cost is not None or regions
            or num_phrases is not None):
        budgets = dict(plan.attempt_budgets)
        budgets.update(limits)
        maximum = (plan.frontier_policy.hard_max_requests if args.max_requests is None
                   else args.max_requests)
        if maximum > sum(budgets.values()):
            raise ValueError("request maximum exceeds the sum of provider attempt budgets")
        if (budgets["yandex_wordstat"] > plan.attempt_budgets["yandex_wordstat"]
                and args.max_estimated_wordstat_cost is None):
            raise ValueError("explicit monetary ceiling is required for more Wordstat calls")
        plan = replace(
            plan, frontier_policy=replace(plan.frontier_policy, hard_max_requests=maximum),
            attempt_budgets=budgets,
            wordstat_regions=regions,
            wordstat_num_phrases=(plan.wordstat_num_phrases if num_phrases is None
                                  else num_phrases),
            max_estimated_wordstat_cost=(
                plan.max_estimated_wordstat_cost
                if args.max_estimated_wordstat_cost is None
                else Decimal(args.max_estimated_wordstat_cost)
            ),
        )
    return plan


def _collect(args: argparse.Namespace) -> dict[str, object]:
    with DataStore(args.store) as store:
        collector = _runtime(store)
        if args.action == "start":
            plan = _start_plan(args)
            run_id = collector.start(plan)
            return _summary(collector.run(run_id, plan))
        plan = _saved_plan(store, args.run_id)
        if args.action == "extend-budget":
            increases = _attempt_budget_args(args.attempt_budget)
            grows_wordstat = increases.get("yandex_wordstat", 0) > plan.attempt_budgets["yandex_wordstat"]
            updated = collector.extend_budget(
                args.run_id, plan, hard_max_requests=args.max_requests,
                attempt_budgets=increases,
                tariff=configured_tariff() if grows_wordstat else None,
                max_estimated_wordstat_cost=(
                    Decimal(args.max_estimated_wordstat_cost)
                    if args.max_estimated_wordstat_cost is not None else None
                ),
            )
            row = store._db.execute(
                "SELECT plan_sha256 FROM collection_runs WHERE run_id=?", (args.run_id,),
            ).fetchone()
            guided_row = store._db.execute(
                "SELECT phase FROM guided_collection_runs WHERE run_id=?", (args.run_id,),
            ).fetchone()
            next_action = ("collect resume" if guided_row is None else
                           "guided wave" if guided_row["phase"] == "wave_ready" else
                           "guided checkpoint")
            return {"run_id": args.run_id, "plan_sha256": row[0],
                    "max_requests": updated.frontier_policy.hard_max_requests,
                    "attempt_budgets": dict(updated.attempt_budgets),
                    "max_estimated_wordstat_cost": str(updated.max_estimated_wordstat_cost),
                    "run_state": collector.core.run_state(args.run_id),
                    "next_action": next_action}
        if args.action == "resume":
            return _summary(collector.run(args.run_id, plan))
        if args.action == "review-batch":
            return {"run_id": args.run_id,
                    "candidates": collector.association_review_batch(args.run_id, plan)}
        if args.action == "apply-review":
            decisions = _json_file(args.decisions)
            if isinstance(decisions, dict):
                if (decisions.get("run_id") != args.run_id
                        or decisions.get("reviewer") != args.reviewer
                        or decisions.get("review_version") != args.review_version):
                    raise ValueError("review envelope does not match run and reviewer metadata")
                decisions = decisions.get("decisions")
            if not isinstance(decisions, list):
                raise ValueError("decisions file must contain an array or review envelope")
            collector.apply_association_reviews(
                args.run_id, plan, decisions,
                reviewer=args.reviewer, review_version=args.review_version,
            )
            return {"run_id": args.run_id, "applied": len(decisions),
                    "remaining": len(collector.association_review_batch(args.run_id, plan))}
        if args.action == "reconsider-association":
            collector.reconsider_association(
                args.run_id, plan, args.branch_id, decision=args.decision,
                reason=args.reason, reviewer=args.reviewer,
                review_version=args.review_version,
            )
            return {"run_id": args.run_id, "branch_id": args.branch_id,
                    "decision": args.decision}
    raise ValueError("unknown collect action")


def _guided(args: argparse.Namespace) -> dict[str, object]:
    if args.action in {"scout-report", "checkpoint", "suggest-preview", "wave"}:
        if args.limit < 1 or args.offset < 0:
            raise ValueError("page limit must be positive and offset nonnegative")
    with DataStore(args.store) as store:
        guided = GuidedCollector(_runtime(store))
        if args.action == "scout-create":
            run_id = guided.create_scout(
                args.topic, num_phrases=args.num_phrases,
                regions=tuple(args.region or ("225",)), tariff=configured_tariff(),
                max_estimated_cost=Decimal(args.max_estimated_wordstat_cost),
            )
            return guided.scout_report(run_id)
        if args.action == "scout-run":
            return guided.run_scout(args.run_id)
        if args.action == "scout-report":
            return guided.scout_report(args.run_id, limit=args.limit, offset=args.offset)
        if args.action == "approve-directions":
            plan = _start_plan(args)
            return guided.approve_directions(args.run_id, plan)
        plan = _saved_plan(store, args.run_id)
        if args.action == "suggest-preview":
            result = guided.suggest_preview(args.run_id, plan)
        elif args.action == "checkpoint":
            return guided.checkpoint(args.run_id, limit=args.limit, offset=args.offset)
        elif args.action == "approve-candidates":
            decisions = _json_file(args.decisions)
            if not isinstance(decisions, list):
                raise ValueError("decisions file must contain an array")
            return guided.approve_candidates(
                args.run_id, plan, decisions,
                reviewer=args.reviewer, review_version=args.review_version,
            )
        elif args.action == "wave":
            result = guided.run_wave(args.run_id, plan)
        elif args.action == "resume-capacity":
            return guided.resume_capacity(args.run_id, plan)
        else:
            raise ValueError("unknown guided action")
        result["snapshot"] = _summary(result["snapshot"])
        candidates = result["candidates"]
        result["offset"] = args.offset
        result["candidates"] = candidates[args.offset:args.offset + args.limit]
        result["has_more"] = args.offset + len(result["candidates"]) < result["candidate_count"]
        return result


def _compare(args: argparse.Namespace) -> dict[str, object]:
    with DataStore(args.store) as store:
        comparer = Comparer(_runtime(store))
        if args.action == "guided-attach":
            plans = tuple(_saved_plan(store, run_id) for run_id in args.run_id)
            plan = ComparePlan(plans, max_llm_hypotheses=(
                32 if plans[0].version == GUIDED_PROFILE_VERSION else 4),
                               max_llm_proposed_rules=0)
            comparison_id = comparer.attach_existing(plan, args.run_id)
            return _summary(comparer.snapshot(comparison_id, plan))
        if args.action == "start":
            topics = _json_file(args.topics)
            if not isinstance(topics, list) or len(topics) < 2:
                raise ValueError("topics file must contain at least two topics")
            tariff = configured_tariff()
            buckets = capacity_buckets()
            plans = tuple(bounded_collect_plan(
                item["topic"], item["family"], item["proposal"],
                tariff=tariff, buckets=buckets,
            ) for item in topics)
            plan = ComparePlan(plans, max_llm_hypotheses=4, max_llm_proposed_rules=0)
            comparison_id = comparer.start(plan)
            return _summary(comparer.run(comparison_id, plan))
        plan = _saved_plan(store, args.comparison_id, compare=True)
        if args.action == "extend-budget":
            increases = _attempt_budget_args(args.attempt_budget)
            grows_wordstat = increases.get("yandex_wordstat", 0) > plan.collect_plans[0].attempt_budgets["yandex_wordstat"]
            updated = comparer.extend_budget(
                args.comparison_id, plan, hard_max_requests=args.max_requests,
                attempt_budgets=increases,
                tariff=configured_tariff() if grows_wordstat else None,
                max_estimated_wordstat_cost=(
                    Decimal(args.max_estimated_wordstat_cost)
                    if args.max_estimated_wordstat_cost is not None else None
                ),
            )
            topics = []
            for member, item in zip(comparer._members(args.comparison_id, updated), updated.collect_plans):
                guided = store._db.execute(
                    "SELECT phase FROM guided_collection_runs WHERE run_id=?", (member["run_id"],),
                ).fetchone()
                topics.append({
                    "topic": item.topic, "run_id": member["run_id"],
                    "max_requests": item.frontier_policy.hard_max_requests,
                    "attempt_budgets": dict(item.attempt_budgets),
                    "max_estimated_wordstat_cost": str(item.max_estimated_wordstat_cost),
                    "run_state": comparer.collector.core.run_state(str(member["run_id"])),
                    "next_action": ("compare resume" if guided is None else
                                    "guided wave" if guided["phase"] == "wave_ready" else
                                    "guided checkpoint"),
                })
            return {"comparison_id": args.comparison_id, "topics": topics,
                    "next_snapshot_action": "compare snapshot"}
        if args.action == "snapshot":
            return _summary(comparer.snapshot(args.comparison_id, plan))
        return _summary(comparer.run(args.comparison_id, plan))


def _topvisor(args: argparse.Namespace) -> dict[str, object]:
    if args.action == "regions":
        raw = TopvisorReadClient(TopvisorCredentials.from_environment()).regions_raw(
            args.search, country_code=args.country_code, only_countries=args.only_countries,
        )
        return {"provider": "topvisor", "searcher_key": 0,
                "search": args.search, "result": response_envelope(raw)["result"]}
    with DataStore(args.store) as store:
        if args.action == "create":
            qualifiers: list[FrequencyQualifier] = []
            if args.qualifiers:
                qualifiers.extend(_parse_qualifier_arg(item) for item in args.qualifiers)
            if args.qualifiers_file:
                raw_qualifiers = _json_file(args.qualifiers_file)
                if not isinstance(raw_qualifiers, list):
                    raise ValueError("qualifiers file must contain a JSON array")
                qualifiers.extend(FrequencyQualifier.from_mapping(item) for item in raw_qualifiers)
            if not qualifiers:
                raise ValueError("at least one qualifier is required")
            phrases: list[str] | None = None
            if args.phrases_file:
                raw_phrases = _json_file(args.phrases_file)
                if not isinstance(raw_phrases, list):
                    raise ValueError("phrases file must contain a JSON array of strings")
                phrases = raw_phrases
            if args.max_phrases_per_job is not None and args.max_phrases_per_job <= 0:
                raise ValueError("max-phrases-per-job must be a positive integer")
            selection = store.plan_unknown_topvisor_measurements(
                args.snapshot_id, qualifiers, phrases=phrases,
            )
            summary = {name: selection[name] for name in (
                "requested_pairs", "skipped_known_pairs", "missing_pairs", "pending_pairs", "pending_job_ids",
            )}
            if not selection["groups"]:
                return {"snapshot_id": args.snapshot_id,
                        "state": "waiting_existing_measurements" if selection["pending_pairs"] else "nothing_to_measure",
                        "jobs": [], "selection": summary}
            chunks = []
            for group in selection["groups"]:
                target = group["keywords"]
                size = args.max_phrases_per_job or len(target)
                for start in range(0, len(target), size):
                    chunks.append((target[start:start + size], group["qualifiers"]))
            ceiling = Decimal(args.max_cost) if args.max_cost is not None else None
            if ceiling is not None and (not ceiling.is_finite() or ceiling < 0):
                raise ValueError("max-cost must be a finite nonnegative amount")
            remaining_ceiling = ceiling
            jobs = []
            for index, (words, group_qualifiers) in enumerate(chunks):
                share = None if ceiling is None else (
                    remaining_ceiling if index == len(chunks) - 1 else
                    min(remaining_ceiling, ceiling * Decimal(len(words) * len(group_qualifiers))
                        / Decimal(selection["missing_pairs"]))
                )
                if share is not None:
                    remaining_ceiling -= share
                job_id = store.create_topvisor_job(
                    args.snapshot_id, group_qualifiers, phrases=words, max_cost=share,
                )
                jobs.append(_topvisor_summary(store.topvisor_job(job_id)))
            if len(jobs) == 1 and args.max_phrases_per_job is None:
                return {**jobs[0], "selection": summary}
            return {"snapshot_id": args.snapshot_id, "jobs": jobs, "selection": summary,
                    "max_cost_total": str(ceiling) if ceiling is not None else None}
        if args.action == "reopen-ambiguous":
            job = store.reopen_ambiguous_topvisor_job(
                args.job_id,
                allow_duplicate_cost_risk=args.allow_duplicate_cost_risk,
            )
            return _topvisor_summary(job)
        runner = _topvisor_runtime(store)
        if args.action == "estimate":
            return _topvisor_summary(runner.estimate(args.job_id))
        if args.action == "submit":
            return _topvisor_summary(runner.submit(args.job_id, max_cost=args.max_cost))
        if args.action == "poll":
            return _topvisor_summary(
                runner.poll(args.job_id, remote_task_id=args.remote_task_id),
            )
        if args.action == "fetch":
            return _topvisor_summary(
                runner.fetch(args.job_id, page_limit=args.page_limit),
            )
        if args.action == "run":
            return _topvisor_summary(
                runner.run(args.job_id, max_cost=args.max_cost, page_limit=args.page_limit),
            )
    raise ValueError("unknown topvisor action")


def _status(args: argparse.Namespace) -> dict[str, object]:
    # No credentials, ownership lock, or schema migration for diagnostics.
    with SnapshotStore(args.store) as store:
        db = store._db
        if args.kind == "topvisor":
            return _topvisor_summary(read_topvisor_job(store, args.id))
        if args.kind == "collect":
            row = db.execute("SELECT * FROM run_states WHERE run_id=?", (args.id,)).fetchone()
            if row is None:
                raise KeyError("unknown run ID")
            latest = db.execute(
                "SELECT id FROM collection_snapshots WHERE run_id=? "
                "ORDER BY captured_at_utc DESC,id DESC LIMIT 1", (args.id,),
            ).fetchone()
            return {"run_id": args.id, "run_state": dict(row),
                    "snapshot_id": latest[0] if latest else None}
        row = db.execute("SELECT id FROM comparison_runs WHERE id=?", (args.id,)).fetchone()
        if row is None:
            raise KeyError("unknown comparison ID")
        latest = db.execute(
            "SELECT id FROM comparison_snapshots WHERE comparison_id=? "
            "ORDER BY captured_at_utc DESC,id DESC LIMIT 1", (args.id,),
        ).fetchone()
        topics = [dict(item) for item in db.execute(
            "SELECT t.position,t.topic,t.run_id,s.outcome,s.semantic_stop,s.pause_reason,s.resumability "
            "FROM comparison_topics t JOIN run_states s ON s.run_id=t.run_id "
            "WHERE t.comparison_id=? ORDER BY t.position", (args.id,),
        )]
        return {"comparison_id": args.id, "snapshot_id": latest[0] if latest else None,
                "topics": topics}


def _export(args: argparse.Namespace) -> dict[str, object]:
    with SnapshotStore(args.store) as store:
        snapshot = read_snapshot(store, args.snapshot_id)
        context = read_report_context(store, snapshot) if args.format == "html" else None
    destination = export_snapshot(snapshot, args.output, format=args.format, report_context=context)
    return {"snapshot_id": args.snapshot_id, "format": args.format,
            "output": str(destination)}


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="run.py")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="check local dependencies and settings without provider requests")
    collect = commands.add_parser("collect", help="start, resume or review one topic")
    actions = collect.add_subparsers(dest="action", required=True)
    for name in ("start", "resume", "extend-budget", "review-batch", "apply-review", "reconsider-association"):
        sub = actions.add_parser(name)
        sub.add_argument("--store", required=True)
        if name == "start":
            sub.add_argument("--topic", required=True)
            sub.add_argument("--family", required=True)
            sub.add_argument("--proposal", required=True, help="validated LLM proposal JSON")
            sub.add_argument("--region", action="append", default=[])
            sub.add_argument("--mask-rules", help="approved deterministic mask rules JSON")
            sub.add_argument("--max-probe-candidates", type=int)
            sub.add_argument("--max-observed-branches", type=int)
        else:
            sub.add_argument("--run-id", required=True)
        if name in {"start", "extend-budget"}:
            sub.add_argument("--max-requests", type=int)
            sub.add_argument("--attempt-budget", action="append", default=[],
                             help="PROVIDER=COUNT; repeat for selected providers")
            sub.add_argument("--max-estimated-wordstat-cost",
                             help="explicit ruble ceiling; required when increasing Wordstat calls")
        if name == "apply-review":
            sub.add_argument("--decisions", required=True)
        if name in {"apply-review", "reconsider-association"}:
            sub.add_argument("--reviewer", required=True)
            sub.add_argument("--review-version", required=True)
        if name == "reconsider-association":
            sub.add_argument("--branch-id", required=True)
            sub.add_argument("--decision", choices=("expand", "uncertain", "defer"), required=True)
            sub.add_argument("--reason", required=True)
    guided = commands.add_parser("guided", help="scout and reviewed collect checkpoints")
    guided_actions = guided.add_subparsers(dest="action", required=True)
    for name in ("scout-create", "scout-run", "scout-report", "approve-directions",
                 "suggest-preview", "checkpoint", "approve-candidates", "wave", "resume-capacity"):
        sub = guided_actions.add_parser(name)
        sub.add_argument("--store", required=True)
        if name != "scout-create":
            sub.add_argument("--run-id", required=True)
        if name in {"scout-create", "approve-directions"}:
            sub.add_argument("--topic", required=True)
            sub.add_argument("--region", action="append", default=[])
            sub.add_argument("--max-estimated-wordstat-cost", required=True)
        if name == "scout-create":
            sub.add_argument("--num-phrases", type=int, default=200)
        if name == "approve-directions":
            sub.add_argument("--profile", choices=(GUIDED_PROFILE_VERSION, PROFILE_VERSION),
                             default=GUIDED_PROFILE_VERSION)
            sub.add_argument("--family", required=True)
            sub.add_argument("--proposal", required=True)
            sub.add_argument("--max-requests", type=int)
            sub.add_argument("--attempt-budget", action="append", default=[])
            sub.add_argument("--mask-rules", help="approved deterministic mask rules JSON")
            sub.add_argument("--max-probe-candidates", type=int)
            sub.add_argument("--max-observed-branches", type=int)
            sub.add_argument("--num-phrases", type=int, default=200)
        if name == "approve-candidates":
            sub.add_argument("--decisions", required=True)
            sub.add_argument("--reviewer", required=True)
            sub.add_argument("--review-version", required=True)
        if name in {"scout-report", "checkpoint", "suggest-preview", "wave"}:
            sub.add_argument("--limit", type=int, default=50)
            sub.add_argument("--offset", type=int, default=0)
    compare = commands.add_parser("compare", help="matched collection of multiple topics")
    actions = compare.add_subparsers(dest="action", required=True)
    for name in ("start", "resume", "guided-attach", "snapshot", "extend-budget"):
        sub = actions.add_parser(name)
        sub.add_argument("--store", required=True)
        if name == "start":
            sub.add_argument("--topics", required=True, help="JSON array of topic/family/proposal")
        elif name == "guided-attach":
            sub.add_argument("--run-id", action="append", required=True,
                             help="repeat for each guided topic in comparison order")
        else:
            sub.add_argument("--comparison-id", required=True)
        if name == "extend-budget":
            sub.add_argument("--max-requests", type=int)
            sub.add_argument("--attempt-budget", action="append", default=[],
                             help="PROVIDER=COUNT; same ceiling for every topic")
            sub.add_argument("--max-estimated-wordstat-cost",
                             help="explicit ruble ceiling per topic; required for more Wordstat calls")
    topvisor = commands.add_parser("topvisor", help="isolated bulk measurement over saved snapshots")
    tv_actions = topvisor.add_subparsers(dest="action", required=True)
    tv_regions = tv_actions.add_parser("regions", help="read provider region directory")
    tv_regions.add_argument("--search", required=True)
    tv_regions.add_argument("--country-code")
    tv_regions.add_argument("--only-countries", action="store_true")
    tv_create = tv_actions.add_parser("create")
    tv_create.add_argument("--store", required=True)
    tv_create.add_argument("--snapshot-id", required=True)
    tv_create.add_argument("--qualifier", dest="qualifiers", action="append",
                           help="REGION:SEARCHER:TYPE, e.g. 213:0:1")
    tv_create.add_argument("--qualifiers-file")
    tv_create.add_argument("--phrases-file")
    tv_create.add_argument("--max-phrases-per-job", type=int)
    tv_create.add_argument("--max-cost")
    for name in ("estimate", "submit", "poll", "fetch", "run", "reopen-ambiguous"):
        sub = tv_actions.add_parser(name)
        sub.add_argument("--store", required=True)
        sub.add_argument("--job-id", required=True)
        if name in {"submit", "run"}:
            sub.add_argument("--max-cost")
        if name == "poll":
            sub.add_argument("--remote-task-id", type=int)
        if name in {"fetch", "run"}:
            sub.add_argument("--page-limit", type=int, default=1000)
        if name == "reopen-ambiguous":
            sub.add_argument("--allow-duplicate-cost-risk", action="store_true")
    status = commands.add_parser("status", help="read current run state without providers")
    status.add_argument("--store", required=True)
    status.add_argument("--kind", choices=("collect", "compare", "topvisor"), required=True)
    status.add_argument("--id", required=True)
    export = commands.add_parser("export", help="verify and export an exact snapshot")
    export.add_argument("--store", required=True)
    export.add_argument("--snapshot-id", required=True)
    export.add_argument("--format", choices=("json", "csv", "html"), required=True)
    export.add_argument("--output", required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        for name in ("store", "output"):
            value = getattr(args, name, None)
            if value and Path(value).resolve().is_relative_to(Path(__file__).resolve().parents[1]):
                raise ValueError(f"{name} must be outside the installed skill folder")
        if args.command == "doctor":
            result = _doctor()
        elif args.command == "collect":
            result = _collect(args)
        elif args.command == "guided":
            result = _guided(args)
        elif args.command == "compare":
            result = _compare(args)
        elif args.command == "topvisor":
            result = _topvisor(args)
        elif args.command == "status":
            result = _status(args)
        else:
            result = _export(args)
        # ASCII JSON keeps stdout machine-readable across Windows console code pages.
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0
    except (ValueError, InvalidOperation, KeyError, FileNotFoundError, StoreBusyError,
            ArtifactIntegrityError, TransportFailure, ParserFailure) as error:
        # Never echo environment values, request headers or raw provider bodies.
        print(json.dumps({"error": type(error).__name__, "message": str(error)},
                         ensure_ascii=True), file=sys.stderr)
        return 2
    except Exception:
        print(json.dumps({"error": "internal_error",
                          "message": "operation failed; inspect the local store safely"}),
              file=sys.stderr)
        return 1


def _doctor() -> dict[str, object]:
    """Report readiness and numeric configuration; never reveal account identifiers."""
    result: dict[str, object] = {"python": ".".join(map(str, sys.version_info[:3])),
                               "python_supported": sys.version_info >= (3, 11),
                               "external_requests": 0}
    try:
        credentials = GetTopCredentials.from_environment()
        result["wordstat"] = {"ready": True, "auth_type": credentials.auth_type}
    except ValueError as error:
        result["wordstat"] = {"ready": False, "reason": str(error)}
    try:
        configured = capacity_buckets()["yandex_wordstat"]
        result["capacity"] = {"rps": configured.rps, "window_limit": configured.window_limit,
                              "window_seconds": configured.window_seconds}
    except ValueError as error:
        result["capacity"] = {"ready": False, "reason": str(error)}
    try:
        tariff = configured_tariff()
        result["tariff"] = {"ready": True, "price_per_1000": str(tariff.price_per_1000),
                            "currency": tariff.currency, "checked_on": tariff.checked_on.isoformat(),
                            "source_url": tariff.source_url}
    except ValueError as error:
        result["tariff"] = {"ready": False, "reason": str(error)}
    result["topvisor"] = {"ready": bool(os.environ.get("TOPVISOR_API_KEY")
                                        and os.environ.get("TOPVISOR_USER_ID")),
                           "required_for_collection": False}
    return result
