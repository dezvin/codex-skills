# Codex Skills

Личная коллекция Agent Skills для Codex.

Это не демо-набор и не библиотека абстрактных команд. Здесь собраны рабочие
процедуры, которые делают Codex более устойчивым: помогают сохранять состояние,
передавать работу в новый чат, консолидировать длинные обсуждения перед
решениями, проектировать реализацию перед действием, вовремя отступать на
уровень выше, вести проектные задачи и собирать визуальные промпты без
превращения каждого диалога в ручной процесс.

## С чего начать

Если хочется поставить минимальный набор:

1. `zoom-out` - чтобы Codex не решал не ту задачу.
2. `handoff` - чтобы переносить работу в новый чат без потери контекста.
3. `export-current-thread` - чтобы сохранять текущую ветку в `.txt`, когда
   нужно вынести историю наружу.

Если нужен проектный слой памяти:

1. Установить `manage-project-tasks` через project installer.
2. Установить `nearest-clarity`, если в проекте часто есть неопределённость,
   короткие итерации и меняющаяся рамка работы.

Если длинное обсуждение уже распухло перед реализацией:

1. `design-pass` - разобрать решения по доступному контексту и подготовить
   проект реализации, карту влияния и команду для следующего агента.
2. Если доступной части разговора недостаточно, дать готовый экспорт или
   разрешить `design-pass` создать технический `.txt` после явного вопроса.
3. Ответить на критические вопросы, если они есть; после ответов тот же
   `design-pass` автоматически закончит проектирование.

Если `.txt` нужен как отдельный артефакт, можно заранее явно запустить
`export-current-thread`.

Если идея ещё не готова к проектированию:

1. `grill-me` - проверить план сильными вопросами, найти важные развилки и
   отсечь мелочи, которые агент должен решить сам.

Если накопился документальный разрос:

1. `document-consolidator` - безопасно сжать или объединить `.md`/`.txt`
   документы без потери фактов, правил, ссылок и незавершённой работы.

## Навыки

| Skill | Тип | Когда использовать |
| --- | --- | --- |
| [`zoom-out`](skills/zoom-out) | Глобальный | Когда надо отступить на уровень выше, проверить рамку, риски, факты и цель перед действием. |
| [`handoff`](skills/handoff) | Глобальный | Когда нужно сохранить рабочее состояние и дать следующему Codex-чату готовый стартовый prompt. |
| [`design-pass`](skills/design-pass) | Глобальный | Когда нужно разобрать решения из обсуждения или довести подтверждённые решения до проекта реализации, проверок и handoff-команды. |
| [`grill-me`](skills/grill-me) | Глобальный | Когда нужно стресс-тестировать идею или план одним сильным вопросом за раз, не превращая работу в бесконечный опрос. |
| [`document-consolidator`](skills/document-consolidator) | Утилита | Когда нужно разобрать, сжать или объединить Markdown/text-документы без потери их рабочей функции. |
| [`export-current-thread`](skills/export-current-thread) | Утилита | Когда нужно явно экспортировать текущую Codex-ветку в локальный `.txt` файл. |
| [`universal-visual-prompt-builder`](skills/universal-visual-prompt-builder) | Глобальный | Когда нужен переносимый визуальный prompt для image models, без генерации изображения. |
| [`manage-project-tasks`](skills/manage-project-tasks) | Project workflow | Когда проекту нужен долговременный `TODO.md`, статусы задач и архив закрытой работы. |
| [`nearest-clarity`](skills/nearest-clarity) | Project workflow | Когда работа идёт через ближайшую ясность: короткие итерации, сигналы, проверяемые участки и честную неопределённость. |

## Типы

**Глобальный skill** ставится один раз в Codex skills и используется в любых
чатах.

**Утилита** вызывается явно для конкретного действия. Например,
`export-current-thread` не должен включаться сам.

**Project workflow** ставится внутрь конкретного проекта и обычно требует
изменения корневого `AGENTS.md`. Это уже не просто skill-папка, а маленький
рабочий контракт для проекта.

## Установка одного глобального skill

Попросите Codex:

