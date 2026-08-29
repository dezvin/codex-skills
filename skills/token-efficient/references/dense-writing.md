# Dense Writing

Read this file fully when wording itself is material: the artifact contains substantial prose, the user asks for denser language, or the first candidate remains verbose.

## Preserve semantic atoms

Keep every proposition, condition, negation, exception, scope boundary, priority, order constraint, decision-relevant cause, exact term, number, unit, path, identifier, command, safety rule, and correctness requirement that the task needs.

Compress wording, not meaning.

## Prefer direct constructions

- Use an imperative verb for an instruction: `Проверь файл` rather than `Выполни проверку файла`.
- Use active voice when the actor matters.
- Put the condition next to its action: `Если X, сделай Y`.
- State order directly: `Сделай X перед Y`.
- State a default with its exception: `Используй X, кроме случая Y`.
- Choose the shortest familiar word that preserves the exact meaning.
- Combine clauses that share one condition or consequence when the result stays clear.
- Split a sentence when density would make its logic ambiguous.

## Remove lexical padding

Delete language that only announces or comments on the statement:

```text
Важно отметить, что X.        -> X.
Необходимо выполнить X.       -> Сделай X.
В случае если X...            -> Если X...
Для того чтобы X...           -> Чтобы X...
Имеет возможность X.          -> Может X.
Существует необходимость X.   -> Нужно X.
Осуществить проверку X.        -> Проверить X.
Принять решение о выборе X.    -> Выбрать X.
```

Remove metadiscourse, throat-clearing, generic emphasis, redundant qualifiers, nominalizations, expanded logical connectors, and repeated subjects or context already unambiguous.

## Remove discourse redundancy

Do not use:

- introduction -> content -> repeated conclusion;
- rule -> explanation -> paraphrase of the rule;
- thesis -> example -> restatement when the thesis is already clear;
- a heading that repeats its first sentence;
- rationale that does not change how a rule is applied;
- several examples proving the same unambiguous point.

Each sentence must add a required fact, distinction, condition, exception, decision, or action. Remove it otherwise.

## Keep language natural

Plain language optimizes understanding; density optimizes meaning per word. Preserve both.

Do not use:

- invented abbreviations;
- omitted grammar that slows parsing;
- fragments used only to look short;
- excessive symbols or arrow chains;
- jargon replacing a clearer familiar term;
- sentences packed with so many relations that the reader must decode them.

Prefer readable concise prose to superficially shorter shorthand.

## Final pass

1. Identify the semantic atoms that must remain.
2. Delete content that carries none.
3. Merge overlapping statements.
4. Replace verbose phrases with direct verbs and conditions.
5. Compare the result with the semantic atoms.
6. Restore any loss in the shortest unambiguous form.
7. Stop when further compression would reduce meaning or clarity.
