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

- **Download incomplete** (U5): ≈ 100k SIs and 24 large Acts are pending, including CA 2006, ITA 2007, CTA 2009/2010 and FSMA 2000.
- **Pre-1963 key collisions in the external fetch** (U2): 421 Acts dropped. The regnal-keyed catalogue (U4 harvest, Stage B) lists exactly which.
- **Other-series listing**:
  - It starts in 1970 and misses `apgb`, `aep`, `aosp`, `aip`, `apni`, `mnia`, `mwa`, `uksro`, `nisro` and the draft series.
  - 6,656 Welsh rows (`wsi`, `anaw`, `asc`) have **no title**. They are kept as untitled catalogue entries, so they still count as existing by number.
  - The Stage B harvest (`ALL_SERIES`) closes all of this.
- **Stage B check before harvesting:** confirm with one request that `/{series}/data.feed` pages through the whole series via `rel="next"`. If it doesn't, switch to per-year feeds.

## BOE (Spain) — Stage C

To be documented when Stage C starts.
