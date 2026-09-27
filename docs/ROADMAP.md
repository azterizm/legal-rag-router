# Phase 1 Roadmap — `legal-rag-router` 0.1.0

Source of truth: `~/.claude/plans/we-are-built-phase-moonlit-honey.md` (the **plan**), and in the vault
`26 Sept - Hosted Reference Architecture/` docs **01** (data shapes), **02** (router spec), **06 §2** (CI surfaces),
**07 §2–3** (Unit 1–2 benchmark) and **10 §2** (Phase 1 build order).

This roadmap puts every item in the plan into an ordered set of milestones, each with a "done when" gate,
so nothing gets dropped. The traceability matrix at the end maps each plan section to the milestone that covers it.

Legend: 🧑 = needs you (an account, hardware, money or approval) · ⛔ = halt point: I stop and ask before going on.

> **This file is the single record of progress and decisions.** Nothing about progress is kept in assistant memory.
> Update **§S Status** at every stop.

---

## S. Status (where we are, and where we stopped)

| Field | Value |
|---|---|
| Last updated | 2026-09-27 |
| Current stage | **Stage A (UK, partial data)**: M0 → M1 → M2 → M3-UK → M4-UK → M6-UK → M7-UK |
| Current milestone | M0 in progress |
| Next step | Finish M0 (repo, packaging, CI), then M1 |
| Waiting on you | The background fetch of the remaining UK XML (≈ 100k SIs, 24 Acts). Also the regnal-key fix in your scraper (see U2) |
| Blocked | Nothing |

### Stop log
Newest first. One line per stop: what was finished, and where to resume.

- 2026-09-27: roadmap approved (D1–D3). UK-first ordering and the regnal decision recorded (§U). Starting M0.

---

## U. UK first, Spain later (decided 27 Sept 2026)

**Order of work:**

| Stage | What | Starts when | Milestones |
|---|---|---|---|
| **A** | Build the router against the UK data already scraped | Now | M0, M1 (UK grammar, with the plugin protocol designed for ES too), M2 (UK licence entry), M3-UK, M4-UK, M6-UK, M7-UK, UK battery drafting (M8) |
| **B** | Cover the entire UK | The background fetch finishes | M5-UK: full UK index, harvest, coverage sweep over the UK split |
| **C** | Spanish law | Stage B is complete | M1-ES, M2-ES, M3-ES, M4-ES, M5-ES, M6-ES, M7-ES, ES batteries |
| **D** | Seal, run, compare, release | A–C are done | M8 freeze → M10 → M11 → M12 → M13 |

Why D can't start early: the plan's exit criteria need **one sealed run** across both domains.

**Until Stage C:** no Spanish code, data, aliases or batteries are written. The `Grammar` protocol and the `Coordinate` type still stay jurisdiction-neutral, so ES plugs in without changing the core.

### Data source for UK (provided 27 Sept 2026, in `uk_scrap_data/`, git-ignored, never published)

| Artifact | Contents | Role |
|---|---|---|
| `raw_xml/{ukpga,uksi}/{year}/{n}.xml.gz` | 17,115 Acts and 16,673 SIs as of 27 Sept. Full CLML XML | Raw cache layer: records, index and `<Citation>` harvest |
| `legislation_queue.db` | `download_queue`: 133,798 rows (ukpga 17,139 · uksi 116,659) with fetch status. `harvest_progress`: 1,046 series-years | Catalogue and completeness tracking |
| `router_other_series.jsonl` | 42,368 titles across 12 other series, 1970 onwards | Feeds `OUT_OF_COVERAGE` |
| `harvest_catalog.py` | Your harvester | Reference only. Porting fetch code into the repo is **deferred until all data is downloaded** (U3) |

**Checked in the XML so far:**
- Element ids: `section-124-1ZA-a`, `schedule-1-paragraph-2-2-b-i`, `part-I` / `part-2A`, `part-2A-chapter-1`, `article-N`, `regulation-N`.
- Cross-references are `<Citation URI Class Year Number SectionRef>` and `<CitationSubRef>`.
- `Status="Repealed" | "Prospective"` appears on elements. Instrument-level repeal is marked with "(repealed …)" in feed titles.
- The root carries `DocumentURI` / `IdURI`.

### Issues found in the scraped data, and decisions

