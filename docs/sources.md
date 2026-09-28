# Data sources

How each corpus source was obtained, what it looks like, and what is known to be missing.
Figures are from the local build on **27 Sept 2026**; the release manifest fixes the final ones.

## legislation.gov.uk (UK)

### Terms (checked 27 Sept 2026)

| Item | Detail |
|---|---|
| Licence | Open Government Licence v3.0 "except where otherwise stated". EUR-Lex-derived material is reused under Commission Decision 2011/833/EU. Attribution is in `NOTICE` and `data/MANIFEST.json` |
| Fair use (`/fair-use-policy`) | ≤ 1,500 requests per 5 minutes. Follow the `robots.txt` crawl-delay. Non-browser clients must identify themselves with contact details. Contact the team before any heavy activity |
| `robots.txt` | `Crawl-delay: 5`. Disallows `*/data.pdf` and `*/data.docx`; `data.xml` and `data.feed` are allowed |

Every repo fetch goes through `ingest/cache.py`, which enforces 1 request per 5 s, an identified User-Agent, `Retry-After` handling and a resumable cache.

### How the UK data was obtained

| Artifact | Produced by | Notes |
|---|---|---|
| `uk_scrap_data/raw_xml/{ukpga,uksi}/{year}/{n}.xml.gz` | External fetch (compliant with the terms; not in the repo, roadmap U3) | `data.xml` per instrument, gzip-compressed, never published |
| `uk_scrap_data/legislation_queue.db` | Same | Download queue and status |
| `uk_scrap_data/router_other_series.jsonl` | Experimental harvester (`harvest_catalog.py`) | Titles of 12 other series, 1970 onwards |
| `data/uk/**`, `data/harvest/uk_citations.jsonl` | `uv run python -m ingest.uk --source uk_scrap_data --data data` | Deterministic; re-runs skip unchanged instruments |
| `data/catalogue/uk_catalogue.jsonl` | `uv run python -m ingest.uk_catalogue import …` (Stage A); `… harvest …` (Stage B) | See U4 |

Porting the fetch into the repo is deferred until the data has finished downloading (roadmap U3).

### CLML facts the ingest relies on

**Identity**
- Identity is the root `IdURI` (`…/id/ukpga/Eliz2/8-9/69`), **never the file path**.
  - Before 1963, Acts are regnal-numbered, and calendar year + chapter is not unique.
  - 697 files under `uksi/` are canonically `wsi` or `nisi`.

**Provisions**
- Provisions are the structural elements (`P1`–`P7`, `P`, `Pblock`, `PsubBlock`, `Part`, `Chapter`, `Schedule`, `Group`, `Appendix`) whose `IdURI`, or failing that `id`, maps through `grammars/uk.py`.
- Excluded:
  - `InternalLink`, which carries the **target's** `IdURI`;
  - everything inside `BlockAmendment`, which is quoted text of another Act;
  - everything inside `Versions`, which holds alternative texts for other extents;
  - cross-headings, wrappers and generated ids.

**Status and headings**
- `Status="Repealed" | "Prospective"` on an element or its `P1group` applies to its subtree.
- A whole instrument is repealed when the published title ends with "(repealed …)" or "(revoked …)".
- A section's heading is its `P1group/Title`. Parts, chapters and schedules carry `Number` + `Title`.

**Cross-references**
- `<Citation URI Class Year Number>` and `<CitationSubRef URI CitationRef>`.
- Those in `Commentaries` are editorial annotations: human-written, and harvested with `in_commentary=true`.

### Ingest results (all 33,788 files on disk, 27 Sept 2026)

| Measure | Value |
|---|---|
| Files ingested / failed | 33,788 / 0 (35 s on 8 cores) |
| Instruments with provision structure | 10,720 |
| Instruments that are **metadata-only** (PDF-only at the source) | 23,068: Acts before 1990 and SIs. A provision citation to one of these returns `ROUTE_OUT_OF_COVERAGE` (roadmap decision 10) |
| Provisions | 1,992,290 |
| Harvested citations | 2,434,792 |
| Provision ids the source publishes twice | 3,407 (0.17 %), recorded as `duplicated_provisions`. See roadmap Q-M7-1 |
| Case-only sibling variants | 16, handled by the `case_variants` table (decision 7) |
| Record files (`data/uk`) | ≈ 1.3 GB uncompressed |

### Known gaps (tracked in the roadmap)

- **Download** (U5): complete since 28 Sept 2026: 17,139 Acts and 116,659 SIs.
- **Pre-1963 key collisions in the external fetch** (U2): **closed 28 Sept 2026.** 421 Acts had never been fetched, because their calendar `year/number` key clashed with another Act's. `missing` listed exactly those 421, and you fetched them to their regnal save paths (`ukpga/Geo5Sess2-13/5.xml.gz`), 419 from the source.
  - **Two files are hand-made, not fetched:** `ukpga/Geo5Sess2-13/3.xml.gz` (Appropriation (Session 2) Act 1922) and `ukpga/Geo5Sess2-13/4.xml.gz` (Trade Facilities and Loans Guarantee Act 1922). The source offers only a PDF for them. Each is a metadata-only CLML record with the real `IdURI` and the catalogue's title and no provisions; its other metadata (publisher, modified date) was copied from a neighbouring Act and is not from the source. Replace them with the source's own `data.xml` if it ever serves one.
  - Result: 134,219 instruments, and `missing` reports 0.
