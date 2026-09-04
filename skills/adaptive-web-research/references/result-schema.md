# Working records and result contract

These are logical records for the current run. Keep them in available context unless the user explicitly asks for a file. Markdown or JSON is acceptable when the required meaning remains visible.

## Working picture

```text
frame
  goal
  expected_result
  material_boundaries
  temporal_boundary
  source_instructions_and_boundary

directions[]
  branch_id
  parent_branch_id
  goal
  why_material
  status: open | active | closed | deferred | separate_research | dropped | blocked
  gap
  next_action
  stop_reason

search_attempts[]
discoveries[]
readings[]
findings[]
contradictions[]
overall_coverage
unresolved_gaps[]
user_changes[]
next_action_reason
outcome
```

Record source instructions in ordinary language. If named sources are a hard boundary, say that widening is not allowed; if they are a starting priority, say that other suitable sources may be used. Do not require a special mode name or enum.

Do not manufacture source metadata that the host did not return. `searched_at` is the worker-observed time of the actual search attempt, not a claimed backend timestamp.

## Discovery normalization input

Invoke `scripts/normalize_search_results.py` with one JSON object on stdin or as a file argument:

```json
{
  "schema_version": "1.0",
  "discoveries": [
    {
      "research_question": "Which condition is being checked?",
      "query": "exact query sent to native search",
      "search_purpose": "primary",
      "search_round": 1,
      "search_surface": "native_codex",
      "search_outcome": "returned",
      "searched_at": "2026-08-12T12:00:00+03:00",
      "raw_url": "http://www.example.com/page?utm_source=x&version=2#section",
      "title_if_returned": "Optional title",
      "snippet_if_returned": "Optional navigation snippet",
      "native_rank_if_returned": 1,
      "resolved_url": "https://example.com/page?version=2",
      "accepted_canonical_url": "https://example.com/page?version=2"
    }
  ]
}
```

Required discovery fields are `research_question`, `query`, `search_purpose`, `search_round`, `search_surface`, `search_outcome`, `searched_at`, and `raw_url`. `search_purpose` is `primary`, `repeat`, `verify`, or `contrarian`; `search_surface` is `native_codex` in this MVP. Optional metadata is preserved only when actually supplied. `resolved_url` means a redirect was observed. `accepted_canonical_url` means the coordinator has already judged the page's declared canonical suitable; do not pass an unverified declaration under this name.

The helper returns stable `search_attempt_id`, `discovery_id`, and `document_id` values, all discovery records, normalized working keys, URL groups, preferred candidates, and mechanical grouping reasons. It never fetches a page or makes a semantic duplicate decision.

Run:

```powershell
Get-Content -Raw discoveries.json | python <skill-dir>\scripts\normalize_search_results.py --pretty
```

or:

```powershell
python <skill-dir>\scripts\normalize_search_results.py discoveries.json --pretty
```

Keep the output in current context unless the user requested a file.

## Reading and finding record

```text
document_id
requested_url
opened_or_resolved_url
read_at
reading_status: full | relevant_part | partial | blocked | failed
reading_scope_or_limit
source_title_if_available
source_author_or_organization_if_available
published_or_updated_at_if_available
source_role_if_determinable
research_question
finding
finding_role: supports | limits | challenges | context | opens_gap
```

For a material source, preserve the title, author or organization, publication or update date, and source role when they are actually available. Use a short ordinary description for the role, such as official document, primary research, independent analysis, secondary orientation, or user experience; do not force a fixed enum or invent missing metadata. `reading_scope_or_limit` remains the place to record incomplete access.

Do not create a supporting finding from a snippet. Separate repeat readings over time when the content may have changed.

## Luna acquisition return

Require exactly one structured package in JSON or clearly parseable Markdown:

```text
status: complete | partial | failed
question
search_attempts[]
raw_discoveries[]
  research_question
  query
  search_purpose: primary | repeat | verify | contrarian
  search_round
  search_surface: native_codex
  search_outcome
  searched_at
  raw_url
  optional metadata only when actually returned
normalization
  status: complete | unavailable | failed
  error
  records[]
  url_groups[]
readings[]
  document_id
  requested_url
  opened_or_resolved_url
  read_at
  reading_status
  reading_scope_or_limit
  source_title_if_available
  source_author_or_organization_if_available
  published_or_updated_at_if_available
  source_role_if_determinable
findings[]
  statement
  role: supports | limits | challenges | context | opens_gap
  document_id
  opened_or_resolved_url
  reading_status
  reading_scope_or_limit
contradictions[]
gaps[]
next_candidates[]
  candidate
  why_material
```

`raw_discoveries` is the exact batch given to the helper. On successful normalization, `normalization.records` and `normalization.url_groups` are the helper output. If normalization is unavailable or fails, keep the raw discoveries, put the reason in `normalization.error`, leave readings and findings empty for those candidates, and return `partial` or `failed`. Coordinator validation, not the worker's `status`, decides whether the package is usable.

## Terra analysis and Sol escalation return

Analysis and review workers use the same outer status and question but do not imitate acquisition. They return:

```text
status: complete | partial | failed
question
input_documents[]
  document_id or supplied_url
reopened_readings[]
  document_id or supplied_url
  reading_status
  reading_scope_or_limit
  source_title_if_available
  source_author_or_organization_if_available
  published_or_updated_at_if_available
  source_role_if_determinable
findings[]
  statement
  role: supports | limits | challenges | context | opens_gap
  supporting_document_ids_or_urls[]
contradictions[]
gaps[]
  evidence_target
  why_material
limitations[]
```

Terra normally analyzes the supplied packet and may reopen its URLs. A new evidence target goes back to Luna. Sol receives the same bounded form only after the coordinator records the material reason for escalation.

## Final outcome and answer

Choose one:

- `complete`: evidence is sufficient for the scoped answer;
- `partial`: useful evidence exists, but a material gap remains;
- `stopped_by_user`: the user ended the run;
- `limited_by_budget_or_permission`: an explicit resource or permission boundary prevented completion;
- `technical_failure`: the required technical route failed before a responsible answer could be built.

Return the answer with this upper-level function:

1. direct answer, conclusion, comparison, recommendation, or explanation;
2. main analysis with task-specific sections;
3. limitations and uncertainty;
4. practical outcome or next step when useful.

Put a clickable link next to each material claim it supports. Do not rely on a detached bibliography to establish the relationship.

## User change, stop, and continuation boundary

Record a material user change with enough meaning to prevent silent mixing:

```text
received_change
received_at
accepted: true | false
applied: true | false
affected_scope
superseded_items[]
new_revision_boundary
```

On `stopped_by_user`, or when the coordinator recognizes that safe continuation is no longer possible, the coordinator itself returns a compact package in chat:

```text
outcome
frame_and_source_instructions
completed_work[]
confirmed_findings_with_links[]
unresolved_gaps[]
user_changes[]
in_flight_or_unknown_operations[]
next_safe_action
continuation_limit
```

This is an honest handoff of known state, not proof of automatic resume and not a promise that the skill can intercept host compaction.

## Optional saved continuation packet or report

Create a file only on explicit user request. If no path is named, propose a readable file such as `.research/YYYY-MM-DD-short-topic.md`. A saved continuation packet preserves:

- what is being researched;
- where work stopped;
- what supports the current conclusions;
- what was actually completed and what remains unknown.

A final report preserves the chat answer and its links. If both are requested, distinguish them clearly in the same file or use two explicitly agreed files. Read back the saved artifact. Do not edit `.gitignore`, create an index, or claim automatic resume.
