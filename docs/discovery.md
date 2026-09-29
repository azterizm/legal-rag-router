# Concept discovery (discover-then-bind), UK

Status: **plan and evidence (29 Sept 2026)**. Roadmap stage D. Nothing here is built yet.

## The gap

The router binds only what a query *cites*. A query with no citation returns `ROUTE_UNRESOLVED` with `next_action = DISCOVER_THEN_BIND` (contract §5). The vault puts discovery in the Phase 4 monolith, as a search over instrument titles and section headings.

Research queries mostly carry no citation. Mart (2017, *Law Library Journal* 109(3)) collected 50 research queries from practitioners. None has a section number, an Act year or a formal citation. They are dense keyword strings: context + doctrinal element + procedural or remedial posture ("same actor inference employment discrimination summary judgment").

A lawyer who knows the answer is ERA 1996 s. 124 has finished their research. The research question is "unfair dismissal compensatory award statutory cap". For most real queries, then, `ROUTE_UNRESOLVED` is the main path, not an edge case.

Headings alone won't carry it. The heading of ERA 1996 s. 124 is "Limit of compensatory award etc.": neither "cap" nor "unfair dismissal" appears in it. "Unfair dismissal" is the title of Part X, which contains the section.

## Evidence (probe, 29 Sept 2026)

This was a throwaway experiment, not committed code. It ranked all 1,118,604 section-level provisions of the full UK index with BM25 on 15 keyword queries written in Mart's style, each with its gold provision.

**These 15 queries are excluded from the stage-D battery**, so the evaluation is never tuned on them.

| Searched fields | Gold in top 10 | Gold ranked 1st |
|---|---|---|
| Section headings only (the vault's design) | 6 / 15 | 3 / 15 |
| + Part / Chapter titles, instrument title, stemming, 6 synonyms | **12 / 15** | 4 / 15 |
| + the section's text, concatenated into one field | 8 / 15 | 3 / 15 |

What it shows:
1. **The heading ceiling is real.** Headings alone found fewer than half.
2. **Structure carries most of the doctrine.** The Part and Chapter titles supply what the heading lacks: "Unfair dismissal" / "Remedies for unfair dismissal" above "Limit of compensatory award".
3. **Body text needs weighting.** Concatenated into one field, long texts drown the short headings. It belongs in a separate, lower-weighted field (BM25F).
4. **Rank 1 is right only a quarter of the time.** Discovery must offer candidates to confirm, never bind. This is the vault's own rule (candidates → exact lookup → confirmation), and the numbers make it necessary.

Fifteen queries is a small sample: these numbers show direction, not a result.

## Signals the data holds

| Signal | In our data today | Notes |
|---|---|---|
| Section, regulation, article and paragraph headings | yes: every provision record's `title` | 1.12M section-level provisions |
| Part / Chapter titles | yes: provision records of `pt…`, `ch…`, linked by `groups` | e.g. Part X "Unfair dismissal" |
| Instrument title | yes | |
| Long title ("An Act to consolidate enactments relating to employment rights…") | **no**: CLML has it, ingest doesn't keep it | re-ingest, offline |
| Cross-headings (e.g. "Compensation" above ss. 118–127) | **no**: CLML `Pblock` titles aren't kept | re-ingest, offline |
| Provision text | yes | per provision, children joined |
| Definitions ("'compensatory award' means …") | derivable from text | |
| How other legislation describes a section ("section 124 (limit of compensatory award etc.)") | partly: harvested citations' `context` | sparse (16 pairs for ERA 1996) |
| Case-law headnotes and judicial vocabulary | **no** | a new source (The National Archives' Find Case Law, under its own licence). A fetch you would run, and a licence check first |
| Everyday synonyms ("cap" → "limit", "sacked" → "dismissal") | no | a small curated thesaurus, like `aliases/` |

## Plan (roadmap stage D; executed one step at a time)

| Step | What | Stops for you |
|---|---|---|
| **D0** | Evidence probe (above) | — done |
| **D1** | Decisions: API shape, index location, signals, evaluation method | ⛔ |
| **D2** | **Evaluation first:** a concept battery of UK keyword queries in Mart's style, each with its acceptable gold provisions, verified against the index. Split `dev` / `test` (as D2); sealed before any ranking code is tuned | ⛔ review, then seal |
| **D3** | Ingest keeps long titles and cross-headings (re-ingest). A separate concept index (`data/concepts/`, its own hashed manifest) holds per-provision fields: heading, cross-heading, Part / Chapter, instrument and long title, definitions, text, citing descriptions | |
| **D4** | `discover()`: BM25F over those fields, stemming, a curated thesaurus (`aliases/uk_concepts.toml`). Every candidate is re-validated through the router's exact lookup. It returns candidate coordinates with their headings and the evidence for each, never provision text, and never binds. Tuned on `dev` only | |
| **D5** | Sealed evaluation on `test`: recall@1/5/10 and MRR against the heading-only baseline (the vault's design); 0 non-existent candidates, 0 bindings; latency | ⛔ results |
| **D6** | Contract §5, README; proposed vault changes for 02 §5, 05 §4, 07 and 10 Phase 4 (vault edits need your go) | ⛔ vault |

Then M10 as planned. D uses a separate index and a separate method, so the sealed router batteries and the router index are untouched (`eval.seal verify` still passes).

## Out of scope here

- **Dense / vector retrieval:** stdlib only, zero runtime dependencies in the wheel. The vault puts vector search in the Phase 4 monolith, and D5's numbers are the lexical baseline it would be compared against.
- **Generation of any kind.**
- **Case law,** until its source is decided (D1).
