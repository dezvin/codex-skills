# Output Templates

Use plain language. Do not lead with internal mode names unless useful.

## Sprawl Map

```text
Похоже, тут не одна правка, а разрастание документов.

Краткая карта:
- [file]: роль, что хранит, риск
- [file]: роль, что хранит, риск

Что можно сделать:
1. [nearest safe segment]
2. [later optional segment]

Я бы начал с: [next action].
Без записи файлов на этом шаге.
```

## Protected Anchor Confirmation

```text
Моё предположение: этот документ нужен для [function].

Защищаю:
- [anchor]
- [anchor]

Можно сжимать сильнее:
- [low-risk material]

Неясно:
- [question]

Утвердить эту карту перед правкой?
Ответ: да / поправить / остановиться.
```

## Dry Run

```text
Файл пока не создаю. Показываю будущую структуру.

Будущий документ:
- [section]
- [section]

Что откуда попадёт:
- [source] -> [section]

Спорное:
- [conflict or unknown]

Следующий безопасный шаг:
[action]
```

## Write Confirmation

```text
Нужно подтверждение записи.

Сделаю:
- создам [candidate]
- после проверки заменю [target]
- старую версию перенесу в [_backup/...]

Не трону:
- [excluded files]

После записи проверю:
- чтение файла
- защищённые смыслы
- ссылки/кириллицу, если применимо

Ответ: да / поправить / остановиться.
```

## Final Report

```text
Готово: [human result].

Проверил:
- [check]
- [check]

Не вошло / осталось отдельно:
- [file/reason]

Осталось решить:
- [question/risk]
```