- **Other-series listing** (U4): **closed 28 Sept 2026.** You harvested every series with your own harvester and imported the listing (`import --listing`, then `import-queue`): 244,564 catalogue entries in 29 series, including the pre-1970 and older series, with regnal coordinates and every Welsh title. The 6,465 untitled rows left are `uksi` rows from the queue; every one of them is indexed (most under their canonical `wsi` coordinate) and titled from its own XML.
- **Welsh SIs from 2026** have their own numbers (`wsi/2026/10` is a different instrument from `uksi/2026/10`). That shows in the data: all 118 of 2026 are missing from the UK SI series, while every 2024–2025 one is in it. They are catalogued (out of coverage) and resolve by title only, until the grammar reads their own citation form.

### Runbook: the catalogue harvest and the U2 re-fetch (you run both)

Both were done on 28 Sept 2026 (Known gaps above). The runbook stays for the next refresh.

Both fetches are yours to run, from your machine, under your contact details. No other client may fetch from the same IP at the same time: together they must stay under the crawl-delay (U7).

**1. What the catalogue harvest does.** `ingest.uk_catalogue harvest` reads each series' Atom feed, `https://www.legislation.gov.uk/{series}/data.feed`, and follows its `rel="next"` links to the last page. From each entry it keeps the identifier (the `IdURI`, so regnal Acts get their real coordinate), the title, and `ukm:Year` / `ukm:Number`. No legislation text is fetched. The result merges into `data/catalogue/uk_catalogue.jsonl`, and feed entries replace imported ones (that is how the untitled Welsh rows get titles). The index uses the catalogue for two things:
- a citation to anything it lists but does not index is **out of coverage**, not refused as invented;
- `missing` (step 4) compares it with the index.

The fetch layer enforces the fair-use terms itself: one request per 5 s, a User-Agent carrying your contact (placeholders such as `example.com` are refused), back-off on 429/5xx and `Retry-After`. Every response is cached under `.cache/http`, so an interrupted run resumes where it stopped, and a re-run costs no requests.

**2. Check first (1 request).** Open `https://www.legislation.gov.uk/ukpga/data.feed` and confirm:
- the page has `<link rel="next" …>`;
- the entries' `<id>` values are `…/id/ukpga/…` URIs.

If there is no next link, the feed does not page through the whole series. Tell me, and I'll switch the harvester to per-year feeds.

**3. Run it.** Each page lists a few dozen entries, and the harvester logs the pages per series as it goes. I can't count the pages offline; the estimates below assume about 20 entries per page.

Targeted run (recommended; roughly 2–3 h): the series missing from your listing, `ukpga` (regnal-correct, for U2), and the older series whose listing starts in 1970:

```bash
uv run python -m ingest.uk_catalogue harvest \
    --out data/catalogue/uk_catalogue.jsonl --contact YOUR-CONTACT \
    --series ukpga ukla ukci ukcm nisr apgb aep aosp aip apni mnia mwa ukppa gbppa gbla \
             ukmo eudn eudr eut uksro nisro ukdsi sdsi wdsi nidsr ukmd
```

Full run (roughly 13–14 h): leave out `--series`. That re-reads every series, including the ones your listing already covers, and fills the untitled Welsh rows.

**4. List what is still missing (offline).** Rebuild the index, then:

```bash
uv run python -m ingest.build_index --data data --out data/index --snapshot YYYY-MM-DD \
    --catalogue data/catalogue/uk_catalogue.jsonl
uv run python -m ingest.uk_catalogue missing --catalogue data/catalogue/uk_catalogue.jsonl \
    --index data/index --raw-xml uk_scrap_data/raw_xml --out missing.tsv
```

`missing.tsv` holds one row per `ukpga`/`uksi` instrument the catalogue lists but the index lacks: `coordinate`, `url` (its `data.xml`), `save_path` and `title`. Expect the 421 regnal Acts (U2), and possibly the 12 `uksi` feed mismatches.

**5. Fetch them (your scraper).** Fetch each `url` and save it gzip-compressed at `uk_scrap_data/raw_xml/{save_path}`:
- for a regnal Act, the save path mirrors its coordinate, e.g. `ukpga/Geo3Sess2-47/78.xml.gz`;
- where the calendar path already holds another instrument, the directory gets a `refetch-` prefix.

Ingest reads identity from the file's own `IdURI`, never from its path. **Do not re-fetch an instrument already on disk:** two files with the same `IdURI` fail the ingest (`identity_collisions` in the report). Key your queue on the `IdURI` path so the collision cannot recur.

**6. Re-ingest and rebuild.** `uv run python -m ingest.uk --source uk_scrap_data --data data`, then step 4's `build_index`. Ingest skips unchanged instruments. Also update `document_count` in `data/MANIFEST.json`; the licence check fails until it matches.

**Using your own harvester instead of step 3:** write one JSON line per instrument with `coordinate` (e.g. `uk/ukpga/Geo3/47/78`), `series`, `year`, `number` and `title`, as in `router_other_series.jsonl`. `import` replaces the catalogue, so the file must cover every series, `router_other_series.jsonl` included. Then run `import --listing <file>` followed by `import-queue`.

## BOE (Spain) — Stage C

To be documented when Stage C starts.
