# Сбор, сравнение и продолжение

Ниже `P` — абсолютный путь к `scripts/run.py`, `S` — отдельная папка состояния, `R` — сохранённый run ID, `C` — comparison ID, `M` — расчётный разрешённый потолок Wordstat в рублях. Подставляй значения сам; пользователь не должен собирать команды или JSON. Входные JSON и экспорт сохраняй вне каталога навыка, в папке текущей работы.

## Один сбор

```text
python P guided scout-create --store S --topic "создание сайта с ИИ" --max-estimated-wordstat-cost M
python P guided scout-run --store S --run-id R
python P guided scout-report --store S --run-id R --limit 50 --offset 0
```

Сохрани возвращённый `run_id`. Один ранний `GetTop` использует регион 225 и `numPhrases=200`, если не задан иной контекст. Сводка содержит `phase`, наблюдения и исход работы. При `has_more` дочитай страницы, не повторяй внешний запрос. Представь карту направлений из наблюдений и собственных гипотез. До утверждения карты не запускай маски.

После утверждения подготовь `proposal.json` и `masks.json` по схемам ниже:

```text
python P guided approve-directions --store S --run-id R --topic "создание сайта с ИИ" --family service --proposal proposal.json --mask-rules masks.json --max-estimated-wordstat-cost M
python P guided suggest-preview --store S --run-id R --limit 50 --offset 0
python P guided checkpoint --store S --run-id R --limit 50 --offset 0
```

Для другого региона передай одинаковые повторяемые `--region ID` в `scout-create` и `approve-directions`. План сохраняется; ранний ответ переиспользуется. `suggest-preview` собирает подсказки Yandex, Google и YouTube и останавливается на `awaiting_suggest_review`. `checkpoint` читает сохранённых кандидатов без запросов. При `has_more` прочитай все страницы через `--offset`; модель оценивает весь набор, человеку показывает сгруппированный итог.

После решения пользователя подготовь один полный JSON-массив решений по текущему batch. Каждый кандидат представлен ровно один раз:

```json
[{"branch_id":"ID из checkpoint","input_sha256":"хеш из checkpoint","decision":"expand","reason":"Связанная с утверждённым направлением ветка"},
 {"branch_id":"другой ID","input_sha256":"его хеш","decision":"defer","reason":"Соседнее направление оставлено вне текущих границ"}]
```

```text
python P guided approve-candidates --store S --run-id R --decisions decisions.json --reviewer ACTUAL_MODEL --review-version semantic-review-v1
python P guided wave --store S --run-id R --limit 50 --offset 0
```

`expand` разрешает исследовать ветку; `defer` сохраняет её без дальнейших запросов. Одобрение не означает, что каждая найденная фраза становится запросом Wordstat. Код распределяет внимание в пределах плана. Новые кандидаты переводят работу в `awaiting_wave_review`; снова прочитай полный `checkpoint`, оцени смысл, покажи группы, сохрани решение и продолжи. Если новых кандидатов нет и остаётся разрешённая работа, следующая порция не требует искусственного вопроса.

Ассоциации рассматриваются вместе с другими кандидатами после любого GetTop. Они не ограничиваются высокочастотными строками. Малое лексическое сходство само по себе не повод отложить ветку. При недостаточной ясности сохраняй `defer`, предлагай краткое уточнение только если оно существенно меняет тему.

## Формат гипотез и масок

```json
{"topic":"создание сайта с ИИ","stage":"initialization","model_id":"ACTUAL_MODEL","prompt_version":"wordstat-seeds-v1","input_context":{"topic":"создание сайта с ИИ","scope":"утверждённые границы","region":"RU"},"hypotheses":[{"phrase":"создать сайт нейросетью","family":"service","rationale":"Альтернативная формулировка утверждённого направления"}],"proposed_rules":[]}
```

Запиши действительную модель/доступное имя и реальные основания. Не выдумывай transcript, измеренный спрос или независимость от прочитанных подсказок. Маски идут отдельным проверяемым списком; `proposed_rules` оставляй пустым.

Семейства гипотез: `service`, `product`, `job`, `pain`, `situation`, `desired_outcome`, `synonym`, `alternative_formulation`, `commercial`, `informational_question`, `comparison`, `alternative`, `brand`, `competitor`, `geo`, `seasonality`, `audience`, `use_case`, `niche_specific`. До 32 начальных гипотез; отбирай содержательные направления, не заполняй лимит ради числа.

```json
[{"id":"questions","family":"question","operation":"prepend","values":["как","сколько стоит"]},
 {"id":"commercial","family":"modifier","operation":"append","values":["цена","заказать"]}]
```

Правила применяются один раз к исходным seeds. До внешних запросов проверь число probes; профиль допускает до 128 начальных кандидатов. Не размножай автоматически все семейства и алфавит вокруг каждой строки.