- **U1 — Pre-1963 Acts use regnal identifiers. Decided: coordinates mirror legislation.gov.uk's `IdURI`.**
  - Examples:
    - `IdURI …/id/ukpga/Geo3Sess2/47/78` → `uk/ukpga/Geo3Sess2/47/78`.
    - `ukpga/Eliz2/8-9/69` → `uk/ukpga/Eliz2/8-9/69/s1`.
  - UK instrument arity is **4** for calendar-numbered instruments and **5** for regnal ones. The grammar decides which from the year segment: `\d{4}` or a regnal token. The M1 EBNF and `instrument_id` rules are written that way (`uk_ukpga_Eliz2_8-9_69`).
  - Users still cite these Acts by title + calendar year ("Law of Property Act 1925"), which the title tables resolve.
- **U2 — The scraper keys on calendar `year/number`, so pre-1963 collisions were dropped.**
  - 421 Acts were lost: `harvest_progress.item_count` is 14,294 but only 13,873 rows are stored, because of `INSERT OR IGNORE` on the key `uk/ukpga/{year}/{n}`.
  - Where two Acts shared a key, only one XML file survives.
  - Plus 12 uksi mismatches from 1963 onwards (probably duplicate feed pages; to verify).
  - **Fix:** key the queue and file paths on the `IdURI` path.
  - Until that fix, ingest reads the identity **from each file's own `IdURI`**, never from its path. M3-UK's catalogue lists the Acts that are still missing.
  - 🧑 The fix belongs in your running scraper.
- **U3 — Fetch code lives outside the repo for now.** Decided: revisit once all data is downloaded. Until then the repo's `ingest/uk.py` *reads* `uk_scrap_data/`. `docs/sources.md` records how the data was obtained. Scraper hygiene to fix at port time:
  - the UA has a placeholder contact (`data-team@example.com`);
  - concurrency is 15 in parallel, against the plan's 1 req/s.
- **U4 — Gaps in the other-series listing. Decided: I write the listing harvest in the repo** (`ingest/uk_catalogue.py`: Atom feeds only, resumable, rate-limited, declared UA).
  - The current listing starts at 1970. It misses `apgb`, `aep`, `aosp`, `aip`, `apni`, `mnia`, `mwa`, `uksro`, `nisro`, `ukdsi`, `sdsi`, `wdsi`, `nidsr`, `ukmo`, `ukmd`, … and pre-1970 years.
  - Without the fix, citations to these would be *refused* when they should be marked out of coverage.
  - The same harvest also writes a regnal-correct catalogue of `ukpga`/`uksi`, which measures the U2 gap.

---

## 0. Departures from the plan (approved 27 Sept 2026)

Each of these changes order or method but not what gets delivered. See §4.

| # | Plan says | Proposal | Why |
|---|---|---|---|
| D1 | Index build (step 6) and parser (step 7) come after the full ingest (steps 4–5) | **Build a vertical slice first:** ingest only the fixture instruments (≈ 30 documents), build the fixture index from them, then develop the parser against it while the ~33 h full ingest runs in the background | The parser can't be tested without an index, and the committed fixture index (02 §8, 06 Surface 4) has to come from the same ingest and build code anyway. This removes days of idle time and catches ingest bugs before the long run |
| D2 | Typo thresholds are "tuned on the typo test set before sealing, then frozen with it" | Split `typo.*` into a **dev** slice (used for tuning, published) and a **test** slice (sealed, never used for tuning), with a fixed seed | Tuning on the rows you then report on inflates auto-correct precision and recall. That is the same thing the plan prevents for misroute by holding harvested rows out of the coverage sweep |
| D3 | The coverage sweep runs over "every harvested citation pair", and misroute rows are "held out from the sweep" | Make the split explicit and do it first: harvested pairs → `sweep` / `heldout` with a fixed seed, the split manifest hashed and committed **before the grammar sees any harvested row** | Otherwise the "held out" claim can't be checked by an auditor |

---

## 1. Milestones

### M0 — Repository, packaging, CI (plan step 2) · day 1

- [x] `git init` on `main`. `.gitignore` covers `.cache/`, `data/**` except `data/MANIFEST.json`, `results/raw/`, `.venv`, and build outputs.
- [x] `uv init --lib` with the `src/` layout. `pyproject.toml` follows 02 §8:
  - hatchling backend; `requires-python >=3.11`; `dependencies = []`; classifiers; `license = "AGPL-3.0-only"`.
  - Author `Memon Systems <abdullah@memonsystems.com>`.
  - Wheel = `src/legal_rag_router` only.
  - Dependency groups `dev`, `ingest`, `eval`, `bench`.
