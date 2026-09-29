# Proposed vault changes: discover-then-bind (roadmap D6)

Status (29 Sept 2026): **proposed, not applied.** The vault (`Business/Technical Consultancy/Drafts/26 Sept - Hosted Reference Architecture/`) is edited only with your go (CLAUDE.md).

Stage D moved discovery from a Phase 4 fallback into the router package, and measured it (`docs/discovery.md`, `reports/discovery-uk.md`). Four vault documents describe the old design. Each change below keeps the safety rule unchanged: **text reaches generation only through a bound coordinate**. Discovery returns candidates for confirmation, never text, and never binds.

## 1. 02 (Layer 1 & 2, router spec), §5, the "Discover-then-bind" paragraph

**Now:** "A search over instrument titles and section headings returns candidate *coordinates*, not text; the candidates go back through the router's exact lookup; the user, or an orchestrating agent, confirms one before any bounded retrieval runs. The router ships the contract and the `next_action` field; discovery is built in the monolith (05 §4, 10 Phase 4)."

**Proposed:**
> Discover-then-bind replaces the old unbounded vector fallback. Research queries rarely cite a statute (Mart 2017: none of 50 practitioner queries did), so this is the main path, not a fallback.
>
> The router ships it: `Router.discover(query)` ranks section-level provisions of a separate, SHA-256-verified concept index. It weights five fields separately: heading, cross-heading, Part / Chapter titles, instrument and long title, and text. It adds a small curated thesaurus and priors from facts about each source (repealed, devolved, amending, commencement; citation in-degree). Headings alone are not enough: "Limit of compensatory award etc." (ERA 1996 s. 124) contains neither "unfair dismissal" nor "cap".
>
> Candidates are coordinates with labels, never text, and each is re-validated against the router index. The user or an orchestrating agent confirms one, and it is routed like any citation. Only that `ROUTE_BOUNDED` result reaches retrieval. `route()` itself is unchanged: a query that cites nothing still routes `ROUTE_UNRESOLVED`.

## 2. 05 (Monolith integration), §4, "Discover-then-Bind: No Open Vector Fallback", step 1

**Now:** "`retriever/discovery.py` searches instrument titles and section headings (lexical plus vector, over headings only) and returns candidate **coordinates**, never provision text."

**Proposed:**
> The monolith calls `router.discover(query)` for every `ROUTE_UNRESOLVED` result. It is lexical and structure-aware, over the concept index, and returns candidate **coordinates**, never provision text. A vector re-ranker over the same candidate fields may be added here. It is measured against the router's lexical baseline on the sealed concept battery, and it is adopted only if it beats that baseline at rank 1 without offering more out-of-scope candidates as confident.

Steps 2 and 3 (exact lookup, confirmation before bounded retrieval) are unchanged. The code sketch around line 152 (`from retriever.discovery import CoordinateDiscovery`) becomes a call to `router.discover`.

## 3. 07 (Benchmark suite), the "Citation-less Queries (`ROUTE_UNRESOLVED`)" row

**Now:** "Discover-then-bind: share of queries, share where the right coordinate is among the candidates, and collision rate after confirmation, reported separately; no generation from open retrieval | By design (Target) — measured at run"

**Proposed** (the figures from the sealed run, 29 Sept 2026, UK):

| Diagnostic metric | System 1 | System 2 | Evidence register |
|---|---|---|---|
| **Citation-less queries (`ROUTE_UNRESOLVED`)** | Same as above | Discover-then-bind: the right provision is among the top 10 candidates for **88 %** and first for **51 %** of drafted keyword queries. Section headings alone: 51 % / 19 %. For queries from an independent probe set: 64 % / 45 %. No candidate the router cannot bind; no binding without confirmation | **Measured** (sealed concept battery, `reports/discovery-uk.md`) |
| **Out-of-scope discovery** | n/a | 30 % of out-of-jurisdiction queries (Mart's US set) still get a "confident" UK candidate. Confirmation stays mandatory | **Measured**; a known weakness |

## 4. 10 (Build roadmap)

- **Phase 4, item 4** ("Discover-then-bind … search over instrument titles and section headings returns candidate coordinates…"), **proposed:**
  > Discover-then-bind is already in the router (Phase 1, stage D). Phase 4 wires `router.discover` into the monolith's `ROUTE_UNRESOLVED` path and the confirmation UI. It may add a vector re-ranker, adopted only if it beats the lexical baseline on the sealed concept battery.
- **The phase table** ("Registry adapters + discover-then-bind | Phase 4"), **proposed:** "Registry adapters | Phase 4"; and "Discover-then-bind (lexical, concept index) | Phase 1 (stage D, done)".
- **Rationale to add to Phase 1:** citation-less queries are most research queries (Mart 2017, *Law Library Journal* 109(3)). Building discovery before Phase 4 puts the main query path under the same sealed, measured discipline as citation routing.

## Not proposed

- Any change to the six statuses, `next_action` values or the rule that text reaches generation only through a bound coordinate.
- Case law as a discovery source (D1: legislation only for now).
