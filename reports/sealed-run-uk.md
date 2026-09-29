# The sealed run (UK), 29 Sept 2026: reading the results

The sealed table is `results/uk-run-2026-09-29.md`, with every row's outcome in `results/uk-run-2026-09-29.json`. Both are sealed in `seals/results-2026-09-29.json` (`3248958d…`), which cites the battery seal `battery-2026-09-29` (`30be2e57…`). The run was at commit `5df82af`, index snapshot 2026-09-28, Python 3.11.15 on macOS arm64. This note explains the table and doesn't change it.

**How the run went.** The first attempt, at `98bf045`, routed every battery and wrote its results, then failed at the sealing step (a relative `--seal` path; fixed in `5df82af` with a test). Its files were deleted unread. Routing is deterministic, and the fix touched only sealing, so the run was repeated once and sealed. Nothing was tuned between the two.

## Headline (plan targets)

| Metric | Result | 95 % upper | Target |
|---|---|---|---|
| Collision (`collision` battery) | 0 / 40 | 7.2 % | 0.0 % ✓ |
| **Misroute on held-out real citations** (`misroute` battery) | **0 / 1,030** | **0.29 %** | ≤ 0.5 % ✓ |
| Misroute, all bound rows | 2 / 1,897 (both mislabelled; see below) | 0.33 % | ≤ 0.5 % ✓ |
| Bound to the wrong instrument, all rows | 0 / 1,897 | 0.16 % | |
| **Bound on invented law** | **0 / 68** | 4.3 % | 0.0 % ✓ |
| Strict abstention on invented law | 68 / 68 | | |
| False abstention, sampled *current* provisions (`false_abstention` battery) | 2 / 773 | 0.81 % | ≤ 0.5 % (the upper bound misses it) |
| False abstention, held-out real citations | 82 / 1,030 | 9.5 % | see below |
| Miss, held-out real citations | 67 / 1,000 | 8.2 % | reported |
| Covered law reported out of coverage | 7 / 2,021 | 0.65 % | |
| Out-of-coverage law refused | 0 / 16 | 17 % | |
| Typo auto-correct precision / recall | 29 / 29, 28 / 31 | | |
| Typo clarify recall | 5 / 7 | | |

## The rows that didn't come out as expected

**The two "misroutes" are my labels, not router errors.** Both are Part / Chapter queries: "Part 2, Chapter 1 of the Data Protection Act 2018" and "Companies Act 2006 Pt 10 Ch 2". I labelled them with the chapter coordinate (`…/pt2/ch1`). The router binds the chapter's sections (`s4`, `s5` …), which is what grammar.md UK-P-13 says a Part or Chapter does. The row expected one thing and the grammar specifies another, so the row is wrong. No wrong law was bound.

**Held-out real citations: no wrong binding in 1,030.** The 196 rows not met are all non-bindings:
- **82 refused.** Mostly citations in annotation text to provisions the current text no longer has: spent regulations of amending SIs, repealed sections ("Companies Act 1989 ss. 114(1), 213(2)"). Decision 19 refuses these by design. Also host provisions linked across annotation prose ("Sch. 8 para. 50 in force … see s. 170(1) and S.I. 1991/2288, art. 3").
- **67 unresolved.** Mostly bare `yyyy/n` table cells (UK-U-05).
- **40 asked.** Also 7 out of coverage.

Current law is refused rarely: 2 in 773 sampled current provisions (0.26 %). Both are unusual titles:
- one contains "(expired—";
- one embeds another Act's name ("… (Amendment of paragraph 7 of Schedule 17 to the Coronavirus Act 2020) …").

A third, "Competition Act 1998 (Section 11 Exemption) Regulations 2001 …, reg. 3(2)", was asked about instead of bound.

**Where the router doesn't do what grammar.md says** (none binds wrong law, except the linking case, which binds across a sentence):
1. `c.18` alone routes unresolved; UK-I-08 says ambiguous.
2. "The Theft Act 1968 applies. Section 1 defines theft." binds Theft Act s. 1. UK-L-02 says a sentence end breaks the link, so it should ask. **The only safety-relevant deviation.** Here it happens to bind the intended provision, but linking across sentences could bind a provision to the wrong Act.
3. 25 repeats of "Theft Act 1968 and" bind rather than trip the too-complex limit (UK-W-03 counts mentions; repeated identical titles seem to be merged first).
4. "the explanatory notes to the Equality Act 2010" binds the Act; UK-U-03 says unresolved.

