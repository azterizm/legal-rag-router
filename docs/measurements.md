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
