# Downstream contract

`Router.route(query)` returns exactly one `RouteResult`. Its `status` says what the router
found. Its `next_action` says what the caller must do next. Every layer after the router
(retrieval, generation, an orchestrating agent) follows one rule:

> **Text reaches generation only through a bound coordinate.**

A caller that retrieves from an open vector search after anything other than
`ROUTE_BOUNDED` has left the contract. That includes an unresolved query ("the router found
nothing, so search everything"). The guarantees the router is measured on then no longer
hold: collisions, invented law and misroutes.

## 1. Status → next action

| Status | `next_action` | Caller does | Caller must not |
|---|---|---|---|
| `ROUTE_BOUNDED` | `RETRIEVE_BOUNDED` | Retrieve only through `partition_filter(result)` (§3) | Widen the filter, drop the `and not (…)` exclusions, or add instruments |
| `ROUTE_AMBIGUOUS` | `ASK_USER` | Show `clarification` and `candidates`, then route the user's answer again | Pick a candidate silently, or retrieve from all candidates |
| `EPISTEMIC_ABSTENTION_INSTRUMENT_NOT_FOUND` | `REFUSE` | Refuse with `messages`, `suggestions` and `index_snapshot` | Retry retrieval, or override the refusal from any source other than the official registry (§4) |
| `EPISTEMIC_ABSTENTION_PROVISION_NOT_FOUND` | `REFUSE` | As above | As above |
| `ROUTE_OUT_OF_COVERAGE` | `VERIFY_LIVE` if a deciding citation is `live_checkable`, else `DECLARE_OUT_OF_COVERAGE` | Say the citation is outside the indexed corpus, or check the registry (§4) | Answer from other law, or treat a web page as proof the instrument exists |
| `ROUTE_UNRESOLVED` | `DISCOVER_THEN_BIND` | Discover candidate *coordinates*, confirm one, and route it (§5) | Generate from open retrieval |

When a query holds several citations, the most cautious outcome decides the status. The
priority is instrument not found > provision not found > ambiguous > out of coverage >
bound > unresolved. For example, "ERA 1996 s.124 and SI 2011/9999" is refused as a whole,
and one out-of-coverage citation beside bound ones makes the query `ROUTE_OUT_OF_COVERAGE`
(roadmap decision 14). Every recognised citation is still listed in `citations`, with its
own `resolution`. None is dropped silently.

## 2. The result fields a caller uses

| Field | Meaning |
|---|---|
| `coordinates` | Bound coordinates (`ROUTE_BOUNDED` only). An instrument coordinate binds the whole instrument |
| `excluded` | Coordinates the query explicitly excludes ("all sections except section 124"). The filter removes them and their subtrees |
| `candidates`, `clarification` | What to offer the user (`ROUTE_AMBIGUOUS`) |
| `suggestions`, `corrections` | Close real titles for a refusal, and the typo corrections the router applied when it bound |
| `citations` | Every `ParsedCitation` found, with its span, what was cited and its `resolution` (`resolved`, `not_in_index`, `out_of_coverage`, `unlinked`, `excluded`) and `live_checkable` |
| `reason` | A machine-readable detail for non-bound outcomes (`year_only`, `case_variants`, `provision_structure_unavailable`, `chapter_mismatch` …) |
| `messages` | Human-readable refusal and coverage wording, and notes on how a citation was read ("“Supreme Court Act 1981” is a former title of the Senior Courts Act 1981.", "“PACE 1984” read as the Police and Criminal Evidence Act 1984.") |
| `source` | `grammar`, `identifier` or `context`: `context` means a follow-up was bound against the previous turn's coordinates |
| `repealed` | The bound instrument is repealed. It is still bound, never refused |
| `temporal_hint` | Raw text such as "as it stood in 2012" or "as enacted". Phase 1 binds the current text and passes the hint through. It is never read as the instrument's year |
| `index_snapshot` | The date the index was built from. Always set, and quoted in every refusal |

## 3. Retrieval: the partition filter

`partition_filter(result)` turns a bound result into a boolean expression over the two
fields every stored chunk carries, `instrument_id` (the partition key) and `coordinate`:

```text
instrument_id in ["uk_ukpga_1996_18"]
  and (coordinate == "uk/ukpga/1996/18/s124" or coordinate like "uk/ukpga/1996/18/s124/%")
  and not (coordinate == "uk/ukpga/1996/18/s98" or coordinate like "uk/ukpga/1996/18/s98/%")
```

- `like "p/%"` includes every sub-provision, and keeps `s124` from matching `s124A`.
- It raises `FilterError` for any status other than `ROUTE_BOUNDED`. There is no filter to
  widen, because an unbound result has none.
- Every value is checked against the coordinate grammar and a closed alphabet before it is
  interpolated, so nothing taken from a query can inject into the expression.

## 4. Live checks: strict and confirm mode

`VERIFY_LIVE` is an instruction to the caller. **The router never goes online.** It means:
"I recognised this citation, but my offline index can't confirm it. Ask the official
registry before you answer or refuse."

`ParsedCitation.live_checkable` is true when both of these hold:

1. The citation carries enough identity to look up: type + year + number, title + year, or
   an identifier.
2. Its jurisdiction declares an official registry (UK: legislation.gov.uk; Spain: the BOE).

It is also limited by a **freshness window**, so that invented law is still refused
instantly:

- A citation to a series the index covers is live-checkable only if its year is the
  snapshot year or later, or its number is above the highest one indexed for its year
  (`SI 2026/450` when the index stops at `2026/380`).
- Everything else in a covered series is a **closed period**, refused offline even in
  confirm mode. Examples: "Marchwood Order 2022", "ERA 1996 s.999", "SI 2011/9999".
- Series and jurisdictions the index does not cover are always live-checkable when a
  registry exists.

| Mode | Behaviour |
|---|---|
| **Strict** (Phase 1, and the published figures) | No registry calls. `VERIFY_LIVE` is treated as `DECLARE_OUT_OF_COVERAGE`. A refusal stays a refusal |
| **Confirm** (Phase 4 adapters) | For a `live_checkable` citation in an abstention or out-of-coverage result, the caller asks `RegistryAdapter.exists(citation)` first |

### Rules for registry adapters (Phase 4)

`RegistryAdapter.exists(parsed_citation) -> Found(official_url) | NotFound | Unknown`

- **Exact match only.** `Found` requires the registry to return that exact number, or an
  exact normalised title + year. Registry title searches are fuzzy, so a near hit is
  `NotFound`, never `Found`.
- **Failure never becomes an answer.** A timeout, an error or a missing adapter is
  `Unknown`, which means "can't verify". It never answers, and it never silently turns into
  a refusal.
- **Cache negatives with a TTL, rate-limit calls, and put them behind a circuit breaker.** A
  flood of invented citations must not become a flood of registry calls.
- **Bound-on-invented stays 0 % in both modes.** It is re-measured in Phase 4 with confirm
  mode on.
- Registries per jurisdiction:
  - legislation.gov.uk: `/{series}/{year}/{number}/data.feed`, or the title search, under
    its fair-use policy.
  - The BOE: its consolidated-legislation API.

## 5. Unresolved queries: discover, then bind

`ROUTE_UNRESOLVED` means that no citation was found ("the unfair dismissal compensation
cap"). It is **not** permission to search everything and generate. The next step, built in
Phase 4, works like this:

1. Search instrument titles and section headings. This returns candidate *coordinates*, not
   text.
2. Send the candidates back through the router's exact lookup.
3. The user, or an orchestrating agent, confirms one before any bounded retrieval runs.

## 6. Follow-ups and context

`route(query, context=[…])` takes the previous turn's bound coordinates.

- Every context coordinate is re-validated against the index. Invalid ones are ignored.
- An instrument named in the query always beats context.
- A bare provision ("what about section 125?") binds against context only when the context
  names a single instrument. The result then has `source="context"`.

## 7. Failure behaviour

- `route` never raises for any input. These return `ROUTE_UNRESOLVED` with a `reason`:
  - a non-string (`not_a_string`);
  - a query longer than 4 KB (`query_too_long`);
  - one with too many citation cues to read safely (`too_complex`);
  - a `jurisdictions` scope that excludes every indexed jurisdiction
    (`no_jurisdiction_in_scope`).
- An internal error is logged and fails safe to `ROUTE_UNRESOLVED`. It never falls back to
  a guess.
- Loading an index whose tables don't match the SHA-256 hashes in its manifest raises
  `IndexLoadError` at load time, never at query time.
