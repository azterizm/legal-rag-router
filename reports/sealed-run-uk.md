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

p99 over all calls meets the < 2 ms target, just. It counts every repeat, not the best of three. Questions and refusals take longer at the tail, because they run the typo tiers and suggestion ranking. The x86-64 run is pending (`scripts/latency_x86.sh`, on your rig).
