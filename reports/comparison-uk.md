# The router against Gemini, Jev and Laya, UK (roadmap M11)

Run 1 October 2026, scored 2 October. Sealed as `seals/results-compare-2026-10-01.json`
(`b96c5c86…`), citing the v2 battery seal (`024da21e…`). The artefacts, including every call,
are in `results/compare-uk-2026-10-01/`. Design and decisions: `docs/ROADMAP.md`, M11 and §4
decisions 3 (amended) and 23.

## What was compared

| System | How it was run | What it answered |
|---|---|---|
| **The router** | In process, no network. Sealed runs v1 (blind) and v2 (after fixes), `reports/sealed-run-uk.md` | Outcome and coordinates, every battery row |
| **Gemini 3.8 Flash, end to end** | Through the author's proxy (below), 2,112 rows | One answer per row, read three ways (below) |
| **Gemini on choice questions** | Same proxy, 6,150 questions | Which instrument, from 3 / 10 / 30 options plus "none of these" |
| **Jev** (`typesafe/jev-1.13-20260917`) | OpenRouter's Decisions API, 6,150 questions | The same choice questions |
| **Laya** (base, 421M) | Self-hosted; speed and footprint only (decision 3) | Not scored; see `docs/measurements.md` |

**Gemini's answer, read three ways** (one call each, approved 1 Oct):
1. **As a parser** (the vault's Unit 1): Gemini lists what was cited (title, year, number, provision). Those citations are resolved by the router's own index, and Gemini's coordinates are unused. This is the "LLM extracts, a lookup resolves" pipeline. A perfect extraction resolves to the gold in 1,915 of 1,918 single-citation rows, so this reading can cost Gemini at most about 0.16 %.
2. **As an LLM-only router:** Gemini's own outcome and coordinates, from memory, with no index.
3. **On existence** (Unit 2): reading 2's outcome on invented law and on real law.

All scored with the sealed run's own metrics code and Clopper–Pearson upper bounds. Fed the router's answers, that code reproduces the v2 run exactly.

## Headline: routing the battery

Rates over the battery's rows. The upper 95 % bound is in brackets.

| Measure | Router v1 (blind) | Router v2 | Gemini as parser, router resolves | Gemini, LLM only |
|---|---|---|---|---|
| Bound to the wrong instrument (of 1,897 real citations) | 2 (0.11 %) | **0** | **0** (≤ 0.16 %) | **102 (5.38 %, ≤ 6.31 %)** |
| Real law refused (false abstention) | 84 (4.43 %) | 82 (4.32 %) | **55 (2.90 %, ≤ 3.62 %)** | 233 (12.28 %, ≤ 13.59 %) |
| Held-out real citations left unresolved (of 1,000) | 67 (6.7 %) | 67 (6.7 %) | **11 (1.1 %)** | 11 (1.1 %) |
| Invented law bound (of 68) | **0** | **0** | **0** | **0** |
| Invented law refused with the right outcome | 68/68 | 68/68 | 68/68 | 68/68 |
| Typos bound when they should not be (of 22) | 1 | 0 | 4 | 3 |
| Rows with the expected outcome (of 2,112) | 1,903 (90.1 %) | 1,916 (90.7 %) | **1,972 (93.4 %)** | 1,799 (85.2 %) |

**Outcomes as expected, per battery** (router v2 / Gemini parser / Gemini LLM only):

| Battery | Rows | Router v2 | Gemini parser | Gemini LLM only |
|---|---|---|---|---|
| ambiguous | 25 | 25 | 8 | 2 |
| catalogue | 45 | 45 | 32 | 31 |
| collision | 40 | 40 | 40 | 39 |
| false_abstention | 773 | 773 | 767 | 633 |
| identifier | 29 | 29 | 26 | 26 |
| informal | 27 | 27 | 19 | 22 |
| invented | 68 | 68 | 68 | 68 |
| misroute (real documents) | 1,030 | 836 | **944** | 926 |
| typo | 75 | 73 | 68 | 52 |

(v2's hand batteries are not blind: they were fixed after v1. v1 scored 23, 43, 40, 770, 29, 27, 68, 834 and 69 on the same rows.)

**What this shows:**
- **Gemini on its own is not a safe router.** It bound the wrong instrument for 1 real citation in 19, and refused 1 real citation in 8. Its outcome also changed between repeats on 17 % of rows (below). It did refuse every invented citation, given a contract that told it how.
- **Gemini as a parser in front of the router is the most accurate pipeline measured.** On the real-document battery, it resolves 116 citations the router left unresolved or refused, and loses 8. Most are bare SI numbers ("1999/3434", which the router does not bind on purpose), multi-citation sentences, and schedule paragraphs the router linked to the wrong Act. With the router's index doing the resolving, it binds nothing wrong and nothing invented.
- **The router is what keeps that pipeline safe.** Every coordinate it binds comes from the index, so the hybrid inherits the router's 0 wrong-instrument and 0 invented bindings. Gemini supplies recall on messy real text. The router alone wins every hand battery: ambiguity, typos, informal titles, identifiers and coverage. Gemini as a parser misses most ambiguities (8 of 25), because it picks one instrument instead of asking.
- **The cost of that recall** is the rest of this report: about 13.5 s and $0.009 per query at p50, 17 % of answers changing between repeats, and the query leaving your network. The router's contract already has the slot for it: `ROUTE_UNRESOLVED` → `DISCOVER_THEN_BIND`. An LLM pass only on the queries the router leaves unresolved or refuses (258 of 2,112 here, 12 %, a share inflated by the battery's invented rows) would buy most of that recall at roughly an eighth of the cost and of the time spent waiting. That is a design proposal, not a measured result.

## Choice questions: Jev and Gemini (perfect-retriever ceiling)

The right instrument is always among the options, each labelled with its title and official citation, plus "none of these". So this is a best case: a retriever that never misses. 2,050 questions per option count; 62 rows without an instrument-level answer are left out by rule. Instrument level only.

| Options | Jev correct | Gemini correct | Jev picked a real instrument when "none" was right (of 90) | Gemini, same |
|---|---|---|---|---|
| 3 | 2,031 (99.1 %) | 2,037 (99.4 %) | 2 | 0 |
| 10 | 2,033 (99.2 %) | 2,038 (99.4 %) | 1 | 0 |
| 30 | 2,023 (98.7 %) | 2,035 (99.3 %) | 6 | 3 |

- **Given the right candidates, both models choose well,** and accuracy barely falls as the options grow. The vault's expected curve (96 → 79 → 54 % for decision models) is not borne out here; those were placeholders, and this measurement replaces them.
- **What still matters:** the right instrument had to be offered. Laya, the self-hosted alternative, sees only 29 % of each title at 30 options (`docs/measurements.md`).

## Determinism

The same query, five times (200 seeded rows):

| System | Rows whose answer changed |
|---|---|
| Router | 0, by construction (the sealed runs reproduce byte for byte) |
| Jev (10 options) | 2 of 197 (1.0 %) |
| **Gemini end to end** | **34 of 200 (17.0 %)** |

## Cost per 1,000 queries

At list price per token, from the token counts each system reported:

| System | Promotional price | Regular price |
|---|---|---|
| Router | $0 | $0 |
| Gemini end to end (1,344 input, 144 output, 1,923 thinking tokens on average) | $8.76 | $17.52 |
| Gemini choice question | $1.00 | $1.99 |
| Jev choice question (986 input tokens) | $0.041 | $0.041 |

- **Gemini prices:** $0.75 / $3.75 per million tokens, Google's promotional price "through December 31, 2026"; $1.50 / $7.50 after. Thinking is billed as output.
- **Jev price:** $0.042 per million input tokens, which matches the cost the API reported per call.
- **Total for this run, every pass, at list price:**
  - Gemini: $37.78 at the promotional price, about $75.56 at the regular one (accuracy $24.63, the rest determinism and latency);
  - Jev: $0.30.

## Latency

The latency pass sent 300 seeded rows one call at a time, interleaved, from the author's Mac in Pakistan. Each system's no-model floor call went on the same connection.

| System | p50 [95 % CI] | p99 | Floor p50 | Note |
|---|---|---|---|---|
| Router, in process | 0.14 ms | 2.10 ms | none | Controlled bench, 306,336 calls (`docs/measurements.md`) |
| Router, in process, inside this pass | 1.18 ms [1.14–1.28] | 6.29 ms | none | Each call follows a multi-second network wait, so the CPU and caches are cold |
| Router as a network service (Row B, 30 Sept) | 276.6 ms | 364.5 ms | 275.7 ms | Modal us-east; the router's own share 0.63 ms |
| Laya on an NVIDIA T4 | 34–37 ms | 44–46 ms | none | Self-hosted, model time only |
| **Jev** (10 options) | **507 ms [497–518]** | 2,222 ms | 103 ms | OpenRouter |
| **Gemini end to end** | **13.5 s [12.1–15.2]** | **192 s** | 1.7 ms | Through the proxy; the slowest call took 249 s |

- **Gemini's floor is the hop to the local proxy only.** Its network path to Google sits inside the proxy and cannot be separated, so this is the proxy path's latency, not Google's API's.
- **Latency is not the headline** (vault 07 §2), but the spread is the point. The router answers in under a millisecond in process, and in a quarter of a second even as a remote service. Gemini's thinking alone takes seconds, with a tail of minutes.

## Data leaving your network

| System | What leaves |
|---|---|
| Router | Nothing; it runs in process |
| Laya | Nothing when self-hosted |
| Jev | The full query text, to OpenRouter and TypeSafe |
| Gemini | The full query text, to the proxy and on to Google |

## How the run went, and what to disclose

- **The Gemini endpoint.** Gemini was reached only through a private OpenAI-compatible proxy at `localhost:8317`, run by the author's engineer, at the author's direction. It is not Google's public API, and it also serves non-Google models.
  - The model was `gemini-3.8-flash-high` (high thinking), reported as `gemini-3.8-flash-n`, at its default temperature.
  - Token counts are the proxy's. Costs are at Google's list price.
  - Google's own API key was on the free tier (20 requests a day) and could not be used.
- **378 Gemini calls** (284 choice, 94 end to end) failed with the proxy's `model_cooldown` 429 during its 5-hour limit (08:26–08:59 UTC). They were rerun and answered. The failed attempts stay in the logs (`superseded_failures` in the summary).
- **Gemini's instructions** gave it the router's whole contract: the coordinate format, outcomes, coverage and snapshot date, with nine worked examples checked not to overlap the battery. Without that, its coordinates would not be comparable at all.
- **Rows that depend on our index's choices** (out of coverage) are scored with all rows and again without them. The figures above do not move.
- **One run, at one time of day,** from one client: the author's Mac. The plan's second, off-peak run and a UK/EU client are left as improvements.
- **The router on Modal was not interleaved** with this pass. Its Row B is the separate run of 30 Sept.
- **Jev and Gemini choice results are instrument-level only,** with the right answer always offered.
- **Router v2 is not blind on the hand batteries.** v1 is the blind figure and is shown beside it.
