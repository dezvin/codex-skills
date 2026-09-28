"""Durable human checkpoints around the existing one-topic collector.

This layer does not choose semantic relevance. It keeps acquisition and branch
approval separate, and reuses the same paid GetTop work after a restart.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Mapping, Sequence

from .collect import CollectPlan, Collector, PROVIDERS
from .execution import CapacityUnavailable, Executor, OutcomeKind, RetryPolicy
from .identity import fingerprint
from .models import canonical_json
from .storage import ArtifactIntegrityError, _now
from .wordstat_gettop import GetTopTariff, PARSER_VERSION, parse_gettop


class GuidedCollector:
    """One scout, two initial checkpoints, then one reviewed tranche per wave."""

    def __init__(self, collector: Collector):
        self.collector = collector
        self.db = collector.db

    def _row(self, run_id: str) -> dict[str, object]:
        row = self.db.execute(
            "SELECT * FROM guided_collection_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if row is None:
            raise KeyError(run_id)
        return dict(row)

    def _phase(self, run_id: str, phase: str, checkpoint: list[dict[str, object]] | None = None) -> None:
        with self.db:
            self.db.execute(
                "UPDATE guided_collection_runs SET phase=?,checkpoint_json=?,updated_at_utc=? "
                "WHERE run_id=?", (phase, canonical_json(checkpoint) if checkpoint is not None else None,
                                 _now(), run_id),
            )

    def create_scout(
        self, topic: str, *, num_phrases: int, regions: tuple[str, ...],
        tariff: GetTopTariff, max_estimated_cost: Decimal,
    ) -> str:
        """Persist one paid-call intent; a separate command dispatches it once."""
        ceiling = Decimal(str(max_estimated_cost))
        if tariff.currency != "RUB":
            raise ValueError("guided Wordstat ceiling must use RUB")
        if not ceiling.is_finite() or ceiling < tariff.estimate(1):
            raise ValueError("scout monetary ceiling is below one checked GetTop estimate")
        request = self.collector.gettop.semantic_request(
            topic, num_phrases=num_phrases, regions=regions,
        )
        run_id = self.collector.store.create_run()
        bucket = self.collector.buckets["yandex_wordstat"].id
        self.collector.core.configure_run_budget(run_id, bucket, 1)
        request_id = fingerprint(request)
        work_id = self.collector.core.create_work(run_id, request_id, request, bucket)
        with self.db:
            self.db.execute(
                "INSERT INTO guided_collection_runs VALUES (?,?,?,?,?,?,?)",
                (run_id, "scout_pending", request_id, work_id,
                 canonical_json({"request": request.descriptor(), "tariff": {
                     "price_per_1000": str(tariff.price_per_1000),
                     "currency": tariff.currency, "checked_on": tariff.checked_on.isoformat(),
                     "source_url": tariff.source_url,
                 }, "max_estimated_cost": str(ceiling)}), None, _now()),
            )
        return run_id

    def run_scout(self, run_id: str) -> dict[str, object]:
        row = self._row(run_id)
        recovery = self.collector.core.recover(self.collector._parser)
        if recovery.integrity_errors:
            raise ArtifactIntegrityError("raw artifact integrity check failed")
        if row["phase"] == "awaiting_directions":
            return self.scout_report(run_id, limit=30)
        if row["phase"] != "scout_pending":
            raise ValueError("scout is not pending; an uncertain paid call is never replayed")
        work = self.collector.core.work(str(row["scout_work_id"]))
        if work["state"] == "completed":
            self._phase(run_id, "awaiting_directions")
            return self.scout_report(run_id, limit=30)
        if work["state"] in {"failed", "ambiguous", "dispatching", "reserved"}:
            self._phase(run_id, "scout_blocked")
            return self.scout_report(run_id, limit=30)
        try:
            outcome = Executor(self.collector.core, policy=RetryPolicy(
                max_attempts=1, max_total_wait=0,
            )).execute(
                str(row["scout_work_id"]), self.collector.gettop.send,
                parse_gettop, parser_version=PARSER_VERSION,
                redactions=self.collector.gettop.credentials.redactions,
            )
        except CapacityUnavailable:
            return self.scout_report(run_id, limit=30)
        self._phase(run_id, "awaiting_directions" if outcome in {
            OutcomeKind.SUCCESS_WITH_DATA, OutcomeKind.SUCCESS_VALID_EMPTY,
        } else "scout_blocked")
        return self.scout_report(run_id, limit=30)

    def scout_report(self, run_id: str, *, limit: int | None = None,
                     offset: int = 0) -> dict[str, object]:
        if (limit is not None and (isinstance(limit, bool) or not isinstance(limit, int)
                                   or limit < 1)) or isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("report limit must be positive and offset nonnegative")
        row = self._row(run_id)
        work_id = str(row["scout_work_id"])
        work = self.collector.core.work(work_id)
        context = json.loads(str(row["scout_context_json"]))
        result: dict[str, object] = {
            "run_id": run_id, "phase": row["phase"], "work_state": work["state"],
            "request": context["request"], "estimated_cost_ceiling": context["max_estimated_cost"],
            "attempts": [
                {"outcome": item["outcome_kind"], "http_status": item["http_status"]}
                for item in self.collector.core.attempts(work_id)
            ],
            "observations": [], "request_measurements": [],
            "total_observations": 0, "offset": offset, "has_more": False,
        }
        if work["state"] == "completed":
            batch_id = self.collector._successful_batch(work_id, PARSER_VERSION)
            all_observations = [
                {"phrase": item["raw_phrase"], "channel": item["channel"],
                 "rank": item["rank"], "measurements": [
                     {"kind": m["kind"], "value": m["value"]}
                     for m in self.collector.store.measurements(batch_id)
                     if m["observation_id"] == item["id"]
                 ]} for item in self.collector.store.observations(batch_id)
            ]
            result["total_observations"] = len(all_observations)
            result["offset"] = offset
            result["observations"] = all_observations[offset:(None if limit is None else offset + limit)]
            result["has_more"] = offset + len(result["observations"]) < len(all_observations)
            result["request_measurements"] = [
                {"kind": m["kind"], "value": m["value"]}
                for m in self.collector.store.measurements(batch_id)
                if m["observation_id"] is None
            ]
        return result

    def approve_directions(self, run_id: str, plan: CollectPlan) -> dict[str, object]:
        row = self._row(run_id)
        if row["phase"] not in {"awaiting_directions", "preview_ready"}:
            raise ValueError("directions cannot be approved at this checkpoint")
        scout = json.loads(str(row["scout_context_json"]))
        expected = self.collector.gettop.semantic_request(
            plan.topic, num_phrases=plan.wordstat_num_phrases,
            regions=plan.wordstat_regions, devices=plan.wordstat_devices,
        )
        if (fingerprint(expected) != row["scout_request_fingerprint"]
                or expected.descriptor() != scout["request"]
                or plan.bucket_ids["yandex_wordstat"] !=
                self.collector.core.work(str(row["scout_work_id"]))["bucket_id"]):
            raise ValueError("approved plan must reuse the exact scout request and capacity bucket")
        if self.collector.core.work(str(row["scout_work_id"]))["state"] != "completed":
            raise ValueError("a successful scout is required before approving directions")
        if not plan.association_review_required:
            raise ValueError("guided collection requires association review")
        prior_estimate = Decimal(scout["tariff"]["price_per_1000"]) / Decimal(1000)
        full_estimate = prior_estimate + plan.tariff.estimate(
            max(0, plan.attempt_budgets["yandex_wordstat"] - 1)
        )
        if plan.tariff.currency != "RUB" or full_estimate > plan.max_estimated_wordstat_cost:
            raise ValueError("approved plan does not cover the scout and remaining Wordstat estimate")
        if row["phase"] == "awaiting_directions":
            self.collector.attach_existing(run_id, plan)
            adopted = self.db.execute(
                "SELECT 1 FROM semantic_request_results WHERE run_id=? AND request_fingerprint=?",
                (run_id, row["scout_request_fingerprint"]),
            ).fetchone()
            if not adopted:
                number, selected = self.collector.frontier.start_tranche(
                    run_id, plan.frontier_policy,
                    available_attempts={provider: (1 if provider == "yandex_wordstat" else 0)
                                        for provider in PROVIDERS},
                )
                if number is None or len(selected) != 1 or selected[0]["request_fingerprint"] != row["scout_request_fingerprint"]:
                    raise ValueError("scout could not be adopted as the first semantic work item")
                self.collector._execute_selected(run_id, selected[0], plan)
                self.collector.frontier.review_tranche(run_id, number)
            else:
                active = self.db.execute(
                    "SELECT number FROM semantic_tranches WHERE run_id=? AND state='active' "
                    "ORDER BY number LIMIT 1", (run_id,),
                ).fetchone()
                if active is not None:
                    self.collector.frontier.review_tranche(run_id, int(active[0]))
            self._phase(run_id, "preview_ready")
        else:
            # Replaying approval must validate the exact saved plan, not merely
            # the same topic and GetTop request.
            self.collector._collection(run_id, plan)
        return {"run_id": run_id, "phase": self._row(run_id)["phase"],
                "scout_reused": True, "wordstat_attempts": len(self.collector.core.attempts(str(row["scout_work_id"]))) }

    def _candidates(self, run_id: str) -> list[dict[str, object]]:
        rows = self.db.execute(
            "SELECT b.id,b.label,b.family,b.transition_kind,b.origin_ref,"
            "(SELECT COUNT(*) FROM semantic_branch_evidence e WHERE e.branch_id=b.id) AS evidence_count "
            "FROM semantic_branches b WHERE b.run_id=? AND b.state='proposed' "
            "ORDER BY b.created_at_utc,b.id", (run_id,),
        ).fetchall()
        result = []
        for row in rows:
            origin = self.collector.store.provenance(int(row["origin_ref"]))
            parents = [item[0] for item in self.db.execute(
                "SELECT p.label FROM semantic_branch_parents x JOIN semantic_branches p "
                "ON p.id=x.parent_id WHERE x.branch_id=? ORDER BY p.id", (row["id"],),
            )]
            item = {"branch_id": row["id"], "phrase": row["label"],
                    "family": row["family"], "origin": row["transition_kind"],
                    "channel": origin["channel"], "parents": parents,
                    "evidence_count": row["evidence_count"]}
            item["input_sha256"] = hashlib.sha256(canonical_json(item).encode("utf-8")).hexdigest()
            result.append(item)
        return result

    def checkpoint(self, run_id: str, *, limit: int | None = None,
                   offset: int = 0) -> dict[str, object]:
        if (limit is not None and (isinstance(limit, bool) or not isinstance(limit, int)
                                   or limit < 1)) or isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("checkpoint limit must be positive and offset nonnegative")
        row = self._row(run_id)
        saved = json.loads(str(row["checkpoint_json"])) if row["checkpoint_json"] else []
        page = saved[offset:(None if limit is None else offset + limit)]
        return {"run_id": run_id, "phase": row["phase"], "candidate_count": len(saved),
                "offset": offset, "has_more": offset + len(page) < len(saved),
                "candidates": page}

    def suggest_preview(self, run_id: str, plan: CollectPlan) -> dict[str, object]:
        if self._row(run_id)["phase"] != "preview_ready":
            raise ValueError("Suggest preview requires approved directions")
        self.collector._collection(run_id, plan)
        recovery = self.collector.core.recover(self.collector._parser)
        if recovery.integrity_errors:
            raise ArtifactIntegrityError("raw artifact integrity check failed")
        while self.collector.frontier.status(run_id)["semantic_stop"] == "continuation_possible":
            self.collector._postpone_disabled_eligible(run_id)
            available = self.collector._available_attempts(run_id, plan)
            available["yandex_wordstat"] = 0
            number, selected = self.collector.frontier.start_tranche(
                run_id, plan.frontier_policy, available_attempts=available,
            )
            if number is None:
                break
            if any(json.loads(str(item["descriptor_json"]))["provider"] == "yandex_wordstat"
                   for item in selected):
                raise ValueError("Wordstat was selected during Suggest-only preview")
            for item in selected:
                self.collector._execute_selected(run_id, item, plan)
            self.collector._postpone_disabled_eligible(run_id)
            self.collector.frontier.review_tranche(run_id, number)
        # Balance branch slots across all preview sources. Materializing after
        # the scout alone could let its long result list crowd out Suggest.
        self.collector._expand_observed(run_id, plan, hold_new=True)
        candidates = self._candidates(run_id)
        self._phase(run_id, "awaiting_suggest_review", candidates)
        self.collector.core.set_run_state(
            run_id, outcome="degraded_success", semantic_stop=self.collector.frontier.status(run_id)["semantic_stop"],
            pause_reason="awaiting_suggest_review", resumability="requires_operator_decision",
        )
        return {"snapshot": self.collector.snapshot(run_id, plan), **self.checkpoint(run_id)}

    def approve_candidates(
        self, run_id: str, plan: CollectPlan, decisions: Sequence[Mapping[str, object]],
        *, reviewer: str, review_version: str,
    ) -> dict[str, object]:
        row = self._row(run_id)
        if row["phase"] not in {"awaiting_suggest_review", "awaiting_wave_review"}:
            raise ValueError("no branch checkpoint is awaiting approval")
        self.collector._collection(run_id, plan)
        saved = json.loads(str(row["checkpoint_json"]))
        expected = {item["branch_id"]: item for item in saved}
        if (len(decisions) != len(expected) or not all(isinstance(item, Mapping) for item in decisions)
                or {item.get("branch_id") for item in decisions} != set(expected)):
            raise ValueError("decisions must cover the complete saved candidate batch")
        if not reviewer.strip() or not review_version.strip():
            raise ValueError("reviewer and review version are required")
        for item in decisions:
            if (set(item) != {"branch_id", "input_sha256", "decision", "reason"}
                    or item["input_sha256"] != expected[item["branch_id"]]["input_sha256"]
                    or item["decision"] not in {"expand", "defer"}
                    or not isinstance(item["reason"], str) or not item["reason"].strip()):
                raise ValueError("invalid or stale candidate decision")
            previous = self.db.execute(
                "SELECT decision,reason,checkpoint_sha256 FROM guided_branch_reviews "
                "WHERE run_id=? AND branch_id=?", (run_id, item["branch_id"]),
            ).fetchone()
            if previous is not None and (
                previous["decision"] != item["decision"] or previous["reason"] != item["reason"]
                or previous["checkpoint_sha256"] != item["input_sha256"]
            ):
                raise ValueError("a recorded branch decision cannot be silently rewritten")
        already_expanded = {item[0] for item in self.db.execute(
            "SELECT branch_id FROM guided_branch_reviews WHERE run_id=? AND decision='expand'",
            (run_id,),
        )}
        expanding_now = {item["branch_id"] for item in decisions
                         if item["decision"] == "expand"}
        if len(already_expanded | expanding_now) > plan.max_observed_branches:
            raise ValueError("approved branch expansion exceeds this run's branch limit")
        association_decisions = []
        pending_associations = {item["branch_id"]: item for item in
                                self.collector.association_review_batch(run_id, plan)}
        for item in decisions:
            if item["branch_id"] in pending_associations:
                association_decisions.append({
                    "branch_id": item["branch_id"],
                    "input_sha256": pending_associations[item["branch_id"]]["input_sha256"],
                    "decision": item["decision"], "reason": item["reason"],
                })
        if association_decisions:
            self.collector.apply_association_reviews(
                run_id, plan, association_decisions, reviewer=reviewer,
                review_version=review_version,
            )
        for item in decisions:
            branch = self.collector.frontier.branch(str(item["branch_id"]))
            if branch["state"] == "proposed":
                self.collector.frontier.set_branch_state(
                    str(item["branch_id"]),
                    "eligible" if item["decision"] == "expand" else "postponed",
                    reason="guided_review_deferred" if item["decision"] == "defer" else None,
                )
            elif branch["state"] != ("eligible" if item["decision"] == "expand" else "postponed"):
                raise ValueError("candidate state changed since checkpoint")
            with self.db:
                self.db.execute(
                    "INSERT OR IGNORE INTO guided_branch_reviews VALUES (?,?,?,?,?,?)",
                    (run_id, item["branch_id"], item["decision"], item["reason"],
                     item["input_sha256"], _now()),
                )
        self._phase(run_id, "wave_ready")
        self.collector.core.set_run_state(
            run_id, outcome="incomplete", semantic_stop=self.collector.frontier.status(run_id)["semantic_stop"],
            pause_reason=None, resumability="resumable_automatically",
        )
        return {"run_id": run_id, "phase": "wave_ready", "reviewed": len(decisions)}

    def resume_capacity(self, run_id: str, plan: CollectPlan) -> dict[str, object]:
        """Prepare capacity-paused work; perform no I/O and bypass no review.

        Auth errors, ordinary failures, budget stops and ambiguous paid work
        remain outside this recovery action. A subsequent wave checks current
        capacity again before dispatching, so early resumption is safe.
        """
        if self._row(run_id)["phase"] != "wave_ready":
            raise ValueError("candidate checkpoint needs review before capacity resumption")
        self.collector._collection(run_id, plan)
        recovery = self.collector.core.recover(self.collector._parser)
        if recovery.integrity_errors:
            raise ArtifactIntegrityError("raw artifact integrity check failed")
        rows = self.db.execute(
            "SELECT request_fingerprint,MAX(tranche_number) AS tranche_number "
            "FROM semantic_opportunities WHERE run_id=? AND state='postponed' "
            "AND outcome='capacity_blocked' GROUP BY request_fingerprint "
            "ORDER BY tranche_number,request_fingerprint", (run_id,),
        ).fetchall()
        resumed = []
        for row in rows:
            if (row["tranche_number"] is None and
                    self.collector.frontier.status(run_id)["semantic_stop"] != "continuation_possible"):
                continue
            self.collector.retry_postponed(run_id, row["request_fingerprint"], plan)
            resumed.append(row["request_fingerprint"])
        return {"run_id": run_id, "phase": "wave_ready", "resumed_capacity_work": resumed,
                "next_action": "guided wave"}

    def run_wave(self, run_id: str, plan: CollectPlan) -> dict[str, object]:
        if self._row(run_id)["phase"] != "wave_ready":
            raise ValueError("the previous candidate checkpoint needs review")
        self.collector._collection(run_id, plan)
        recovery = self.collector.core.recover(self.collector._parser)
        if recovery.integrity_errors:
            raise ArtifactIntegrityError("raw artifact integrity check failed")
        # A crash after recording a tranche but before persisting the gate must
        # not release the next wave of provider calls.
        active = self.db.execute(
            "SELECT 1 FROM semantic_tranches WHERE run_id=? AND state='active' LIMIT 1",
            (run_id,),
        ).fetchone()
        existing_candidates = self._candidates(run_id)
        if existing_candidates and active is None:
            self._phase(run_id, "awaiting_wave_review", existing_candidates)
            self.collector.core.set_run_state(
                run_id, outcome="degraded_success",
                semantic_stop=self.collector.frontier.status(run_id)["semantic_stop"],
                pause_reason="awaiting_wave_review", resumability="requires_operator_decision",
            )
            return {"snapshot": self.collector.snapshot(run_id, plan), **self.checkpoint(run_id)}
        self.collector._expand_observed(run_id, plan, hold_new=True)
        self.collector._postpone_disabled_eligible(run_id)
        exhausted = self.db.execute(
            "SELECT b.id FROM semantic_branches b WHERE b.run_id=? "
            "AND b.state IN ('eligible','active') "
            "AND EXISTS (SELECT 1 FROM semantic_opportunities o WHERE o.branch_id=b.id) "
            "AND NOT EXISTS (SELECT 1 FROM semantic_opportunities o WHERE o.branch_id=b.id "
            "AND o.state IN ('eligible','selected','postponed'))", (run_id,),
        ).fetchall()
        for branch in exhausted:
            self.collector.frontier.set_branch_state(
                branch["id"], "terminal", reason="known_opportunities_exhausted",
            )
        if self.collector.frontier.status(run_id)["semantic_stop"] != "continuation_possible":
            return {"snapshot": self.collector.snapshot(run_id, plan), **self.checkpoint(run_id)}
        number, selected = self.collector.frontier.start_tranche(
            run_id, plan.frontier_policy,
            available_attempts=self.collector._available_attempts(run_id, plan),
        )
        if number is None:
            eligible = {item[0] for item in self.db.execute(
                "SELECT DISTINCT o.provider FROM semantic_opportunities o "
                "JOIN semantic_branches b ON b.id=o.branch_id "
                "WHERE o.run_id=? AND o.state='eligible' AND b.state IN ('eligible','active')",
                (run_id,),
            )}
            remaining = self.collector._available_attempts(run_id, plan)
            if eligible and all(remaining.get(provider, 0) == 0 for provider in eligible):
                self.collector.core.set_run_state(
                    run_id, outcome="degraded_success", semantic_stop="continuation_possible",
                    pause_reason="run_budget_exhausted", resumability="requires_operator_decision",
                )
            return {"snapshot": self.collector.snapshot(run_id, plan), **self.checkpoint(run_id)}
        for item in selected:
            self.collector._execute_selected(run_id, item, plan)
        self.collector._expand_observed(run_id, plan, hold_new=True)
        self.collector._postpone_disabled_eligible(run_id)
        self.collector.frontier.review_tranche(run_id, number)
        candidates = self._candidates(run_id)
        if candidates:
            self._phase(run_id, "awaiting_wave_review", candidates)
            self.collector.core.set_run_state(
                run_id, outcome="degraded_success",
                semantic_stop=self.collector.frontier.status(run_id)["semantic_stop"],
                pause_reason="awaiting_wave_review", resumability="requires_operator_decision",
            )
        return {"snapshot": self.collector.snapshot(run_id, plan), **self.checkpoint(run_id)}