- [x] `src/legal_rag_router/{__init__.py, py.typed}`, with `__version__` taken from the package metadata.
- [x] `LICENSE` (full AGPL-3.0 text), `SECURITY.md` (reporting address, supported versions), `CHANGELOG.md` (Keep a Changelog), README skeleton.
- [x] Tooling config:
  - ruff: lint + format, a strict rule set.
  - `mypy --strict` on `src/`. `ingest/`, `eval/` and `bench/` are also type-checked, since they produce the published numbers.
  - pytest + hypothesis.
  - `pytest-cov` with a floor of **90 % on `src/`**, raised once M7 lands.
- [x] `.github/workflows/ci.yml`:
  - ruff, mypy and pytest on 3.11 / 3.12 / 3.13 / 3.14 × ubuntu / macos.
  - Actions pinned by full SHA; `permissions: contents: read`; uv cache on; `concurrency` cancels superseded runs.
- [x] `.github/workflows/codeql.yml` (Python, one file) and `.github/dependabot.yml` (github-actions + uv).
- [ ] 🧑 Create the GitHub repo `azterizm/legal-rag-router` and push. `gh` is **not installed** on this Mac; either `brew install gh` or you create the repo.
- [ ] 🧑 On PyPI, set up a pending Trusted Publisher for `legal-rag-router` (owner `azterizm`, repo `legal-rag-router`, workflow `release.yml`, environment `pypi`), and create the `pypi` environment in the GitHub repo settings.
- **Done when:** `uv run ruff check && uv run ruff format --check && uv run mypy --strict src && uv run pytest` passes locally, and CI is green on the first push.

### M1 — Coordinate format and citation grammar spec (plan step 1) · day 1

- [ ] `docs/grammar.md` v1. It is the source of truth for tests and is versioned with the index format.
  - **Coordinate EBNF per jurisdiction:**
    - UK: `s124`, `s124A`, `s124/1ZA/a/ii`, `art2`, `reg3`, `sch2/para4`, `pt2`, with the mapping from legislation.gov.uk element ids (`section-124-1ZA-a` → `s124/1ZA/a`).
    - ES: `art42`, `art42bis`, `art42/1/b`, and `da|dt|dd|df` + n, with ordinal words mapped up to *vigésima*.
  - **Instrument arity per jurisdiction:** UK = 4, ES = 4.
  - **Surface-form table:** each row has a **stable row ID** (e.g. `UK-SF-012`) so battery rows can cite it. Covers every form listed in plan step 1 and step 7 and in the Spanish and UK sections of the case catalogue.
  - **Unsupported-forms table:** each form with the behaviour it gets (recitals, EU/US forms, case citations, concept-only queries, relative references).
  - **Case catalogue:** every entry from the plan, each with a row ID. Test rows reference these IDs.
- [ ] `coordinate.py`:
  - A frozen, slotted `Coordinate(jurisdiction, series, year, number, provision: tuple[str, ...])`.
  - `parse()`, `__str__`, `instrument_id`, `parent`, `is_instrument`, and `key` (casefolded).
  - Segment validation with anchored regexes only, per-jurisdiction arity, and case kept in the canonical string.
- [ ] README: extension slots for `eu/`, `us/`, `contract/` (01 §2).
- **Done when:** every grammar.md example round-trips, and the hypothesis property `parse(str(c)) == c` passes, along with the negative parse cases.

### M2 — Licence record (plan step 3) · days 1–2

- [ ] Re-check both sets of terms and record the URL and date checked (🧑 if anything has changed):
  - legislation.gov.uk: OGL v3.0, plus its **fair-use / API rate terms** (plan step 4 says to check these first).
  - BOE: reuse conditions of 27 June 2024; attribution string plus link; *Biblioteca Jurídica Digital* excluded.
- [ ] `data/MANIFEST.json` (with a schema): per source, the licence, URL, date checked, attribution, and `document_count`, which ingest fills in.
- [ ] `NOTICE`, with attribution text for both sources. It ships with the index release.
- [ ] `scripts/check_licences.py`, wired into CI. It fails on a `data/` subtree with no manifest entry or a count mismatch, and it also checks `tests/fixtures/index/`.
- **Done when:** the script passes in CI on the empty data tree and the fixture tree, and fails on a planted bad case in its tests.

### M3 — Fetch layer and source reconnaissance (prep for plan steps 4–5) · day 2

- [ ] `ingest/cache.py`, shared by both sources:
  - Content-addressed disk cache under `.cache/`.
  - Token-bucket limit of 1 req/s.
  - Declared User-Agent with contact details.
  - Exponential backoff with jitter that honours `Retry-After`, 429 and 503.
  - Conditional GETs (ETag / Last-Modified).
  - `defusedxml` for all XML.
  - Structured progress log. Resumable and idempotent.
