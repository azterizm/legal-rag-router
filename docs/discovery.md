# Concept discovery (discover-then-bind), UK

Status (29 Sept 2026): **stage D complete.** The sealed test run is in `reports/discovery-uk.md` (hit@10 88 % against 51 % for headings only), and you accepted it. The contract (§5) and README are updated, and the proposed vault text is in `docs/vault-proposals-discovery.md`. Roadmap stage D.

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

## D1 decisions (29 Sept 2026)

1. **A separate `discover()`**, over its own `data/concepts/` index. `route()`, its statuses, the router index and the sealed M8 batteries stay unchanged.
2. **Legislation only** in this stage. Case law comes later.
3. **Evaluation queries from both of us:** mine, split dev / test; yours, test only.

## D2: the concept battery (`batteries/concept/uk.jsonl`, 265 rows)

Built by `batteries/build_concepts.py` and validated in CI (`tests/test_batteries.py`). No row went through the router or any ranking.

| Source | Rows | Split | Gold |
|---|---|---|---|
| Drafted by me (`batteries/concept_uk.py`) | 203, in 12 areas of 15–23 each | dev 112 / test 91 (salted hash of the query, 50 %) | The provisions that answer it. Written from the doctrine first; then every gold coordinate was checked in the index and its heading read. No query was reworded to match a heading |
| Your `rag-security-probes` | 12: 6 fabrication, 6 Mode C | test only | The real provision your repository names for each (`real_law_reached_for`, Mode C pass strings). FAB-004 has none, since materiality is not fixed by statute |
| Mart (2017) Appendix B | 50, verbatim | test only | None: US questions answered by case law, so no indexed UK statute answers them |

Areas: employment, equality, criminal offences, criminal procedure, housing, land, companies, insolvency, consumer and contract, data and information, family, tax. Queries follow Mart's form, a dense keyword string with no citation. Some use statutory terms ("indirect discrimination provision criterion"), some practitioners' words ("sacked for being pregnant", "hacking", "squatter").

Each row also carries **`route_status`**, what `route()` must return for the same query, labelled from grammar.md and checked against the index:
- drafted and Appendix B rows: `ROUTE_UNRESOLVED`, since they carry no citation;
- your probes, by their citation:
  - invented Acts: instrument not found;
  - ERA s. 342: provision not found;
  - the repealed Sex Discrimination Act 1975 s. 6: bound with `repealed=True` (UK-C-02).

This makes a second check possible: citation-less queries never get bound by `route()`.

**Scoring at D5 (proposed):**
- **Rows with gold:** a candidate is a hit when it is a gold coordinate or lies beneath one. Reported: recall@1, @5, @10 and MRR, per source and per area, against the headings-only baseline.
- **Rows without gold** (Appendix B, FAB-004): the share that get a confident candidate. Lower is better.
- **Safety, which must be 0:** candidates that don't exist in the index, and results that bind.

The 15 D0 probe queries are recorded in `concept_uk.py` and kept out of the battery (CI test).

Sources quoted verbatim:
- Mart's searches: S. N. Mart, *Appendix B: The Algorithm as a Human Artifact: Implications for Legal [Re]Search*, 109 Law Libr. J. app. B (2017), https://scholar.law.colorado.edu/research-data/5;
- the probe queries: `rag-security-probes` (Memon Systems Ltd).

### D2 review points (all four approved, 29 Sept 2026)

1. **Appendix B as out-of-jurisdiction negatives.** I read "add appendixb.md" as: use its 50 searches verbatim, where the good outcome is *no confident UK candidate*. Several have UK analogues ("age employment discrimination disparate treatment" ↔ Equality Act 2010 s. 13 / s. 19). The alternative is to translate them into UK questions with gold. But then I would write them, and they would no longer be independent of me.
2. **Gold where your repository names an Act or a range rather than a section:**
   - DEVOLV-UK-001 → MCA 2005 ss. 16 and 19 (Court of Protection powers; appointment of deputies);
   - FAB-005 and FAB-006 → the 1993 Act's ss. 76–84 (FAB-005 also CLRA 2002 Sch. 11);
   - REPEAL-UK-001 → Equality Act 2010 s. 124 (remedies; no cap).
