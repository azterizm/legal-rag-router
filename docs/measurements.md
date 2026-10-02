# Measurements

Build and load measurements for the router index (plan step 6 / roadmap M6).
Machine: Apple Silicon (Darwin arm64), CPython 3.11.15.

## 2026-09-27: partial UK (Stage A data), index format v1 (JSON tables + gzipped coordinate list)

Input:
- 33,788 instruments (10,720 with structure, 23,068 metadata-only);
- 2,026,078 coordinates;
- 41,668 out-of-coverage catalogue instruments.

| Measure | Value | Target |
|---|---|---|
| Build time (`--no-verify`) | 21.0 s | — |
| Build peak RSS | 960 MB | — |
| Index size on disk | 59.4 MB (coordinates 5.3 MB gz; coverage 15.1; typo 11.2; instruments 9.9; titles 8.3; words 6.3; wordsets 2.1; numbers 1.3) | — |
| **Load time** (`load_index`) | **2,028 ms** | **< 450 ms ✗** |
| **Resident memory after load** | **≈ 990 MB** | ✗ |
| Existence lookup (frozenset) | 80 ns | ✓ |

Per-table load profile (the tracer inflates times about 2×; the proportions hold):

| Table | Load | Retained |
|---|---|---|
| coordinates (frozenset + sorted list + canonical map) | 1,829 ms | 285 MB |
| typo (418k delete variants) | 301 ms | 104 MB |
| coverage | 122 ms | 54 MB |
| instruments | 125 ms | 47 MB |
| titles (100,636 keys) | 59 ms | 31 MB |
| words | 39 ms | 24 MB |
| numbers + wordsets + aliases + case variants | 26 ms | 14 MB |

Reading:
- **frozenset + bisect misses the load budget** at 2M coordinates.
- A node-per-token trie holds one object per segment and would be heavier still.
- Full UK is roughly 2–3× this size (≈ 100k SIs still downloading).
- Plan step 6 anticipated this: past about 1M coordinates, switch to a memory-mapped sorted blob searched with bisect.
- Raw sorted coordinate blob: 54 MB. A Python scan for line offsets takes 158 ms; precomputing the offsets at build time makes that 0 ms.

Decided 2026-09-27: memory-mapped sorted tables (next section).

## 2026-09-27: same data, memory-mapped sorted tables (decision Q-M6-1)

| Measure | frozenset + JSON | mmap sorted tables |
|---|---|---|
| Build time (`--no-verify`) | 21.0 s | 17.8 s |
| Index size on disk (uncompressed; release tarball is compressed) | 59 MB | 121 MB |
| **Load time** (incl. SHA-256 of every file) | 2,028 ms | **132 ms** ✓ (import 34 ms extra) |
| **Resident memory after load + lookups** | ≈ 990 MB | **29 MB** ✓ |
| Coordinate existence lookup | 80 ns | 5.7 µs |
| Title key lookup | — | 4.6 µs |

- Load time is dominated by hashing the files, and grows linearly with index size (roughly 1 ms per MB). Parsing no longer does.
- Lookups stay far inside the < 2 ms routing budget.
- The in-memory token trie is dropped: titles are found by looking up the query's n-grams in the title table.


## 2026-09-27: latency on 4 KB noise (roadmap Q-M7-2, `bench/stress.py`)

Decision: **split budget.**
- The **< 2 ms p99 target applies to real queries**. It is measured and published by `bench/latency.py` at M10. Typical queries on the fixture take 0.003–0.3 ms; a realistic 4 KB legal paragraph with several citations takes 1.3 ms.
- For **random noise** at the 4 KB cap, the published figure is the measured worst case across the gibberish classes below, not an assumed bound. Each class strains a different stage. Each sample is the fastest of 5 warm runs (the machine's own jitter is removed, the algorithm's cost is not); 40 samples per class; fixture index; macOS-26.6.2-arm64-arm-64bit, Python 3.11.15.
- The test suite guards **2× this floor** (scaled on CI, where `LRR_LATENCY_BUDGET_MS=25`). It also checks **linear scaling** per class: doubling the input must not more than 2.5× the time.

