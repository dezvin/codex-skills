"""Bounded seed hypotheses and deterministic probe generation.

No model or provider is called here. A proposal is never an observation.
Rules are explicit data, applied once to their original seeds, not recursively.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from .identity import normalize_phrase_v1
from .models import canonical_json, strict_json_object


GRAMMAR_VERSION = "seed-masks-v1"


class SeedFamily(StrEnum):
    SERVICE = "service"
    PRODUCT = "product"
    JOB = "job"
    PAIN = "pain"
    SITUATION = "situation"
    DESIRED_OUTCOME = "desired_outcome"
    SYNONYM = "synonym"
    ALTERNATIVE_FORMULATION = "alternative_formulation"
    COMMERCIAL = "commercial"
    INFORMATIONAL_QUESTION = "informational_question"
    COMPARISON = "comparison"
    ALTERNATIVE = "alternative"
    BRAND = "brand"
    COMPETITOR = "competitor"
    GEO = "geo"
    SEASONALITY = "seasonality"
    AUDIENCE = "audience"
    USE_CASE = "use_case"
    NICHE_SPECIFIC = "niche_specific"


class ProposalStage(StrEnum):
    INITIALIZATION = "initialization"
    UNCOVERED_REGION_RECOVERY = "uncovered_region_recovery"


class ProbeFamily(StrEnum):
    PREFIX = "prefix"
    SUFFIX = "suffix"
    QUESTION = "question"
    PREPOSITION = "preposition"
    COMPARISON = "comparison"
    ALPHABET = "alphabet"
    NUMBER = "number"
    TOKEN_INSERTION = "token_insertion"
    MODIFIER = "modifier"
    WORD_ORDER = "word_order"
    MORPHOLOGY = "morphology"
    ENTITY_SUBSTITUTION = "entity_substitution"
    NICHE_SPECIFIC = "niche_specific"


class MaskOperation(StrEnum):
    PREPEND = "prepend"
    APPEND = "append"
    INSERT = "insert"
    REPLACE = "replace"
    SWAP = "swap"


_ALLOWED_OPERATIONS = {
    ProbeFamily.PREFIX: {MaskOperation.PREPEND},
    ProbeFamily.SUFFIX: {MaskOperation.APPEND},
    ProbeFamily.QUESTION: {MaskOperation.PREPEND},
    ProbeFamily.PREPOSITION: {MaskOperation.PREPEND},
    ProbeFamily.COMPARISON: {MaskOperation.PREPEND, MaskOperation.APPEND},
    ProbeFamily.ALPHABET: {MaskOperation.APPEND},
    ProbeFamily.NUMBER: {MaskOperation.PREPEND, MaskOperation.APPEND},
    ProbeFamily.TOKEN_INSERTION: {MaskOperation.INSERT},
    ProbeFamily.MODIFIER: {MaskOperation.PREPEND, MaskOperation.APPEND, MaskOperation.INSERT},
    ProbeFamily.WORD_ORDER: {MaskOperation.SWAP},
    ProbeFamily.MORPHOLOGY: {MaskOperation.REPLACE},
    ProbeFamily.ENTITY_SUBSTITUTION: {MaskOperation.REPLACE},
    ProbeFamily.NICHE_SPECIFIC: {
        MaskOperation.PREPEND, MaskOperation.APPEND, MaskOperation.INSERT,
        MaskOperation.REPLACE,
    },
}


def _nonempty(name: str, value: object) -> str:
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


def _exact_keys(value: Mapping[str, object], allowed: set[str], required: set[str]) -> None:
    unknown = set(value) - allowed
    missing = required - set(value)
    if unknown or missing:
        raise ValueError(f"unknown or missing fields: unknown={sorted(unknown)}, missing={sorted(missing)}")


@dataclass(frozen=True)
class LLMHypothesis:
    phrase: str
    family: SeedFamily
    rationale: str

    def __post_init__(self) -> None:
        normalize_phrase_v1(self.phrase)
        _nonempty("rationale", self.rationale)
        object.__setattr__(self, "family", SeedFamily(self.family))

    def descriptor(self) -> dict[str, str]:
        return {"phrase": self.phrase, "family": self.family.value, "rationale": self.rationale}


@dataclass(frozen=True)
class ProbeRule:
    id: str
    family: ProbeFamily
    operation: MaskOperation
    values: tuple[str, ...] = ()
    index: int | None = None
    other_index: int | None = None
    target: str | None = None
    origin: str = "deterministic"  # deterministic or llm_proposed

    def __post_init__(self) -> None:
        _nonempty("rule id", self.id)
        family = ProbeFamily(self.family)
        operation = MaskOperation(self.operation)
        object.__setattr__(self, "family", family)
        object.__setattr__(self, "operation", operation)
        if operation not in _ALLOWED_OPERATIONS[family]:
            raise ValueError("operation is not valid for this probe family")
        if self.origin not in {"deterministic", "llm_proposed"}:
            raise ValueError("invalid rule origin")
        if self.origin == "llm_proposed" and family != ProbeFamily.NICHE_SPECIFIC:
            raise ValueError("unvalidated model rule must be niche_specific")
        if isinstance(self.values, str):
            raise ValueError("values must be a sequence")
        values = tuple(self.values)
        if operation == MaskOperation.SWAP:
            if values or self.target is not None or self.index is None or self.other_index is None:
                raise ValueError("swap requires two indices and no values/target")
            _nonnegative("index", self.index)
            _nonnegative("other_index", self.other_index)
            if self.index == self.other_index:
                raise ValueError("swap indices must differ")
        else:
            if not values or any(not isinstance(item, str) or not item.strip() for item in values):
                raise ValueError("mask values must be nonempty text")
            if family == ProbeFamily.ALPHABET and any(len(item) != 1 for item in values):
                raise ValueError("alphabet values must be single characters")
            if operation in {MaskOperation.INSERT, MaskOperation.REPLACE}:
                if self.index is None:
                    raise ValueError("insert/replace requires an index")
                _nonnegative("index", self.index)
            elif self.index is not None:
                raise ValueError("position is unsupported for prepend/append")
            if operation == MaskOperation.REPLACE:
                _nonempty("replace target", self.target)
                if len(self.target.split()) != 1:
                    raise ValueError("replace target must be one token")
            elif self.target is not None:
                raise ValueError("target is only valid for replace")
            if self.other_index is not None:
                raise ValueError("other_index is only valid for swap")
        object.__setattr__(self, "values", values)

    @classmethod
    def from_mapping(cls, value: Mapping[str, object], *, origin: str) -> ProbeRule:
        if not isinstance(value, Mapping):
            raise ValueError("rule must be an object")
        allowed = {"id", "family", "operation", "values", "index", "other_index", "target"}
        _exact_keys(value, allowed, {"id", "family", "operation"})
        values = value.get("values", ())
        if not isinstance(values, (list, tuple)):
            raise ValueError("values must be an array")
        return cls(
            id=value["id"], family=value["family"], operation=value["operation"],
            values=tuple(values), index=value.get("index"),
            other_index=value.get("other_index"), target=value.get("target"),
            origin=origin,
        )

    def descriptor(self) -> dict[str, object]:
        return {
            "id": self.id, "family": self.family.value, "operation": self.operation.value,
            "values": list(self.values), "index": self.index,
            "other_index": self.other_index, "target": self.target, "origin": self.origin,
        }


@dataclass(frozen=True)
class LLMProposalBatch:
    topic: str
    stage: ProposalStage
    model_id: str
    prompt_version: str
    input_context_json: str
    hypotheses: tuple[LLMHypothesis, ...]
    proposed_rules: tuple[ProbeRule, ...] = ()

    def __post_init__(self) -> None:
        _nonempty("topic", self.topic)
        object.__setattr__(self, "stage", ProposalStage(self.stage))
        _nonempty("model_id", self.model_id)
        _nonempty("prompt_version", self.prompt_version)
        context = strict_json_object(self.input_context_json)
        object.__setattr__(self, "input_context_json", canonical_json(context))
        hypotheses = tuple(self.hypotheses)
        rules = tuple(self.proposed_rules)
        if not all(isinstance(item, LLMHypothesis) for item in hypotheses):
            raise ValueError("invalid hypotheses")
        if not all(isinstance(item, ProbeRule) and item.origin == "llm_proposed" for item in rules):
            raise ValueError("invalid proposed rules")
        if len({rule.id for rule in rules}) != len(rules):
            raise ValueError("duplicate proposed rule IDs")
        object.__setattr__(self, "hypotheses", hypotheses)
        object.__setattr__(self, "proposed_rules", rules)

    @classmethod
    def from_mapping(
        cls, value: Mapping[str, object], *, max_hypotheses: int, max_rules: int,
    ) -> LLMProposalBatch:
        """Validate untrusted structured model output against explicit caller limits."""
        _positive("max_hypotheses", max_hypotheses)
        _nonnegative("max_rules", max_rules)
        if not isinstance(value, Mapping):
            raise ValueError("proposal batch must be an object")
        required = {
            "topic", "stage", "model_id", "prompt_version", "input_context",
            "hypotheses", "proposed_rules",
        }
        _exact_keys(value, required, required)
        raw_hypotheses = value["hypotheses"]
        raw_rules = value["proposed_rules"]
        if not isinstance(raw_hypotheses, list) or not isinstance(raw_rules, list):
            raise ValueError("hypotheses and proposed_rules must be arrays")
        if len(raw_hypotheses) > max_hypotheses or len(raw_rules) > max_rules:
            raise ValueError("model proposal exceeds explicit item limits")
        hypotheses: list[LLMHypothesis] = []
        for item in raw_hypotheses:
            if not isinstance(item, Mapping):
                raise ValueError("hypothesis must be an object")
            _exact_keys(item, {"phrase", "family", "rationale"},
                        {"phrase", "family", "rationale"})
            hypotheses.append(LLMHypothesis(
                item["phrase"], SeedFamily(item["family"]), item["rationale"],
            ))
        rules = tuple(
            ProbeRule.from_mapping(item, origin="llm_proposed") for item in raw_rules
        )
        return cls(
            topic=value["topic"], stage=ProposalStage(value["stage"]),
            model_id=value["model_id"], prompt_version=value["prompt_version"],
            input_context_json=canonical_json(value["input_context"]),
            hypotheses=tuple(hypotheses), proposed_rules=rules,
        )

    def descriptor(self) -> dict[str, object]:
        return {
            "topic": self.topic, "stage": self.stage.value,
            "model_id": self.model_id, "prompt_version": self.prompt_version,
            "input_context": json.loads(self.input_context_json),
            "hypotheses": [item.descriptor() for item in self.hypotheses],
            "proposed_rules": [item.descriptor() for item in self.proposed_rules],
        }

    def seeds(self, batch_id: str) -> tuple[ProbeSeed, ...]:
        """Link every proposed phrase to its immutable batch and item index."""
        _nonempty("batch_id", batch_id)
        return tuple(
            ProbeSeed(item.phrase, item.family, "llm_hypothesis", f"{batch_id}:{index}")
            for index, item in enumerate(self.hypotheses)
        )


@dataclass(frozen=True)
class ProbeSeed:
    phrase: str
    family: SeedFamily
    origin_kind: str  # topic, llm_hypothesis, or observation
    origin_ref: str

    def __post_init__(self) -> None:
        normalize_phrase_v1(self.phrase)
        object.__setattr__(self, "family", SeedFamily(self.family))
        if self.origin_kind not in {"topic", "llm_hypothesis", "observation"}:
            raise ValueError("invalid seed origin kind")
        _nonempty("origin_ref", self.origin_ref)

    def descriptor(self) -> dict[str, str]:
        return {
            "phrase": self.phrase, "family": self.family.value,
            "origin_kind": self.origin_kind, "origin_ref": self.origin_ref,
        }


@dataclass(frozen=True)
class ProbePlan:
    seeds: tuple[ProbeSeed, ...]
    rules: tuple[ProbeRule, ...]
    max_candidates: int
    grammar_version: str = GRAMMAR_VERSION

    def __post_init__(self) -> None:
        if self.grammar_version != GRAMMAR_VERSION:
            raise ValueError("unknown probe grammar version")
        _positive("max_candidates", self.max_candidates)
        seeds = tuple(self.seeds)
        rules = tuple(self.rules)
        if not seeds or not all(isinstance(seed, ProbeSeed) for seed in seeds):
            raise ValueError("plan needs typed seeds")
        if not all(isinstance(rule, ProbeRule) for rule in rules):
            raise ValueError("plan needs typed rules")
        if len({rule.id for rule in rules}) != len(rules):
            raise ValueError("duplicate probe rule IDs")
        object.__setattr__(self, "seeds", seeds)
        object.__setattr__(self, "rules", rules)

    def descriptor(self) -> dict[str, object]:
        return {
            "grammar_version": self.grammar_version,
            "max_candidates": self.max_candidates,
            "seeds": [seed.descriptor() for seed in self.seeds],
            "rules": [rule.descriptor() for rule in self.rules],
        }

    def digest(self) -> str:
        return hashlib.sha256(canonical_json(self.descriptor()).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ProbeOrigin:
    seed_kind: str
    seed_ref: str
    seed_family: SeedFamily
    rule_id: str | None
    rule_family: ProbeFamily | None
    variant: str | None

    def descriptor(self) -> dict[str, object]:
        return {
            "seed_kind": self.seed_kind, "seed_ref": self.seed_ref,
            "seed_family": self.seed_family.value, "rule_id": self.rule_id,
            "rule_family": self.rule_family.value if self.rule_family else None,
            "variant": self.variant,
        }


@dataclass(frozen=True)
class GeneratedProbe:
    phrase: str
    normalized_phrase: str
    origins: tuple[ProbeOrigin, ...]

    def descriptor(self) -> dict[str, object]:
        return {
            "phrase": self.phrase, "normalized_phrase": self.normalized_phrase,
            "origins": [origin.descriptor() for origin in self.origins],
        }


@dataclass(frozen=True)
class ProbeBatch:
    plan_digest: str
    generated_candidates: int
    probes: tuple[GeneratedProbe, ...]

    def descriptor(self) -> dict[str, object]:
        return {
            "plan_digest": self.plan_digest,
            "generated_candidates": self.generated_candidates,
            "unique_probes": len(self.probes),
            "probes": [probe.descriptor() for probe in self.probes],
        }


def _variants(seed: str, rule: ProbeRule) -> tuple[tuple[str, str], ...]:
    words = seed.split()
    operation = rule.operation
    if operation == MaskOperation.SWAP:
        assert rule.index is not None and rule.other_index is not None
        if max(rule.index, rule.other_index) >= len(words):
            return ()
        altered = words.copy()
        altered[rule.index], altered[rule.other_index] = altered[rule.other_index], altered[rule.index]
        return ((" ".join(altered), f"{rule.index}:{rule.other_index}"),)
    if operation == MaskOperation.INSERT and (rule.index is None or rule.index > len(words)):
        return ()
    if operation == MaskOperation.REPLACE and (
        rule.index is None or rule.index >= len(words) or words[rule.index] != rule.target
    ):
        return ()
    variants: list[tuple[str, str]] = []
    for value in rule.values:
        if operation == MaskOperation.PREPEND:
            candidate = f"{value} {seed}"
        elif operation == MaskOperation.APPEND:
            candidate = f"{seed} {value}"
        elif operation == MaskOperation.INSERT:
            assert rule.index is not None
            candidate = " ".join(words[:rule.index] + [value] + words[rule.index:])
        else:
            assert rule.index is not None
            altered = words.copy()
            altered[rule.index] = value
            candidate = " ".join(altered)
        variants.append((candidate, value))
    return tuple(variants)


def generate_probes(plan: ProbePlan) -> ProbeBatch:
    """Apply each rule once to each original seed; fail before silent truncation."""
    candidates = 0
    ordered: dict[str, tuple[str, list[ProbeOrigin]]] = {}

    def add(phrase: str, origin: ProbeOrigin) -> None:
        nonlocal candidates
        candidates += 1
        if candidates > plan.max_candidates:
            raise ValueError("probe generation exceeds explicit candidate budget")
        normalized = normalize_phrase_v1(phrase)
        if normalized in ordered:
            ordered[normalized][1].append(origin)
        else:
            ordered[normalized] = (phrase, [origin])

    for seed in plan.seeds:
        add(seed.phrase, ProbeOrigin(seed.origin_kind, seed.origin_ref, seed.family,
                                     None, None, None))
        for rule in plan.rules:
            for phrase, variant in _variants(seed.phrase, rule):
                add(phrase, ProbeOrigin(
                    seed.origin_kind, seed.origin_ref, seed.family,
                    rule.id, rule.family, variant,
                ))
    probes = tuple(
        GeneratedProbe(phrase, normalized, tuple(origins))
        for normalized, (phrase, origins) in ordered.items()
    )
    return ProbeBatch(plan.digest(), candidates, probes)