3. **The dev / test split** of my rows is 112 / 91: a 50 % hash, landing where it did. Your rows are reported as their own slice, as the independent result.
4. **The scoring above,** in particular "no confident candidate" for the negatives. `discover()` will need a confidence threshold, tuned on dev only.

Sealed with `uv run python -m eval.seal concept` and verified with `eval.seal verify seals/concept-2026-09-29.json`. It pins the battery file and the router index its gold was checked against. It is not tagged, since a tag needs your go.

## D3: the concept index (29 Sept 2026)

- **Ingest, record schema 2:**
  - instruments carry `long_title` ("An Act to consolidate enactments relating to employment rights.");
  - sections, regulations, articles and schedule paragraphs carry `crossheading` ("Compensation" for ERA 1996 s. 124).

  A forced re-ingest of all 134,219 instruments left the harvest and the router index byte-identical, so both seals still verify.
- **`data/concepts/`** (`ingest/build_concept_index.py`, format and loader in `src/legal_rag_router/concepts.py`):
  - one document per section-level unit (and per schedule), with its subdivisions' text as the body, and one per instrument;
  - five fields: heading, cross-heading, structure (Part / Chapter / Schedule titles), title (with the long title), body (the first 200 terms);
  - postings are uint32 arrays read through `mmap`: document ids plus per-field term counts, 6 bits a field. Terms, documents and lengths are in sorted tables. Every file's SHA-256 is in its own manifest and checked on load. Stdlib only.
  - Numbers are in `docs/measurements.md`: 1.32M documents, 575 MB, built in 141 s, loaded in 213 ms, deterministic.
- **Terms:** NFKC, casefold, stop words dropped, a light suffix stemmer (`compensation` and `compensatory` both give `compens`). One known gap is left for D4 to tune on dev: `dismissal` stays `dismissal` while `dismissed` becomes `dismiss`.

## D4: `discover()` (29 Sept 2026)

**API** (D1: a separate method; `route()` is unchanged):

```python
router = Router.from_path("data/index", concepts="data/concepts")
result = router.discover("unfair dismissal compensatory award statutory cap")
result.candidates[0].label  # "Employment Rights Act 1996, s. 124: Limit of compensatory award etc."
result.confident, result.next_action  # True, NextAction.ASK_USER
router.route(str(result.candidates[0].coordinate))  # bound only once the user confirms
```

- A `DiscoveryResult` holds `candidates`, each a `Discovered` with its coordinate, label, heading, score and the query terms it matched. It also holds `confident`, a `reason` (`no_concept_index`, `not_a_string`, `query_too_long`, `no_terms`, `no_match`, `low_confidence`) and `index_snapshot`.
- It never returns provision text and never binds. It never raises for any input.
- Every candidate is re-checked against the router index. A coordinate the router cannot bind is never offered: 0 on dev.

**Ranking** (`src/legal_rag_router/discovery.py`):
- **BM25F over the five fields.** Each field's count is normalised by that field's length, weighted, summed, then saturated.
- **Terms:**
  - a light stemmer that lets plurals and past tenses meet (magistrate / magistrates, dismissal / dismissed, child / children);
  - a curated thesaurus (`thesaurus/uk.toml`, compiled into the index) for everyday words (cap → limit, sacked → dismissal). Seeded from general usage; one entry added from a dev failure (magistrate → justice of the peace).
