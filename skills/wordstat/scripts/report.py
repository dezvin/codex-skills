"""Deterministic, self-contained HTML over verified snapshots; no provider I/O."""

from __future__ import annotations

import html
import json
import math
from collections import Counter
from collections.abc import Mapping

from .measurement_selection import _count


CHANNELS = {"gettop.results": "Wordstat · фразы", "gettop.associations": "Wordstat · соседние",
            "yandex_suggest": "Яндекс · подсказки", "google_suggest": "Google · подсказки",
            "youtube_suggest": "YouTube · подсказки", "topvisor.keywords": "Topvisor · замеры"}
PROVIDERS = {"yandex_wordstat": "Wordstat", "yandex_suggest": "Яндекс Suggest",
             "google_suggest": "Google Autocomplete", "youtube_suggest": "YouTube Suggest"}
STATES = {"proposed": "Ждёт решения", "eligible": "Можно продолжить", "active": "В работе",
          "postponed": "Отложено", "terminal": "Обработано"}
TYPES = {1: "Широкая", 2: "В кавычках", 3: "Кавычки и фиксированные формы",
         5: "С заданным порядком", 6: "Порядок и фиксированные формы"}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def number(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _context(regions: tuple[str, ...], devices: tuple[str, ...], frequency_type: int,
             operator_phrase: str = "") -> str:
    if devices == ("DEVICE_ALL",):
        devices = ()
    return json.dumps([regions, devices, frequency_type, operator_phrase], ensure_ascii=False)


def _context_label(key: str) -> str:
    regions, devices, frequency_type, operators = json.loads(key)
    region = ", ".join(regions) if regions else "не указан"
    device = ", ".join(devices) if devices else "все устройства"
    label = f"{TYPES.get(frequency_type, str(frequency_type))} · регион {region} · {device}"
    return label + (f" · запрос с операторами: {operators}" if operators else "")


def measurements(phrase: Mapping[str, object]) -> dict[str, set[int]]:
    result: dict[str, set[int]] = {}
    for observation in phrase.get("observations", ()):
        request = observation.get("request", {})
        seed = request.get("phrase") or ""
        special = seed if any(character in seed for character in '!"[]()+-') else ""
        key = _context(tuple(request.get("regions", ())), tuple(request.get("devices", ())), 1, special)
        for item in observation.get("measurements", ()):
            value = _count(item.get("value"))
            if item.get("kind") == "wordstat_gettop_phrase_count" and value is not None:
                result.setdefault(key, set()).add(value)
    for item in phrase.get("topvisor_measurements", ()):
        value = _count(item.get("value"))
        if item.get("status") == "measured" and value is not None:
            key = _context((str(item["region_key"]),), (), int(item["frequency_type"]))
            result.setdefault(key, set()).add(value)
    return result


def _status(dataset: Mapping[str, object]) -> str:
    axes = dataset.get("run_state", {})
    pause = axes.get("pause_reason")
    if pause in {"awaiting_suggest_review", "awaiting_wave_review", "awaiting_semantic_review"}:
        return "Найдены кандидаты. Продолжение ждёт решения по направлениям."
    if pause in {"provider_capacity_unavailable", "provider_capacity", "hourly_quota_unavailable"}:
        return "Часть работы ждёт доступной квоты. Это не означает завершение исследования."
    stop = axes.get("semantic_stop")
    if stop == "hard_run_budget_exhausted" or pause == "run_budget_exhausted":
        return "Сбор остановлен по выделенному лимиту. Оставшиеся направления сохранены."
    if stop == "frontier_exhausted_under_current_grammar":
        return "Разрешённые направления обработаны в рамках действующих правил."
    if stop == "marginal_return_exhausted":
        return "Сбор остановлен из-за низкой отдачи следующих порций."
    return "Сохранён промежуточный результат; работу можно продолжить по состоянию запуска."


def _row(dataset: Mapping[str, object], phrase: Mapping[str, object], topic_index: int) -> tuple[int, str]:
    values = measurements(phrase)
    sort_value = None
    if len(values) == 1 and len(next(iter(values.values()))) == 1:
        sort_value = next(iter(next(iter(values.values()))))
    counts = []
    for key, entries in sorted(values.items()):
        label = ", ".join(number(value) for value in sorted(entries))
        if len(entries) > 1:
            label = "Разные значения: " + label
        counts.append(f'<div class="count">{esc(label)}</div><div class="small">{esc(_context_label(key))}</div>')
    observed = phrase.get("observations", ())
    sources = sorted({item["channel"] for item in observed}
                     | ({"topvisor.keywords"} if phrase.get("topvisor_measurements") else set()))
    chips = " ".join(f'<span class="chip">{esc(CHANNELS.get(source, source))}</span>' for source in sources)
    history = []
    for item in observed:
        request = item.get("request", {})
        history.append(f'<li>{esc(item["original_phrase"])} · {esc(CHANNELS.get(item["channel"], item["channel"]))}'
                       f' · позиция {esc(item.get("rank"))} · запрос: {esc(request.get("phrase", ""))}'
                       f' · raw: {esc(item.get("artifact_id", ""))}</li>')
    for item in phrase.get("topvisor_measurements", ()):
        history.append(f'<li>Topvisor · {esc(item.get("received_at_utc", ""))}'
                       f' · значение: {esc(item.get("value") if item.get("value") is not None else "не измерено")}'
                       f' · raw: {esc(item.get("raw_artifact_id", ""))}</li>')
    row = (f'<tr class="phrase-row" data-topic="{topic_index}" data-source="{esc("|".join(sources))}" '
           f'data-known="{str(bool(values)).lower()}" data-search="{esc(phrase["normalized_phrase"].lower())}">'
           f'<td class="phrase">{esc(phrase["normalized_phrase"])}<details><summary>Происхождение и замеры</summary>'
           f'<ul>{"".join(history)}</ul></details></td><td>{esc(dataset["topic"])}<br>{chips}</td>'
           f'<td>{"".join(counts) or "<span class=unknown>Не измерена</span>"}</td></tr>')
    return (-sort_value if sort_value is not None else 10**30, row)


def _branches(context: Mapping[str, object]) -> str:
    branches = context.get("branches", ())
    if not branches:
        return '<p class="small">Для этого сохранённого набора доступна только сводка направлений.</p>'
    labels = {item["id"]: item["label"] for item in branches}
    parents: dict[str, list[str]] = {}
    for edge in context.get("parents", ()):
        parents.setdefault(edge["branch_id"], []).append(labels.get(edge["parent_id"], edge["parent_id"]))
    reviews: dict[str, list[object]] = {}
    for item in context.get("reviews", ()):
        reviews.setdefault(item["branch_id"], []).append(item)
    rows = []
    for item in branches:
        reasons = [str(item.get("state_reason") or item["creation_reason"])]
        reasons.extend(str(review["reason"]) for review in reviews.get(item["id"], ()))
        rows.append(f'<tr><td>{esc(item["label"])}</td><td>{esc(STATES.get(item["state"], item["state"]))}</td>'
                    f'<td>{esc(", ".join(sorted(set(parents.get(item["id"], ())))))}'
                    f'<details><summary>Решения и основание</summary><ul>'
                    f'{"".join("<li>" + esc(reason) + "</li>" for reason in reasons)}</ul></details></td></tr>')
    return ('<p class="small">Это текущее сохранённое состояние запуска. Фразы в отчёте взяты из выбранного '
            'снимка; карта направлений могла измениться позже. Это рабочие направления, не SEO-кластеры.</p>'
            '<div class="scroll"><table><thead><tr><th>Направление</th><th>Состояние</th><th>Родитель и решения</th>'
            '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>')


def _exposure(dataset: Mapping[str, object], context: Mapping[str, object]) -> str:
    diagnostics = {item["provider"]: item for item in dataset.get("provider_diagnostics", ())}
    exposures = {item["provider"]: item for item in dataset.get("provider_exposure", ())}
    budgets = context.get("plan", {}).get("attempt_budgets", {})
    rows = []
    for provider in sorted(set(exposures) | set(diagnostics)):
        diag, exposure = diagnostics.get(provider, {}), exposures.get(provider, {})
        entries = [PROVIDERS.get(provider, provider), budgets.get(provider, "—"), diag.get("attempted", 0),
                   diag.get("success", 0), diag.get("valid_empty", 0), diag.get("failed", 0),
                   exposure.get("missing", 0) + exposure.get("selected", 0), exposure.get("remaining", 0)]
        rows.append('<tr>' + ''.join('<td>' + esc(item) + '</td>' for item in entries) + '</tr>')
    return ('<p class="small">Выделенный максимум может отличаться от расхода. Если план изменён после снимка, '
            'максимумы здесь относятся к текущему плану; выполненные обращения — к снимку.</p>'
            '<div class="scroll"><table><thead><tr><th>Источник</th><th>Максимум попыток</th><th>Попыток</th>'
            '<th>С данными</th><th>Пустых</th><th>Ошибок</th><th>Пробелов</th><th>В очереди</th></tr></thead><tbody>'
            + ''.join(rows) + '</tbody></table></div>')


def _comparison(snapshot: Mapping[str, object], datasets: list[object]) -> str:
    matrices = [{phrase["normalized_phrase"]: measurements(phrase) for phrase in dataset["phrases"]}
                for dataset in datasets]
    keys = sorted({key for matrix in matrices for values in matrix.values() for key in values})
    sections = []
    for key in keys:
        rows, totals, complete = [], [], True
        resolved = [{phrase: next(iter(values[key])) for phrase, values in matrix.items()
                     if key in values and len(values[key]) == 1} for matrix in matrices]
        positive = sorted(value for values in resolved for value in values.values() if value > 0)
        high = positive[max(0, math.ceil(len(positive) * .8) - 1)] if positive else None
        medium = positive[max(0, math.ceil(len(positive) * .5) - 1)] if positive else None
        for dataset, matrix, values in zip(datasets, matrices, resolved):
            total = sum(values.values())
            totals.append(total)
            complete = complete and len(values) == len(matrix)
            top = sorted(values.items(), key=lambda item: (-item[1], item[0]))
            groups = []
            if positive:
                for label, predicate in (
                    ("Высокие", lambda value: value >= high),
                    ("Средние", lambda value: medium <= value < high),
                ):
                    found = [(text, value) for text, value in top if value > 0 and predicate(value)]
                    groups.append(f'<details><summary>{label} · {len(found)}</summary><ol>'
                                  + ''.join(f'<li>{esc(text)} — {number(value)}</li>' for text, value in found[:10])
                                  + ('</ol><p class="small">Первые 10; остальные доступны в таблице.</p></details>'
                                     if len(found) > 10 else '</ol></details>'))
            rows.append(f'<tr><td>{esc(dataset["topic"])}</td><td>{len(values)} / {len(matrix)}</td>'
                        f'<td>{number(total)}</td><td>{"".join(groups)}</td></tr>')
        conclusion = ''
        if len(datasets) > 1:
            if complete and snapshot.get("comparability") == "matched_method_and_allocation":
                best = max(totals)
                leaders = [dataset["topic"] for dataset, total in zip(datasets, totals) if total == best]
                if len(leaders) == 1:
                    conclusion = f'<p>Больше сумма измерений собранного списка у темы «{esc(leaders[0])}».</p>'
                else:
                    conclusion = '<p>Максимальная сумма собранных измерений одинакова у нескольких тем.</p>'
            else:
                conclusion = '<p>Общий вывод «спрос выше» не сделан: есть неизвестные значения, конфликты или пробелы сбора.</p>'
        bounds = (f'Высокие: от {number(high)}; средние: от {number(medium)} до {number(high)} (не включая). '
                  'Границы получены по 80-му и 50-му процентилям положительных значений этих наборов; '
                  'это относительные группы для просмотра, не категории рынка.' if positive else 'Положительных значений нет.')
        sections.append(f'<h3>{esc(_context_label(key))}</h3><p class="small">{esc(bounds)}</p>'
                        '<div class="scroll"><table><thead><tr><th>Тема</th><th>Измерено без конфликта</th>'
                        '<th>Сумма списка</th><th>Основные измеренные фразы</th></tr></thead><tbody>'
                        + ''.join(rows) + '</tbody></table></div>' + conclusion)
    return ('<p class="small">Сумма широких частотностей может содержать пересечения. Она не равна числу уникальных '
            'поисков по нише и не определяет привлекательность бизнеса. Разные контексты измерений считаются отдельно.</p>'
            + (''.join(sections) if sections else '<p>Для подсчёта частотностей пока нет измерений.</p>'))


STYLE = '''
:root{color-scheme:light;--ink:#1e2933;--muted:#5d6873;--line:#dbe3e9;--paper:#fff;--back:#f5f8fa;--blue:#185a86}
*{box-sizing:border-box}body{margin:0;background:var(--back);color:var(--ink);font:16px/1.5 Arial,sans-serif}
.wrap{width:min(1160px,calc(100% - 32px));margin:auto}header{background:#fff;border-bottom:1px solid var(--line)}
header .wrap{padding:16px 0;font-size:15px;font-weight:bold;color:var(--blue)}main{padding:28px 0 60px}
h1{font-size:clamp(28px,4vw,42px);line-height:1.15;margin:0 0 20px}h2{font-size:22px}h3{font-size:17px}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.stat,.panel{background:#fff;border:1px solid var(--line);border-radius:8px}
.stat{padding:18px}.stat strong{display:block;font-size:30px}.stat span,.small{color:var(--muted)}.small{font-size:14px}
.panel{margin:16px 0;padding:22px}.notice{padding:16px 18px;border-left:4px solid var(--blue);background:#eaf3f9}
.sources,.filters{display:flex;gap:10px;flex-wrap:wrap}.source{padding:10px 12px;background:var(--back);border-radius:5px}
input,select{min-height:40px;border:1px solid #b6c7d2;border-radius:5px;background:#fff;padding:8px 10px;font:inherit}
input{flex:2 1 240px}select{flex:1 1 180px}:focus-visible{outline:3px solid #68a8d1;outline-offset:2px}
.scroll{overflow:auto}table{width:100%;border-collapse:collapse;min-width:690px}th{background:#f2f6f8;text-align:left;font-size:13px}
th,td{padding:10px 12px;vertical-align:top;border-bottom:1px solid var(--line)}.phrase{width:42%;font-weight:600}
.chip{display:inline-block;margin:2px 4px 2px 0;padding:2px 7px;border-radius:4px;background:#edf3f6;color:#355267;font-size:12px}
.count{font-weight:bold;font-variant-numeric:tabular-nums}.unknown{color:var(--muted)}details{font-size:13px;font-weight:normal}
summary{cursor:pointer}details ul{padding-left:18px;overflow-wrap:anywhere}footer{color:var(--muted);font-size:13px;overflow-wrap:anywhere}
@media(max-width:680px){.stats{grid-template-columns:1fr}.panel{padding:16px}}
'''
SCRIPT = '''
const controls = ['query','source','known','topic'].map(id => document.getElementById(id));
const rows = [...document.querySelectorAll('.phrase-row')];
function filterRows(){
  const [query,source,known,topic] = controls;
  let visible=0;
  for(const row of rows){
    const show=row.dataset.search.includes(query.value.trim().toLocaleLowerCase('ru')) &&
      (!source.value || row.dataset.source.split('|').includes(source.value)) &&
      (!known.value || row.dataset.known===known.value) && (!topic.value || row.dataset.topic===topic.value);
    row.hidden=!show; if(show) visible++;
  }
  document.getElementById('shown').textContent=`Показано ${visible} из ${rows.length} фраз`;
}
for(const control of controls) control.addEventListener('input',filterRows);
'''


def build_report(snapshot: Mapping[str, object], *, report_context: Mapping[str, object] | None = None) -> str:
    datasets = list(snapshot.get("datasets", (snapshot,)))
    contexts = report_context or {}
    phrases = sum(len(dataset["phrases"]) for dataset in datasets)
    known = sum(bool(measurements(phrase)) for dataset in datasets for phrase in dataset["phrases"])
    channels = Counter(observation["channel"] for dataset in datasets for phrase in dataset["phrases"]
                       for observation in phrase.get("observations", ()))
    rows = ''.join(row for _, row in sorted(_row(dataset, phrase, index)
                   for index, dataset in enumerate(datasets) for phrase in dataset["phrases"]))
    topic_options = ''.join(f'<option value="{index}">{esc(dataset["topic"])}</option>'
                            for index, dataset in enumerate(datasets))
    source_options = ''.join(f'<option value="{esc(key)}">{esc(label)}</option>' for key, label in CHANNELS.items())
    cards = ''.join(f'<div class="source">{esc(CHANNELS.get(key,key))} · <strong>{value}</strong></div>'
                    for key, value in sorted(channels.items()))
    sections = []
    for dataset in datasets:
        context = contexts.get(dataset["run_id"], {})
        pending = dataset.get("frontier", {}).get("pending_semantic_requests", 0)
        sections.append(f'<section class="panel"><h2>{esc(dataset["topic"])}</h2>'
                        f'<p class="notice">{esc(_status(dataset))}</p>'
                        f'<p>В очереди: {pending}. Пробелов источников: {len(dataset.get("gaps", ())) }.</p>'
                        '<details><summary>Направления и решения</summary>' + _branches(context) + '</details>'
                        '<details><summary>Расход и доступность источников</summary>' + _exposure(dataset, context)
                        + '</details></section>')
    title = datasets[0]["topic"] if len(datasets) == 1 else "Сравнение поискового спроса"
    return (f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width,initial-scale=1"><title>Wordstat — {esc(title)}</title><style>{STYLE}</style>'
            f'</head><body><header><div class="wrap">WORDSTAT · ОТЧЁТ</div></header><main class="wrap"><h1>{esc(title)}</h1>'
            f'<div class="stats"><div class="stat"><strong>{phrases}</strong><span>фраз в наборах</span></div>'
            f'<div class="stat"><strong>{known}</strong><span>есть хотя бы один замер</span></div>'
            f'<div class="stat"><strong>{phrases-known}</strong><span>ни одного замера</span></div></div>'
            f'<section class="panel"><h2>Источники формулировок</h2><div class="sources">{cards}</div>'
            '<p class="small">Одна фраза может наблюдаться несколько раз и в разных источниках.</p></section>'
            + ''.join(sections) + '<section class="panel"><h2>Измерения и основные фразы</h2>'
            + _comparison(snapshot, datasets) + '</section><section class="panel"><h2>Все найденные фразы</h2>'
            '<div class="filters"><input id="query" type="search" aria-label="Поиск по фразам" placeholder="Поиск по фразам">'
            f'<select id="topic" aria-label="Тема"><option value="">Все темы</option>{topic_options}</select>'
            f'<select id="source" aria-label="Источник"><option value="">Все источники</option>{source_options}</select>'
            '<select id="known" aria-label="Измерение"><option value="">Любая частотность</option>'
            '<option value="true">Есть замер</option><option value="false">Не измерена</option></select></div>'
            f'<p id="shown" class="small" aria-live="polite">Показано {phrases} из {phrases} фраз</p>'
            '<div class="scroll"><table><thead><tr><th>Фраза</th><th>Тема и источники</th><th>Частотность</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></div><p class="small">Ноль — измеренное значение. '
            'Отсутствие замера — неизвестное значение. Конфликтующие значения показаны вместе; разные регионы, '
            'устройства и виды частотности не объединены молча.</p></section>'
            f'</main><script>{SCRIPT}</script></body></html>\n')