| Class | p50 ms | p99 ms | max ms | 2× ratio |
|---|---|---|---|---|
| title_vocabulary | 4.74 | 7.22 | 7.22 | 1.20 |
| unicode_expanding | 4.90 | 6.43 | 6.43 | 2.06 |
| digits_and_years | 6.00 | 6.23 | 6.23 | 1.55 |
| unicode_mix | 4.28 | 4.99 | 4.99 | 2.19 |
| printable | 3.26 | 4.71 | 4.71 | 2.15 |
| type_words_and_years | 3.40 | 3.68 | 3.68 | 1.23 |
| dense_punctuation | 2.67 | 2.71 | 2.71 | 2.01 |
| identifier_soup | 2.39 | 2.40 | 2.40 | 2.03 |
| whitespace_heavy | 2.02 | 2.05 | 2.05 | 2.01 |
| citation_soup | 1.98 | 2.03 | 2.03 | 1.86 |
| provision_soup | 2.01 | 2.03 | 2.03 | 1.89 |
| letters_digits | 1.52 | 1.99 | 1.99 | 2.27 |
| no_spaces | 0.06 | 0.06 | 0.06 | 1.93 |

**4 KB noise floor: 7.22 ms** (worst class, worst sample).

What made it linear and bounded:
- The plan's prefilter: text with no digits, instrument-type words, alias words or out-of-coverage cues returns before tokenising.
- Fold once, with fast paths for ASCII and one-to-one characters.
- `NamedTuple` tokens.
- Binary-search span checks.
- Caps on provision, number, identifier and cue mentions, applied before any pairwise work.
- Alias anchors only where a whole alias is spelt out.
- A title-lookup budget that fails safe to `ROUTE_UNRESOLVED`.


## 2026-09-28: 4 KB noise floor re-measured

The floor recorded on 27 Sept (7.22 ms) was measured before that day's coverage-sweep fixes. Re-measured on 28 Sept, same machine and method, and it rose. Three trees were measured side by side on 28 Sept:

- `e0d07f7` (where 7.22 ms was recorded): 7.00 ms.
- `afc49c4` (after the sweep fixes): 9.52 ms.
- Today's tree: 9.49 ms.

The rise came from the sweep fixes (more title work per anchor: chapter notes, capitals, back-references), not from today's former-title, acronym and grammar changes. Real queries are unaffected at this scale (M10 measures them). The published figure and the test guard follow the new measurement (decision 16).

| Class | p50 ms | p99 ms | max ms | 2× ratio |
|---|---|---|---|---|
| title_vocabulary | 8.12 | 9.49 | 9.49 | 1.30 |
| digits_and_years | 7.03 | 7.29 | 7.29 | 1.46 |
| unicode_expanding | 5.19 | 6.99 | 6.99 | 2.12 |
| unicode_mix | 4.57 | 5.33 | 5.33 | 2.19 |
| printable | 3.43 | 4.70 | 4.70 | 2.01 |
| type_words_and_years | 4.52 | 4.61 | 4.61 | 1.19 |
| dense_punctuation | 2.90 | 2.97 | 2.97 | 1.99 |
| identifier_soup | 2.62 | 2.64 | 2.64 | 2.02 |
| letters_digits | 1.68 | 2.37 | 2.37 | 2.45 |
| whitespace_heavy | 2.31 | 2.34 | 2.34 | 2.01 |
| provision_soup | 2.27 | 2.28 | 2.28 | 1.89 |
| citation_soup | 2.19 | 2.26 | 2.26 | 1.86 |
| no_spaces | 0.06 | 0.06 | 0.06 | 1.91 |

**4 KB noise floor: 9.49 ms** (worst class, worst sample). Doubling stays linear (every ratio ≤ 2.5).


## 2026-09-28: full UK index (Stage B)

All of legislation.gov.uk's `ukpga` and `uksi` as downloaded on 28 Sept: 133,798 files, all read with 0 failures. Mac (Apple silicon), macOS 26.6.2, Python 3.11.15.

| Measure | Stage A (partial) | **Full UK** | Target |
|---|---|---|---|
| Ingest (`ingest.uk`, 9 workers) | 35 s | **124 s**, peak RSS 0.44 GB | |
| Instruments / with structure / PDF-only | 33,788 / 10,720 / 23,068 | **133,798 / 69,902 / 63,896** | |
| Provisions / harvested citations | 2.0M / 2.4M | **5.56M / 4.51M** | |
| Index build (`ingest.build_index`) | 17.8 s | **132 s**, peak RSS 4.2 GB | |
| Coordinates / title keys / catalogue (out of coverage) | 2.0M / — / — | **5.70M / 420,776 / 34,912**; after the U2 re-fetch and your full catalogue: 134,219 instruments, 421,472 title keys, **103,008** out of coverage | |
| Index size on disk | 121 MB | **320 MB** | |
| **Load time** (incl. SHA-256 of every file) | 132 ms | **120–134 ms** | < 450 ms ✓ |
| **Resident memory after load + lookups** | 29 MB | **35 MB** | |