| Family | Operation / необходимые поля |
|---|---|
| `prefix`, `question`, `preposition` | `prepend`, `values` |
| `suffix`, `alphabet` | `append`, `values`; для alphabet по одному символу |
| `comparison`, `number` | `prepend` или `append`, `values` |
| `modifier` | `prepend`, `append` или `insert`; для insert нужен `index` |
| `token_insertion` | `insert`, `index`, `values` |
| `word_order` | `swap`, `index`, `other_index`; без values |
| `morphology`, `entity_substitution` | `replace`, `index`, `target`, `values` |
| `niche_specific` | `prepend`, `append`, `insert` или `replace` с соответствующими полями |

## Сравнение

Для каждой темы проведи тот же `guided`-маршрут; согласования представь одним блоком с группами по темам. Используй одинаковые версии предложений, грамматику масок, регион, бюджеты и правила остановки. У `input_context` должен быть общий шаблон, одинаковый после исключения поля `topic`: не помещай туда разные run IDs или topic-specific scout-записи. Обоснования конкретных гипотез могут различаться.

```text
python P compare guided-attach --store S --run-id R_A --run-id R_B
python P compare snapshot --store S --comparison-id C
```

Эти команды связывают сохранённые сборы и создают общий снимок без новых запросов. Сохрани `comparison_id` и `snapshot_id`. Уже связанные управляемые темы продолжай через их `guided`-команды; `compare resume` не обходит согласования. После продолжения обнови общий `compare snapshot`.

Главное условие — равные **выделенные максимумы**, одинаковая методика и политика остановки. Одна тема может естественно закончиться раньше. Сохраняй весь набор другой темы и отдельно фактический расход, успешные/пустые ответы и пропущенную работу. Сбой источника делает exposure неполным; он не требует удалить успешные наблюдения другой темы.

## Остановка и восстановление

- **Бюджет:** покажи накопленный результат и оставшиеся направления. Продолжай только после разрешения увеличить потолок; сохраняй прежний run.
- **Убывание прироста:** код проверяет три слабые порции без новых фраз/поддержки веток, с защитой от ошибок и неисследованных доступных возможностей. Это рабочая остановка, не доказательство полного охвата рынка.
- **Квота:** сохраняй полезную работу; отсутствие capacity не означает исчерпание смысла. Никакого обещания автоматического фонового запуска следующего часа.
- **Ошибка источника:** остальные результаты остаются; назови пробел и возможность продолжить. Не превращай корректный пустой ответ в ошибку.
- **Неоднозначный платный исход:** отсутствие локального результата не доказывает, что провайдер ничего не выполнил. Не отправляй повторно без принятой политики риска.

```text
python P status --store S --kind collect --id R
python P guided checkpoint --store S --run-id R
python P guided resume-capacity --store S --run-id R
```

Последняя команда только готовит известную capacity-paused работу; запросов не делает и согласования не обходит. Затем используй нужную сохранённую фазу.

```text
python P collect extend-budget --store S --run-id R --max-requests NEW_TOTAL --attempt-budget yandex_wordstat=NEW_MAX --max-estimated-wordstat-cost NEW_RUB_CEILING
```

Для одиночного сбора увеличивай согласованные общие пределы, не предел на каждую ветку. Для связанных тем compare увеличивай их одной командой после разрешения пользователя:

```text
python P compare extend-budget --store S --comparison-id C --max-requests NEW_TOTAL --attempt-budget yandex_wordstat=NEW_MAX --max-estimated-wordstat-cost NEW_RUB_CEILING
```

Все переданные потолки применяются одинаково **к каждой теме** и записываются вместе. Они не могут уменьшаться. При увеличении Wordstat код требует актуальный тариф и явный денежный потолок на тему; общую цену объясняй с учётом числа тем. Команда сохраняет comparison ID, run IDs, прежние снимки, измерения и решения по направлениям; внешних запросов не делает. Затем продолжай управляемые темы через их сохранённые `guided`-фазы и обнови `compare snapshot`; обычное сравнение — через `compare resume`. Естественно завершённые темы сохраняют свою смысловую остановку. Одиночное расширение участника compare запрещено.

## Отчёт

Из последнего `snapshot_id`:

```text
python P export --store S --snapshot-id SNAPSHOT --format html --output report.html
python P export --store S --snapshot-id SNAPSHOT --format json --output dataset.json
python P export --store S --snapshot-id SNAPSHOT --format csv --output dataset.csv
```

Экспорт читает сохранённые данные без credentials и внешних запросов. Снимок и актуальная карта веток имеют отдельный контекст/время; не выдавай более поздние решения веток за исходный snapshot.
