"""Select missing, context-matched measurements without losing observations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation

from .identity import normalize_phrase_v1


def _count(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    if not number.is_finite() or number < 0 or number != number.to_integral_value():
        return None
    return int(number)


def measurement_values(phrase: Mapping[str, object], qualifier: Mapping[str, int]) -> list[int]:
    """Return known values in one requested Yandex region/frequency context.

    The owner's paired check permits reusing plain GetTop returned counts for
    broad measurement. Restricted devices, aggregate regions and operator
    requests do not silently satisfy that context. Zero is a known value.
    """
    key = (qualifier["region_key"], qualifier["searcher_key"], qualifier["type"])
    values: set[int] = set()
    for item in phrase.get("topvisor_measurements", ()):
        if (item.get("region_key"), item.get("searcher_key"), item.get("frequency_type")) != key:
            continue
        value = _count(item.get("value"))
        if item.get("status") == "measured" and value is not None:
            values.add(value)
    if key[1:] != (0, 1):
        return sorted(values)
    for observation in phrase.get("observations", ()):
        request = observation.get("request", {})
        if (request.get("provider") != "yandex_wordstat" or request.get("operation") != "GetTop"
                or tuple(request.get("regions", ())) != (str(key[0]),)
                or tuple(request.get("devices", ())) not in ((), ("DEVICE_ALL",))
                or any(character in (request.get("phrase") or "") for character in '!"[]()+-')):
            continue
        for measurement in observation.get("measurements", ()):
            value = _count(measurement.get("value"))
            if measurement.get("kind") == "wordstat_gettop_phrase_count" and value is not None:
                values.add(value)
    return sorted(values)


def select_unknown_measurements(
    snapshot: Mapping[str, object], qualifiers: Sequence[Mapping[str, int]], *,
    phrases: Sequence[str] | None = None,
) -> dict[str, object]:
    """Group identical missing qualifier sets: no paid Cartesian pair is known."""
    keys = [tuple(item[name] for name in ("region_key", "searcher_key", "type"))
            for item in qualifiers]
    if not keys or len(set(keys)) != len(keys):
        raise ValueError("nonempty unique qualifiers are required")
    if any(key[1] != 0 for key in keys):
        raise ValueError("only Yandex measurements are supported")
    by_phrase: dict[str, dict[str, object]] = {}
    active_pairs: dict[tuple[str, tuple[int, ...]], set[str]] = {}
    jobs = list(snapshot.get("topvisor_jobs", ()))
    for dataset in snapshot.get("datasets", (snapshot,)):
        jobs.extend(dataset.get("topvisor_jobs", ()))
        for entry in dataset["phrases"]:
            text = entry["normalized_phrase"]
            item = by_phrase.setdefault(text, {"observations": [], "topvisor_measurements": []})
            item["observations"].extend(entry.get("observations", ()))
            item["topvisor_measurements"].extend(entry.get("topvisor_measurements", ()))
    for job in jobs:
        if job.get("state") not in {"intent_recorded", "ambiguous_submit", "submitted", "ongoing"}:
            continue
        for text in job["keywords"]:
            for qualifier in job["qualifiers"]:
                key = tuple(qualifier[name] for name in ("region_key", "searcher_key", "type"))
                active_pairs.setdefault((normalize_phrase_v1(text), key), set()).add(str(job["id"]))
    if phrases is None:
        targets = [(text, text) for text in sorted(by_phrase)]
    else:
        if isinstance(phrases, (str, bytes)) or not phrases:
            raise ValueError("phrases must be a nonempty sequence")
        targets = []
        seen: set[str] = set()
        for text in phrases:
            if not isinstance(text, str) or not text.strip():
                raise ValueError("nonempty keywords are required")
            normalized = normalize_phrase_v1(text)
            if normalized not in by_phrase:
                raise ValueError("phrase does not belong to the snapshot")
            if normalized in seen:
                raise ValueError("duplicate keywords must be resolved before billing")
            seen.add(normalized)
            targets.append((text.strip(), normalized))
    grouped: dict[tuple[int, ...], list[str]] = {}
    known, blocked = 0, 0
    blocked_jobs: set[str] = set()
    for text, normalized in targets:
        missing_indexes = []
        for index, qualifier in enumerate(qualifiers):
            if measurement_values(by_phrase[normalized], qualifier):
                known += 1
            elif (normalized, keys[index]) in active_pairs:
                blocked += 1
                blocked_jobs.update(active_pairs[(normalized, keys[index])])
            else:
                missing_indexes.append(index)
        missing = tuple(missing_indexes)
        if missing:
            grouped.setdefault(missing, []).append(text)
    requested = len(targets) * len(qualifiers)
    return {
        "requested_pairs": requested, "skipped_known_pairs": known,
        "missing_pairs": requested - known - blocked, "pending_pairs": blocked,
        "pending_job_ids": sorted(blocked_jobs),
        "groups": [{"keywords": words, "qualifiers": [dict(qualifiers[i]) for i in indexes]}
                   for indexes, words in sorted(grouped.items())],
    }