**Typo tiers:**
- "Rights of Employmnet Act 1996" (reordered and misspelled) was bound to ERA 1996, the right Act, where the tiers say to ask. It counts in "bound when it should not" (1 / 22). **No invented near-miss was bound.**
- "Road Trafic", "Health and Saftey" and "Employment Right" were not corrected (recall misses: refused with suggestions).
- "Partys" (two edits) was refused rather than asked about.
- "rights of employment act 1990" was asked about rather than refused.

## Latency (Apple Silicon)

`bench/results/latency-darwin-arm64.json`: 306,336 calls (the 100,000 replayed real citations plus every battery row, 3 repeats each, garbage collection paused).

| Status | calls | p50 | p99 |
|---|---|---|---|
| All | 306,336 | 138 µs | **1.98 ms** |
| `ROUTE_BOUNDED` | 245,652 | 135 µs | 0.70 ms |
| `ROUTE_UNRESOLVED` | 25,854 | 35 µs | 3.40 ms |
| Provision not found | 18,246 | 191 µs | 1.65 ms |
| `ROUTE_AMBIGUOUS` | 13,371 | 391 µs | 5.95 ms |
| Out of coverage | 1,905 | 135 µs | 1.70 ms |
| Instrument not found | 1,308 | 388 µs | 4.86 ms |

(These are v1's figures, measured at `f96ef94`. That file now holds v2's measurement; see the v2 section below.) p99 over all calls meets the < 2 ms target, just. It counts every repeat, not the best of three. Questions and refusals take longer at the tail, because they run the typo tiers and suggestion ranking. The x86-64 run was measured on the v2 seal; see below.

## Second sealed run (v2), 29 Sept 2026

You approved fixing the deviations above, in particular the cross-sentence link, and the two titles, then one final clean seal (stop log 15). The v2 table is `results/uk-run-2026-09-29-v2.md`, with rows in `…-v2.json`. Both are sealed in `seals/results-2026-09-29-v2.json` (`f3618d71…`), which cites the battery seal `battery-2026-09-29-v2` (`024da21e…`, tag `battery-seal-2026-09-29-v2`). The run was once, at `0b25a14`, on the same index snapshot, Python and machine.

**Read v2 as a check that the fixes work, not as a fresh estimate.** The fixes answer failures v1 showed, so the rows v1 failed are no longer held out. v1 stays published beside it, and where the two differ v1's numbers are the blind ones. Held-out rows v1 had not failed are still blind, and v2 binds none of them wrongly.

**What changed between the runs.**
- Router (`dffbc40`, `80b7645`):
  - a sentence end breaks provision linking (UK-L-02);
  - a bare `c.18` asks (UK-I-08);
  - more than 48 title anchors is too complex (UK-W-03);
  - notes and recitals are unsupported (UK-U-03);
  - a provision inside a cited title is part of the title;
  - editorial notes such as "(expired—not approved)" leave title keys;
  - the known-word typo pass;
  - a reordered title that also needs a correction asks.
- Batteries: two labels only, `uk-false_abstention-0018` and `-0019`, now the chapter's sections (`docs/batteries.md`, Second seal). No rows were added.
- The fixes first broke 124 correct rows of the 100,000-citation sweep. Those regressions were fixed before sealing (`80b7645`). Against v1's code on the same index, one sweep row that was correct now asks. It is a malformed source: "(S.I. 1038 C. 95)", with no year.