- [ ] `ingest/records.py`: pydantic `ProvisionRecord` (01 §4) with a per-record `checksum_sha256`. Canonical JSON serialisation.
- [ ] **Reconnaissance, written up in `docs/sources.md`:**
  - legislation.gov.uk:
    - Atom feed paging per type and year.
    - `data.xml` element-id conventions for sections, subsections, schedules, parts and SI articles/regulations.
    - `<Citation>` attributes.
    - Repeal markers and chapter number.
    - How to list every other series (`asp`, `nia`, `anaw`, `asc`, `nisr`, `ssi`, `wsi`, `eur`, `ukla`, …).
  - BOE:
    - `legislacion-consolidada` paging.
    - `/id/{id}/texto` XML structure and `<version>` handling.
    - **The exact field names for `análisis/referencias`, `ámbito` and `derogado`**, confirmed on the CdC and LGT.
    - Re-check that the LGT id is `BOE-A-2003-23186` and the ET id is `BOE-A-2015-11430`.
  - Real request counts and time estimates for both sources.
- ⛔ **Halt if reconnaissance contradicts the plan.** For example: referencias need a second call per norm (≈ +10k calls), fair-use terms forbid 1 req/s, or the element-id depth doesn't reach `1ZA`.
- **Done when:** cache unit tests pass (rate limit, backoff, resume, conditional GET, all using a fake transport), and `docs/sources.md` records the confirmed field names.

### M4 — Fixture vertical slice (D1; feeds plan steps 6–7 early) · days 2–3

- [ ] `ingest/uk.py` and `ingest/es.py`, with an `--only <ids>` mode.
- [ ] Fixture instrument set. It covers every alias target, so the rule "the build fails if an alias target is missing" holds on the fixture too:
  - UK:
    - ERA 1996, CA 2006, Arbitration Act 1996 (Marchwood embedded title).
    - Employment Act 1990, if it exists (suggestion probe).
    - Data Protection Act 2018 (reorder probe).
    - Two Finance Acts from different years ("Finance Act" ambiguity).
    - Several Acts of 1996 (*the 1996 Act*).
    - A repealed Act.
    - An Act with a `Part X`.
    - SI 2011/3006, SI 2010/2926, and a pair of same-title / same-year SIs.
    - A small sample of other-series titles for `OUT_OF_COVERAGE`.
  - ES:
    - CdC `BOE-A-1885-6627`, LGT, ET, Ley 15/1988, CE, CC, LEC, LECrim, CP, LGSS, LOPDGDD.
    - A state/regional pair sharing a number (`Ley 1/2015`).
    - An RDL / RDLeg pair.
    - A repealed norm.
    - A norm with an `artículo único`.
- [ ] Golden check: Art. 42 CdC has apartados 1–6, and letras a)–d) under apartado 1.
- [ ] First `build_index.py` pass (see M6) → `tests/fixtures/index/`, committed and covered by the licence check. The size budget keeps the repo < 5 MB (01 §7).
- **Done when:** the fixture index loads through `Router.from_path` (a stub at this point) with the hashes checked, and the golden Art. 42 structure test passes.

### M5 — Full ingest in the background (plan steps 4–5) · starts day 3, ≈ 33 h UK + ES in parallel

- [ ] UK, `ukpga` + `uksi`:
  - Instrument lists from the Atom feeds.
  - `data.xml` per instrument: element ids down to subsection/paragraph depth, text, repealed status, part → sections map, chapter number.
  - `<Citation>` harvest → `data/harvest/uk_citations.jsonl`.
  - Titles of every other series from the feeds (no provisions fetched).
- [ ] ES:
  - Norm list: `identificador`, `rango`, `numero_oficial`, `titulo`, `ámbito`, `derogado`.
  - `/texto` XML per norm. Apartado/letra split from the text: a leading `N.` for apartados and `x)` for letras, not the CSS class. Article number normalised from the heading (`art42` vs `a642`).
  - The current `<version>` is indexed and the older ones are kept for Phase 2.
  - `referencias` harvest → `data/harvest/es_citations.jsonl`.
- [ ] Records → `data/{uk,es}/…/{instrument_id}.jsonl`, validated, checksummed. `MANIFEST.json` counts are filled in.
- [ ] Runs on the Mac in the background with a progress log I monitor. On failure it resumes from the cache.
- **Done when:** both runs finish with zero unvalidated records, the licence check passes on the full `data/`, and the ES golden test passes on full data.