Load time did not grow with the index: hashing is fast and nothing is parsed up front.

### Real-query latency (plan step 7: p99 < 2 ms)

First measured over 20,000 replayed source citations of the sweep sample (superseded below by the 100,000-query measurement) (real drafting, mean 70 characters, up to about 300). Each query is timed as its fastest of 3 warm runs.

| p50 | p90 | **p99** | p99.9 | max |
|---|---|---|---|---|
| 0.13 ms | 0.29 ms | **1.89 ms** ✓ | 7.1 ms | 11.4 ms |

On the full index the first measurement was **p99 3.83 ms, max 366 ms**. Three changes brought it under 2 ms, and none changes a result:

- **Refusal suggestions** (`typo.suggestions`) measured title edit distance against every candidate sharing a word: 1,400 long titles for "Offshore Installations (Safety Zones) Regulations". It now ranks in stages (shared words, then year gap, then edit distance) and reads an instrument only for the groups that can reach the top 3. Edit distance is capped at the worst one still kept. Checked against the old ranking on 2,963 titles: identical results, 5–6× faster.
- **Table lookups** (`table.SortedTable`): a probe compares the key with the line's first `len(key) + 1` bytes instead of finding the tab and building a tuple. This is exact because tab and newline sort below every byte a key may hold. The encoder now rejects control characters in keys, so that holds by construction; no key in either index had one.
- Together: max 366 → 11 ms, p99 3.83 → 1.89 ms.

The margin under 2 ms is thin. The remaining tail is still suggestions for refused titles whose words are common (thousands of candidates share "regulations", "amendment"…). M10's `bench/latency.py` publishes the sealed figure.

**Re-measured on 100,000 queries (28 Sept, after the U2 re-fetch).** The table above came from one 20,000-query draw, and that draw was easier than average. On the refreshed sweep sample (new seeded draw, because the re-fetch added citations to the harvest), five 20,000-query slices gave p99 2.13–2.43 ms, and all 100,000 gave **2.25 ms**. That misses the target. The old draw still gives 1.86 ms on the same index. Neither the 421 re-fetched Acts nor the larger catalogue caused it: indexes built without either give the same 2.17–2.18 ms on the same queries.

The tail was again refusal suggestions. Grouping candidates by year gap read and parsed every candidate instrument (about 520 per refused title) just for its year. A UK calendar id carries its year (`uk_uksi_2011_3006`), and the build now fails if a record's year disagrees with its id, so the ranking reads records only for regnal Acts and for the titles it compares. The ranking is unchanged: it was checked against the old one on all 450 ranking calls in 20,000 queries, with and without a year.

| Sample | p50 | p90 | **p99** | p99.9 | max |
|---|---|---|---|---|---|
| 100,000 replays, before | 0.13 ms | 0.29 ms | 2.25 ms ✗ | 7.04 ms | 30.5 ms |
| **100,000 replays, after** | 0.13 ms | 0.29 ms | **1.88 ms** ✓ | 5.29 ms | 30.6 ms |

After the change the five slices give p99 1.81–1.91 ms. The margin is still thin, and M10's `bench/latency.py` should publish p99 over the full 100,000, not over one slice. The 30.6 ms maximum is a single query: a refused title whose words are shared by 1,289 pension regulations of the same year, each compared by edit distance.

### 4 KB noise (decision 16)

| Index | Floor (worst class, worst sample) | Worst class |
|---|---|---|
| Fixture (the test guard: 2× this) | **9.38 ms** (9.06 before the M10 fixes) | `unicode_expanding` |
| **Full UK** | **9.34 ms** (9.21 before the M10 fixes; 17.47 ms before Q-B-3) | `unicode_expanding` |

Before Q-B-3 the full index's worst class was `title_vocabulary` at 17.47 ms: a soup of title words made up to 16 unknown-title checks, each ranking suggestions over the full vocabulary. Since Q-B-3 (roadmap decision 21) each check costs 32 lookups against the 320-lookup work limit (grammar.md UK-W-03). At most 10 run per query, and that class now takes 8.6 ms at worst. The figures above are from after the U2 re-fetch and the year-from-id change (fixture 9.14 → 9.06 ms, rebuilt from your catalogue; full 9.31 → 9.21 ms). The fixes from the first sealed run (29 Sept: the known-word typo pass, the 48-anchor limit) move the floor by a few tenths of a millisecond, inside run-to-run noise. On the full index the anchor limit now stops `title_vocabulary` soup early (8.6 → 1.4 ms), and `digits_and_years` falls from 7.3 to 2.6 ms.

