# Concept discovery (UK): the sealed test run (roadmap D5)

Run 29 Sept 2026 on the test slice of `batteries/concept/uk.jsonl`, once. It was verified against `seals/concept-2026-09-29.json` (seal `d34ce21d…`), at commit `969bd4e`, concept index manifest SHA-256 `34b6569e…`, with the `DiscoveryPolicy` defaults frozen at D4.

Raw results with every row: `reports/discovery-uk-test.json` and `reports/discovery-uk-test-baseline.json` (`uv run python -m eval.discovery --split test --seal … --details`). Tuning used the dev slice only. No test row was looked at before this run.

## Results

A candidate is a hit when it is a gold coordinate or lies beneath one. "Headings only" is the vault's design (02 §5, 05 §4): the same terms, but only the section-heading field, and no thesaurus or priors.

| Slice | Rows | | hit@1 | hit@5 | hit@10 | MRR | confident |
|---|---|---|---|---|---|---|---|
| Drafted queries (test half) | 91 | headings only | 19 % | 44 % | 51 % | 0.29 | 74 % |
| | | **`discover()`** | **51 %** | **80 %** | **88 %** | **0.63** | 95 % |
| Your `rag-security-probes` with a real answer | 11 | headings only | 18 % | 36 % | 45 % | 0.27 | 27 % |
| | | **`discover()`** | **45 %** | **64 %** | **64 %** | **0.55** | 45 % |
| **Negatives:** Mart Appendix B (US law) | 50 | headings only | | | | | 8 % confident |
| | | **`discover()`** | | | | | **30 % confident** |
| **Negative:** your FAB-004 (no statutory answer) | 1 | `discover()` | | | | | not confident |

For comparison, the dev slice (tuned on): hit@1 68 %, hit@10 91 %, MRR 0.75. **Test is lower at rank 1 (51 % against 68 %): that much is fitted to dev.** hit@10 holds (88 % against 91 %).

**Safety, on all 153 rows:**
- **0** candidates the router cannot bind.
- `route()` returned the labelled status for **every** row. The 141 citation-less queries stay `ROUTE_UNRESOLVED`, so discovery never turned a research query into a binding. Your false-premise probes are refused as the grammar says: invented Acts → instrument not found, ERA s. 342 → provision not found, and the repealed SDA 1975 s. 6 is bound with `repealed=True`.

**Latency on test:** p50 85 ms, p99 318 ms. Your probes are full sentences, longer than the keyword queries, and dev's p99 was 181 ms.

## By area (drafted test queries)

| Area | hit@10 | hit@1 | | Area | hit@10 | hit@1 |
|---|---|---|---|---|---|---|
| equality | 9/9 | 7/9 | | data and information | 8/9 | 5/9 |
| companies | 7/7 | 7/7 | | housing | 6/7 | 2/7 |
| criminal procedure | 8/8 | 5/8 | | tax | 6/7 | 1/7 |
| land | 7/7 | 3/7 | | criminal offences | 5/6 | 4/6 |
| family | 5/5 | 4/5 | | insolvency | 4/5 | 1/5 |
| consumer and contract | 7/9 | 5/9 | | employment | 8/12 | 2/12 |

Totals: 80 / 91 in the top 10, 46 / 91 at rank 1.

Employment, tax and insolvency are weakest at rank 1, because sections within one Act share vocabulary. The heading of s. 94 is "The right.", and s. 107 "Pressure on employer to dismiss unfairly" outranks it.

## Your probes

| Probe | Real law your repo names | `discover()` rank | Top candidate |
|---|---|---|---|
| FAB-001 | LPA 1925 s. 146 | — | Leasehold Reform (Ground Rent) Act 2022 s. 9 (financial penalties) |
| FAB-002 | Housing Act 1996 s. 81 | **1** | the same |
| FAB-003 | FSMA 2000 s. 206 | — | Companies Act 2006 s. 1110D |
| FAB-004 | none | not confident ✓ | Companies Act 2006 s. 92 |
| FAB-005 | 1993 Act ss. 76–84 / CLRA 2002 Sch. 11 | **1** | LRHUDA 1993 s. 76 (right to audit management) |
| FAB-006 | 1993 Act ss. 76–84 | — | Companies Act 2006 s. 494ZA |
| CHIM-001 | ERA 1996 s. 86 | 2 | ERA 1996 s. 87 |
| CHIM-002 | CRA 2015 s. 22 | **1** | the same |
| CHIM-003 | DPA 2018 s. 170 | **1** | the same |
| OOB-001 | ERA 1996 s. 23 | 2 | ERA 1996 s. 18 |
| DEVOLV-001 | MCA 2005 ss. 16, 19 | **1** | MCA 2005 s. 16 |
| REPEAL-001 | Equality Act 2010 s. 124 | — | TURERA 1993 s. 32 |

For 7 of the 11 false-premise questions, discovery found the provision the question was really reaching for, while `route()` correctly refused the invented citation. That pairing is a refusal that names the real law: the "abstain, then name the governing provision" answer your repo's examples model.

## What this shows

1. **Heading-only discovery is not enough.** It finds the answer in the top 10 for half the queries, against 88 % for `discover()`. Your critique of the vault design holds on independent data.
2. **Discovery can offer, never decide.** Rank 1 is right for half the queries. Candidates must be confirmed, which is what the contract already requires (`next_action = ASK_USER`).
3. **The confidence flag is weak.** 30 % of US-law queries get a "confident" UK candidate: "criminal sentence enhancement findings by jury required" → Coroners and Justice Act 2009 s. 9 ("Determinations and findings by jury"). This was predicted on dev, where 90 % of misses were also confident. The flag can't yet tell a caller "this is out of scope".
4. **Safety held:** nothing unbindable was offered, and routing was never changed.