### M6 — Index, title tables, aliases (plan step 6) · days 4–5 (fixture first, full data once M5 lands)

- [ ] `ingest/build_index.py` → `data/index/`:
  - `coordinates.txt.gz` (sorted).
  - `titles.json`, with multi-key variants: full+year, no-type+year, no-year, core words. Values are **lists**, to handle same-title/same-year SIs.
  - `numbers.json`: `Ley 58/2003`, `RDLeg 2/2015`, `SI 2011/3006`, `1996 c. 18`.
  - `aliases.json`, compiled from `aliases/{uk,es}.toml`, with a `salient` flag.
  - `wordsets.json`: content-word set + year. Any word set shared by two instruments is removed at build time.
  - `words.json`: word → titles, for ranking suggestions.
  - `typo.json`: SymSpell symmetric-delete table, ≤ 2 edits.
  - `coverage.json`: titles of other series, for `OUT_OF_COVERAGE`.
  - `index-manifest.json`:
    - Format version and per-file SHA-256.
    - Counts.
    - Snapshot dates.
    - Per series, the date the index is complete through and the highest number indexed per year (freshness window).
- [ ] Title normalisation key: casefold, accent-fold, particle and punctuation drop.
- [ ] Spanish short-title derivation: strip the `rango N/YYYY, de <fecha>,` preamble. Collisions are written to a build report and resolved in the alias TOML.
- [ ] The build fails on:
  - a casefold collision between coordinates;
  - an alias whose target is missing;
  - an alias that maps to two targets;
  - an unresolved short-title collision.
- [ ] `index.py`:
  - A `CoordinateIndex` protocol with a frozenset + bisect implementation.
  - A node-per-token trie as the benchmark alternative.
  - `load()` verifies the manifest hashes and format version, and refuses to load on a mismatch.
  - JSON only, never a pickle.
- [ ] `docs/measurements.md`: build time, load time (target < 450 ms), RSS, and frozenset+bisect vs trie on the full index. **Keep the lighter one.**
- **Done when:** a tamper test (one byte flipped) refuses to load, the measurements are recorded, and the structure decision is recorded. ⛔ If the load time misses 450 ms, I'll bring you options before going further.

### M7 — Parser and router (plan step 7) · days 5–7 (against the fixture index from M4; the sweep uses the full index)

- [ ] **7a Normalise** (`normalise.py`):
  - NFKC and casefold; accent fold; look-alike skeleton map.
  - `§/s./sec./art./artículo/reg./apdo.` canonicalisation; provision-word variant list (`secton`, `artcle`).
  - A 4 KB cap: over the cap → `UNRESOLVED` with the query flagged.
  - A tokeniser that keeps **character offsets** back to the original query.