```text
Use $skill-installer to install a skill from:
https://github.com/dezvin/codex-skills/tree/main/skills/<skill-name>
```

Например:

```text
Use $skill-installer to install a skill from:
https://github.com/dezvin/codex-skills/tree/main/skills/handoff
```

Или из терминала PowerShell:

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" `
  --repo dezvin/codex-skills `
  --path skills/handoff
```

После установки перезапустите Codex, чтобы новый skill появился в списке
доступных.

## Пути для установки

| Skill | GitHub path |
| --- | --- |
| `design-pass` | [`skills/design-pass`](skills/design-pass) |
| `grill-me` | [`skills/grill-me`](skills/grill-me) |
| `document-consolidator` | [`skills/document-consolidator`](skills/document-consolidator) |
| `export-current-thread` | [`skills/export-current-thread`](skills/export-current-thread) |
| `handoff` | [`skills/handoff`](skills/handoff) |
| `zoom-out` | [`skills/zoom-out`](skills/zoom-out) |
| `universal-visual-prompt-builder` | [`skills/universal-visual-prompt-builder`](skills/universal-visual-prompt-builder) |
| `manage-project-tasks` | [`skills/manage-project-tasks`](skills/manage-project-tasks) |
| `nearest-clarity` | [`skills/nearest-clarity`](skills/nearest-clarity) |

## Design Pass

`design-pass` объединяет проверку решений и проектирование перед реализацией.
Сначала он устанавливает, что пользователь действительно принял, отверг,
заменил или оставил открытым. Только после этого превращает подтверждённые
решения в требования, ограничения, устройство результата, карту влияния,
проверки и handoff-команду.

Skill можно использовать в двух формах:

- только разобрать решения, противоречия и открытые вопросы;
- пройти полный путь до handoff-ready design.

Пользователю не нужно запоминать отдельную команду режима. Если намерение
понятно из запроса, `design-pass` выбирает результат сам. Если нет - задаёт
один короткий вопрос.

Источником может быть текущий доступный контекст, вставленный текст, локальный
`.txt`/`.md`, готовый экспорт, Decision Ledger или ранее подготовленный
preflight-brief. Ограниченный контекст помечается честно. Если отсутствие
ранней истории может изменить решение, skill просит источник или явное
согласие на технический экспорт; молча файл не создаётся.

Если для дизайна нужны критические ответы, skill показывает уже установленные
решения и задаёт только вопросы, которые меняют границы или устройство. После
ответов он продолжает автоматически, без повторного вызова.

Результат `design-pass` - не код и не прямое внедрение. Он готовит отдельную
реализацию: требования, guardrails, traceability, проверки, readiness status и
готовую команду для следующего Codex-чата.

## Project workflow installers

`manage-project-tasks` и `nearest-clarity` лучше ставить не как обычные
глобальные skills, а через project installer.

Project installer - это bootstrap-документ для Codex. Он не дублирует
содержимое skill-файлов. Каноническое содержимое лежит в `skills/<skill-name>/`,
а installer объясняет, как встроить workflow в конкретный проект:

- скопировать project skill в `.agents/skills/...`;
- обновить корневой `AGENTS.md`;
- сохранить существующие проектные правила;
- не создать второй конфликтующий workflow;
- показать финальный diff перед коммитом.

### Task system

Из корня целевого проекта попросите Codex:

```text
Read and apply this installer to the current project:
https://raw.githubusercontent.com/dezvin/codex-skills/main/installers/codex-todo-system.md

Install only the necessary project files, preserve existing project conventions
when the installer allows it, and show the final diff before committing.
```

Что появится в проекте:

- короткий раздел `Project Task Tracking` в `AGENTS.md`;
- `.agents/skills/manage-project-tasks/`;
- `TODO.md`, если его ещё нет;
- ленивый архив закрытых задач, например `archive/tasks/YYYY-MM.md`.

### Nearest clarity

Из корня целевого проекта попросите Codex:

```text
Read and apply this installer to the current project:
https://raw.githubusercontent.com/dezvin/codex-skills/main/installers/nearest-clarity-method.md

Install only the necessary project files, preserve existing project conventions
when the installer allows it, and show the final diff before committing.
```

