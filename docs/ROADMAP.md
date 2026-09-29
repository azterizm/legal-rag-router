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
| Last updated | 2026-09-29 |
| Current stage | **M10-UK done: sealed runs v1 and v2 done** (`reports/sealed-run-uk.md`), **x86-64 latency measured** (`bench/results/latency-windows-x86_64.json`). Before it, **Stage D (concept discovery, UK)**, inserted before M10 at your request: **stage D done** (`Router.discover()`; sealed test run in `reports/discovery-uk.md`; contract and README updated). Stage B done; UK batteries and the concept battery sealed and tagged |
| Current milestone | M0 ✅, M1 ✅ (UK), M2 ✅ (UK), M3-UK ✅, M4-UK ✅, **M5-UK ✅**, M6 ✅ (UK, full data), **M7-UK ✅ (full index: 100k sweep, p99 1.88 ms over 100,000 real queries)**, **M8-UK ✅ (sealed: `battery-seal-2026-09-29`; v2 `battery-seal-2026-09-29-v2`)**, **M10-UK ✅** |
| Next step | M11 (Unit 1–2 comparison) |
| Waiting on you | ⛔ The Mac p99 of 2.11 ms after the fixes (stop log 16). Optional: a go for the vault proposals |
| Blocked | Nothing |

### Stop log
Newest first. One line per stop: what was finished, and where to resume.

- 2026-09-29 (17): **M10-UK: x86-64 latency measured; M10 complete.** Reading: `reports/sealed-run-uk.md`, `bench/results/latency-windows-x86_64.json`.
  - **Seal verified on x86-64:** `seals/battery-2026-09-29-v2.json` matched byte-for-byte (`024da21e…`) on the rig.
  - **Latency results (Intel64 / Windows AMD64):** 306,336 calls, p50 623 µs, p99 12.27 ms (bound queries: p50 618 µs, p99 5.50 ms). All 306,336 call outcomes match Mac v2 exactly.
  - **Resume:** M11 (Unit 1–2 comparison).

- 2026-09-29 (16): **M10-UK v2: the fixes, a second seal and one run; x86 latency pending.** Reading: `reports/sealed-run-uk.md`, "Second sealed run (v2)".
  - **Your decisions on stop 15:** fix the deviations (the cross-sentence link above all) and the two titles, then one final clean seal.
  - **Fixes:**
    - Router: `dffbc40`, and `80b7645` for the 124 sweep rows the first fixes broke.
    - grammar.md and the contract document them (`cb04a83`).
    - Two battery labels corrected (`4c3c168`): the Part/Chapter rows are the chapter's sections. No rows added. A rebuild reproduces every other v1 row byte for byte.
  - **Seal:** `seals/battery-2026-09-29-v2.json` (`024da21e…`), committed as `0b25a14` and tagged `battery-seal-2026-09-29-v2` (local). The v1 battery seal and the concept seal no longer verify against the rebuilt index (title keys, typo thresholds). They still verify at their own commits.
  - **Run** (once, `--suffix v2`; `eval.run` now refuses to overwrite a run):
    - collision 0/40;
    - held-out misroute 0/1,030;
    - **misroute over all bound rows 0/1,897**;
    - bound on invented 0/68;
    - **false abstention on current provisions 0/773 (upper bound 0.39 %)**;
    - typo auto-correct 31/31 precision and recall.

    These check the fixes; they are not blind. v1's 2/773 (0.81 %) stays the blind figure.
  - **Mac latency after the fixes:** p99 **2.11 ms** (v1 1.98). It misses < 2 ms by 0.11 ms. A back-to-back A/B shows it is the fixes' cost, about 10 µs per query, and not noise. Not tuned after the seal.
  - **Questions for you:**
    1. ⛔ **Mac p99 of 2.11 ms:** record it as not met for v2, or allow a performance-only pass? Any such pass would have to show identical outcomes on every battery row and the 100k sweep, with latency re-measured at the new commit.
    2. 🧑 **Run `bash scripts/latency_x86.sh` on the rig.** It now verifies the v2 seal. Copy over `data/index/` (rebuilt since v1) and `results/raw/replays-100k.txt` first, then bring back `bench/results/latency-*-x86_64.json`.
  - **Resume:** the x86 result into M10, then M11.

- 2026-09-29 (15): **M10-UK: the sealed run is done; x86 latency pending.** Reading: `reports/sealed-run-uk.md`.
  - **Tooling:** `eval/run.py` refuses a changed battery byte or uncommitted code. `eval/metrics.py` gives the plan's metrics with exact one-sided 95 % Clopper-Pearson bounds. `eval/seal.py` gains `seal_results`. `bench/latency.py`.
    - Before the run, the misroute headline was fixed to the plan's wording (bound, expected not met), split into wrong instrument and wrong provision.
  - **One sealed run** at `5df82af`. The first attempt failed at the sealing step (a relative-path bug). Its files were deleted unread and the run repeated.
  - **Results:**
    - collision 0/40;
    - **held-out real citations: 0 wrong bindings in 1,030 (upper bound 0.29 %)**;
    - bound on invented 0/68; strict abstention 68/68;
    - misroute 2/1,897 overall: both are my mislabelled Part/Chapter rows. The router follows UK-P-13;
    - false abstention on sampled current provisions 2/773 (upper bound 0.81 %, **above the 0.5 % target**); on held-out citations 82/1,030, mostly historical provisions refused by design (decision 19);
    - typo auto-correct precision 29/29.
  - **Mac latency** over 306k calls: p50 138 µs, **p99 1.98 ms**. Bound results p99 0.70 ms; questions 5.9 ms and instrument refusals 4.9 ms at p99.
  - **Questions for you (⛔):**
    1. **The deviations the run found:**
       - `c.18` is unresolved (should be ambiguous);
       - **linking across a sentence end** (UK-L-02, safety-relevant);
       - 25 repeated titles don't trip too-complex;
       - "explanatory notes to X" binds;
       - typo recall misses (Trafic, Saftey, Right);
       - the two mislabelled Part/Chapter rows.

       Fixing them changes code after the seal. The sealed figures stay as published. A fix is shown by a *new* battery version (v2, relabelled rows plus rows for each fix) with its own seal and run. Fix now (recommended: the cross-sentence link first), or record them and move on to M11?
    2. **False abstention on current law:** the upper bound of 0.81 % misses the 0.5 % target. It comes from two unusual titles. Record as not met, or fix with the others in v2?
    3. 🧑 **Run `bash scripts/latency_x86.sh` on the rig.** First copy over `data/index/` and `results/raw/replays-100k.txt`, then bring back `bench/results/latency-*-x86_64.json`.

- 2026-09-29 (14): **D5 accepted; D6 done; stage D complete.**
  - **Your decisions on D5:**
    1. D5 is the stage-D result (no further tuning);
    2. p99 ≈ 320 ms is acceptable for the interactive discovery step, so no optimisation now;
    3. the concept seal is tagged `concept-seal-2026-09-29` (local, on `b1b06e9`, by you).

    Your D5 commit didn't land (only its `git add` did), so D5 and D6 went into one commit ("D5 sealed test run and D6 docs").
  - **D6:**
    - `docs/contract.md` §5 now describes `Router.discover`: candidates only, `ASK_USER`, confirm then route. It states the weak `confident` flag and the measured figures. §7 gains `discover` failure behaviour.
    - The README has a discover-then-bind section.
    - `docs/vault-proposals-discovery.md` holds the proposed vault text for 02 §5, 05 §4, 07 and 10 Phase 4. Not applied: the vault needs your go.
  - **Resume:** M10-UK.

