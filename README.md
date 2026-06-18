# Codex Skills

Личная коллекция Agent Skills для Codex.

Это не демо-набор и не библиотека абстрактных команд. Здесь собраны рабочие
процедуры, которые делают Codex более устойчивым: помогают сохранять состояние,
передавать работу в новый чат, консолидировать длинные обсуждения перед
решениями, вовремя отступать на уровень выше, вести проектные задачи и собирать
визуальные промпты без превращения каждого диалога в ручной процесс.

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

1. `export-current-thread` - получить `.txt` текущей Codex-ветки.
2. `discussion-rfc-consolidator` - собрать RFC: решения, отказы, развилки,
   риски и вопросы перед финальным документом.

## Навыки

| Skill | Тип | Когда использовать |
| --- | --- | --- |
| [`zoom-out`](skills/zoom-out) | Глобальный | Когда надо отступить на уровень выше, проверить рамку, риски, факты и цель перед действием. |
| [`handoff`](skills/handoff) | Глобальный | Когда нужно сохранить рабочее состояние и дать следующему Codex-чату готовый стартовый prompt. |
| [`discussion-rfc-consolidator`](skills/discussion-rfc-consolidator) | Глобальный | Когда нужно превратить экспорт длинного обсуждения в RFC-консолидацию решений перед design doc или реализацией. |
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
| `discussion-rfc-consolidator` | [`skills/discussion-rfc-consolidator`](skills/discussion-rfc-consolidator) |
| `export-current-thread` | [`skills/export-current-thread`](skills/export-current-thread) |
| `handoff` | [`skills/handoff`](skills/handoff) |
| `zoom-out` | [`skills/zoom-out`](skills/zoom-out) |
| `universal-visual-prompt-builder` | [`skills/universal-visual-prompt-builder`](skills/universal-visual-prompt-builder) |
| `manage-project-tasks` | [`skills/manage-project-tasks`](skills/manage-project-tasks) |
| `nearest-clarity` | [`skills/nearest-clarity`](skills/nearest-clarity) |

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

### `discussion-rfc-consolidator`

Превращает экспорт длинного обсуждения в RFC-консолидацию перед финальным
design doc, architecture brief, implementation plan или созданием нового skill.

Главный результат - не пересказ чата, а Decision Ledger и полный RFC: что
принято, что отвергнуто, что заменено, что только предложено, где развилки,
риски и вопросы перед реализацией.

Если экспорт уже есть, skill использует его. Если нужен текущий Codex thread,
он может использовать `export-current-thread`; если его нет, внутри есть
fallback-скрипт экспорта.

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
- отделяет verified facts, reported claims, assumptions и unknowns;
- проверяет decision-critical foundations;
- вводит Execution Frame;
- явно борется с overconfidence и решением не той задачи.

## Структура репозитория

```text
skills/
  discussion-rfc-consolidator/
    agents/
    references/
    scripts/
    SKILL.md
  export-current-thread/
    agents/
    scripts/
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