**Real queries are unaffected.** Across the 100,000-citation sweep sample, no query needs more than 5 checks, and a charge of 32 moves none over the limit. The 154 over it were already over on plain lookups. The sweep's outcome counts are unchanged apart from decision 20, and p99 on that 20,000-query draw stays at 1.88 ms.

`letters_digits` shows a 2.7× doubling ratio on both indexes. That is not superlinear cost: the bench's fixed 4 KB sample contains a bare provision that its 2 KB prefix doesn't, and resolving it over the salient instruments adds about 0.6 ms. Timed on other seeds, the class scales 1.6–1.7× per doubling. Results: `bench/results/stress-darwin-arm64.json` (fixture) and `stress-darwin-arm64-full-index.json`.

## 2026-09-29: concept index and discovery (stages D3–D4)

`ingest.build_concept_index` over the full UK records (schema 2: long titles and cross-headings), with the D4 stemmer, priors and thesaurus. Mac (Apple silicon), Python 3.11.15.

| Measure | Value |
|---|---|
| Documents | 1,322,050: 1,187,831 section-level provisions and schedules, 134,219 instruments |
| Terms / postings | 197,195 / 52,552,653 |
| Build (with the harvest's citation in-degree) | 168 s, peak RSS about 2.8 GB |
| Size on disk | 546 MB (postings 2 × 210 MB, documents 131 MB, priors 2.6 MB) |
| Load (SHA-256 of every file) | about 210 ms |
| Determinism | a second build is byte-identical (checked at D3) |

The concept index is a separate directory from the router index. Building it doesn't change the router index, and loading the router doesn't load it.

**`discover()` latency, on the concept battery's dev slice (112 queries), tuned policy:** p50 73 ms, p99 181 ms, max 219 ms.

This is outside `route()`'s < 2 ms path: discovery is an interactive step, followed by confirmation. The common-word cut-off trades speed for recall:

| Cut-off (share of documents) | Top 10 | p99 |
|---|---|---|
| 2 % | 73 % | 46 ms |
| 10 % (chosen) | 91 % | 181 ms |
| 20 % | 91 % | 245 ms |
| no cut-off | 92 % | 334 ms |


## 2026-09-29: sealed-run latency, Apple Silicon (roadmap M10)

`bench/latency.py`, `bench/results/latency-darwin-arm64.json`: the 100,000 replayed real citations of the coverage sweep plus every battery row. That is 102,112 queries, 3 timed repeats each (306,336 calls), after a warm-up pass, with garbage collection paused. The full UK index. macOS 26.6.2 arm64, Python 3.11.15.

| Status | calls | p50 | p99 | max |
|---|---|---|---|---|
| All | 306,336 | 138 µs | **1.98 ms** | 31.2 ms |
| `ROUTE_BOUNDED` | 245,652 | 135 µs | 0.70 ms | 31.2 ms |
| `ROUTE_UNRESOLVED` | 25,854 | 35 µs | 3.40 ms | 10.5 ms |
| Provision not found | 18,246 | 191 µs | 1.65 ms | 12.7 ms |
| `ROUTE_AMBIGUOUS` | 13,371 | 391 µs | 5.95 ms | 13.6 ms |
| Out of coverage | 1,905 | 135 µs | 1.70 ms | 4.9 ms |
| Instrument not found | 1,308 | 388 µs | 4.86 ms | 17.8 ms |

It counts every call rather than the best of three per query, which is stricter than the earlier 1.88 ms figure.

### After the sealed-run fixes (v2, 29 Sept)

The same bench at `0b25a14` (the v2 battery seal) on the same machine: p50 141 µs, **p99 2.11 ms** over all 306,336 calls. Bound results p99 0.85 ms. That misses the < 2 ms target by 0.11 ms. The per-status table and the v1 → v2 comparison are in `reports/sealed-run-uk.md`. A back-to-back A/B on 30,000 queries confirms it is the fixes' cost (1.98 → 2.1 ms), not noise.

The controlled three-pass figures below supersede this single pass. A first x86-64 run on 29 Sept was withdrawn: Chrome was running heavily in the background.

## 2026-09-30: controlled latency, Apple Silicon (roadmap stop 18)

`bench/results/mac-rerun-2026-09-30/`, from `scripts/latency_mac.py` at `7221a1b`. It ran 3 passes of the unchanged bench, each in a fresh process: 306,336 calls per pass (the 100,000 replayed citations plus every battery row, 3 repeats), with garbage collection paused. It used the full UK index, verified against the v2 seal (`024da21e…`).

**Machine and conditions** (`env-before.json`, `env-after.json`):
- **Hardware:** Apple M4 MacBook Air (Mac16,12), 4 performance and 6 efficiency cores, 16 GB; internal SSD.
- **Software:** macOS 26.6.2 (25G83); Python 3.11.15 (Clang); `perf_counter` resolution 42 ns.
- **Power:** on mains power; low-power mode off; no thermal or performance warning recorded before or after.
- **Background:** no browser running. Spotlight indexing is off on `/`, Time Machine idle, Gatekeeper on.
- **Uptime:** 251.6 hours, so the Mac was not rebooted first.
- **Launch:** from a Terminal window at the machine, not over SSH; no tracked changes in the tree.

**Each pass:**

| Pass | CPU busy before | CPU busy during | p50 | p99 | max |
|---|---|---|---|---|---|
| 1 | 1.3 % | 10.9 % | 139.8 µs | 2.10 ms | 31.3 ms |
| 2 | 1.7 % | 11.1 % | 138.4 µs | 2.08 ms | 31.5 ms |
| **3 (median by p99)** | 7.4 % | 21.6 % | 140.0 µs | **2.10 ms** | 31.3 ms |

- **Quiet start:** all three passes started quiet on the first try (≤ 10 % average CPU busy).
- **The bench's own load:** the bench keeps one of ten cores busy, about 10 %.
- **Pass 3 background:** macOS's XProtect remediator scanned during pass 3 (listed after it, about one more core). Pass 3's p99 is the middle of the three, so the scan did not visibly move it.
- **Before the run:** Safari's SafeBrowsing service and `mobileassetd` were busy when the machine's state was recorded. They had settled by the first quiet check.

**Headline, pass 3 (median by p99):**

| Status | calls | p50 | p99 | max |
|---|---|---|---|---|
| All | 306,336 | 140 µs | **2.10 ms** | 31.3 ms |
| `ROUTE_BOUNDED` | 246,285 | 137 µs | 0.84 ms | 31.3 ms |
| `ROUTE_UNRESOLVED` | 25,794 | 37 µs | 3.58 ms | 10.4 ms |
| Provision not found | 18,282 | 197 µs | 1.99 ms | 12.7 ms |
| `ROUTE_AMBIGUOUS` | 12,804 | 393 µs | 6.22 ms | 14.2 ms |
| Out of coverage | 1,899 | 139 µs | 1.73 ms | 4.9 ms |
| Instrument not found | 1,272 | 405 µs | 5.87 ms | 18.5 ms |

- **Across passes:** p50 138–140 µs, p99 2.08–2.10 ms. **p99 misses the < 2 ms target in every pass, by 0.08–0.10 ms.**
- **Agreement with 29 Sept:** the single-pass 2.11 ms of 29 Sept (`bench/results/latency-darwin-arm64.json`, now superseded) agrees.
- **Outcomes:** every pass has the same per-status call counts, which also match 29 Sept's.

**The tail is a fixed set of slow queries, not noise.** Timed once each, 1,109 of the 102,112 queries (1.09 %) take over 2 ms. A tail slightly heavier than 1 % is exactly what puts p99 just past 2 ms.

The maximum is the same query in every run. It is one of the replayed real citations, a 232-character bound query that lists several SI numbers ("These Regulations amend the Parliamentary Pensions (Consolidation and Amendment) Regulations 1993 (S.I. 1993/3…"), and it takes 31 ms. The next slowest (14–19 ms) are also long, real citations with many instruments or provisions.

## 2026-09-30: controlled latency, x86-64 (roadmap stop 18)

`bench/results/x86-rerun-2026-09-30/`, from `scripts/latency_rig.ps1` at `7221a1b`. The same 3 passes of the unchanged bench as the Mac: 306,336 calls each, full UK index, v2 seal verified on the rig. The files are the rig's originals (Windows line endings).

**Machine and conditions** (`env-before.json`, `env-after.json`):
- **Hardware:** Intel Core i5-3570 (Ivy Bridge, 2012), 4 cores / 4 threads, 3.4 GHz base; 16 GB DDR3-1600 (2 modules); PNY CS900 SATA SSD.
- **Software:** Windows 11 Pro 24H2 (build 26100); Python 3.11.16 (MSVC); `perf_counter` via QueryPerformanceCounter, 100 ns resolution.
- **Power:** "Ultimate" power plan, minimum and maximum processor state 100 % on mains; desktop, no battery. During the passes the clock ran at 110–111 % of base (turbo, about 3.8 GHz).
- **Security, left on as in a deployment:** Defender real-time, on-access and behaviour monitoring on, tamper-protected; the repo is not excluded.
- **Services:** SysMain and Windows Search running; Windows Update stopped.
- **Background:** no browser running.
- **Uptime:** 15.3 hours.
- **Launch:** at the machine (not over SSH), elevated; no tracked changes.

**Each pass:**

| Pass | Quiet start (tries) | CPU busy during (avg / max) | p50 | p99 | max |
|---|---|---|---|---|---|
| 1 | yes (1) | 38 % / 100 % | 510.4 µs | 9.25 ms | 136.8 ms |
| 2 | yes (3) | 29 % / 66 % | 501.2 µs | 9.14 ms | 130.4 ms |
| **3 (median by p99)** | yes (1) | 27 % / 47 % | 501.0 µs | **9.21 ms** | 130.1 ms |

- **The bench's own load:** the bench keeps one of four threads busy, 25 %.
- **Defender during pass 1:** Defender's engine (`MsMpEng`) scanned during pass 1. It was at 47 % CPU just after it, and busy peaked at 100 %. That pass has the highest p99 and max.
- **Pass 2's start:** the quiet check turned pass 2 away twice (26 % and 19.5 % busy) before it started quiet on the third try.
- **The headline pass:** pass 3 is the cleanest of the three.

**Headline, pass 3 (median by p99):**

| Status | calls | p50 | p99 | max |
|---|---|---|---|---|
| All | 306,336 | 501 µs | **9.21 ms** | 130.1 ms |
| `ROUTE_BOUNDED` | 246,285 | 494 µs | 3.56 ms | 130.1 ms |
| `ROUTE_UNRESOLVED` | 25,794 | 130 µs | 15.21 ms | 47.8 ms |
| Provision not found | 18,282 | 698 µs | 8.62 ms | 58.6 ms |
| `ROUTE_AMBIGUOUS` | 12,804 | 1,508 µs | 28.23 ms | 68.3 ms |
| Out of coverage | 1,899 | 492 µs | 6.92 ms | 21.6 ms |
| Instrument not found | 1,272 | 1,677 µs | 24.71 ms | 79.4 ms |

**Range across passes:** p50 501–510 µs, p99 9.14–9.25 ms.

**p99 misses the < 2 ms target by a factor of 4.6 in every pass. Bound results miss it too (3.49–3.60 ms).**

**Against the Mac's headline pass:**
- The rig is 3.6× slower at p50 and 4.4× slower at p99. The ratio is about the same for every status (3.5–4.1× at p50, 4.0–4.5× at p99), so the whole distribution scales with the machine.
- Per-status call counts are identical to the Mac's in every pass.

**Recorded (your decision, 30 Sept):** the < 2 ms p99 target is **not met on either machine**, and the code is not changed after the seal.

**The withdrawn 29 Sept run** (Chrome running) gave p99 12.27 ms: 33 % above this, and p50 24 % above.

## 2026-09-30: Row B, the router as a network service (roadmap M11)

`bench/results/row-b-router-2026-09-30/` (`summary.json` and every call in `calls.jsonl`), from `bench/row_b.py` against `deploy/modal_router.py`. This is the router's side of Row B; the interleaved run with Jev and Gemini comes later.

**Setup:**
- **Client:** the Mac (M4), in Pakistan; one keep-alive HTTPS connection (httpx 0.28.1).
- **Service:** Modal, pinned to us-east (§4 decision 23); it ran on GCP, AMD Zen 3 (family 25, model 1) at 2.45 GHz, in the gVisor sandbox, with a 1-core quota and 1 GiB; Python 3.11.12. The same container ran from start to finish, with no reconnects.
- **Calls:** every battery row (2,112) × 3. Each `/route` call is paired with a `/floor` call: the same request to the same host, with no routing. The pairs, and the order within each pair, are seeded random; 50 warm-up pairs are discarded. 59 minutes.

| Measure (6,336 calls each) | p50 [95 % CI] | p99 [95 % CI] | max |
|---|---|---|---|
| `/route` round trip | **276.6 ms** [276.4–276.8] | 364.5 ms [352.7–374.9] | 1,336 ms |
| `/floor` round trip (network only) | 275.7 ms [275.5–275.9] | 367.0 ms [358.6–377.1] | 1,389 ms |
| The router's own time, in the container | 0.63 ms [0.62–0.63] | 3.65 ms [3.46–4.04] | 15.7 ms |
| Paired difference, route − floor | 0.84 ms | 79 ms (two calls' network jitter) | |

- **Correctness:** **0 of 6,336 answers differ** from the local router on the same index.
- **Where the time goes:** the round trip is almost all network. The router is 0.3 % of it at p50.
- **The container is slower than the Mac:** on the same battery rows × 3, in-process on the Mac, the router takes p50 0.12 ms and p99 1.23 ms. The container is 5.4× slower at p50 and 3× at p99, on a slower core under a sandbox and a CPU quota.
- **Choosing the region:** the region was chosen by the lowest measured network floor (§4 decision 23). Pakistan has no Modal region, and every Modal web call enters through `*.modal.run` in AWS us-east. So the nearest regions were the slowest: the Middle East at 587 ms and Mumbai at 648–730 ms, against us-east at 249–276 ms.
- **Cost:** about an hour of container time at 1.75× (the pinned region) for this run, plus nine short smoke runs. That is roughly $0.2 in all by the published rates. The Modal dashboard has the billed figure.

## 2026-09-30: Laya, speed and footprint, Apple M4 (roadmap M11, §4 decision 3 as amended)

`bench/results/laya-darwin-{cpu,mps}-2026-09-30.json`, from `bench/clients/laya.py`. Speed and footprint only: the answers are never read, because the vendor documents the base checkpoint as near chance without fine-tuning.

**Setup:**
- **Model:** `convaiinnovations/laya` (421M, base English checkpoint) at revision `55cf4c4e…`, every weight file verified against its recorded SHA-256; loaded directly with `laya.load`.
- **Software:** laya 0.3.22, torch 2.14.0, transformers 5.17.0, Python 3.11.15.
- **Where it ran:** the Mac (M4, macOS 26.6.2), plugged in, browsers closed; weights offline (`HF_HUB_OFFLINE=1`). On the CPU, PyTorch used 4 threads; the router uses one.
- **Calls:** 300 battery queries (seeded sample), each asked one `choice` question ("Which instrument does this text cite?"). The options are 3, 10 or 30 titles drawn from the 1,562 real instruments the batteries cite. 20 warm-up calls discarded. p50/p99 with bootstrap 95 % intervals.

| Options | CPU p50 [95 % CI] | CPU p99 | GPU (MPS) p50 [95 % CI] | GPU p99 | Tokens per option | Share of each title seen (median) |
|---|---|---|---|---|---|---|
| 3 | 89.3 ms [88.8–90.3] | 137.0 ms | 50.2 ms [50.1–50.4] | 88.0 ms | whole title | 100 % |
| 10 | 139.1 ms [138.3–139.6] | 170.1 ms | 80.2 ms [80.0–80.5] | 106.0 ms | up to 17 | 100 % |
| 30 | 138.5 ms [138.3–138.7] | 169.7 ms | 81.0 ms [80.7–82.3] | 116.5 ms | **5** | **29 %** |

- **Every call fitted** (0 of 300 at each count), and no options collapsed into identical tokens.
- **But at 30 options Laya cuts every title to 5 tokens, marker included.** That is its 192-token option budget, `max(4, 176 // n)` per option, in laya 0.3.22's `common.build_sequence`. It raises nothing and flags nothing. The model sees a median 29 % of each title. The longest title in the pool, "The Welfare Reform Act 2012 (Commencement No. 9, 21 and 23 (Amendment), … ) Order 2018", reaches the model as **"The Welfare Reform Act"**, which is the same for every Welfare Reform Act commencement order.
- **Why 30 options cost no more than 10:** the input is capped by that budget. 30 options use 180 input tokens at p50, 10 options 188.
- **Laya's own warning at load:** "this checkpoint ships invalid temperatures … Treat confidence from the affected entries as uncalibrated." It does not affect speed.

**Footprint, against the router on the same Mac:**

| | Laya (CPU) | Laya (MPS) | The router |
|---|---|---|---|
| Install | 693 MB (PyTorch, transformers, laya) | same | 0.6 MB of source, no dependencies |
| Model or index on disk | 807 MB of weights | same | 362 MB index |
| Load | 1.8 s | 1.6 s | 0.14 s |
| Peak memory | 2.81 GB | 2.82 GB, plus 2.07 GB of GPU memory | 0.32 GB after 20,000 real queries (mostly the memory-mapped index) |
| Time per call, p50 | 89–139 ms | 50–81 ms | 0.12 ms (battery rows) / 0.14 ms (all 306,336 calls) |

- **Laya is about 740–1,200× the router's p50 on the CPU, and 420–690× on the Mac's GPU.**
- **None of this depends on fine-tuning:** a tuned checkpoint has the same size, the same context and the same cut.

### The rig, CPU (30 Sept)

`bench/results/laya-windows-cpu-2026-09-30.json`: the same client, pinned weights (copied from the Mac, SHA-256 verified on the rig), 300 queries at each option count, 20 warm-up calls discarded.
- **Machine:** Intel i5-3570, Windows 11; torch 2.14.0+cpu with 4 threads. PyTorch runs on this CPU although it lacks AVX2.
- **Version difference:** the rig resolved transformers **5.18.0** (the Mac 5.17.0), because the command did not pin it. The GPU run pins 5.17.0.

| Options | p50 [95 % CI] | p99 | Share of each title seen |
|---|---|---|---|
| 3 | 1,165 ms [1,128–1,209] | 2,336 ms | 100 % |
| 10 | 1,987 ms [1,969–2,021] | 2,706 ms | 100 % |
| 30 | 1,927 ms [1,906–1,951] | 2,670 ms | 29 % (5 tokens per title) |

- **Every call fitted** and no options collapsed; the same cut as on the Mac.
- **Load:** 9.8 s.
- **Memory was not measured:** the client read peak memory only through `resource`, which Windows lacks. It now reads the peak working set on Windows too, for the GPU run.
- **Against the router on the same machine** (p50 0.50 ms over all 306,336 calls, 29 Sept): Laya takes about **2,300–4,000×** as long per call.

### NVIDIA Tesla T4 on Modal (30 Sept, UTC)

`bench/results/laya-modal-t4-2026-09-30.json`, from `deploy/modal_laya.py`.
- **Setup:** the same timing code (`bench.clients.laya.measure`) on the same seeded plan, written on the Mac. Weights fetched at the pinned revision in the image build and verified against the Mac's SHA-256s. Model time only, inside the container.
- **Machine:** Tesla T4 on Modal, with 4 cores and 8 GiB (gVisor); torch 2.14.0+cu130, transformers 5.17.0, laya 0.3.22, Python 3.11.12.
- **Why the T4:** it is the GPU of the vendor's published figure, 33–40 ms per call. It replaces the rig's GTX 1650, which was dropped on 1 Oct.

| Options | p50 [95 % CI] | p99 | Share of each title seen |
|---|---|---|---|
| 3 | 34.2 ms [34.0–34.3] | 43.8 ms | 100 % |
| 10 | 35.5 ms [35.4–35.7] | 44.6 ms | 100 % |
| 30 | 36.9 ms [36.7–37.0] | 46.4 ms | 29 % (5 tokens per title) |

- **The vendor's figure reproduced:** 34–37 ms at p50, against their 33–40 ms. Laya was run as intended, on its reference GPU.
- **Every call fitted**, with no collapsed options, and the same title cut as on every other machine.
- **Footprint:** installed 5.6 GB (Linux PyTorch bundles the CUDA libraries); weights 807 MB; load 10.2 s; 2.32 GB of GPU memory. The sandbox's peak-RSS figure (6.0 GB) already reads 3.1 GB before the model loads, so it is not comparable with the Mac's and is not used.
- **Cost:** a few minutes of T4 time, a few US cents.

**Laya across machines, p50 at 3 / 10 / 30 options, against the router:**

| Where | Laya | The router, same machine |
|---|---|---|
| Tesla T4 (Modal, the vendor's GPU) | 34 / 36 / 37 ms | no GPU needed. On a Modal CPU container: 0.63 ms (Row B, battery rows) |
| Apple M4 GPU (MPS) | 50 / 80 / 81 ms | 0.12 ms on the M4's CPU (battery rows) |
| Apple M4 CPU | 89 / 139 / 139 ms | 0.12 ms |
| Intel i5-3570 CPU (the rig) | 1,165 / 1,987 / 1,927 ms | 0.50 ms (all 306,336 calls) |

- **Even on its reference GPU, Laya's p50 is about 55–60× the router's on a single cloud CPU core, and 280–310× the router's on the Mac.**
- **Laya needs a GPU to get there.** On the same CPUs the router runs on, it is 740–4,000× slower.
- **None of this depends on fine-tuning.** The title cut at 30 options is the same on every machine.

## 2026-10-01: the router against Gemini, Jev and Laya (roadmap M11)

The full comparison (accuracy, determinism, cost, latency and data egress) is in `reports/comparison-uk.md`, sealed as `seals/results-compare-2026-10-01.json`. Latency from that run:
- Jev, p50 507 ms;
- Gemini through the author's proxy, p50 13.5 s and p99 192 s;
- the router in process inside the interleaved pass, p50 1.18 ms, slower than the controlled 0.14 ms because every call followed a multi-second network wait.