`nearest-clarity` ожидает, что глобальный `zoom-out` доступен. Во время
итерационной работы `nearest-clarity` остаётся родительским процессом, а
`zoom-out` используется только как зависимый пересмотр рамки, когда меняется
основание работы.

## Skill-only установка project workflow

Используйте skill-only установку для `manage-project-tasks` и
`nearest-clarity` только если проект уже подготовлен: есть правильный
`AGENTS.md`, понятная task-система или согласованная политика workflow.

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" `
  --repo dezvin/codex-skills `
  --path skills/manage-project-tasks `
  --dest .agents\skills
```

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" `
  --repo dezvin/codex-skills `
  --path skills/nearest-clarity `
  --dest .agents\skills
```

Важно: стандартный installer падает, если destination skill directory уже
существует. Для обновления существующего project skill сначала проверьте, что
это тот же совместимый workflow, и только потом обновляйте файлы на месте.

## Коротко по каждому skill

### `zoom-out`

Заставляет Codex сменить масштаб перед действием: понять класс задачи, систему,
факты, допущения, риски, зависимости, критерий успеха и только потом решать.

Особенно полезен для стратегии, маркетинга, research, agent instructions,
сложных документов, незнакомого кода и задач, где легко сделать красивую, но
не ту работу.

### `handoff`

Создаёт handoff-файл и готовый prompt для нового Codex-чата. Это не пересказ
разговора, а перенос рабочего состояния: цель, решения, ограничения, источники
правды, сделанное, оставшееся и следующий шаг.

Если пользователь дал существующий handoff-файл и попросил обновить его, skill
обновляет этот файл in place. Если создаётся новый handoff и имя занято,
создаётся numbered copy.

### `design-pass`

Разбирает текущий контекст, экспорт, Decision Ledger или другой источник
решений и либо останавливается на компактной сверке, либо готовит проект
реализации перед отдельным запуском агента.

Главный результат полного режима - handoff-ready design: что должно
измениться, какие требования и ограничения подтверждены, какие части системы
или процесса затрагиваются, как это проверить и можно ли отдавать задачу в
реализацию.

Skill не принимает предложения ассистента за решения пользователя, не создаёт
экспорт без согласия и не требует отдельного preflight. Если нужны критические
ответы, после них он продолжает автоматически. Необязательные таблицы и views
появляются только когда действительно помогают контролировать результат.

Skill специально не реализует проект сам. Он готовит следующего агента:
связывает решения с изменениями и проверками, ставит readiness status и даёт
готовую команду для нового Codex-чата.

### `grill-me`

Стресс-тестирует идею, план или дизайн до реализации: задаёт один сильный
вопрос за раз, объясняет зачем он нужен, предлагает рекомендуемый ответ и
останавливается, когда оставшиеся детали можно безопасно принять дефолтом.

Эта версия особенно бережёт внимание пользователя: не спрашивает про мелочи,
не заставляет выбирать домен из меню и для non-tech задач сначала понимает
форму работы - что создаётся, для кого, какой результат нужен, где риски,
границы и самый маленький полезный тест.

### `document-consolidator`

Помогает безопасно уменьшать документальный разрос: сначала понимает роль
каждого `.md`/`.txt` файла, потом предлагает сжатие, объединение или план
уборки без потери доказательств, правил, решений, ссылок и открытой работы.

Skill специально работает через candidate-файлы и подтверждения перед заменой
или перемещением источников. Он не предназначен для `SKILL.md`, prompt-файлов,
обычной редакторской правки, публикационных текстов, `.docx`, PDF или кода.

### `export-current-thread`

Явная утилита для экспорта текущей Codex-ветки в `.txt`. Полезно, когда нужно
сохранить разговор как артефакт, отдать его другому инструменту или вынести из
Codex историю работы.

Skill не вставляет transcript в чат, а сохраняет файл и возвращает ссылку на
него.

### `universal-visual-prompt-builder`

Помогает делать переносимые image prompts: от идеи, референса или слабого
промпта к структурированному описанию сцены, стиля, камеры, формата, текста,
вариантов и исправлений.

Он не генерирует картинки. Его задача - сделать prompt, который можно нести в
другие image models.

### `manage-project-tasks`

Проектная система долговременных задач. Хранит открытые задачи в `TODO.md`,
закрытые задачи - в месячном архиве. Разделяет короткие session tasks и то, что
должно пережить текущую сессию.

Главная идея: не превращать чат в память проекта и не превращать `TODO.md` в
дневник мыслей.

### `nearest-clarity`

Workflow для сложной работы, где нельзя честно расписать весь маршрут заранее.
Он держит целевой контур, выбирает ближайший понятный участок, заранее называет
ожидаемый сигнал, после итерации считывает фактический сигнал и обновляет
следующий шаг.

Подходит для исследований, продукта, контента, стратегии, пересборки workflow и
других задач, где ясность появляется по ходу движения.

## Происхождение и адаптации

`handoff` основан на минимальном productivity skill Мэтта Покока:
[`handoff`](https://github.com/mattpocock/skills/blob/main/skills/productivity/handoff/SKILL.md).

Эта версия сильнее заточена под Codex:

- создаёт не только handoff-файл, но и готовую команду для нового чата;
- сохраняет project handoff в ближайший project root;
- различает факты, допущения и то, что надо проверить;
- поддерживает non-dev задачи;
- не использует `argument-hint` во frontmatter.

`zoom-out` вдохновлён инженерным skill Мэтта Покока:
[`zoom-out`](https://github.com/mattpocock/skills/blob/main/skills/engineering/zoom-out/SKILL.md).

Эта версия расширяет идею за пределы кода:

- работает для стратегии, research, маркетинга, контента и agent workflows;
- считает `zoom out` полной командой, без выбора подрежима пользователем;
- умеет выходить из зацикливания и менять рамку, если локальный ответ снова
  не попадает в задачу;
- отделяет verified facts, reported claims, assumptions и unknowns;
- проверяет decision-critical foundations;
- вводит Execution Frame;
- явно борется с overconfidence и решением не той задачи.

`grill-me` основан на productivity skill Мэтта Покока:
[`grill-me`](https://github.com/mattpocock/skills/blob/main/skills/productivity/grill-me/SKILL.md).

Исходная идея сильная: агент интервьюирует пользователя и помогает пройти по
дереву решений до общего понимания. Но в практической работе формулировки в
духе "relentlessly" и "every aspect" легко превращаются в бесконечный допрос:
агент начинает спрашивать про формат timestamp, названия и другие мелочи,
которые должен решить сам.

Эта версия исправляет именно это:

- спрашивает только то, что меняет цель, риск, границы, ответственность,
  поведение или следующий шаг;
- принимает разумные дефолты для обратимых и низкорисковых деталей;
- делает checkpoint после 5-7 сильных вопросов для non-tech задач;
- адаптируется через форму работы, а не через список доменов;
- выдаёт `Grill Result` как карту решений, а не design doc и не план
  реализации.

## Структура репозитория

```text
skills/
  design-pass/
    agents/
    references/
    scripts/
    SKILL.md
  document-consolidator/
    agents/
    references/
    scripts/
    SKILL.md
  export-current-thread/
    agents/
    scripts/
    SKILL.md
  grill-me/
    agents/
    SKILL.md
  handoff/
    SKILL.md
  manage-project-tasks/
    agents/
    references/
    SKILL.md
  nearest-clarity/
    agents/
    references/
    SKILL.md
  universal-visual-prompt-builder/
    agents/
    references/
    SKILL.md
  zoom-out/
    agents/
    SKILL.md
installers/
  codex-todo-system.md
  nearest-clarity-method.md
```

Каждый skill лежит в отдельной папке, чтобы его можно было устанавливать
независимо. Project workflow installers лежат отдельно, потому что они могут
менять файлы за пределами skill-папки.

## Проверка

Для быстрой проверки skill:

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" `
  ".\skills\<skill-name>"
```

Для установки из этого репозитория во временную папку:

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py" `
  --repo dezvin/codex-skills `
  --path skills/<skill-name> `
  --dest "$env:TEMP\codex-skill-test"
```
