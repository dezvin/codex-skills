# Compression

Compression means preserving document function while reducing noise and improving density.

## Function First

Before editing, identify:

- why the document exists;
- who or what uses it;
- what the reader must understand, decide, verify, or do;
- which parts are current meaning;
- which parts are source, evidence, context, or original wording;
- which parts are unfinished work;
- which parts are service traces or removable repetition.

If the function is unclear, state your best guess and ask before editing.

## Protected Anchors

Protect anything whose loss can change function, evidence, or behavior:

- facts, numbers, dates, names, links, paths, commands, fields, and formats;
- sources and provenance needed for trust;
- boundaries and applicability;
- important examples;
- open questions, blockers, TODOs, and statuses;
- conditions, order, exceptions, and stop points;
- rules, prohibitions, approvals, and ownership;
- original wording when it is evidence or a current decision.

Evidence is more important than brevity. If shortening would reduce proof or checkability, keep the evidence or report that compression is unsafe.

The lists in this skill are examples, not closed menus. If a fragment is not named here, classify it by function, risk, and effect on the document before compressing it.

Before substantive compression or restructuring, show the protected-anchor map and get explicit approval. The map must separate protected anchors, low-risk material, and unclear items. Without approval, stay in analysis or dry-run mode.

## Ordinary Document Compression

Allowed:

- remove repetition without separate meaning;
- shorten explanatory tails;
- merge adjacent fragments with the same condition and purpose;
- remove service traces if they are not content;
- replace heavy wording with simple working language;
- restructure sections when it preserves function.

Forbidden:

- turn a specific case into a vague rule;
- weaken a prohibition, requirement, or approval;
- remove a source needed for trust;
- remove a caveat that changes applicability;
- remove unfinished work by making it look resolved;
- make claims stronger than the source supports.

Do not leave process traces in the main document: before/after wording, proof-pass notes, read-back status, diff explanations, or comments about how the document was edited. Keep those in chat unless the history itself is the document's content.

## Instructional Document Compression

Use this stricter path for process docs, runbooks, rules, approvals, workflow instructions, and guardrails.

Preserve:

- trigger conditions;
- step order;
- stop rules;
- required questions;
- approval points;
- ownership;
- forbidden actions;
- exact paths, statuses, commands, and field names;
- fallback or degraded behavior;
- differences between modes.

For risky instructional documents, derive 5-10 validation scenarios from the document itself. Do not invent generic scenarios. Each scenario should check whether the compressed version gives the same answer about when to continue, stop, ask, read, write, or refuse.

## When Not To Compress

Say compression is unsafe when:

- every section carries evidence, rules, or unresolved state;
- the text is long because it preserves proof;
- source roles are mixed and not yet mapped;
- the document is a raw/source record whose roughness is content;
- you cannot validate the new version against protected anchors.

Offer restructuring or navigation improvements instead of forced shortening.