- 2026-09-29 (13): **D5 done: the sealed test run of `discover()`; ⛔ your review.** Report: `reports/discovery-uk.md`. The run was once, against the verified concept seal, at `969bd4e`.
  - **Drafted test queries (91):**
    - `discover()`: hit@1 51 %, hit@10 88 %, MRR 0.63;
    - headings only (the vault's design): 19 %, 51 %, 0.29.
    - Dev had 68 % at rank 1: that much was fitted to dev. hit@10 held.
  - **Your 11 probes with a real answer:** hit@10 64 % (headings only 45 %). Discovery found the law 7 of your false-premise questions were reaching for, while `route()` refused the invented citation.
  - **Negatives:** 30 % of Mart's 50 US queries got a "confident" UK candidate (headings only: 8 %); your FAB-004 did not. The confidence flag is weak, as dev predicted.
  - **Safety on all 153 rows:** 0 unbindable candidates, and every `route()` status as labelled. No research query was bound.
  - **Latency on test:** p50 85 ms, p99 318 ms (your probes are long sentences).
  - **Questions for you (⛔):**
    1. **Accept D5 as the stage-D result and go on to D6** (contract §5, README, proposed vault changes)? Or improve first? Two improvements are visible:
       - (a) a better confidence signal (score margin, agreement across fields), tuned on a new *dev* set of out-of-scope queries that I would draft;
       - (b) rank-1 precision within one Act (employment, tax).

       Either one needs a fresh, sealed test set to report on, since this test slice has now been used.
    2. **Latency:** is p99 ≈ 320 ms acceptable for an interactive discovery step, or should I optimise? (Precomputing the per-field normalisation at build time should roughly halve it.)
    3. **The concept seal is still untagged.** Tag it (`concept-seal-2026-09-29`, local only)?

- 2026-09-29 (12): **D4 done: `Router.discover()`, tuned on dev only.**
  - **API:** `Router.from_path(index, concepts=…)`, then `router.discover(query)` → a `DiscoveryResult` of `Discovered` candidates (coordinate, label, heading, score, matched terms), with `confident` and `reason`. It never binds, never returns text and never raises. `route()` is unchanged.
  - **Ranking:** BM25F over five fields, a stemmer that lets plurals and past tenses meet, the thesaurus `thesaurus/uk.toml`, and authority priors (repealed, Northern Ireland, Scotland, amending, commencement, secondary; citation in-degree). Candidates are re-validated against the router index.
  - **Dev slice:** hit@1 68 %, hit@10 91 %, MRR 0.75, against 17 % / 55 % / 0.29 for the vault's headings-only design. 0 phantom candidates; every dev query still routes unresolved. p99 181 ms.
  - **Honest weakness:** the confidence cut-off, set by a pre-declared rule, marks 90 % of dev misses confident too.
  - Tests: 797 pass, 1 skip. Coverage 100 %.
  - **Resume:** D5, the sealed run on the test slice (drafted test rows, your 12 probes, Appendix B), then ⛔ results for you.

- 2026-09-29 (11): **D3 done: long titles, cross-headings and the concept index.**
  - **Ingest (record schema 2):** instruments keep `long_title`; section-level provisions keep `crossheading`. A forced re-ingest of all 134,219 left the harvest and the router index byte-identical, so both seals still verify.
  - **`data/concepts/`:** 1,322,050 documents in five fields (heading, cross-heading, structure, title with long title, body), 53M postings, 575 MB. Built in 141 s, loaded with SHA-256 checks in 213 ms, and a rebuild is byte-identical.
    - Stdlib `mmap` arrays and sorted tables (`src/legal_rag_router/concepts.py`); licensed as derived legislation.gov.uk data (`data/MANIFEST.json`).
  - Tests: 755 pass, 1 skip. Coverage 100 %.
  - **Resume:** D4. `discover()`: BM25F over the five fields, stemming and a thesaurus, with a confidence cut-off. Candidates are re-validated by exact lookup and never bound; tuned on the dev slice only.

- 2026-09-29 (10): **D2 approved (all four review points) and the concept battery sealed.**
  - `eval.seal` has a `concept` kind. It pins `batteries/concept/*.jsonl` and the router index the gold was checked against. `seals/concept-2026-09-29.json` is committed, not tagged (a tag needs your go).
  - The M8 seal still verifies.
  - **Resume:** D3 (ingest keeps long titles and cross-headings; then the concept index).

- 2026-09-29 (9): **D1 decided, D2 concept battery built; ⛔ your review.**
  - **D1:** a separate `discover()` over its own index; legislation only; evaluation queries from both of us.
  - **D2:** 265 rows in `batteries/concept/uk.jsonl`:
    - 203 drafted in Mart's keyword style across 12 areas, gold verified in the index, split dev 112 / test 91;
    - your 12 statute-related `rag-security-probes` (gold from the provisions your repository names), test only;
    - Mart's 50 Appendix B searches verbatim, as out-of-jurisdiction negatives, test only.

    Each row also says what `route()` must return for it (concept queries must stay unresolved).
  - **The plan-battery seal** now hashes the jurisdiction directories only (`batteries/uk/`), so the concept battery gets its own seal. `seals/battery-2026-09-29.json` still verifies unchanged.
  - Tests: all pass.
  - **Resume:** your answers to the D2 review points. Then seal the concept battery (tag only with your go), then D3.

- 2026-09-29 (8): **Stage D planned (concept discovery), D0 evidence done; ⛔ D1 decisions.**
  - **Why (your note, citing Mart 2017):** research queries rarely carry a citation, so `ROUTE_UNRESOLVED` → discover-then-bind is the main path, not a Phase 4 fallback. Section headings alone won't find ERA s. 124 for "unfair dismissal compensatory award statutory cap".
  - **D0 probe** (scratch, not committed; the 15 probe queries are excluded from any battery). BM25 over all 1,118,604 section-level provisions of the full index:
    - headings only (the vault's design) put the gold provision in the top 10 for 6 of 15;
    - adding Part / Chapter titles, the instrument title, stemming and 6 synonyms gave 12 of 15;
    - rank 1 was right for only 4 of 15, so discovery must offer candidates and never bind;
    - text concatenated into one field hurt (8 of 15): it needs its own weighted field.
  - **Plan:** `docs/discovery.md`, steps D1 to D6, one at a time. It uses a separate `data/concepts/` index and a separate method, so `route()`, the router index and the sealed batteries are unchanged.
  - **Resume:** D1 answers, then D2 (concept battery first, sealed before any tuning).

- 2026-09-29 (7): **M8-UK sealed and tagged locally (`battery-seal-2026-09-29`).**
  - **Your review:** all six review points in `docs/batteries.md` approved as written.
  - **Invented instruments: all 52 confirmed absent at the source.** Your `verify_absence` run stopped on the last row: legislation.gov.uk answers `400 Bad Request` for `uksi/2011/9999`, and the fetch layer raised on it before anything was saved.
    - The 51 title searches were recorded from your cached responses (`--from-cache`, no request). None found an instrument with the same title.
    - Row 52 was recorded from your run's log, and its notes say so.
    - Fixed: 400/404/410 count as absent for a number-cited row, each row is saved at once, `--from-cache` exists, and `FetchError` carries the HTTP status. The cache helpers are module-level (`read_cached`).
  - **`eval/seal.py`:** canonical-JSON SHA-256 over the battery files, every index file, the alias TOMLs, the harvest split manifest, the typo thresholds, the package version and the git commit. `verify` names every difference. Tests cover one changed byte in a battery, index, alias or split file, an added battery file, an edited seal, and a dirty tree.
  - **The sealed index is reproducible:** a fresh build from the committed code is byte-identical to `data/index`.
  - **Resume:** M10-UK. Write `eval/run.py` (refuses to start unless `eval.seal verify` passes), `eval/metrics.py` and `bench/latency.py`, then the sealed run.

- 2026-09-28 (6): **M8-UK batteries built; halted for your review (⛔). Committed locally.**
  - **2,112 rows in nine files** (`batteries/uk/`), schema in `batteries/schema.py`, validated in CI:
    - `misroute` 1,030: 1,000 **held-out** real citations (D3), seed 20260928, plus 30 hand rows;
    - `false_abstention` 773: 700 sampled from the index (350 Acts, 350 SIs), plus 73 hand rows;
    - `invented` 68: Marchwood, 50 other invented instruments, 16 invented provisions;
    - `typo` 75: 50 real misspellings, 25 adversarial near-misses; split dev 22 / test 53 (D2);
    - `collision` 40, `catalogue` 45, `identifier` 29, `informal` 27, `ambiguous` 25.
  - **Labels come from grammar.md, never from a router run.** `batteries/build_uk.py` checks each hand label's facts against the full index before writing: coordinates exist, `absent:` ones don't, and invented titles are in neither the index nor the catalogue. It caught one wrong label (Bribery Act 2010 s. 20 exists).
  - Every supported grammar.md row is exercised by a battery row (CI test). The one exception is UK-C-17 (an API argument).
  - **Typo dev slice (D2):** the router matches all 22 dev rows, so the thresholds are unchanged and freeze with the seal. The test slice has not been run.
  - **Absence of invented instruments:** checked offline against the index and your 244,564-entry catalogue. `batteries/verify_absence.py` confirms them with the source's own search. It is yours to run (a fetch).
  - grammar.md's injection wording is corrected: such input yields only the safe key, and nothing else reaches the filter.
  - Tests: 709 pass, 1 skip. Coverage 100 %.
  - **Questions for you (⛔ halt):** the six review points in `docs/batteries.md`. The main one: "Employment Rights Act" without a year now also names the Employment Rights Act 2025, so the plan's informal example is labelled ambiguous.
  - **Resume:** after your review, seal and run (M10-UK).

- 2026-09-28 (5): **Your U2 re-fetch and U4 catalogue landed; checked, three fixes, re-swept. Committed locally.**
  - **Your data, checked:**
    - catalogue: 244,564 entries in 29 series, no duplicate coordinates, `ukpga` exactly 17,139 + 421;
    - 421 Acts ingested (134,219 instruments), `missing` reports 0;
    - the two hand-made records for the PDF-only Acts `ukpga/Geo5Sess2/13/3` and `/4` carry the right `IdURI`, the catalogue's titles and no provisions. They are recorded in `docs/sources.md`, because they are not from the source.
  - **Fix 1: number keys by series (decision 22).** The new catalogue exposed that regnal number keys ignored the series. 11,240 catalogued instruments were silently left out of the out-of-coverage table, because a public Act shared their key:
    - 10,116 local Acts (`c. i`), 858 personal Acts, 115 Church Measures, 3 Northern Ireland Acts;
    - 116 Welsh SIs of 2026, which have their own numbers from 2026 (`wsi/2026/10` is not SI 2026/10);
    - 32 Great Britain Acts of 41 Geo. 3.

    Out of coverage now lists 103,008 instruments (was 91,768).
  - **Fix 2: SI list with unbracketed pinpoints.** "S.I. 1969/1369, article 3, 1969/1371, article 2" bound both articles to 1969/1369. Now each item keeps its own (UK-I-22). ", article 3, 400" still reads as article 400, never SI 400.
  - **Fix 3: sweep classifier.** A provision the router saw but left unlinked had counted as a misroute. It is now `dropped`.
  - **Sweep (100,000, new seeded draw, because the re-fetch changed the harvest):**
    - correct 80,024;
    - miss 8,541 (about 7,900 bare `yyyy/n` table cells);
    - false abstention 6,333;
    - ambiguous 4,371 (21 `number_mismatch`);
    - out of coverage 612;
    - dropped 107;
    - **misroute 7, all wrong link targets in the source**;
    - wrong provision 5.
  - **Latency, corrected:** the earlier p99 of 1.88 ms came from one easy 20,000-query draw. Over the full 100,000 it was **2.25 ms**, which misses the target. It was not caused by the new data (indexes without the 421 Acts, or without the catalogue, give the same). The tail was refusal suggestions parsing about 520 instrument records per refused title just to read their years. A UK calendar id carries its year, and the build now fails if the two disagree. With that, **p99 is 1.88 ms over all 100,000** (slices 1.81–1.91), p99.9 7.0 → 5.3 ms, with the ranking unchanged (checked on 450 calls). 4 KB noise: fixture 9.06 ms, full 9.21 ms. The fixture index is rebuilt from your catalogue: only its out-of-coverage sample changed (86 entries, was 44).
  - Tests: 679 pass, 1 skip. Coverage 100 %.
  - **Resume:** M8-UK batteries.

- 2026-09-28 (4): **Q-B-1 to Q-B-4 answered and applied (decisions 20, 21; U2 and U4 fetches are yours). Committed locally.**
  - **Q-B-1 → `number_mismatch` (decision 20):** a title followed by a bracketed SI number of another SI is asked, with both offered, never both bound. Across 100,000 sweep citations this makes 18 questions, most of them drafting typos in the source ("… Regulations 2011 (S.I. 2011/998)" for 2011/988). It does not fire when the bracket numbers several titles named before it ("A Regs 1987 and B Regs 1989 (S.I. 1987/899 and …)"), or without brackets (a list). The last real misroute is gone: the sweep's 6 remaining misroutes are all wrong link targets in the source.
  - **Q-B-3 → unknown-title checks count against the work limit (decision 21):** each costs 32 of the 320 lookups (UK-W-03), so at most 10 run per query. 4 KB noise on the full index fell from 17.47 to 9.31 ms. No real query in the 100k sample changes; p99 stays 1.88 ms.
  - **Q-B-2 / Q-B-4 → you run both fetches.** For the repo side:
    - `harvest` now merges into the catalogue, with feed entries winning, instead of overwriting it;
    - a new offline `missing` command lists every catalogued Act or SI the index lacks, with its `data.xml` URL and a free save path;
    - runbook in `docs/sources.md`.
  - Tests: 661 pass, 1 skip. Coverage 100 %.
  - **Resume:** M8-UK batteries. When your fetches land, follow runbook steps 4 and 6, then re-run the sweep.

- 2026-09-28 (3): **Stage B: the full UK run. Committed locally.**
  - **Data:** your download is complete: 17,139 Acts and 116,659 SIs, 133,798 files, all `done`. The U2 gap remains: 421 pre-1963 Acts share a calendar key with another Act and were never fetched (U2).
  - **Ingest:** every file read, 0 failures, 124 s. 69,902 instruments with structure, 63,896 PDF-only; 5.56M provisions; 4.51M harvested citations. `data/MANIFEST.json` records 133,798 documents; the licence check passes on the full `data/`.
  - **Index:** 5.70M coordinates, 420,776 title keys, 320 MB. Every curated alias target is present, so the index is no longer `partial`. **Load 120–134 ms (< 450 ms ✓), 35 MB resident.**
  - **Decision 7, refined:** the full build stopped on 4 case collisions in SI 1994/1433 and SI 2015/596. The source has genuinely distinct ids (`paragraph-5-A-i` and `paragraph-5-a-i` under different appendix parts), and their parents are never coordinates themselves. The build now records case variants anywhere inside one instrument. A collision across instruments still fails. Lookups are unchanged: exact case binds, otherwise **A**.
  - **Latency on the full index:** first measured at p99 3.83 ms, max 366 ms. Two changes that don't alter any result brought it to **p99 1.89 ms ✓, max 11 ms**: staged refusal-suggestion ranking (checked identical on 2,963 titles) and cheaper table probes. The margin is thin (`docs/measurements.md`).
  - **Sweep (100,000 real citations, `reports/coverage-sweep-uk.md`):**
    - correct 80,015 (80.0 %);
    - miss 8,553, of which 7,459 are bare `2005/275` table cells (UK-U-05);
    - false abstention 6,470, mostly provisions the current text no longer has (decision 19);
    - ambiguous 4,281;
    - out of coverage 566;
    - dropped 99;
    - wrong provision 9;
    - **misroute 7: 6 are wrong link targets in the source itself; 1 is Q-B-1.**
  - **Fixed from the sweep:**
    - SI lists: notes such as "(C. 41)", ", and", "1988 No. 1640" items, "(article 3)" pinpoints, "S.I.s", "2005/ 224". One real misroute went: "S.I. 1980 No. 765 and 1988 No. 1640" had bound SI 1980/1988;
    - "(S. 1)" after an SI number was read as section 1;
    - "reg. 3 and 2020 c. 26" was read as reg. 2020;
    - an unknown title followed by a real SI number is now asked (`title_number_conflict`), as it already was for "(c. N)";
    - "the The …" in clarifications.
  - **Sweep method:** a bound result missing the target is now split into `misroute` (the router read that citation and bound something else) and `dropped` (it never recognised it). On the first full run, most of the 48 rows counted as misroutes were list items the router never recognised. Two were real misroutes, and both are fixed or open above.
  - **Fixture:** complete, `partial` false, snapshot 28 Sept. The CA 2006 collision test runs.
  - **4 KB noise:** fixture 9.17 ms (the test guard); full index **17.47 ms** (`title_vocabulary`).
  - Grammar rows UK-P-06, UK-I-09, UK-I-22, UK-I-29, UK-I-30 and UK-U-05 are added or updated. Tests: 652 pass, 1 skip (Spanish data). Coverage 100 %.
  - **Questions for you:**
    1. **Q-B-1** A title and its SI number name different SIs: "…Regulations 2017 (S.I. 2018/1232)". Today both are bound; this is the one real misroute left. I propose to ask, as "(c. N)" does, listing both. Reuse the reason `chapter_mismatch`, or add `number_mismatch` (a new public reason value)?
    2. **Q-B-2** The U4 catalogue harvest from the Atom feeds needs a contact for the User-Agent (the fair-use policy requires one). Your fetch is finished, so the two can't overlap. At 1 request per 5 s, the whole site is about 9,000–10,000 pages (13–14 h). A targeted run is 2–3 h: only the series missing from your listing, plus `ukpga`, which measures the U2 gap. Which run, and which contact?
    3. **Q-B-3** 4 KB noise on the full index is 17.5 ms. Publish it as measured (decision 16), or count unknown-title analyses against the UK-W-03 work budget, so title-word soup stops earlier as `too_complex`?
    4. **Q-B-4** U2: can your scraper re-fetch the 421 regnal Acts keyed on their `IdURI`? Until then they are catalogued but not indexed.
    - **Answered 28 Sept:** Q-B-1 → `number_mismatch` (decision 20); Q-B-2 and Q-B-4 → you run both fetches (runbook in `docs/sources.md`); Q-B-3 → count against the work limit (decision 21).
  - **Resume:** answers to Q-B-1 to Q-B-4, then M8-UK batteries.

- 2026-09-28 (2): **Your answers applied (decisions 5, 17, 18, 19). Committed locally.**
  - **Coverage is 100 % line and branch on `src/`, enforced in CI** (decision 5 corrected to vault 06 §5).
    - Unreachable defensive branches were removed, not excluded.
    - Index-internal lookups go through `RouterIndex.info()`.
    - The fail-safe `except` in `route()` is now tested.
  - **Former titles (decision 17):**
    - Ingest records `other_titles` from the effects.
    - The build keeps 11 Acts after the guards (Senior Courts ← Supreme Court 1981, Employment Tribunals ← Industrial Tribunals 1996 …) and rejects 6 source errors.
    - The router adds a note to `messages`.
    - The fixture gains the Employment Tribunals Act 1996.
  - **Acronyms (decision 18):**
    - A new `acronyms` table holds generated forms with their year only; curated aliases win.
    - You chose curated-only bare forms after measurement: FCA, CMA and similar collide with 7–45 Acts.
    - `EA 2010` was added to the Equality Act alias.
  - **Historical provisions (decision 19):** the plain refusal is kept.
  - **Parser bugs found while covering branches, all fixed and tested:**
    - letter-first designators (`Sch. A1`, `Sch. B1`) were not parsed;
    - "Schedule 2, Part 1" was read as paragraph "t";
    - abbreviation full stops ("Sch. B1") ended the clause for decision 15.
  - **Stage A sweep:** correct 17,220 of 20,000 (was 17,145); false abstention 1,508 (was 1,551); misroute still 1.
  - **4 KB noise floor re-measured: 9.49 ms** (was 7.22). Measured side by side, the rise came from the 27 Sept sweep fixes, not today's work (`docs/measurements.md`).
  - Tests: 631 pass, 2 skip.
  - **Resume:** M8-UK batteries. When the fetch completes, run Stage B: full ingest, catalogue harvest (U4), full sweep, p99 on the full index.

- 2026-09-28: **M7-UK done for Stage A. Committed locally.**
  - Stage A sweep (20,000 citations, `reports/coverage-sweep-uk-stageA.md`):
    - correct 17,145 (85.7 %);
    - false abstention 1,551;
    - ambiguous 644;
    - out of coverage 431;
    - miss 225;
    - wrong provision 3;
    - misroute 1.
  - More fixes since the last stop:
    - "(the 1996 Act)" definitions and "that Act" refer back to the Act just named;
    - "section 1 of the 1996 Act" with no earlier Act is asked (`year_only`), narrowed to the Acts of that year holding the provision. It binds only if neither the index nor the catalogue knows another Act of that year;
    - regnal Acts are also keyed by calendar year and chapter (`1925 c. 20`);
    - title + wrong chapter → `chapter_mismatch`, and unknown title + real chapter → `title_number_conflict`. Both are asked, never refused;
    - capitals mark where a title starts after lower-case prose.
  - Tests: 554 pass, 2 skip (they wait for CA 2006 and Spanish data). Coverage is 95.8 %, and the floor is raised to 95 % (decision 5).
  - Docs:
    - `docs/contract.md` is written;
    - `docs/grammar.md` gains UK-P-18/19, UK-I-21–26, §4.5 linking and cues (UK-L-01–07) and §4.6 work limits (UK-W-01–05), and the case collision decision is recorded.
  - What the remaining false abstentions are:
    - provisions that no longer exist in the current text (historical, Phase 2);
    - renamed Acts cited by a former title ("Supreme Court Act 1981" = Senior Courts Act 1981);
    - catalogue gaps (other series before 1970).
  - **Questions for you (⛔ before M8 freezes battery expectations):**
    1. Former titles: should the build index an Act's former titles (from the CLML metadata) as aliases that bind to the current Act?
    2. Acronyms ("FA 2022", "TCGA 1992"): keep them to the curated alias table, or generate them from the titles?
    3. A historical provision that the current text lacks: keep `PROVISION_NOT_FOUND`, or add a wording note ("the current text has no s. X; it may have been repealed")?
  - **Resume:** answers to the three questions, then M8-UK (batteries).

- 2026-09-27: **STOPPED HERE (usage limit). M7-UK coverage sweep in progress.**
  - Added:
    - `eval/sweep.py`: harvest split rule, committed as `reports/harvest-split.json` (D3), plus the sweep runner.
    - A queue-db catalogue import (162,290 known instruments; SIs not yet downloaded now read as out of coverage, not invented).
  - Fixes from the sweep:
    - SI number lists;
    - agentive "by" blocks default linking;
    - "(c. N)" chapter notes;
    - dates are never years;
    - commas inside titles;
    - the provision scan restarts correctly;
    - sibling sub-division lists ("s. 6(1)(2)").
  - Stage A sweep (20k citations), before → after: correct 3,090 → 7,101; false abstention 9,321 → 2,611; ambiguous 8,745; miss 214; misroute 3.
  - **Resume:**
    1. Inspect the remaining ambiguous and false-abstention examples: `uv run python -m eval.sweep run --harvest <scratch>/full/harvest/uk_citations.jsonl --index <scratch>/index --sample 20000 --out <scratch>/sweep.md`. The Stage A index was rebuilt from a full scratch ingest; to redo it, run `python -m ingest.uk` and then `python -m ingest.build_index` with `--allow-missing-alias-targets`.
    2. Add tests for the new behaviours (SI lists, agentive "by", chapter notes, dates, sibling lists, `import-queue`, sweep split).
    3. Coverage to 95 %.
    4. grammar.md rows, `docs/contract.md`.
    5. Commit the M7 report.
- 2026-09-27: **Q-M7-2 decided and done.**
  - `bench/stress.py`: 13 gibberish classes at 4 KB. Floor 7.22 ms; doubling ratios 1.2–2.3.
  - Router made linear and bounded: caps before pairwise work, bisect span checks, whole-alias anchors.
  - 493 tests pass.
- 2026-09-27: **M7-UK part 2.** Router, identifiers, typo tiers, partition filter, prefilter and the M7 test suite: 480 pass, 2 skip until CA 2006 / Spanish data land, 93 % coverage.
  - Every UK probe in the plan's Verification section behaves as specified.
  - Typical queries take 0.003–0.3 ms; realistic 4 KB prose 1.3 ms.
  - Random 4 KB noise: p50 ≈ 2 ms, p99 ≈ 4–5 ms (Q-M7-2).
- 2026-09-27: M7-UK part 1:
  - Public result types.
  - Grammar plugin protocol.
  - UK citation grammar: provisions incl. lists, ranges, nested schedule/part units and subsection forms; SI, SSI, SR, chapter and regnal numbers; negation, context, temporal and out-of-coverage cues.
  - Decisions 13–15 recorded.
- 2026-09-27: **M4-UK and M6 done (Stage A).**
  - Index format v1 = memory-mapped sorted tables (decision 12).
  - Partial UK: load 132 ms, 29 MB, lookups ~5 µs (`docs/measurements.md`).
  - Committed fixture index `tests/fixtures/index/`: 2.8 MB, 32 instruments, 64,909 coordinates. It is deterministic, rebuilt by `python -m scripts.build_fixture`, and marked partial until CA 2006, SI 2011/3006, SI 2026/310 and FSMA 2000 are downloaded.
  - 253 tests, 97.75 % coverage.

  Resume at M7-UK.
- 2026-09-27: **Halted at M6 on Q-M6-1.**
  - Drafted:
    - `normalise.py`: folding with offsets, tokeniser, title keys; tested.
    - `index.py`: v1 loader with SHA-256 and format checks.
    - `ingest/build_index.py`: deterministic, with integrity failures, case variants and coverage.
    - `aliases/uk.toml`.
  - A trial build on all Stage A data passes every integrity rule, but loads in 2.0 s using about 1 GB (`docs/measurements.md`).
  - Fixture candidates chosen (see M4 notes). Resume once Q-M6-1 is answered.
- 2026-09-27: **M3-UK done.**
  - `ingest/cache.py`: polite fetch layer, 23 offline tests.
  - `ingest/uk_catalogue.py`: importer (run: 42,365 entries in `data/catalogue/uk_catalogue.jsonl`) and Atom harvester for Stage B.
  - `docs/sources.md`.
  - Found: 6,656 Welsh rows in your listing have no title. They are kept as untitled entries and fixed by the Stage B harvest.

  Resume at M4-UK.
- 2026-09-27: **M3-UK part 1.** `ingest/records.py` and `ingest/uk.py` read `uk_scrap_data/`. A full run over all 33,788 files takes 35 s with 0 failures:
  - 10,720 instruments with full structure and 23,068 metadata-only (decision 10);
  - 1,992,290 provisions;
  - 2,434,792 harvested citations.

  Bugs found and fixed on real data:
  - `InternalLink` ids were taken as provisions;
  - `<Versions>` alternative texts were duplicated;
  - three-year regnal sessions (`12-13-14`) were rejected.

  3,407 provision ids are duplicated in the source itself; these are recorded as `duplicated_provisions` (**Q-M7-1**). Resume: `ingest/cache.py`, `ingest/uk_catalogue.py`, `docs/sources.md`.
- 2026-09-27: **M2 done (UK).** `data/MANIFEST.json`, `NOTICE`, `scripts/check_licences.py` (runs in CI). Resume at M3-UK.
- 2026-09-27: U7 resolved (your fetch is compliant; faster rate requested). Continuing Stage A with the data on disk.
- 2026-09-27: **Halted in M2 on U7** (legislation.gov.uk fair-use terms vs the running scraper and the plan's 1 req/s). Resume M2 (`MANIFEST.json`, `NOTICE`, `check_licences.py`) once U7 is decided.
- 2026-09-27: **M1 done (UK).** `coordinate.py` (jurisdiction-neutral, per-scheme arity), `grammars/uk.py` (UK scheme, element-id/URL ↔ provision mapping, checked against 2.0M real ids), `docs/grammar.md` v1 (UK surface forms, case catalogue, row IDs). 105 tests, 98.8 % coverage. Resume at M2.
- 2026-09-27: **M0 done.** Packaging, tooling, CI, CodeQL, Dependabot, wheel check. Local commit.
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
- **U2 and U4 — closed 28 Sept:** both fetches done by you; `missing` reports 0, and the catalogue covers 29 series (`docs/sources.md`, Known gaps). Two of the 421 files are hand-made metadata-only records for PDF-only Acts.
- **U2/U4 fetches — decided 28 Sept:** you run both from your machine (runbook in `docs/sources.md`): the catalogue harvest with the repo's `ingest.uk_catalogue harvest` or your own harvester, and the re-fetch of the pre-1963 Acts from the list `ingest.uk_catalogue missing` writes.
- **U3 — Fetch code lives outside the repo for now.** Decided: revisit once all data is downloaded. Until then the repo's `ingest/uk.py` *reads* `uk_scrap_data/`. `docs/sources.md` records how the data was obtained. Scraper hygiene to fix at port time:
  - the UA has a placeholder contact (`data-team@example.com`);
  - concurrency is 15 in parallel, against the plan's 1 req/s.
- **U4 — Gaps in the other-series listing. Decided: I write the listing harvest in the repo** (`ingest/uk_catalogue.py`: Atom feeds only, resumable, rate-limited, declared UA).
  - The current listing starts at 1970. It misses `apgb`, `aep`, `aosp`, `aip`, `apni`, `mnia`, `mwa`, `uksro`, `nisro`, `ukdsi`, `sdsi`, `wdsi`, `nidsr`, `ukmo`, `ukmd`, … and pre-1970 years.
  - Without the fix, citations to these would be *refused* when they should be marked out of coverage.
  - The same harvest also writes a regnal-correct catalogue of `ukpga`/`uksi`, which measures the U2 gap.
- **U5 — resolved 28 Sept:** the download is complete, including every large Act and both cap Orders. The original note follows.
- **U5 — 24 large Acts are still pending** (as of 27 Sept), probably failing on size.
  - The Acts are: Companies Act 2006, ITA 2007, CTA 2009/2010, FSMA 2000, TCGA 1992, Communications Act 2003, Criminal Procedure (Scotland) Act 1995, and 16 smaller pre-1970 Acts.
  - Also pending: SI 2011/3006 and SI 2026/310 (the s.124 cap Orders).
  - The M4-UK fixture needs CA 2006 and SI 2011/3006. 🧑 Please check that your downloader handles very large responses (CA 2006 `data.xml` is tens of MB).
- **U7 — legislation.gov.uk fair-use terms (checked 27 Sept 2026). Resolved 27 Sept.**
  - **Resolution:**
    - `harvest_catalog.py` was an experimental script and is not the running fetch.
    - The running fetch follows the fair-use policy with a real contact.
    - You have emailed legislation@nationalarchives.gov.uk asking for a faster rate.
    - Stage B starts when the fetch completes, or sooner if they grant a faster rate.
  - **Rule for the repo:** any fetch run from the repo (the U4 listing harvest, single fixture files) must not overlap with your fetch from the same IP. The two together must stay under the crawl-delay. The repo's fetch layer defaults to 1 request per 5 s, with a real contact in the User-Agent.
  - Sources: `legislation.gov.uk/fair-use-policy` and `robots.txt`.
  - **Rate:** the policy says "You must not exceed the request rate limit of 1,500 requests in any 5-minute period". It also says to follow the robots.txt crawl-delay, which is **`Crawl-delay: 5`** (one request every 5 s).
  - **Identification:** "Anonymous user agents are not accepted"; a non-browser client must give contact details.
  - **Bulk:** use the New Legislation and Publication Log feeds rather than crawling everything, and contact the team before any activity that might affect performance.
  - **Enforcement:** access can be suspended, rate-reduced or blocked.
  - **Consequences:**
    - The running scraper (concurrency 15, UA contact `data-team@example.com`) is outside these terms.
    - The plan's 1 req/s is also above the crawl-delay.
    - At 1 req / 5 s, the ≈ 100k remaining SIs take **≈ 6 days** (the plan assumed ≈ 33 h).
    - `robots.txt` also disallows `*/data.pdf` and `*/data.docx`; `data.xml` is allowed.
  - Licence: OGL v3.0 "except where otherwise stated"; EUR-Lex-derived material is under Commission Decision 2011/833/EU. Attribution follows OGL v3.0.
- **U6 — Findings that shaped M1.**
  - 697 files under `uksi/` are canonically `wsi/…` or `nisi/…` (their `IdURI`). They keep that canonical coordinate and resolve from `SI yyyy/n` through the numbers table.
  - Provision ids inside `<BlockAmendment>` are quoted text from another Act and are never indexed.
  - Lower-case designators occur only on schedules and paragraphs in older Acts (`sch13/parab`).

---

## D. Stage D: concept discovery, UK (added 29 Sept 2026, before M10)

Plan, evidence and signals: `docs/discovery.md`. Executed one step at a time; ⛔ marks a stop.

- [x] **D0** Evidence probe: headings-only search finds the gold provision in the top 10 for 6 of 15 keyword queries. Adding structure titles, stemming and synonyms raises that to 12 of 15. Rank 1 was right for 4 of 15.
- [x] ⛔ **D1** Decisions (29 Sept, your answers):
  1. **A separate `discover()`**, over its own `data/concepts/` index. `route()`, its statuses, the router index and the sealed M8 batteries stay unchanged.
  2. **Legislation only** in this stage: headings, cross-headings, structure titles, long titles, definitions, text, citing descriptions, and a curated thesaurus. Case law later.
  3. **The evaluation set comes from both of us:**
     - about 200 queries I draft across 12 UK areas, split dev / test;
     - your sources, test only: the 12 statute-related probes of `rag-security-probes` (6 fabrication + 6 Mode C, gold from the provisions your repo names) and Mart's Appendix B (50 US queries: out-of-jurisdiction negatives and the style reference).
- [x] ⛔ **D2** (29 Sept: 265 rows, `batteries/concept/uk.jsonl`; review points approved; sealed as `seals/concept-2026-09-29.json`, untagged) Concept battery (evaluation first): keyword queries in Mart's style with acceptable gold provisions, dev / test split. Reviewed by you, then sealed before any ranking is tuned.
- [x] **D3** (29 Sept: record schema 2; `data/concepts/` 1.32M documents, 575 MB, 213 ms load, deterministic) Ingest keeps long titles and cross-headings. Concept index `data/concepts/` (own manifest, SHA-256 verified, stdlib tables).
- [x] **D4** (29 Sept: dev hit@10 91 %, MRR 0.75, against 55 % / 0.29 for headings only; p99 181 ms) `discover()`: BM25F, stemming, curated thesaurus. Candidates re-validated by exact lookup, with headings and evidence; never text, never bound. Tuned on dev only.
- [x] ⛔ **D5** (29 Sept: `reports/discovery-uk.md`; test hit@10 88 % against 51 % for headings only; waiting for your review) Sealed evaluation on test against the heading-only baseline: recall@1/5/10, MRR, safety invariants, latency.
- [x] ⛔ **D6** (29 Sept: contract §5 and §7, README, and `docs/vault-proposals-discovery.md`; the vault edits themselves wait for your go) Contract §5 and README; proposed vault changes (02 §5, 05 §4, 07, 10 Phase 4) need your go.

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

- [x] `docs/grammar.md` v1 (UK; ES in Stage C). It is the source of truth for tests and is versioned with the index format.
  - **Coordinate EBNF per jurisdiction:**
    - UK: `s124`, `s124A`, `s124/1ZA/a/ii`, `art2`, `reg3`, `sch2/para4`, `pt2`, with the mapping from legislation.gov.uk element ids (`section-124-1ZA-a` → `s124/1ZA/a`).
    - ES: `art42`, `art42bis`, `art42/1/b`, and `da|dt|dd|df` + n, with ordinal words mapped up to *vigésima*.
  - **Instrument arity per jurisdiction:** UK = 4, ES = 4.
  - **Surface-form table:** each row has a **stable row ID** (e.g. `UK-SF-012`) so battery rows can cite it. Covers every form listed in plan step 1 and step 7 and in the Spanish and UK sections of the case catalogue.
  - **Unsupported-forms table:** each form with the behaviour it gets (recitals, EU/US forms, case citations, concept-only queries, relative references).
  - **Case catalogue:** every entry from the plan, each with a row ID. Test rows reference these IDs.
- [x] `coordinate.py`:
  - A frozen, slotted `Coordinate(jurisdiction, series, year, number, provision: tuple[str, ...])`.
  - `parse()`, `__str__`, `instrument_id`, `parent`, `is_instrument`, and `key` (casefolded).
  - Segment validation with anchored regexes only, per-jurisdiction arity, and case kept in the canonical string.
- [x] README: extension slots for `eu/`, `us/`, `contract/` (01 §2).
- **Done when:** every grammar.md example round-trips, and the hypothesis property `parse(str(c)) == c` passes, along with the negative parse cases.

### M2 — Licence record (plan step 3) · days 1–2

- [x] Re-check both (UK checked 27 Sept, see U7; BOE in Stage C) sets of terms and record the URL and date checked (🧑 if anything has changed):
  - legislation.gov.uk: OGL v3.0, plus its **fair-use / API rate terms** (plan step 4 says to check these first).
  - BOE: reuse conditions of 27 June 2024; attribution string plus link; *Biblioteca Jurídica Digital* excluded.
- [x] `data/MANIFEST.json` (with a schema): per source, the licence, URL, date checked, attribution, and `document_count`, which ingest fills in.
- [x] `NOTICE`, with attribution text for both sources. It ships with the index release.
- [x] `scripts/check_licences.py`, wired into CI. It fails on a `data/` subtree with no manifest entry or a count mismatch, and it also checks `tests/fixtures/index/`.
- **Done when:** the script passes in CI on the empty data tree and the fixture tree, and fails on a planted bad case in its tests.

### M3 — Fetch layer and source reconnaissance (prep for plan steps 4–5) · day 2

- [x] `ingest/cache.py`, shared by both sources:
  - Content-addressed disk cache under `.cache/`.
  - Token-bucket limit of 1 req/s.
  - Declared User-Agent with contact details.
  - Exponential backoff with jitter that honours `Retry-After`, 429 and 503.
  - Conditional GETs (ETag / Last-Modified).
  - `defusedxml` for all XML.
  - Structured progress log. Resumable and idempotent.
- [x] `ingest/records.py`: pydantic `ProvisionRecord` (01 §4) with a per-record `checksum_sha256`. Canonical JSON serialisation.
- [x] **Reconnaissance, written up in `docs/sources.md`:**
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


### M3-UK open question
- **Q-M7-1 — Provisions the source publishes twice** (0.17 %).
  - Example: a schedule whose Parts restart paragraph numbering under one id, so `sch2/para1` stands for several paragraphs.
  - Existence checks are correct, but only the first occurrence's text is in the records.
  - *Proposal for M7:* a citation that resolves to a coordinate in `duplicated_provisions` returns `ROUTE_AMBIGUOUS` ("this schedule numbers paragraphs per Part; which Part?"), never a silent bind.
  - To be confirmed at the M7 halt.

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

> **Status (28 Sept):** UK done from your download (§U): 134,219 instruments, including the 421 regnal Acts you re-fetched (U2), 0 failures, and the licence check passes on the full `data/`. Your harvest supplied the other series' titles (U4): 244,564 catalogue entries. ES waits for Stage C.

- [x] UK, `ukpga` + `uksi` (from your download), and the other series' titles (from your harvest, U4):
  - Instrument lists from the Atom feeds.
  - `data.xml` per instrument: element ids down to subsection/paragraph depth, text, repealed status, part → sections map, chapter number.
  - `<Citation>` harvest → `data/harvest/uk_citations.jsonl`.
  - Titles of every other series from the feeds (no provisions fetched).
- [ ] ES:
  - Norm list: `identificador`, `rango`, `numero_oficial`, `titulo`, `ámbito`, `derogado`.
  - `/texto` XML per norm. Apartado/letra split from the text: a leading `N.` for apartados and `x)` for letras, not the CSS class. Article number normalised from the heading (`art42` vs `a642`).
  - The current `<version>` is indexed and the older ones are kept for Phase 2.
  - `referencias` harvest → `data/harvest/es_citations.jsonl`.
- [x] Records → `data/{uk,es}/…/{instrument_id}.jsonl`, validated, checksummed. `MANIFEST.json` counts are filled in. (UK)
- [ ] Runs on the Mac in the background with a progress log I monitor. On failure it resumes from the cache.
- **Done when:** both runs finish with zero unvalidated records, the licence check passes on the full `data/`, and the ES golden test passes on full data.

### M6 — Index, title tables, aliases (plan step 6) · days 4–5 (fixture first, full data once M5 lands)

> **Status (28 Sept):** done for the UK on full data. Built as memory-mapped sorted tables (decision 12), not the JSON files listed below. Full index: 5.70M coordinates, 320 MB, load 120–134 ms, 35 MB resident (`docs/measurements.md`).

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

> **Status (28 Sept):**
> - 7a–7j are done for the UK.
> - The Spanish parts (`es.py`, BOE identifiers, `artículo único`, `RDL`, state vs regional, Spanish negation words) wait for Stage C.
> - 7k: done on the full index. `reports/coverage-sweep-uk.md` holds 100,000 citations, and the misses are grammar rows or documented unsupported forms. p99 is 1.88 ms over the 100,000 real queries (28 Sept; the earlier 1.89 ms was one 20,000-query draw, see stop log (5)).

- [x] **7a Normalise** (`normalise.py`):
  - NFKC and casefold; accent fold; look-alike skeleton map.
  - `§/s./sec./art./artículo/reg./apdo.` canonicalisation; provision-word variant list (`secton`, `artcle`).
  - A 4 KB cap: over the cap → `UNRESOLVED` with the query flagged.
  - A tokeniser that keeps **character offsets** back to the original query.
- [x] **7b Public types:**
  - `RouteStatus` (StrEnum, using the spec's values).
  - `NextAction` (`RETRIEVE_BOUNDED | ASK_USER | REFUSE | VERIFY_LIVE | DECLARE_OUT_OF_COVERAGE | DISCOVER_THEN_BIND`).
  - `RouteResult` and `ParsedCitation`, with every field from plan departure 2 and 02 §3.
  - `Candidate` and `RouteContext`.
  - All frozen and slotted.
- [x] **7c Identifier scanner:**
  - Accepts coordinates, `instrument_id`s, legislation.gov.uk URLs (`/id/`, `/contents`, `/enacted`, date suffixes), `BOE-A-…` ids and `boe.es …?id=` URLs.
  - Case-insensitive, checked against the grammar, never typo-corrected.
  - A provision word after an identifier extends it; a partial path falls through to the grammars.
- [x] **7d `grammars/base.py`, the `Grammar` protocol (frozen here).** Each grammar supplies:
  - a normalisation hook;
  - stopwords and boundaries;
  - anchor and provision patterns;
  - coordinate EBNF and arity;
  - the official registry (for `live_checkable`);
  - a clarification template.

  `grammars/uk.py` and `grammars/es.py` implement it. Every regex is linear-time (no nested quantifiers) and each pattern is tied to a grammar.md row ID.
- [x] **7e `titles.py`:** token-trie gazetteer (longest match), a prefilter on trigger words, and the number-citation table. Built as sorted memory-mapped tables (decision 12) with right-to-left n-gram lookups in `router.py`, not as a separate `titles.py` trie.
- [x] **7f Link and spans:**
  - Connector rules: `<prov> of/del <inst>`, `<inst>, <prov>`, `<inst> <prov>`.
  - The span is extended left to a boundary, and the whole title has to cover it.
  - Negation scope (`not`, `rather than`, `no`, `salvo`, `excepto` …).
  - Temporal-hint extraction.
  - Context resolution: context coordinates are re-validated against the index, and the query beats context; results resolved this way get `source="context"`.
- [x] **7g Resolution:**
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
- [x] **7h `filters.py`:** `partition_filter()` as in 02 §4. Every value is re-checked against the grammar and the index before it is interpolated.
- [x] **7i Observability:**
  - The `citation_signal` rules.
  - An opt-in structured event on signal-but-`UNRESOLVED`, through a `logging` logger that is silent by default.
  - **Query text is never logged** unless the caller supplies a redactor.
  - `latency_ns` taken with `perf_counter_ns`.
- [x] **7j Tests:**
  - Unit tests per grammar and per scanner.
  - The **span-accounting invariant**.
  - `tests/test_collision_rate.py` (02 §8, ported to the new shape).
  - Golden tests: the three April 2026 probes verbatim, plus every probe in the plan's Verification section.
  - Hypothesis: `route()` never raises, and 4 KB random input finishes in < 2 ms (ReDoS guard).
  - A thread-safety smoke test.
  - Injection-shaped identifiers never reach the filter.
- [x] **7k Harvest split, then coverage sweep (D3):**
  1. Split the pairs into `sweep` / `heldout` with a fixed seed, and commit a hashed split manifest.
  2. Run the router over `sweep` only.
  3. Each miss becomes either a grammar row or a documented unsupported form.
  4. Commit `reports/coverage-sweep-*.md` next to the batteries.
- **Done when:** the full test suite is green on the fixture index in CI across the matrix, the plan's Verification probes all behave as specified, the sweep report is committed, and p99 is < 2 ms locally on the full index.

### M8 — Batteries (plan step 8) · written during M4–M7, frozen at the end of M8

> **Status (29 Sept):** UK sealed (2,112 rows, `docs/batteries.md`, `seals/battery-2026-09-29.json`, tag `battery-seal-2026-09-29`). ES follows in Stage C.

- [x] `batteries/schema.py` (pydantic). Row fields:
  - `id, query, context?, lang, domain, expected_status, expected_coordinates, source (hand|real_document|sampled), notes`;
  - `surface_form_ids`;
  - `absence_verified_via` on invented rows;
  - `split` on typo rows (D2).
- [x] Validated in CI (`tests/test_batteries.py`).
- [x] Files, per domain where one applies (UK; ES in Stage C):

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

- [x] Coverage check: every supported surface-form row in grammar.md is exercised by at least one battery row (CI test).
- [x] 🧑 (confirmed 29 Sept: all 52 absent at the source) Invented rows need the absence confirmed with the source's own search. I record the search URL and date for each; you may want to spot-check a sample.
- [x] Typo thresholds are tuned on the `dev` slice only (D2), then frozen in the constants block. (22/22 dev rows met: no change.)
- ⛔ **Halt: you review the batteries before they are sealed.** ✅ Approved 29 Sept; sealed as `battery-seal-2026-09-29`.

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

- [x] `eval/seal.py`: canonical-JSON SHA-256 (ported from `jev-vs-sovereign-benchmark/src/engine/audit_seal.py`, without torch/transformers).
  - [x] `seal_battery` (29 Sept, also the typo thresholds): hashes the batteries, index files, alias TOMLs, harvest split manifest, package version and git commit → `seals/battery-YYYY-MM-DD.json`.
  - [x] `seal_results`: hashes the results and cites the battery-seal hash.
- [x] `eval/run.py`: refuses to start if the recomputed battery hash differs from the tagged seal. A negative test flips one byte to prove this. (It also refuses uncommitted code.)
- [x] `eval/metrics.py`, per domain:
  - collision, misroute, miss rate (on `heldout`), out-of-coverage precision, false abstention;
  - bound-on-invented and strict abstention;
  - auto-correct precision and recall, and clarify recall;
  - each with a Clopper–Pearson 95 % upper bound, implemented in stdlib and tested against known values.
- [x] `bench/latency.py`: p50/p99 per status, `perf_counter_ns`, warm-up, GC paused, platform recorded.
- [x] ⛔ **Halt:** commit the battery seal and tag it (`battery-seal-YYYY-MM-DD`) **before** the run. I ask before creating the tag. (You said go on 29 Sept: `battery-seal-2026-09-29`, local only.)
- [x] The run → `results/*.json`, a markdown table, and the sealed results. (29 Sept: `results/uk-run-2026-09-29.*`, `seals/results-2026-09-29.json`, reading in `reports/sealed-run-uk.md`.)
- [x] v2 (your go, 29 Sept): the run's deviations fixed, two labels corrected, sealed once more (`battery-seal-2026-09-29-v2`, local) and run once (`results/uk-run-2026-09-29-v2.*`, `seals/results-2026-09-29-v2.json`). v1 stays published as the blind figures.
- [ ] 🧑 An x86-64 latency run on the GTX 1650 rig's CPU. I provide a one-command script; you run it and bring back the results file. (Script: `scripts/latency_x86.sh`.)
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
5. **Coverage:** **100 % line and branch coverage on `src/`** (vault 06 §5: "100% unit test coverage" for the router tier; corrected 28 Sept). The first version of this roadmap said 90 % → 95 %, taken from the plan's step 0 without checking it against 06. That was wrong. Reached 28 Sept and enforced in CI (`fail_under = 100`, branch coverage on). Four lines are excluded, each for a host we don't run on: the big-endian table paths (3) and the bare-source-tree version fallback (1). Unreachable defensive branches were removed rather than excluded. Index lookups by an id taken from the index's own tables now go through `RouterIndex.info()`, which raises on an inconsistent index, and `route()` fails safe to `ROUTE_UNRESOLVED`.
6. **UK first, Spain after UK is complete** (§U). Pre-1963 Acts use regnal coordinates (U1). The other-series listing harvest is written in the repo (U4). Porting the fetch code waits until the data is downloaded (U3).

7. **Q-M1-1 (case collisions), decided 27 Sept:** use a case-variant table.
   - The build allows a collision only between coordinates that differ solely by case under the same parent, and records them in a `case_variants` index table.
   - **Refined 28 Sept (Stage B):** a case variant is any such collision inside one instrument. SI 1994/1433 and SI 2015/596 have distinct source ids (`paragraph-5-A-i` and `paragraph-5-a-i`) whose parents are never coordinates themselves. A collision across instruments still fails.
   - A lookup that hits such a key binds only on an exact-case match; otherwise it returns `ROUTE_AMBIGUOUS` listing both.
   - Every other collision still fails the build.
8. **Fixture data (27 Sept):** you move CA 2006, SI 2011/3006 and SI 2026/310 to the front of your fetch queue. Meanwhile I build the fixture from what's on disk and add these when they land.
10. **PDF-only instruments (27 Sept):** 21,731 of the 33,788 scraped files have no provision structure (legislation.gov.uk holds them as PDFs only).
    - Citing the instrument binds normally.
    - A *provision* citation to one returns `ROUTE_OUT_OF_COVERAGE`, reason "provision structure not available", `next_action` `VERIFY_LIVE`. It is never refused.
    - The index records `structure: full | metadata_only` per instrument.
16. **Q-M7-2 latency on 4 KB noise (27 Sept):** split budget.
    - **Real queries:** < 2 ms p99, published by `bench/latency.py`.
    - **Random noise at the 4 KB cap:** the published number is the *measured* worst case across gibberish classes (`bench/stress.py`). On the Mac:
      - fixture index: 9.06 ms (28 Sept, after the U2 re-fetch; 9.49 ms earlier that day, 7.22 ms on 27 Sept);
      - **full UK index: 9.21 ms** (17.47 ms before decision 21).

      The tests guard 2× the fixture floor, plus linear doubling (≤ 2.5×) per class.
    - The 4 KB cap is unchanged. See `docs/measurements.md`.
13. **Q-M7-1 duplicated source ids (27 Sept):** a citation that resolves to a coordinate in an instrument's `duplicated_provisions` returns `ROUTE_AMBIGUOUS` (which Part?). It is never bound.
14. **Mixed coverage (27 Sept):** if one citation is out of coverage and the others are bound, the query is `ROUTE_OUT_OF_COVERAGE`, and every citation is listed with its resolution. A recognised citation is never dropped silently.
20. **Q-B-1 title vs SI number (28 Sept):** a real title followed by a bracketed SI number of another SI → `ROUTE_AMBIGUOUS`, new reason **`number_mismatch`**, both instruments offered. Not when another title named in the query owns that number (a bracket numbering several titles), and not without brackets (a list). Acts keep `chapter_mismatch` (UK-I-21). grammar.md UK-I-30, contract §2.
22. **Number keys by series (28 Sept, found in your full catalogue):** an official number resolves only to the series it numbers.
    - Regnal chapters (`rc/…`) are keyed for `ukpga`, `apgb` and `aep`. Local Acts, personal Acts, Church Measures, and Irish and Northern Ireland Acts get no number key, and resolve by title only.
    - Welsh SIs from 2026 get no `si/…` key: they have their own number series.
    - The out-of-coverage table drops a catalogue entry as "already indexed" only on an SI-number hit (the `wsi`/`nisi` canonical coordinates). A chapter hit doesn't count: 41 Geo. 3 c. 1 is both a Great Britain and a UK Act. Known limit: that citation binds the indexed UK Act.
    - Index format is unchanged; only the keys' content changed.
21. **Q-B-3 work limit (28 Sept):** an unknown-title check (typo tiers and suggestions) costs `UNKNOWN_TITLE_COST` = 32 of the 320 lookups (UK-W-03). Chosen as the largest power of two that changes no real query in the 100,000-citation sweep sample (40 would change 2).
17. **Former titles (28 Sept):** a renamed Act cited by its former title binds to the current Act ("Supreme Court Act 1981" → Senior Courts Act 1981). The router adds a note saying the title is a former one.
    - **Source:** the `ukm:AffectedTitle` values in each Act's own effects list. It is the only place the CLML records old titles. The short-title section shows only the new words.
    - **Acts only.** SI effect titles are mostly abbreviations ("Regs", "O") and typos.
    - **Guards against source errors.** The data maps some effects to the wrong Act, e.g. Homelessness Act 2002 listed as "Budget (No. 2) Act (Northern Ireland) 2002", and Army Act 1955 as "Aliens' Employment Act 1955". Support counts don't separate these from real renames. So a former title is used only if:
      - it names the same year;
      - it ends in "Act";
      - it isn't the current title of any other instrument in the index or the catalogue.
    - **Coverage limit:** current files list only *unapplied* effects, so Stage A finds only the renames with pending effects. A fuller source (the legislation.gov.uk changes feed) is a Stage B fetch and needs your go. Well-known renames can also go in `aliases/uk.toml`.
18. **Acronyms (28 Sept):** a hybrid, with curated entries taking precedence.
    - **Generated from indexed Act titles:**
      - initials with particles skipped (TCGA, ITEPA, SOCPA) and with them kept (POCA, PACE);
      - each with and without the "Act" initial (LASPO, PACE).
    - **Stored in their own index table** (`acronyms`), with every target.
    - **With a year:** unique for that year → `ROUTE_BOUNDED`. A clash → `ROUTE_AMBIGUOUS` ("Did you mean X or Y?").
    - **Curated aliases (`aliases/uk.toml`) always win,** and bind directly (CA 2006 → Companies Act 2006, EA 2010 → Equality Act 2010).
    - **Guardrails:**
      - every generated form needs its year, and at least 2 letters;
      - no plain form for numbered titles ("Finance (No. 2) Act"), so "FA 2023" means the Finance Act 2023;
      - an acronym written in lower case counts only with a year, at least 3 letters, and when it isn't a word in any indexed title ("in 2006" is never an acronym).
    - **Bare acronyms (no year) come only from the curated aliases** (HRA, TULRCA, EqA …). You chose this on 28 Sept after measurement: on the Stage A index, generated bare forms collide with regulator names (FCA 7 Acts, PRA 30, CMA 16, CAA 45, FSA 35, SIA 21), so "What does the FCA require?" would have asked about the Foreign Compensation Act 1969.
    - **Index format v1 gains an `acronyms` table** (pre-release; no version bump).
19. **Historical provisions (28 Sept):** a provision missing from the current text keeps the plain `EPISTEMIC_ABSTENTION_PROVISION_NOT_FOUND` refusal. No extra wording. Historical versions are Phase 2.
15. **Linking and exclusion (27 Sept):** an unlinked provision attaches to the one instrument the query names, if there is exactly one that is not negated.
    - **Exclusion is handled at both levels, provision and instrument.** A cue ("except", "other than", "apart from", "excluding", "save for", "with the exception of", "not", "but not", "rather than", "instead of") marks the mention straight after it (and any list joined to it) as excluded.
    - An excluded mention is never a bound target. It appears in `citations` with `resolution="excluded"` and in the new `RouteResult.excluded`, and `partition_filter` removes it (`and not (coordinate == … or coordinate like …/%)`).
    - Example: "…all sections except section 124" of ERA 1996 → bound to the whole Act minus s.124.
    - If the cue's scope is unclear, the result is `ROUTE_AMBIGUOUS`.
12. **Q-M6-1 index storage (27 Sept):** memory-mapped sorted tables (`*.tbl` + `*.off`, SHA-256 verified).
    - Replaces the JSON tables and the frozenset / node trie. The plan anticipated this past about 1M coordinates.
    - Titles are found by n-gram lookups, not an in-memory trie.
    - Case variants are stored in the coordinate table value.
11. **Record text (27 Sept):** each provision record's `text` holds its own text only, excluding child provisions. Records carry `parent` and `order`, and full text is rebuilt by joining descendants.
9. **U4 listing harvest (27 Sept):** written and tested offline now, against recorded feed pages. It runs in Stage B, after your fetch completes, so the two never overlap.

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