- **Authority priors** (`priors.bin`, facts about the source, never the query):
  - score multipliers for repealed, Northern Ireland, Scotland, amending (by title, or by a provision's opening amending words: "for … substitute"), commencement, and secondary legislation;
  - a boost for instruments that the text of other legislation cites often (harvest in-degree).

  A query naming Northern Ireland or Scotland lifts that penalty. Dev failures before the priors were mostly this: the Insolvency (Northern Ireland) Order, the Race Relations Act 1968, and Finance Act sections that amend another Act, all ranked above the law they mirror or amend.
- **Common words:** a word in more than 10 % of documents is not scored, unless every typed word is that common. Then the two rarest are scored.

**Tuning, on the dev slice only:** a coordinate search maximising MRR, two sweeps over field weights, length normalisation, k1, synonym weight, the common-word cut-off, prior penalties and in-degree weight. The frozen values are the `DiscoveryPolicy` defaults. The test slice has not been run.

| Dev slice (112 queries) | hit@1 | hit@5 | hit@10 | MRR |
|---|---|---|---|---|
| Headings only (the vault's design; no other field, thesaurus or priors) | 17 % | 46 % | 55 % | 0.29 |
| `discover()`, first version | 26 % | 62 % | 68 % | 0.41 |
| **`discover()`, tuned** | **68 %** | **84 %** | **91 %** | **0.75** |

- **By area** (hit@10): 100 % for criminal procedure, consumer, data, employment, equality, housing and insolvency; lowest for tax (70 %), land (75 %) and companies (80 %).
- **Confidence cut-off** (`min_share` 0.5), set by a rule written down before looking: the largest value keeping 90 % of dev hits confident. **It separates poorly: at 0.5, 90 % of dev misses are also "confident".** The share of the query's weight that the top candidate matches is a weak signal. D5 will show how the negatives fare. A better signal (the margin between the top candidates, or agreement across fields) is a candidate follow-up.
- **Latency** on dev: p50 73 ms, p99 181 ms (`docs/measurements.md`).
- **Safety on dev:** 0 candidates the router cannot bind. All 112 queries still route `ROUTE_UNRESOLVED`: discovery changes nothing about routing.
- **Bug found by a test while tuning:** once the synonym weight was tuned to 1, `discover` counted synonyms as typed words when measuring confidence. It now identifies typed words directly.

## Plan (roadmap stage D; executed one step at a time)

| Step | What | Stops for you |
|---|---|---|
| **D0** | Evidence probe (above) | — done |
| **D1** | Decisions: API shape, index location, signals, evaluation method | ✅ 29 Sept |
| **D2** | ✅ approved and sealed 29 Sept. **Evaluation first:** a concept battery of UK keyword queries in Mart's style, each with its acceptable gold provisions, verified against the index. Split `dev` / `test` (as D2); sealed before any ranking code is tuned | ⛔ review, then seal |
| **D3** | ✅ 29 Sept. Ingest keeps long titles and cross-headings (re-ingest). A separate concept index (`data/concepts/`, its own hashed manifest) holds per-provision fields: heading, cross-heading, Part / Chapter, instrument and long title, definitions, text, citing descriptions | |
| **D4** | ✅ 29 Sept. `discover()`: BM25F over those fields, stemming, a curated thesaurus (`thesaurus/uk.toml`). Every candidate is re-validated through the router's exact lookup. It returns candidate coordinates with their headings and the evidence for each, never provision text, and never binds. Tuned on `dev` only | |
| **D5** | ✅ 29 Sept (`reports/discovery-uk.md`). Sealed evaluation on `test`: recall@1/5/10 and MRR against the heading-only baseline (the vault's design); 0 non-existent candidates, 0 bindings; latency | ⛔ results: accepted 29 Sept |
| **D6** | ✅ 29 Sept (`docs/vault-proposals-discovery.md`; vault not edited). Contract §5, README; proposed vault changes for 02 §5, 05 §4, 07 and 10 Phase 4 (vault edits need your go) | ⛔ vault |

Then M10 as planned. D uses a separate index and a separate method, so the sealed router batteries and the router index are untouched (`eval.seal verify` still passes).

## Out of scope here

- **Dense / vector retrieval:** stdlib only, zero runtime dependencies in the wheel. The vault puts vector search in the Phase 4 monolith, and D5's numbers are the lexical baseline it would be compared against.
- **Generation of any kind.**
- **Case law,** until its source is decided (D1).