- [ ] **7b Public types:**
  - `RouteStatus` (StrEnum, using the spec's values).
  - `NextAction` (`RETRIEVE_BOUNDED | ASK_USER | REFUSE | VERIFY_LIVE | DECLARE_OUT_OF_COVERAGE | DISCOVER_THEN_BIND`).
  - `RouteResult` and `ParsedCitation`, with every field from plan departure 2 and 02 §3.
  - `Candidate` and `RouteContext`.
  - All frozen and slotted.
- [ ] **7c Identifier scanner:**
  - Accepts coordinates, `instrument_id`s, legislation.gov.uk URLs (`/id/`, `/contents`, `/enacted`, date suffixes), `BOE-A-…` ids and `boe.es …?id=` URLs.
  - Case-insensitive, checked against the grammar, never typo-corrected.
  - A provision word after an identifier extends it; a partial path falls through to the grammars.
- [ ] **7d `grammars/base.py`, the `Grammar` protocol (frozen here).** Each grammar supplies:
  - a normalisation hook;
  - stopwords and boundaries;
  - anchor and provision patterns;
  - coordinate EBNF and arity;
  - the official registry (for `live_checkable`);
  - a clarification template.

  `grammars/uk.py` and `grammars/es.py` implement it. Every regex is linear-time (no nested quantifiers) and each pattern is tied to a grammar.md row ID.
- [ ] **7e `titles.py`:** token-trie gazetteer (longest match), a prefilter on trigger words, and the number-citation table.
- [ ] **7f Link and spans:**
  - Connector rules: `<prov> of/del <inst>`, `<inst>, <prov>`, `<inst> <prov>`.
  - The span is extended left to a boundary, and the whole title has to cover it.
  - Negation scope (`not`, `rather than`, `no`, `salvo`, `excepto` …).
  - Temporal-hint extraction.
  - Context resolution: context coordinates are re-validated against the index, and the query beats context; results resolved this way get `source="context"`.
- [ ] **7g Resolution:**
  - **Instrument:** exact / alias / number, then the typo tiers from departure 7 (Damerau, one word of ≥ 5 letters, uniqueness margin, no correction of aliases under 5 letters, corrections only inside the span), with suggestions ranked by the fixed rules, at most 3.
  - **Where the router refuses and where it asks:**
    - Refusal needs a clear claim.
    - Capitalised extra words before a real title → `INSTRUMENT_NOT_FOUND`; lower-case → `AMBIGUOUS`.
  - **Provision:**
    - Index lookup.
    - Mixed-up provision words (`art.` ↔ `s.`).
    - A 4-digit number after a provision word is a provision number.
    - `1.902` vs `42.1`: both readings are tried and the data decides.
    - Letra-only resolution.
    - Ranges (≤ 20, every endpoint must exist); open ranges → `AMBIGUOUS`.
    - Part → sections.
    - `artículo único` / ordinals.
    - `RDL` means both readings; `L.O.` = Ley Orgánica.
    - State vs regional: if both exist → `AMBIGUOUS`.
  - **Across citations:** several citations → `BOUNDED` with all coordinates, but any abstention makes the whole query abstain.
  - Out-of-coverage cues (other series, bills, cases, foreign law).
  - `repealed`.
  - `live_checkable` with the freshness window.
  - `next_action`.
  - `index_snapshot` is always set.
  - `jurisdictions=` scoping.
  - Clarification text in the query's language.
- [ ] **7h `filters.py`:** `partition_filter()` as in 02 §4. Every value is re-checked against the grammar and the index before it is interpolated.
- [ ] **7i Observability:**
  - The `citation_signal` rules.
  - An opt-in structured event on signal-but-`UNRESOLVED`, through a `logging` logger that is silent by default.
  - **Query text is never logged** unless the caller supplies a redactor.
  - `latency_ns` taken with `perf_counter_ns`.
- [ ] **7j Tests:**
  - Unit tests per grammar and per scanner.
  - The **span-accounting invariant**.
  - `tests/test_collision_rate.py` (02 §8, ported to the new shape).
  - Golden tests: the three April 2026 probes verbatim, plus every probe in the plan's Verification section.
  - Hypothesis: `route()` never raises, and 4 KB random input finishes in < 2 ms (ReDoS guard).
  - A thread-safety smoke test.
  - Injection-shaped identifiers never reach the filter.
- [ ] **7k Harvest split, then coverage sweep (D3):**
  1. Split the pairs into `sweep` / `heldout` with a fixed seed, and commit a hashed split manifest.
  2. Run the router over `sweep` only.
  3. Each miss becomes either a grammar row or a documented unsupported form.
  4. Commit `reports/coverage-sweep-*.md` next to the batteries.
- **Done when:** the full test suite is green on the fixture index in CI across the matrix, the plan's Verification probes all behave as specified, the sweep report is committed, and p99 is < 2 ms locally on the full index.

### M8 — Batteries (plan step 8) · written during M4–M7, frozen at the end of M8

- [ ] `batteries/schema.py` (pydantic). Row fields:
  - `id, query, context?, lang, domain, expected_status, expected_coordinates, source (hand|real_document|sampled), notes`;
  - `surface_form_ids`;
  - `absence_verified_via` on invented rows;
  - `split` on typo rows (D2).
- [ ] Validated in CI.
- [ ] Files, per domain where one applies:

  | Battery | Contents | Size |
  |---|---|---|
  | `collision` | | |
  | `misroute` | Drawn from `heldout` with a fixed seed, plus an informal hand-written slice | ≥ 600 / domain |
  | `false_abstention` | Sampled from the index with a fixed seed, varied templates, plus a hand-written slice | ≥ 600 / domain |
  | `invented` | Marchwood, invented instruments, invented provisions | ~50 invented instruments / language |
  | `ambiguous` | | |
  | `typo` | Real-title misspellings; adversarial near-misses (one edit, wrong year, semantic neighbours, embedded titles, both cases) | |
  | `identifier` | | |
  | `informal` | | |
  | `catalogue` | ≥ 1 row per catalogue entry | |

- [ ] Coverage check: every supported surface-form row in grammar.md is exercised by at least one battery row (CI test).
- [ ] 🧑 Invented rows need the absence confirmed with the source's own search. I record the search URL and date for each; you may want to spot-check a sample.
- [ ] Typo thresholds are tuned on the `dev` slice only (D2), then frozen in the constants block.
- ⛔ **Halt: you review the batteries before they are sealed.**

### M9 — Documentation (production-readiness; spread across M1–M8, finished here)

- [ ] `docs/contract.md`: the downstream contract, the `next_action` table, the "text reaches generation only through a bound coordinate" rule, strict vs confirm mode (Phase 4), and the registry-adapter rules.
- [ ] `docs/grammar.md` final; `docs/sources.md`; `docs/measurements.md`.
- [ ] README:
  - install;
  - the two-command index fetch (01 §5);
  - `Router.from_path`;
  - a usage example per status;
  - `jurisdictions=` and `context=`;
  - coverage and snapshot honesty;
  - opt-in logging and privacy;
  - extension slots;
  - how to add a jurisdiction;
  - licence and attribution.
- [ ] Public API docstrings. `__all__` defines the stable surface.

### M10 — Seal, then run (plan step 9) · day 8

- [ ] `eval/seal.py`: canonical-JSON SHA-256 (ported from `jev-vs-sovereign-benchmark/src/engine/audit_seal.py`, without torch/transformers).
  - `seal_battery`: hashes the batteries, index files, alias TOMLs, harvest split manifest, package version and git commit → `seals/battery-YYYY-MM-DD.json`.
  - `seal_results`: hashes the results and cites the battery-seal hash.
- [ ] `eval/run.py`: refuses to start if the recomputed battery hash differs from the tagged seal. A negative test flips one byte to prove this.
- [ ] `eval/metrics.py`, per domain:
  - collision, misroute, miss rate (on `heldout`), out-of-coverage precision, false abstention;
  - bound-on-invented and strict abstention;
  - auto-correct precision and recall, and clarify recall;
  - each with a Clopper–Pearson 95 % upper bound, implemented in stdlib and tested against known values.
- [ ] `bench/latency.py`: p50/p99 per status, `perf_counter_ns`, warm-up, GC paused, platform recorded.
- [ ] ⛔ **Halt:** commit the battery seal and tag it (`battery-seal-YYYY-MM-DD`) **before** the run. I ask before creating the tag.
- [ ] The run → `results/*.json`, a markdown table, and the sealed results.
- [ ] 🧑 An x86-64 latency run on the GTX 1650 rig's CPU. I provide a one-command script; you run it and bring back the results file.
- **Done when:** the per-domain table exists from one sealed run, collision is 0.0 %, bound-on-invented is 0.0 %, and both platforms' p50/p99 are recorded.

### M11 — Unit 1–2 comparison (plan step 10) · days 8–10 · `bench/`, outside the wheel

- [ ] `bench/clients/gemini.py`: Gemini Flash with structured output; model id pinned in the run manifest.
- [ ] `bench/clients/jev.py`: ported from `jev_client.py`.
- [ ] Harness:
  - Interleaved randomised order.
  - Warm keep-alive pools.
  - httpx `trace` split (DNS, connect, TLS, TTFB).
  - Warm-up calls discarded.
  - Bootstrap CIs; raw per-call timings kept.
- [ ] Latency rows:
  - **Row A:** a measured network floor (a no-model request to the same host), with provider-reported timing shown beside it.
  - **Row B:** the router as a warm Modal CPU HTTP function in the provider's region.
  - **Row C:** as deployed.
- [ ] Other axes:
  - accuracy on the sealed battery, or a stated sample of it;
  - bound-on-invented;
  - **determinism** (5 repeats of each query);
  - tokens and cost;
  - egress.
- [ ] `bench/unit1_cardinality.py`: accuracy as the option set grows (3 / 10 / 30+ options), from 07 §2.
- [ ] Two runs: UK/EU business hours and off-peak. Results sealed against the same battery seal.
- ⛔ 🧑 **A cost estimate is printed and needs your confirmation before any paid call.** Keys come from env vars only. Row B needs your Modal account.

### M12 — Release (plan step 11)

- [ ] `.github/workflows/release.yml`, triggered on tag `v*`:
  1. uv build the sdist and wheel.
  2. Check that the wheel contains only `legal_rag_router` and that the package has zero runtime dependencies.
  3. Publish to PyPI through the Trusted Publisher (OIDC, `pypi` environment, PEP 740 attestations).
  4. Create a GitHub release with `index-*.tar.gz`, `SHA256SUMS` and `NOTICE`.
- [ ] Release checklist:
  - CHANGELOG entry and version bump.
  - `pip install legal-rag-router==0.1.0` in a clean venv.
  - `Router.from_path()` works on the downloaded release index.
  - `gh attestation verify` passes on the wheel.
- ⛔ 🧑 **Tag `v0.1.0` and publish only on your explicit go.** Publishing to PyPI can't be undone.

### M13 — Vault doc updates (plan step 12)

- [ ] Compare the vault docs with the build. 10 §5 says 01/02/03/05/07 were already updated on 27 Sept, so only the remaining differences get folded back:
  - the index structure chosen in M6;
  - measured sizes and load time;
  - the confirmed BOE field names;
  - the Trie wording in 02 §2;
  - the measured figures, with their register changed from `By design (Target)` to `Measured`.
- ⛔ I show you the diff before writing into the vault.

---

## 2. Dependency order

```
M0 ─┬─ M1 ─┬─ M3 ── M4 ─┬─ M5 (background, ~33 h) ──┐
    └─ M2 ─┘            ├─ M6 (fixture) ── M7 ──────┼─ M6 (full) ── M7k sweep ── M8 freeze ── M10 ── M11 ── M12 ── M13
                        └─ M8 hand-written rows ────┘
M9 docs are written alongside and finished before M10.
```

## 3. Halt points (summary)

1. **Now:** you review this roadmap and answer §4.
2. M3: reconnaissance contradicts the plan (request counts, fair-use terms, field names, id depth).
3. M6: load-time target missed, or the structure decision is surprising.
4. Any change to public API shape, statuses, coordinate format, index format or battery methodology beyond what the plan specifies.
5. M8: battery review before sealing.
6. M10: creating the battery-seal tag.
7. M11: cost estimate before paid calls.
8. M12: `v0.1.0` tag and PyPI publish.
9. M13: vault edits.

## 4. Decisions (27 Sept 2026)

1. **D1, D2, D3** (§0): all approved.
2. **Git and GitHub:** local commits only, one at the end of each milestone. You create the remote and push yourself. `gh` is not installed by me. The M0 GitHub/PyPI items and the M12 `gh attestation verify` step are yours.
3. **Laya:** deferred. The Phase 1 comparison (M11) covers Gemini and Jev only.
4. **Normalised-record shards:** Phase 1 releases **the index only**. Record shards go out with `legal-rag-retriever` in Phase 4 (01 §5).
5. **Coverage floor:** 90 % on `src/` to start, raised to 95 % after M7 (the default; tell me if you want it different).

---

## 5. Traceability: plan → milestone

| Plan section | Milestone |
|---|---|
| Context: six statuses, exit criteria | M7b, M10 |
| Departure 1: token trie, anchors, whole-title rule, key variants, clear-claim refusal, mixed provision words, identifiers first, no models | M7c–M7g |
| Departure 2: `RouteResult`, `ParsedCitation`, signature | M7b |
| Departure 3: multiple citations, abstain dominates | M7g |
| Departure 4: per-jurisdiction arity | M1, M7d |
| Departure 5: data not pickle, `CoordinateIndex`, SHA-256 on load | M6 |
| Departure 6: author email | M0 |
| Departure 7: typo tiers, suggestions, metrics | M6 (typo table), M7g, M8, M10 |
| Data on disk (3 layers, sizes in manifest) | M3–M6 |
| How matching works: pipeline, prefilter, plugins, `jurisdictions=` scoping, mmap past 1M | M7; the mmap switch is measured in M6, not built (UK+ES is below 1M) |
| Missed patterns 1–4: fail safe, harvest, `citation_signal` event, no models | M7 invariant, M5 harvest, M7k, M7i |
| Downstream contract, `next_action`, `live_checkable`, freshness window | M7b/g, M6 manifest, M9 `contract.md` |
| Case catalogue: coverage honesty, context, negation, time, UK forms, ES forms, robustness | M1 (catalogue IDs), M7, M8 `catalogue` |
| Repository layout, zero runtime deps | M0 onwards |
| Step 1 | M1 |
| Step 2 | M0 |
| Step 3 | M2 |
| Step 4 | M3, M4, M5 |
| Step 5 | M3, M4, M5 |
| Step 6 | M6 |
| Step 7 | M7 |
| Step 8 | M8 |
| Step 9 | M10 |
| Step 10 | M11 |
| Step 11 | M12 |
| Step 12 | M13 |
| Verification section | M7j golden tests, M10, M12 checklist |
