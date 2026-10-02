# The router against Gemini 3.8 Flash (high), Jev and Laya, UK (roadmap M11)

Run 1 October 2026, scored 2 October. Sealed as `seals/results-compare-2026-10-01.json`
(`b96c5c86…`), citing the v2 battery seal (`024da21e…`). The artefacts, including every call,
are in `results/compare-uk-2026-10-01/`. Design and decisions: `docs/ROADMAP.md`, M11 and §4
decisions 3 (amended) and 23.

**Gemini** throughout means **Gemini 3.8 Flash (high)**: Gemini 3.8 Flash at the high thinking
level, the setting most people use it with and a considerably stronger one than the default. Its
figures should not be read as the model at a lower thinking level.

## What was compared

| System | How it was run | What it answered |
|---|---|---|
| **The router** | In process, no network. Sealed runs v1 (blind) and v2 (after fixes), `reports/sealed-run-uk.md` | Outcome and coordinates, every battery row |
| **Gemini 3.8 Flash (high), end to end** | Google AI Studio (how it was reached: below), 2,112 rows | One answer per row, read three ways (below) |
| **Gemini 3.8 Flash (high) on choice questions** | The same, 6,150 questions | Which instrument, from 3 / 10 / 30 options plus "none of these" |
| **Jev** (`typesafe/jev-1.13-20260917`) | OpenRouter's Decisions API, 6,150 questions | The same choice questions |
| **Laya** (base, 421M) | Self-hosted; speed and footprint only (decision 3) | Not scored; see `docs/measurements.md` |

