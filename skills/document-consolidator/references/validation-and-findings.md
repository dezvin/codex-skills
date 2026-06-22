# Validation And Findings

Validation proves that the new document still does its job.

## Candidate Checks

After creating a candidate:

- read it back from disk;
- compare it with the source material by function, not by phrase matching;
- check protected anchors;
- check that no stronger unsupported claims appeared;
- check that unfinished work did not become resolved prose;
- check that service traces did not leak into the main document;
- check that the document can be used without knowing the editing conversation;
- check UTF-8 readability for Cyrillic text;
- check relative source links when a consolidated document is involved.

## Instructional Scenario Checks

For risky instructional documents, derive 5-10 scenarios from the source document.

For each scenario, verify the candidate gives the same answer about:

- when to start;
- what to read;
- what to preserve;
- when to ask;
- when to stop;
- what is forbidden;
- what output is required;
- what status, field, path, or command matters.

Do not invent generic scenarios that are not grounded in the document.

## Finding Format

Use findings only for meaningful losses or risks:

```text
Severity: P1/P2/P3
Что потеряно или ослаблено:
Где было:
Где стало:
Почему это важно:
Как исправить без раздувания:
```

Severity:

- `P1`: changes behavior, loses evidence, breaks source role, or risks data loss.
- `P2`: creates ambiguity, weakens a rule, or hides unresolved work.
- `P3`: local clarity issue or low-risk cleanup problem.

After findings, stop before fixing if the fix changes scope, output role, protected anchors, or file operations.

## Final Chat Report

Keep it short. Include only:

- what was created, compressed, consolidated, or moved;
- what was excluded and why;
- what remains uncertain;
- links updated or link risks;
- checks completed;
- whether backup cleanup can be offered.

Do not include a step-by-step operation journal unless something failed.