| Metric | v1 | **v2** | 95 % upper (v2) | Target |
|---|---|---|---|---|
| Collision | 0 / 40 | **0 / 40** | 7.2 % | 0.0 % ✓ |
| Misroute, held-out real citations | 0 / 1,030 | **0 / 1,030** | 0.29 % | ≤ 0.5 % ✓ |
| Misroute, all bound rows | 2 / 1,897 (labels) | **0 / 1,897** | 0.16 % | ≤ 0.5 % ✓ |
| Bound on invented law | 0 / 68 | **0 / 68** | 4.3 % | 0.0 % ✓ |
| Strict abstention on invented law | 68 / 68 | **68 / 68** | | |
| False abstention, sampled current provisions | 2 / 773 | **0 / 773** | 0.39 % | ≤ 0.5 % ✓ (v1's blind 0.81 % did not meet it) |
| False abstention, held-out real citations | 82 / 1,030 | 82 / 1,030 | 9.5 % | reported |
| Miss, held-out real citations | 67 / 1,000 | 67 / 1,000 | 8.2 % | reported |
| Covered law reported out of coverage | 7 / 2,021 | 7 / 2,021 | 0.65 % | |
| Out-of-coverage law refused | 0 / 16 | 0 / 16 | 17 % | |
| Typo auto-correct precision / recall | 29 / 29, 28 / 31 | **31 / 31, 31 / 31** | | |
| Typo clarify recall | 5 / 7 | 6 / 7 | | |
| Typo bound when it should not | 1 / 22 | **0 / 22** | 12.7 % | |

**Rows that changed (15 of 2,112):**
- 13 are the fixes above and the two relabels.
- The other 2 are held-out rows that v1 asked about and v2 binds correctly: `misroute-0205` and `-0989`, both SI titles with a provision pinpoint.

**Still not as expected (2 typo rows, left as they are):**
- "Contracts (Rights of Third Partys) Act 1999" is refused with suggestions where the tiers say ask ("Partys" is two edits away).
- "rights of employment act 1990" is asked about where the label says refuse.

Neither binds anything.

## Latency after the fixes (Apple Silicon, v2)

`bench/results/latency-darwin-arm64.json` (v1's is at `f96ef94`). Same 306,336 calls, same machine.

| Status | calls | p50 | p99 (v1 → **v2**) |
|---|---|---|---|
| All | 306,336 | 141 µs | 1.98 → **2.11 ms** |
| `ROUTE_BOUNDED` | 246,285 | 138 µs | 0.70 → 0.85 ms |
| `ROUTE_UNRESOLVED` | 25,794 | 37 µs | 3.40 → 3.56 ms |
| Provision not found | 18,282 | 197 µs | 1.65 → 2.00 ms |
| `ROUTE_AMBIGUOUS` | 12,804 | 393 µs | 5.95 → 6.22 ms |
| Out of coverage | 1,899 | 138 µs | 1.70 → 1.72 ms |
| Instrument not found | 1,272 | 408 µs | 4.86 → 5.84 ms |

**p99 over all calls now misses the < 2 ms target, by 0.11 ms.** This is the fixes' cost, not noise. Timed back to back on the same 30,000 queries and index, v1's code gives p99 1.98 / 1.97 ms and v2's 2.09 / 2.12 ms. The extra cost is spread out: about 10 µs per query from two more cue scans and the SI-number lookahead, with no single hotspot. It shows most on long SI lists. It has not been tuned, since that would change code after the seal.

## Latency on x86-64 (Windows rig, v2)

`bench/results/latency-windows-x86_64.json`. 306,336 calls (the 100,000 replayed real citations plus every battery row, 3 repeats each, garbage collection paused). Full UK index, verified byte-for-byte against the v2 seal (`024da21e…`). Machine: Intel64 Family 6 Model 58 Stepping 9, Python 3.11.16 on Windows 10 (AMD64), executed via Git Bash (`scripts/latency_x86.sh`).

| Status | calls | p50 | p99 | max |
|---|---|---|---|---|
| All | 306,336 | 623 µs | **12.27 ms** | 229.3 ms |
| `ROUTE_BOUNDED` | 246,285 | 618 µs | 5.50 ms | 229.3 ms |
| `ROUTE_UNRESOLVED` | 25,794 | 180 µs | 19.38 ms | 93.9 ms |
| Provision not found | 18,282 | 904 µs | 11.46 ms | 76.7 ms |
| `ROUTE_AMBIGUOUS` | 12,804 | 1,955 µs | 36.01 ms | 97.2 ms |
| Out of coverage | 1,899 | 643 µs | 8.23 ms | 31.5 ms |
| Instrument not found | 1,272 | 2,250 µs | 44.70 ms | 95.7 ms |

Outcome counts match Mac v2 exactly across all 306,336 calls. On this x86-64 CPU, p50 across all queries is 623 µs (< 1 ms); bound queries run at p50 618 µs and p99 5.50 ms. Overall p99 is 12.27 ms, reflecting the single-thread performance of this processor compared to Apple Silicon on string parsing, mmap lookups, and typo-tier suggestion ranking.

