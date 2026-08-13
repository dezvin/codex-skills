# Research expansion

Use this reference after reading reveals a possible new direction. A new link or term is not automatically a new branch.

## Candidate sources

Extract only candidates that may affect the answer:

- terms and concepts;
- cited or citing sources;
- authors and related work;
- methods, projects, and tools;
- benchmarks, datasets, and evaluation methods;
- standards and specifications;
- criticism, limitations, and failure modes;
- competing explanations and alternatives;
- relevant evidence not yet integrated into the working picture.

Keep the parent finding or document and the reason the candidate appeared.

## Decision gate

Open a branch only when all are true:

1. it is a distinct question rather than another label for an existing branch;
2. it can materially change, qualify, or de-risk the answer;
3. it lies within the current scope;
4. a concrete allowed search or reading action can test it;
5. another active branch does not already cover it.

Choose one outcome:

- `search`: investigate now;
- `background`: retain as context without spending a branch;
- `separate_research`: important but outside the current scope;
- `discard`: weak, duplicate, irrelevant, or not decision-relevant.

Record the reason. Do not show an internal graph to the user unless it materially helps or the user asks.

## Rank competing branches

Prefer the branch with the strongest combination of:

- expected effect on the final answer;
- size of the current evidence gap;
- risk if left unresolved;
- likelihood that an available action will resolve it;
- novelty relative to completed work;
- reasonable resource cost.

Depth is provenance and a protective ceiling, not a quality score. A free worker slot is not a reason to create a branch.

## Share context without flooding workers

Give a branch worker:

- its question and evidence target;
- why the answer matters;
- material boundaries and source policy;
- only dependencies and global gaps needed to avoid duplicate work;
- relevant prior findings and URLs;
- the common return contract.

Do not send the full corpus by default. Merge the result into the coordinator's shared coverage picture before opening dependent work.

## Stop expansion

Stop opening branches when candidates only repeat known material, add minor detail, lie outside scope, cannot be tested with available permissions or sources, or cannot materially change the answer. Preserve an important excluded direction as `separate_research` rather than silently losing it.
