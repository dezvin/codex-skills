"""Durable, bounded semantic frontier without provider I/O or collection loop.

This is the approved branch/opportunity baseline. Numeric policy values must be
supplied by the caller; no calibration result or production preset is implied.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from .identity import fingerprint
from .models import SemanticRequest, canonical_json
from .seed_probes import ProbeFamily, SeedFamily
from .storage import DataStore, _now


class FrontierStateError(ValueError):
    """A transition would erase provenance or misstate unresolved work."""


class BranchState(StrEnum):
    PROPOSED = "proposed"
    ELIGIBLE = "eligible"
    ACTIVE = "active"
    POSTPONED = "postponed"
    TERMINAL = "terminal"


class OpportunityState(StrEnum):
    ELIGIBLE = "eligible"
    SELECTED = "selected"
    POSTPONED = "postponed"
    COMPLETED = "completed"
    INVALID = "invalid"


_BRANCH_TRANSITIONS = {
    BranchState.PROPOSED: {BranchState.ELIGIBLE, BranchState.POSTPONED, BranchState.TERMINAL},
    BranchState.ELIGIBLE: {BranchState.ACTIVE, BranchState.POSTPONED, BranchState.TERMINAL},
    BranchState.ACTIVE: {BranchState.ELIGIBLE, BranchState.POSTPONED, BranchState.TERMINAL},
    BranchState.POSTPONED: {BranchState.ELIGIBLE, BranchState.TERMINAL},
    BranchState.TERMINAL: set(),
}

_OBSERVED_TRANSITIONS = {
    "observed_modifier", "observed_entity", "observed_relation", "wordstat_association",
}
_TRANSITIONS = _OBSERVED_TRANSITIONS | {
    "initial_seed_family", "deterministic_probe_family", "validated_llm_family",
    "split", "merge",
}


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    return value


def _positive(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _nonnegative(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


@dataclass(frozen=True)
class FrontierPolicy:
    """All values are explicit trial inputs, not production defaults."""

    tranche_size: int
    hard_max_requests: int
    breadth_reserve: int
    per_branch_cap: int
    weak_max_new_unique: int
    weak_min_rediscovered: int
    weak_max_newly_supported_branches: int
    weak_tranches_to_stop: int
    version: str = "staged-breadth-depth-v1-provisional"

    def __post_init__(self) -> None:
        for name in ("tranche_size", "hard_max_requests", "breadth_reserve",
                     "per_branch_cap", "weak_tranches_to_stop"):
            _positive(name, getattr(self, name))
        for name in ("weak_max_new_unique", "weak_min_rediscovered",
                     "weak_max_newly_supported_branches"):
            _nonnegative(name, getattr(self, name))
        if self.breadth_reserve > self.tranche_size:
            raise ValueError("breadth reserve exceeds tranche size")
        _text("policy version", self.version)

    def descriptor(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


class SemanticFrontier:
    """One local writer; branch history and selected semantic work survive restart."""

    def __init__(self, store: DataStore):
        self.store = store
        self.db = store._db

    def _run(self, run_id: str) -> None:
        if self.db.execute("SELECT 1 FROM runs WHERE id=?", (run_id,)).fetchone() is None:
            raise KeyError(run_id)

    def _observation(self, observation_id: int):
        row = self.db.execute(
            "SELECT o.id,o.channel,o.raw_phrase,o.canonical_id,a.request_fingerprint "
            "FROM observations o JOIN parse_batches b ON b.id=o.batch_id "
            "JOIN raw_artifacts a ON a.id=b.artifact_id WHERE o.id=?",
            (observation_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown external observation: {observation_id}")
        return row

    def _branch(self, branch_id: str, run_id: str | None = None):
        row = self.db.execute("SELECT * FROM semantic_branches WHERE id=?", (branch_id,)).fetchone()
        if row is None or (run_id is not None and row["run_id"] != run_id):
            raise KeyError(f"branch does not belong to run: {branch_id}")
        return row

    def _check_parent_cycle(self, branch_id: str, parent_id: str) -> None:
        if branch_id == parent_id or self.db.execute(
            "WITH RECURSIVE ancestors(id) AS ("
            "SELECT ? UNION SELECT p.parent_id FROM semantic_branch_parents p "
            "JOIN ancestors a ON p.branch_id=a.id) "
            "SELECT 1 FROM ancestors WHERE id=? LIMIT 1",
            (parent_id, branch_id),
        ).fetchone():
            raise FrontierStateError("branch parent relationship would form a cycle")

    def create_branch(
        self, run_id: str, creation_key: str, *, transition_kind: str,
        origin_kind: str, origin_ref: str, family: SeedFamily | str,
        label: str, reason: str, parents: tuple[str, ...] = (),
        evidence_ids: tuple[int, ...] = (),
    ) -> str:
        """Create a stable typed branch; repeated creation adds parents/evidence."""
        self._run(run_id)
        _text("creation_key", creation_key)
        _text("origin_ref", origin_ref)
        _text("label", label)
        _text("reason", reason)
        if transition_kind not in _TRANSITIONS:
            raise ValueError("unknown typed branch transition")
        family = SeedFamily(family)
        parent_ids = tuple(dict.fromkeys(parents))
        for parent_id in parent_ids:
            self._branch(parent_id, run_id)
        if transition_kind == "initial_seed_family":
            if origin_kind != "topic":
                raise ValueError("initial family must originate from a topic")
        elif transition_kind == "deterministic_probe_family":
            if origin_kind != "probe_generation":
                raise ValueError("deterministic branch requires a saved probe generation")
            batch_id, separator, index_text = origin_ref.partition(":")
            if not separator:
                raise ValueError("probe origin must identify one generated probe")
            batch = self.store.load_seed_batch(batch_id)
            if batch["run_id"] != run_id or batch["kind"] != "probe_generation":
                raise ValueError("probe generation belongs to another run or kind")
            try:
                generated = batch["payload"]["result"]["probes"][int(index_text)]
            except (ValueError, IndexError):
                raise ValueError("invalid generated probe index") from None
            if int(index_text) < 0:
                raise ValueError("invalid generated probe index")
            deterministic_rules = {
                rule["id"] for rule in batch["payload"]["plan"]["rules"]
                if rule["origin"] == "deterministic"
            }
            if not any(origin["rule_id"] in deterministic_rules
                       and origin["seed_kind"] != "llm_hypothesis"
                       for origin in generated["origins"]):
                raise ValueError("model-only proposal cannot create a durable branch")
        elif transition_kind in _OBSERVED_TRANSITIONS:
            if origin_kind != "observation":
                raise ValueError("observed transition requires an observation")
            try:
                observation_id = int(origin_ref)
            except ValueError:
                raise ValueError("observation origin must be an ID") from None
            source = self._observation(observation_id)
            if transition_kind == "wordstat_association" and source["channel"] not in {"associations", "gettop.associations"}:
                raise ValueError("association branch requires an association observation")
            if transition_kind == "wordstat_association":
                descriptor = self.db.execute(
                    "SELECT descriptor_json FROM semantic_requests WHERE fingerprint=?",
                    (source["request_fingerprint"],),
                ).fetchone()[0]
                if json.loads(descriptor)["provider"] != "yandex_wordstat":
                    raise ValueError("association branch requires a Wordstat observation")
            evidence_ids = tuple(dict.fromkeys((*evidence_ids, observation_id)))
        elif transition_kind == "validated_llm_family":
            if origin_kind != "llm_proposal" or not evidence_ids:
                raise ValueError("LLM family requires a saved proposal and external evidence")
            batch = self.store.load_seed_batch(origin_ref)
            if batch["run_id"] != run_id or batch["kind"] != "llm_proposal":
                raise ValueError("LLM proposal belongs to another run or kind")
        else:
            if origin_kind != "branch" or len(parent_ids) < (2 if transition_kind == "merge" else 1):
                raise ValueError("split/merge needs historical parent branches")
            if origin_ref not in parent_ids:
                raise ValueError("split/merge origin must name a recorded parent")
        for observation_id in evidence_ids:
            self._observation(observation_id)
        branch_id = hashlib.sha256(canonical_json([run_id, creation_key]).encode("utf-8")).hexdigest()
        immutable = (run_id, creation_key, transition_kind, origin_kind, origin_ref,
                     family.value, label, reason)
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO semantic_branches "
                "(id,run_id,creation_key,transition_kind,origin_kind,origin_ref,family,label,"
                "creation_reason,state,created_at_utc) VALUES (?,?,?,?,?,?,?,?,?,'proposed',?)",
                (branch_id, *immutable, _now()),
            )
            stored = self._branch(branch_id, run_id)
            actual = tuple(stored[key] for key in (
                "run_id", "creation_key", "transition_kind", "origin_kind", "origin_ref",
                "family", "label", "creation_reason",
            ))
            if actual != immutable:
                raise FrontierStateError("creation key already belongs to a different branch event")
            for parent_id in parent_ids:
                self._check_parent_cycle(branch_id, parent_id)
                relation = transition_kind if transition_kind in {"split", "merge"} else "derived_from"
                self.db.execute(
                    "INSERT OR IGNORE INTO semantic_branch_parents VALUES (?,?,?)",
                    (branch_id, parent_id, relation),
                )
            for observation_id in evidence_ids:
                self.db.execute(
                    "INSERT OR IGNORE INTO semantic_branch_evidence VALUES (?,?,?)",
                    (branch_id, observation_id, "creation_evidence"),
                )
        return branch_id

    def add_parent(self, branch_id: str, parent_id: str, *, relation: str = "derived_from") -> None:
        branch = self._branch(branch_id)
        self._branch(parent_id, branch["run_id"])
        if relation not in {"derived_from", "split", "merge"}:
            raise ValueError("invalid historical branch link")
        self._check_parent_cycle(branch_id, parent_id)
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO semantic_branch_parents VALUES (?,?,?)",
                (branch_id, parent_id, relation),
            )

    def add_evidence(self, branch_id: str, observation_id: int, *, role: str) -> None:
        self._branch(branch_id)
        self._observation(observation_id)
        _text("evidence role", role)
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO semantic_branch_evidence VALUES (?,?,?)",
                (branch_id, observation_id, role),
            )

    def branch(self, branch_id: str) -> dict[str, object]:
        row = self._branch(branch_id)
        result = dict(row)
        result["parents"] = [dict(item) for item in self.db.execute(
            "SELECT parent_id,relation FROM semantic_branch_parents WHERE branch_id=? ORDER BY parent_id",
            (branch_id,),
        )]
        result["evidence"] = [dict(item) for item in self.db.execute(
            "SELECT observation_id,role FROM semantic_branch_evidence "
            "WHERE branch_id=? ORDER BY observation_id,role", (branch_id,),
        )]
        return result

    def set_branch_state(
        self, branch_id: str, state: BranchState | str, *, reason: str | None = None,
    ) -> None:
        current = BranchState(self._branch(branch_id)["state"])
        target = BranchState(state)
        if target not in _BRANCH_TRANSITIONS[current]:
            raise FrontierStateError(f"invalid branch transition: {current} -> {target}")
        if target in {BranchState.POSTPONED, BranchState.TERMINAL}:
            _text("state reason", reason)
        elif reason is not None:
            raise ValueError("reason belongs only to postponed or terminal branch")
        with self.db:
            if target == BranchState.TERMINAL:
                outstanding = self.db.execute(
                    "SELECT 1 FROM semantic_opportunities WHERE branch_id=? "
                    "AND state IN ('selected','postponed') LIMIT 1", (branch_id,),
                ).fetchone()
                if outstanding:
                    raise FrontierStateError("resolve selected or postponed work before terminal branch")
                self.db.execute(
                    "UPDATE semantic_opportunities SET state='invalid',state_reason=? "
                    "WHERE branch_id=? AND state='eligible'", (reason, branch_id),
                )
            self.db.execute(
                "UPDATE semantic_branches SET state=?,state_reason=? WHERE id=?",
                (target.value, reason, branch_id),
            )

    def add_opportunity(
        self, run_id: str, branch_id: str, probe_family: ProbeFamily | str,
        request: SemanticRequest,
    ) -> str:
        branch = self._branch(branch_id, run_id)
        if branch["state"] == BranchState.TERMINAL:
            raise FrontierStateError("cannot add opportunity to terminal branch")
        family = str(probe_family)
        if family != "seed":
            family = ProbeFamily(family).value
        if not isinstance(request, SemanticRequest):
            raise TypeError("request must be typed")
        request_id = fingerprint(request)
        descriptor = canonical_json(request.descriptor())
        opportunity_id = hashlib.sha256(
            canonical_json([run_id, branch_id, family, request_id]).encode("utf-8")
        ).hexdigest()
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO semantic_requests VALUES (?,?)", (request_id, descriptor)
            )
            stored = self.db.execute(
                "SELECT descriptor_json FROM semantic_requests WHERE fingerprint=?", (request_id,)
            ).fetchone()[0]
            if stored != descriptor:
                raise FrontierStateError("semantic request fingerprint collision or drift")
            completed = self.db.execute(
                "SELECT outcome FROM semantic_request_results WHERE run_id=? AND request_fingerprint=?",
                (run_id, request_id),
            ).fetchone()
            selected = self.db.execute(
                "SELECT tranche_number FROM semantic_tranche_requests "
                "WHERE run_id=? AND request_fingerprint=?", (run_id, request_id),
            ).fetchone()
            unresolved = self.db.execute(
                "SELECT state,state_reason,outcome FROM semantic_opportunities "
                "WHERE run_id=? AND request_fingerprint=? AND state='postponed' LIMIT 1",
                (run_id, request_id),
            ).fetchone()
            state = (OpportunityState.COMPLETED if completed else
                     OpportunityState.POSTPONED if unresolved else
                     OpportunityState.SELECTED if selected else OpportunityState.ELIGIBLE)
            self.db.execute(
                "INSERT OR IGNORE INTO semantic_opportunities "
                "(id,run_id,branch_id,provider,probe_family,request_fingerprint,state,"
                "state_reason,outcome,tranche_number,created_at_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (opportunity_id, run_id, branch_id, request.provider, family, request_id,
                 state.value, unresolved["state_reason"] if unresolved else None,
                 completed["outcome"] if completed else unresolved["outcome"] if unresolved else None,
                 selected["tranche_number"] if selected else None, _now()),
            )
            if completed:
                for evidence in self.db.execute(
                    "SELECT observation_id FROM semantic_request_evidence "
                    "WHERE run_id=? AND request_fingerprint=?", (run_id, request_id),
                ).fetchall():
                    self.db.execute(
                        "INSERT OR IGNORE INTO semantic_branch_evidence VALUES (?,?,?)",
                        (branch_id, evidence["observation_id"], "opportunity_result"),
                    )
        return opportunity_id

    def opportunity(self, opportunity_id: str) -> dict[str, object]:
        row = self.db.execute(
            "SELECT * FROM semantic_opportunities WHERE id=?", (opportunity_id,)
        ).fetchone()
        if row is None:
            raise KeyError(opportunity_id)
        return dict(row)

    def _selected(self, run_id: str, tranche_number: int) -> list[dict[str, object]]:
        return [dict(row) for row in self.db.execute(
            "SELECT t.request_fingerprint,t.selection_order,t.phase,t.reason,"
            "r.descriptor_json,results.outcome "
            "FROM semantic_tranche_requests t "
            "JOIN semantic_requests r ON r.fingerprint=t.request_fingerprint "
            "LEFT JOIN semantic_request_results results ON results.run_id=t.run_id "
            "AND results.request_fingerprint=t.request_fingerprint "
            "WHERE t.run_id=? AND t.tranche_number=? ORDER BY t.selection_order",
            (run_id, tranche_number),
        )]

    def start_tranche(
        self, run_id: str, policy: FrontierPolicy,
        *, available_attempts: Mapping[str, int] | None = None,
    ) -> tuple[int | None, list[dict[str, object]]]:
        """Choose one durable tranche; repeat returns the same selected requests."""
        self._run(run_id)
        if not isinstance(policy, FrontierPolicy):
            raise TypeError("explicit FrontierPolicy is required")
        if available_attempts is not None and any(
            not isinstance(provider, str) or isinstance(remaining, bool)
            or not isinstance(remaining, int) or remaining < 0
            for provider, remaining in available_attempts.items()
        ):
            raise ValueError("available attempts must be nonnegative provider counts")
        serialized = canonical_json(policy.descriptor())
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO semantic_frontier_policy(run_id,policy_json) VALUES (?,?)",
                (run_id, serialized),
            )
            stored = self.db.execute(
                "SELECT policy_json FROM semantic_frontier_policy WHERE run_id=?", (run_id,)
            ).fetchone()[0]
            if stored != serialized:
                raise FrontierStateError("frontier policy changed during this run")
            active = self.db.execute(
                "SELECT number FROM semantic_tranches WHERE run_id=? AND state='active' "
                "ORDER BY number LIMIT 1", (run_id,),
            ).fetchone()
            if active:
                number = int(active["number"])
                return number, self._selected(run_id, number)
            current_stop = self.db.execute(
                "SELECT semantic_stop FROM run_states WHERE run_id=?", (run_id,)
            ).fetchone()[0]
            if current_stop != "continuation_possible":
                raise FrontierStateError(f"semantic work has stopped: {current_stop}")
            used = self.db.execute(
                "SELECT COUNT(*) FROM semantic_tranche_requests WHERE run_id=?", (run_id,)
            ).fetchone()[0]
            if used >= policy.hard_max_requests:
                self._set_semantic_stop(run_id, "hard_run_budget_exhausted")
                return None, []
            candidates = [dict(row) for row in self.db.execute(
                "SELECT o.id,o.branch_id,o.provider,o.probe_family,o.request_fingerprint,"
                "b.family,b.created_at_utc,COALESCE((SELECT review.decision "
                "FROM collection_association_reviews review WHERE review.branch_id=b.id "
                "ORDER BY review.revision DESC LIMIT 1),'expand') AS review_decision,"
                "(SELECT COUNT(DISTINCT x.request_fingerprint) FROM semantic_opportunities x "
                "WHERE x.branch_id=b.id AND x.tranche_number IS NOT NULL) AS branch_exposure,"
                "(SELECT COUNT(*) FROM semantic_branch_evidence e WHERE e.branch_id=b.id) "
                "AS observed_support,"
                "(SELECT COUNT(DISTINCT json_extract(r.descriptor_json,'$.provider')) "
                "FROM semantic_branch_evidence e JOIN observations ob ON ob.id=e.observation_id "
                "JOIN parse_batches pb ON pb.id=ob.batch_id "
                "JOIN raw_artifacts raw ON raw.id=pb.artifact_id "
                "JOIN semantic_requests r ON r.fingerprint=raw.request_fingerprint "
                "WHERE e.branch_id=b.id) AS source_support,"
                "(SELECT COUNT(*) FROM semantic_opportunities prior "
                "JOIN semantic_request_results result ON result.run_id=prior.run_id "
                "AND result.request_fingerprint=prior.request_fingerprint "
                "WHERE prior.branch_id=b.id AND result.new_unique>0) AS prior_yield "
                "FROM semantic_opportunities o JOIN semantic_branches b ON b.id=o.branch_id "
                "WHERE o.run_id=? AND o.state='eligible' AND b.state IN ('eligible','active')",
                (run_id,),
            )]
            if not candidates:
                self._maybe_mark_exhausted(run_id)
                return None, []
            if available_attempts is not None:
                candidates = [item for item in candidates
                              if available_attempts.get(str(item["provider"]), 0) > 0]
            if not candidates:
                return None, []
            limit = min(policy.tranche_size, policy.hard_max_requests - used)
            number = self.db.execute(
                "SELECT COALESCE(MAX(number),0)+1 FROM semantic_tranches WHERE run_id=?",
                (run_id,),
            ).fetchone()[0]
            self.db.execute(
                "INSERT INTO semantic_tranches(run_id,number,state,created_at_utc) "
                "VALUES (?,?,'active',?)", (run_id, number, _now()),
            )
            family_exposure = {
                row["family"]: row["n"] for row in self.db.execute(
                    "SELECT b.family,COUNT(DISTINCT t.request_fingerprint) AS n "
                    "FROM semantic_branches b JOIN semantic_opportunities o ON o.branch_id=b.id "
                    "JOIN semantic_tranche_requests t ON t.run_id=o.run_id "
                    "AND t.request_fingerprint=o.request_fingerprint "
                    "WHERE b.run_id=? GROUP BY b.family", (run_id,),
                )
            }
            provider_exposure = {
                row["provider"]: row["n"] for row in self.db.execute(
                    "SELECT o.provider,COUNT(DISTINCT t.request_fingerprint) AS n "
                    "FROM semantic_opportunities o JOIN semantic_tranche_requests t "
                    "ON t.run_id=o.run_id AND t.request_fingerprint=o.request_fingerprint "
                    "WHERE o.run_id=? GROUP BY o.provider", (run_id,),
                )
            }
            chosen_fps: set[str] = set()
            per_branch: dict[str, int] = {}
            selected_by_provider: dict[str, int] = {}
            for slot in range(limit):
                available = [item for item in candidates
                             if item["request_fingerprint"] not in chosen_fps
                             and per_branch.get(item["branch_id"], 0) < policy.per_branch_cap
                             and (available_attempts is None or
                                  selected_by_provider.get(str(item["provider"]), 0)
                                  < available_attempts.get(str(item["provider"]), 0))]
                if not available:
                    break
                breadth = slot < policy.breadth_reserve and any(
                    item["branch_exposure"] == 0 for item in available
                )
                if breadth:
                    available = [item for item in available if item["branch_exposure"] == 0]
                def priority(item: dict[str, object]) -> tuple[object, ...]:
                    family_count = family_exposure.get(str(item["family"]), 0)
                    provider_count = provider_exposure.get(str(item["provider"]), 0)
                    review_penalty = int(item["review_decision"] == "uncertain")
                    expensive_unobserved = int(
                        item["provider"] == "yandex_wordstat" and item["observed_support"] == 0
                    )
                    if number == 1:
                        # Under a small first tranche, explore original seeds across
                        # source classes before arbitrary hash-tied mask variants.
                        return (int(item["probe_family"] != "seed"), review_penalty, provider_count,
                                family_count, expensive_unobserved,
                                item["created_at_utc"], item["branch_id"],
                                item["request_fingerprint"])
                    if breadth:
                        return (review_penalty, family_count, provider_count, expensive_unobserved,
                                item["created_at_utc"], item["branch_id"],
                                item["request_fingerprint"])
                    return (review_penalty, family_count, provider_count, expensive_unobserved,
                            -int(item["observed_support"] > 0),
                            -int(item["source_support"] > 1),
                            -int(item["prior_yield"] > 0),
                            item["branch_exposure"], item["created_at_utc"],
                            item["branch_id"], item["request_fingerprint"])
                selected = min(available, key=priority)
                request_id = str(selected["request_fingerprint"])
                branch_id = str(selected["branch_id"])
                phase = "breadth" if breadth else "depth"
                reason = "unexplored_branch" if breadth else "category_order_with_breadth_protection"
                self.db.execute(
                    "INSERT INTO semantic_tranche_requests VALUES (?,?,?,?,?,?)",
                    (run_id, number, request_id, slot + 1, phase, reason),
                )
                self.db.execute(
                    "UPDATE semantic_opportunities SET state='selected',tranche_number=?,"
                    "state_reason=NULL WHERE run_id=? AND request_fingerprint=? "
                    "AND state='eligible' AND branch_id IN (SELECT id FROM semantic_branches "
                    "WHERE state IN ('eligible','active'))", (number, run_id, request_id),
                )
                self.db.execute(
                    "UPDATE semantic_branches SET state='active',state_reason=NULL "
                    "WHERE id IN (SELECT branch_id FROM semantic_opportunities WHERE run_id=? "
                    "AND request_fingerprint=?) AND state='eligible'", (run_id, request_id),
                )
                chosen_fps.add(request_id)
                linked_branches = {str(item["branch_id"]): str(item["family"])
                                   for item in candidates if item["request_fingerprint"] == request_id}
                for linked_branch, linked_family in linked_branches.items():
                    per_branch[linked_branch] = per_branch.get(linked_branch, 0) + 1
                    family_exposure[linked_family] = family_exposure.get(linked_family, 0) + 1
                provider_exposure[str(selected["provider"])] = provider_exposure.get(str(selected["provider"]), 0) + 1
                selected_by_provider[str(selected["provider"])] = selected_by_provider.get(str(selected["provider"]), 0) + 1
                for item in candidates:
                    if item["request_fingerprint"] == request_id:
                        item["branch_exposure"] += 1
            if not chosen_fps:
                raise FrontierStateError("eligible frontier could not fit policy caps")
            return number, self._selected(run_id, number)

    def record_result(
        self, run_id: str, request_fingerprint: str, *, parse_batch_id: str,
    ) -> dict[str, int]:
        """Classify selected work from a durable parsed 2xx raw response."""
        parsed = self.db.execute(
            "SELECT b.kind,a.run_id,a.request_fingerprint,a.status_code FROM parse_batches b "
            "JOIN raw_artifacts a ON a.id=b.artifact_id WHERE b.id=?",
            (parse_batch_id,),
        ).fetchone()
        if (parsed is None or parsed["run_id"] != run_id
                or parsed["request_fingerprint"] != request_fingerprint
                or not 200 <= parsed["status_code"] < 300):
            raise ValueError("parse batch is not a successful response for this run and request")
        outcome = "observed" if parsed["kind"] == "data" else "valid_empty"
        identifiers = tuple(row[0] for row in self.db.execute(
            "SELECT id FROM observations WHERE batch_id=? ORDER BY id", (parse_batch_id,),
        ))
        selected = self.db.execute(
            "SELECT 1 FROM semantic_tranche_requests WHERE run_id=? AND request_fingerprint=?",
            (run_id, request_fingerprint),
        ).fetchone()
        if selected is None:
            raise FrontierStateError("semantic request was not selected")
        active = self.db.execute(
            "SELECT 1 FROM semantic_tranche_requests t JOIN semantic_tranches tr "
            "ON tr.run_id=t.run_id AND tr.number=t.tranche_number "
            "WHERE t.run_id=? AND t.request_fingerprint=? AND tr.state='active'",
            (run_id, request_fingerprint),
        ).fetchone()
        if active is None:
            raise FrontierStateError("reviewed tranche must be resumed before a late result")
        previous = self.db.execute(
            "SELECT outcome FROM semantic_request_results WHERE run_id=? AND request_fingerprint=?",
            (run_id, request_fingerprint),
        ).fetchone()
        if previous:
            raise FrontierStateError("semantic request already has a durable result")
        canonical_ids: set[int] = set()
        for observation_id in identifiers:
            observation = self._observation(observation_id)
            if observation["request_fingerprint"] != request_fingerprint:
                raise ValueError("observation came from another semantic request")
            canonical_ids.add(int(observation["canonical_id"]))
        seen = {
            row[0] for row in self.db.execute(
                "SELECT DISTINCT o.canonical_id FROM observations o "
                "JOIN parse_batches b ON b.id=o.batch_id "
                "JOIN raw_artifacts a ON a.id=b.artifact_id "
                "WHERE a.run_id=? AND b.id!=?", (run_id, parse_batch_id),
            )
        }
        branches = [row[0] for row in self.db.execute(
            "SELECT DISTINCT branch_id FROM semantic_opportunities "
            "WHERE run_id=? AND request_fingerprint=? AND state!='invalid'",
            (run_id, request_fingerprint),
        )]
        newly_supported = sum(
            self.db.execute(
                "SELECT 1 FROM semantic_branch_evidence WHERE branch_id=? LIMIT 1", (branch_id,)
            ).fetchone() is None for branch_id in branches
        ) if identifiers else 0
        metrics = {
            "new_unique": len(canonical_ids - seen),
            "rediscovered": len(canonical_ids & seen),
            "newly_supported_branches": newly_supported,
        }
        with self.db:
            self.db.execute(
                "INSERT INTO semantic_request_results VALUES (?,?,?,?,?,?,?)",
                (run_id, request_fingerprint, outcome, metrics["new_unique"],
                 metrics["rediscovered"], metrics["newly_supported_branches"], _now()),
            )
            for observation_id in identifiers:
                self.db.execute(
                    "INSERT INTO semantic_request_evidence VALUES (?,?,?)",
                    (run_id, request_fingerprint, observation_id),
                )
                for branch_id in branches:
                    self.db.execute(
                        "INSERT OR IGNORE INTO semantic_branch_evidence VALUES (?,?,?)",
                        (branch_id, observation_id, "opportunity_result"),
                    )
            self.db.execute(
                "UPDATE semantic_opportunities SET state='completed',state_reason=NULL,outcome=? "
                "WHERE run_id=? AND request_fingerprint=? AND state!='invalid'",
                (outcome, run_id, request_fingerprint),
            )
            pending = self.db.execute(
                "SELECT 1 FROM semantic_opportunities WHERE run_id=? AND state='postponed' LIMIT 1",
                (run_id,),
            ).fetchone()
            if not pending:
                self.db.execute(
                    "UPDATE run_states SET pause_reason=NULL,resumability='resumable_automatically',"
                    "updated_at_utc=? WHERE run_id=? AND pause_reason IS NOT NULL",
                    (_now(), run_id),
                )
        return metrics

    def postpone_request(
        self, run_id: str, request_fingerprint: str, *,
        reason: str, outcome: str,
    ) -> None:
        if outcome not in {"error", "ambiguous", "capacity_blocked", "budget_blocked"}:
            raise ValueError("invalid unresolved provider outcome")
        _text("postpone reason", reason)
        row = self.db.execute(
            "SELECT 1 FROM semantic_opportunities WHERE run_id=? AND request_fingerprint=? "
            "AND state='selected' LIMIT 1", (run_id, request_fingerprint),
        ).fetchone()
        if row is None:
            raise FrontierStateError("only selected work can be postponed")
        with self.db:
            self.db.execute(
                "UPDATE semantic_opportunities SET state='postponed',state_reason=?,outcome=? "
                "WHERE run_id=? AND request_fingerprint=? AND state='selected'",
                (reason, outcome, run_id, request_fingerprint),
            )
            pause = ("provider_capacity_unavailable" if outcome == "capacity_blocked"
                     else "run_budget_exhausted" if outcome == "budget_blocked"
                     else "unresolved_ambiguous_side_effect" if outcome == "ambiguous"
                     else "provider_cooldown")
            resumability = ("after_capacity_available" if outcome == "capacity_blocked"
                            else "requires_operator_decision" if outcome in {"ambiguous", "budget_blocked"}
                            else "resumable_automatically")
            self.db.execute(
                "UPDATE run_states SET outcome='incomplete',pause_reason=?,resumability=?,"
                "updated_at_utc=? WHERE run_id=?", (pause, resumability, _now(), run_id),
            )

    def resume_request(
        self, run_id: str, request_fingerprint: str, *, accept_ambiguous_risk: bool = False,
    ) -> None:
        rows = self.db.execute(
            "SELECT outcome,tranche_number FROM semantic_opportunities WHERE run_id=? "
            "AND request_fingerprint=? AND state='postponed'", (run_id, request_fingerprint),
        ).fetchall()
        if not rows:
            raise FrontierStateError("request is not postponed")
        if any(row["outcome"] == "ambiguous" for row in rows) and not accept_ambiguous_risk:
            raise FrontierStateError("ambiguous external outcome needs an explicit operator policy")
        number = rows[0]["tranche_number"]
        with self.db:
            self.db.execute(
                "UPDATE semantic_opportunities SET state='selected',state_reason=NULL,outcome=NULL "
                "WHERE run_id=? AND request_fingerprint=? AND state='postponed'",
                (run_id, request_fingerprint),
            )
            self.db.execute(
                "UPDATE semantic_tranches SET state='active',review_json=NULL,reviewed_at_utc=NULL "
                "WHERE run_id=? AND number=?", (run_id, number),
            )
            self.db.execute(
                "UPDATE semantic_frontier_policy SET weak_tranches=0 WHERE run_id=?", (run_id,)
            )
            other_gap = self.db.execute(
                "SELECT 1 FROM semantic_opportunities WHERE run_id=? AND state='postponed' LIMIT 1",
                (run_id,),
            ).fetchone()
            if other_gap:
                self.db.execute(
                    "UPDATE run_states SET semantic_stop='continuation_possible',updated_at_utc=? "
                    "WHERE run_id=?", (_now(), run_id),
                )
            else:
                self.db.execute(
                    "UPDATE run_states SET semantic_stop='continuation_possible',pause_reason=NULL,"
                    "resumability='resumable_automatically',updated_at_utc=? WHERE run_id=?",
                    (_now(), run_id),
                )

    def _set_semantic_stop(self, run_id: str, reason: str) -> None:
        self.db.execute(
            "UPDATE run_states SET semantic_stop=?,updated_at_utc=? WHERE run_id=?",
            (reason, _now(), run_id),
        )

    def _maybe_mark_exhausted(self, run_id: str) -> bool:
        has_branch = self.db.execute(
            "SELECT 1 FROM semantic_branches WHERE run_id=? LIMIT 1", (run_id,),
        ).fetchone()
        if not has_branch:
            return False
        open_branch = self.db.execute(
            "SELECT 1 FROM semantic_branches WHERE run_id=? AND state!='terminal' "
            "AND NOT (state='postponed' AND state_reason IN "
            "('association_review_deferred','guided_review_deferred')) LIMIT 1",
            (run_id,),
        ).fetchone()
        pending = self.db.execute(
            "SELECT 1 FROM semantic_opportunities WHERE run_id=? "
            "AND state IN ('eligible','selected','postponed') LIMIT 1", (run_id,),
        ).fetchone()
        if not open_branch and not pending:
            self._set_semantic_stop(run_id, "frontier_exhausted_under_current_grammar")
            return True
        return False

    def status(self, run_id: str) -> dict[str, object]:
        """Keep semantic frontier pending work distinct from the HTTP work ledger."""
        self._run(run_id)
        axes = dict(self.db.execute("SELECT * FROM run_states WHERE run_id=?", (run_id,)).fetchone())
        branches = {row["state"]: row["n"] for row in self.db.execute(
            "SELECT state,COUNT(*) AS n FROM semantic_branches WHERE run_id=? GROUP BY state",
            (run_id,),
        )}
        opportunities = {row["state"]: row["n"] for row in self.db.execute(
            "SELECT state,COUNT(*) AS n FROM semantic_opportunities WHERE run_id=? GROUP BY state",
            (run_id,),
        )}
        pending_requests = self.db.execute(
            "SELECT COUNT(DISTINCT request_fingerprint) FROM semantic_opportunities "
            "WHERE run_id=? AND state IN ('eligible','selected','postponed')", (run_id,),
        ).fetchone()[0]
        return {
            "run_id": run_id, "outcome": axes["outcome"],
            "semantic_stop": axes["semantic_stop"], "pause_reason": axes["pause_reason"],
            "resumability": axes["resumability"], "branch_states": branches,
            "opportunity_states": opportunities, "pending_semantic_requests": pending_requests,
        }

    def review_tranche(self, run_id: str, number: int) -> dict[str, object]:
        """Review observed marginal signals; provider gaps never prove saturation."""
        row = self.db.execute(
            "SELECT state FROM semantic_tranches WHERE run_id=? AND number=?", (run_id, number),
        ).fetchone()
        if row is None:
            raise KeyError((run_id, number))
        if row["state"] == "reviewed":
            saved = self.db.execute(
                "SELECT review_json FROM semantic_tranches WHERE run_id=? AND number=?",
                (run_id, number),
            ).fetchone()[0]
            return json.loads(saved)
        requests = self._selected(run_id, number)
        unresolved = [item for item in requests if item["outcome"] is None and self.db.execute(
            "SELECT 1 FROM semantic_opportunities WHERE run_id=? AND request_fingerprint=? "
            "AND state='selected' LIMIT 1", (run_id, item["request_fingerprint"]),
        ).fetchone()]
        if unresolved:
            raise FrontierStateError("selected requests still lack a classified result or gap")
        request_ids = [item["request_fingerprint"] for item in requests]
        results = [dict(row) for row in self.db.execute(
            "SELECT request_fingerprint,new_unique,rediscovered,newly_supported_branches "
            "FROM semantic_request_results WHERE run_id=?", (run_id,),
        ) if row["request_fingerprint"] in request_ids]
        missing = len(requests) - len(results)
        policy_row = self.db.execute(
            "SELECT policy_json,weak_tranches FROM semantic_frontier_policy WHERE run_id=?",
            (run_id,),
        ).fetchone()
        policy = FrontierPolicy(**json.loads(policy_row["policy_json"]))
        totals = {
            "new_unique": sum(item["new_unique"] for item in results),
            "rediscovered": sum(item["rediscovered"] for item in results),
            "newly_supported_branches": sum(item["newly_supported_branches"] for item in results),
        }
        untested_branch = self.db.execute(
            "SELECT 1 FROM semantic_branches b WHERE b.run_id=? "
            "AND b.state!='terminal' "
            "AND NOT (b.state='postponed' AND b.state_reason IN "
            "('association_review_deferred','guided_review_deferred')) "
            "AND NOT EXISTS ("
            "SELECT 1 FROM semantic_opportunities x WHERE x.branch_id=b.id "
            "AND x.tranche_number IS NOT NULL) LIMIT 1", (run_id,),
        ).fetchone() is not None
        untested_source = self.db.execute(
            "SELECT 1 FROM semantic_opportunities o JOIN semantic_branches b "
            "ON b.id=o.branch_id WHERE o.run_id=? AND o.state='eligible' "
            "AND b.state IN ('eligible','active') "
            "AND EXISTS (SELECT 1 FROM semantic_branch_evidence e WHERE e.branch_id=b.id) "
            "AND NOT EXISTS (SELECT 1 FROM semantic_opportunities earlier "
            "WHERE earlier.branch_id=b.id AND earlier.provider=o.provider "
            "AND earlier.tranche_number IS NOT NULL) LIMIT 1", (run_id,),
        ).fetchone() is not None
        any_gap = self.db.execute(
            "SELECT 1 FROM semantic_opportunities WHERE run_id=? AND state='postponed' LIMIT 1",
            (run_id,),
        ).fetchone() is not None
        weak = (
            missing == 0 and not any_gap and not untested_branch and not untested_source
            and totals["new_unique"] <= policy.weak_max_new_unique
            and totals["rediscovered"] >= policy.weak_min_rediscovered
            and totals["newly_supported_branches"] <= policy.weak_max_newly_supported_branches
        )
        weak_count = policy_row["weak_tranches"] + 1 if weak else 0
        used = self.db.execute(
            "SELECT COUNT(*) FROM semantic_tranche_requests WHERE run_id=?", (run_id,),
        ).fetchone()[0]
        stop = "continuation_possible"
        if used >= policy.hard_max_requests:
            stop = "hard_run_budget_exhausted"
        elif missing == 0 and weak_count >= policy.weak_tranches_to_stop:
            stop = "marginal_return_exhausted"
        review = {
            "tranche": number, "selected": len(requests), "successful": len(results),
            "missing_exposure": missing, **totals,
            "untested_branch_remains": untested_branch,
            "supported_untried_source_remains": untested_source, "weak": weak,
            "consecutive_weak_tranches": weak_count, "semantic_stop": stop,
        }
        with self.db:
            self.db.execute(
                "UPDATE semantic_tranches SET state='reviewed',reviewed_at_utc=?,review_json=? "
                "WHERE run_id=? AND number=?",
                (_now(), canonical_json(review), run_id, number),
            )
            self.db.execute(
                "UPDATE semantic_frontier_policy SET weak_tranches=? WHERE run_id=?",
                (weak_count, run_id),
            )
            if stop == "continuation_possible":
                self._maybe_mark_exhausted(run_id)
                review["semantic_stop"] = self.db.execute(
                    "SELECT semantic_stop FROM run_states WHERE run_id=?", (run_id,),
                ).fetchone()[0]
                self.db.execute(
                    "UPDATE semantic_tranches SET review_json=? WHERE run_id=? AND number=?",
                    (canonical_json(review), run_id, number),
                )
            else:
                self._set_semantic_stop(run_id, stop)
        return review