**Gemini's answer, read three ways** (one call each, approved 1 Oct):
1. **As a parser** (the vault's Unit 1): Gemini lists what was cited (title, year, number, provision). Those citations are resolved by the router's own index, and Gemini's coordinates are unused. This is the "LLM extracts, a lookup resolves" pipeline. A perfect extraction resolves to the gold in 1,915 / 1,918 single-citation rows, so this reading can cost Gemini at most about 0.16 %.
2. **As an LLM-only router:** Gemini's own outcome and coordinates, from memory, with no index.
3. **On existence** (Unit 2): reading 2's outcome on invented law and on real law.

All scored with the sealed run's own metrics code and Clopper–Pearson upper bounds. Fed the router's answers, that code reproduces the v2 run exactly.

## Headline: routing the battery

Each cell is *count / out of* (rate). The upper 95 % bound, where shown, is after "≤".

| Measure | Router v1 (blind) | Router v2 | Gemini 3.8 Flash (high) as parser, router resolves | Gemini 3.8 Flash (high), LLM only |
|---|---|---|---|---|
| Bound to the wrong instrument (real citations) | 2 / 1,897 (0.11 %) | **0 / 1,897** | **0 / 1,897** (≤ 0.16 %) | **102 / 1,897 (5.38 %, ≤ 6.31 %)** |
| Real law refused (false abstention) | 84 / 1,897 (4.43 %) | 82 / 1,897 (4.32 %) | **55 / 1,897 (2.90 %, ≤ 3.62 %)** | 233 / 1,897 (12.28 %, ≤ 13.59 %) |
| Held-out real citations left unresolved | 67 / 1,000 (6.7 %) | 67 / 1,000 (6.7 %) | **11 / 1,000 (1.1 %)** | 11 / 1,000 (1.1 %) |
| Invented law bound | **0 / 68** | **0 / 68** | **0 / 68** | **0 / 68** |
| Invented law refused with the right outcome | 68 / 68 | 68 / 68 | 68 / 68 | 68 / 68 |
| Typos bound when they should not be | 1 / 22 | 0 / 22 | 4 / 22 | 3 / 22 |
| Rows with the expected outcome | 1,903 / 2,112 (90.1 %) | 1,916 / 2,112 (90.7 %) | **1,972 / 2,112 (93.4 %)** | 1,799 / 2,112 (85.2 %) |

**Outcomes as expected, per battery** (rows with the expected outcome / rows in the battery):

| Battery | Router v1 (blind) | Router v2 | Gemini parser | Gemini LLM only |
|---|---|---|---|---|
| ambiguous | 23 / 25 | 25 / 25 | 8 / 25 | 2 / 25 |
| catalogue | 43 / 45 | 45 / 45 | 32 / 45 | 31 / 45 |
| collision | 40 / 40 | 40 / 40 | 40 / 40 | 39 / 40 |
| false_abstention | 770 / 773 | 773 / 773 | 767 / 773 | 633 / 773 |
| identifier | 29 / 29 | 29 / 29 | 26 / 29 | 26 / 29 |
| informal | 27 / 27 | 27 / 27 | 19 / 27 | 22 / 27 |
| invented | 68 / 68 | 68 / 68 | 68 / 68 | 68 / 68 |
| misroute (real documents) | 834 / 1,030 | 836 / 1,030 | **944 / 1,030** | 926 / 1,030 |
| typo | 69 / 75 | 73 / 75 | 68 / 75 | 52 / 75 |
| **All batteries** | 1,903 / 2,112 | 1,916 / 2,112 | **1,972 / 2,112** | 1,799 / 2,112 |

(v2's hand batteries are not blind: they were fixed after v1, so v1 is the blind figure.)

**What this shows:**
- **Gemini on its own is not a safe router.** It bound the wrong instrument for 102 / 1,897 real citations (about 1 in 19), and refused 233 / 1,897 (about 1 in 8). Its outcome also changed between repeats on 34 / 200 rows (17 %, below). It did refuse every invented citation (68 / 68), given a contract that told it how.
- **Gemini as a parser in front of the router is the most accurate pipeline measured.** On the real-document battery (1,030 rows), it resolves 116 that the router left unresolved or refused, and loses 8 that the router got right. Most are bare SI numbers ("1999/3434", which the router does not bind on purpose), multi-citation sentences, and schedule paragraphs the router linked to the wrong Act. With the router's index doing the resolving, it binds nothing wrong and nothing invented.
- **The router is what keeps that pipeline safe.** Every coordinate it binds comes from the index, so the hybrid inherits the router's 0 wrong-instrument and 0 invented bindings. Gemini supplies recall on messy real text. The router alone wins every hand battery: ambiguity, typos, informal titles, identifiers and coverage. Gemini as a parser handles only 8 / 25 ambiguities, because it picks one instrument instead of asking.
- **The cost of that recall** is the rest of this report: about 13.5 s at p50 and $0.009 per query, 34 / 200 answers changing between repeats, and the query leaving your network. The router's contract already has the slot for it: `ROUTE_UNRESOLVED` → `DISCOVER_THEN_BIND`. An LLM pass only on the queries the router leaves unresolved or refuses (258 / 2,112 here, 12 %, a share inflated by the battery's invented rows) would buy most of that recall at roughly an eighth of the cost and of the time spent waiting. That is a design proposal, not a measured result.

## Choice questions: Jev and Gemini 3.8 Flash (high) (perfect-retriever ceiling)

The right instrument is always among the options, each labelled with its title and official citation, plus "none of these". So this is a best case: a retriever that never misses. 2,050 questions per option count, of which 1,960 have a real instrument as the answer and 90 have "none of these". 62 of the 2,112 rows have no instrument-level answer and are left out by rule. Instrument level only.

| Options | Jev correct | Gemini correct | Jev picked a real instrument when "none" was right | Gemini, same |
|---|---|---|---|---|
| 3 | 2,031 / 2,050 (99.1 %) | 2,037 / 2,050 (99.4 %) | 2 / 90 | 0 / 90 |
| 10 | 2,033 / 2,050 (99.2 %) | 2,038 / 2,050 (99.4 %) | 1 / 90 | 0 / 90 |
| 30 | 2,023 / 2,050 (98.7 %) | 2,035 / 2,050 (99.3 %) | 6 / 90 | 3 / 90 |

- **Given the right candidates, both models choose well,** and accuracy barely falls as the options grow. The vault's expected curve (96 → 79 → 54 % for decision models) is not borne out here; those were placeholders, and this measurement replaces them.
- **What still matters:** the right instrument had to be offered. Laya, the self-hosted alternative, sees only 29 % of each title at 30 options (`docs/measurements.md`).

## Determinism

The same query, five times, over 200 seeded rows:

| System | Rows whose answer changed |
|---|---|
| Router | 0, by construction (the sealed runs reproduce byte for byte) |
| Jev (10 options) | 2 / 197 (1.0 %); 3 of the 200 rows have no choice question |
| **Gemini 3.8 Flash (high), end to end** | **34 / 200 (17.0 %)** |

## Cost per 1,000 queries

At list price per token, from the token counts each system reported. The calls measured: Gemini end to end 2,112, Gemini choice 6,150, Jev 6,150 (accuracy pass).

| System | Promotional price | Regular price |
|---|---|---|
| Router | $0 | $0 |
| Gemini 3.8 Flash (high), end to end (1,344 input, 144 output, 1,923 thinking tokens on average) | $8.76 | $17.52 |
| Gemini 3.8 Flash (high), choice question | $1.00 | $1.99 |
| Jev choice question (986 input tokens) | $0.041 | $0.041 |

- **Gemini prices:** $0.75 / $3.75 per million tokens, Google's promotional price "through December 31, 2026"; $1.50 / $7.50 after. Thinking is billed as output.
- **Jev price:** $0.042 per million input tokens, which matches the cost the API reported per call.
- **Total for this run, every pass, at list price:**
  - Gemini: $37.78 at the promotional price, about $75.56 at the regular one (accuracy $24.63, the rest determinism and latency);
  - Jev: $0.30.

## Latency

The latency pass sent 300 seeded rows one call at a time, interleaved, from the author's Mac in Pakistan. Each system's no-model floor call went on the same connection.

| System | Calls | p50 [95 % CI] | p99 | Floor p50 | Note |
|---|---|---|---|---|---|
| Router, in process | 306,336 | 0.14 ms | 2.10 ms | none | Controlled bench (`docs/measurements.md`) |
| Router, in process, inside this pass | 300 | 1.18 ms [1.14–1.28] | 6.29 ms | none | Each call follows a multi-second network wait, so the CPU and caches are cold |
| Router as a network service (Row B, 30 Sept) | 6,336 | 276.6 ms | 364.5 ms | 275.7 ms | Modal us-east; the router's own share 0.63 ms |
| Laya on an NVIDIA T4 | 900 | 34–37 ms | 44–46 ms | none | Self-hosted, model time only; 300 per option count |
| **Jev** (10 options) | 287 | **507 ms [497–518]** | 2,222 ms | 103 ms | OpenRouter; 13 of the 300 rows have no choice question |
| **Gemini 3.8 Flash (high), end to end** | 300 | **13.5 s [12.1–15.2]** | **192 s** | 1.7 ms | The tail is thinking: the slowest call took 249 s for 32,497 thinking tokens |

- **Gemini's time is the model's own.** Its floor call measures the hop from the client to the local proxy on the same Mac: 1.7 ms at p50. Beyond that, the calls went to Google AI Studio over the Mac's connection, as a direct call would.
- **The long tail is thinking, not waiting.** In this one-call-at-a-time pass:
  - 22 / 300 calls took over a minute, and 4 / 300 over two minutes;
  - the slowest four (173–249 s) each thought 24,500–34,300 tokens, about 15× the typical 1,900, and generated at 130–150 tokens a second, the model's own pace;
  - each finished normally with a valid answer, but 2 / 4 were wrong;
  - they are dense amendment-note citations ("S.I. 2020/1495, regs. 1(2), 21), S.I. 2020/1545…").

  The high thinking level spends minutes on exactly the queries a router would answer in a millisecond.
- **Waiting under load is a separate thing, and it is not in this table.** In the concurrent determinism pass (12 calls at a time), a few calls waited minutes while thinking under 1,000 tokens (about 3 tokens a second). That is queueing upstream under load, and the latency figures here come only from the one-at-a-time pass.
- **Latency is not the headline** (vault 07 §2), but the spread is the point. The router answers in under a millisecond in process, and in a quarter of a second even as a remote service. Gemini's thinking alone takes seconds, with a tail of minutes.

## Data leaving your network

| System | What leaves |
|---|---|
| Router | Nothing; it runs in process |
| Laya | Nothing when self-hosted |
| Jev | The full query text, to OpenRouter and TypeSafe |
| Gemini | The full query text, to Google |

## How the run went, and what to disclose

- **How Gemini was reached in this run.** The calls went to Google AI Studio through the author's own routing setup, an OpenAI-compatible proxy on the author's machine (`localhost:8317`). The author's direct Google AI Studio key was on the free tier (20 requests a day) and could not carry the run.
  - The model was Gemini 3.8 Flash at the high thinking level and its default temperature (`gemini-3.8-flash-high`, reported as `gemini-3.8-flash-n`).
  - Token counts are the ones the proxy passed back. Costs are at Google's list price.
  - Reaching the proxy took 1.7 ms (p50) on the same Mac, and the slow calls generated at the model's own rate (see **Latency**). So nothing measured points to the setup adding time.
  - The proxy client is not part of the published code (removed 2 Oct). The code calls Google AI Studio's API directly with the same settings: see **Reproducing**.
- **378 / 8,262 Gemini accuracy calls** (284 / 6,150 choice, 94 / 2,112 end to end) failed with the proxy's `model_cooldown` 429 during its 5-hour limit (08:26–08:59 UTC). They were rerun and answered. The failed attempts stay in the logs (`superseded_failures` in the summary).
- **Gemini's instructions** gave it the router's whole contract: the coordinate format, outcomes, coverage and snapshot date, with nine worked examples checked not to overlap the battery. Without that, its coordinates would not be comparable at all.
- **Rows that depend on our index's choices** (out of coverage) are scored with all rows and again without them. The figures above do not move.
- **One run, at one time of day,** from one client: the author's Mac. The plan's second, off-peak run and a UK/EU client are left as improvements.
- **The router on Modal was not interleaved** with this pass. Its Row B is the separate run of 30 Sept.
- **Jev and Gemini choice results are instrument-level only,** with the right answer always offered.
- **Router v2 is not blind on the hand batteries.** v1 is the blind figure and is shown beside it.

## Reproducing

`scripts/compare_run.sh <results dir>` reruns every pass: accuracy, determinism and latency, then the scoring.
- **Gemini** is called through Google AI Studio's API directly (`bench/clients/gemini.py`, key in `GEMINI_API_KEY`). It uses `gemini-3.8-flash` at `thinkingLevel: "high"` and the model's default temperature, the settings of this run.
- **The key must be on a paid-tier project:** the run makes about 9,500 Gemini calls, and the free tier allows 20 a day per model.
- **Jev** needs `OPENROUTER_API_KEY`.
- **The latency pass leaves out the router on Modal** unless `LRR_ROW_B=1` is set, with a deployed `deploy/modal_router.py`.
- **Resumable:** every call is written as it returns. A rerun makes only the missing or failed calls.
- **Inputs:** the battery, the option sets and every seed are fixed, so a rerun asks exactly the same questions.
- **What may differ:** Gemini's answers vary between runs (34 / 200 rows changed on repeat here). Its latency will also differ with the client's location, the time of day and Google's load.
- **Cost:** about $38 at Google's promotional list price ($76 regular), and $0.30 of OpenRouter credit.
