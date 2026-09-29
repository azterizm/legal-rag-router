# Batteries (UK)

The labelled queries the sealed run (M10) scores the router on (plan step 8). One JSON Lines file per battery under `batteries/uk/`, validated in CI by `tests/test_batteries.py` against `batteries/schema.py`.

**Status (29 Sept 2026): sealed.** You approved the six review points below on 29 Sept, and every invented instrument is confirmed absent at the source. The seal is `seals/battery-2026-09-29.json`, tagged locally as `battery-seal-2026-09-29` (see Seal below).

The `misroute` queries quote source text from legislation.gov.uk: Crown copyright, used under the Open Government Licence v3.0.

## Files

| Battery | Rows | Made from | Measures |
|---|---|---|---|
| `collision` | 40 | hand | The same provision number in different instruments: ERA 1996 / CA 2006 / EqA 2010 / FSMA 2000 / TULRCA s. 124, Theft / Fraud / Bribery s. 1, and others. A wrong instrument is a collision |
| `misroute` | 1,030 | 1,000 **held-out** harvested citations + 30 hand | Bound, but to the wrong coordinate. Real drafting, never seen by the grammar |
| `false_abstention` | 773 | 700 sampled from the index + 73 hand | Refusals of citations that exist. Hand rows cover every provision and instrument form in grammar.md 4.1–4.2 |
| `invented` | 68 | hand | 52 invented instruments (Marchwood and 50 others) and 16 invented provisions of real instruments. Never bound |
| `ambiguous` | 25 | hand | Bare provisions, `the 1996 Act`, `the Act`, year-less titles, shared SI titles, open and wide ranges, chapter and SI-number mismatches, duplicated source ids |
| `typo` | 75 | hand | 50 real titles misspelled the way people do it (bound or asked) and 25 adversarial near-misses (never bound). Split `dev` 22 / `test` 53 |
| `identifier` | 29 | hand | Coordinates, instrument ids and legislation.gov.uk URLs, present and absent, any case, with provision words, partial paths, and injection-shaped input |
| `informal` | 27 | hand | Missing type word or year, and mixed-up provision words. Bound when one instrument fits, asked otherwise, never refused |
| `catalogue` | 45 | hand | At least one row per case-catalogue entry (grammar.md 4.4–6): out of coverage, repealed, context follow-ups, negation, exclusion, time qualifiers, several citations, Unicode, look-alike letters, ALL CAPS, work limits, unsupported forms |

Every supported grammar.md row is exercised by at least one battery row (`surface_form_ids`), checked in CI. The one exception is UK-C-17: `jurisdictions=` is an API argument, not query text.

## How rows were made

**No row's label comes from a router run.**

- **Hand rows (412):** `batteries/hand_uk.py`, labelled from grammar.md and the plan. Before writing, `batteries/build_uk.py` checks each label's facts against the full index:
  - every expected coordinate exists in its canonical case and is not a duplicated source id;
  - every `absent:` coordinate in `notes` is absent, and its instrument exists;
  - every invented title is in neither the index nor the catalogue (244,564 entries from the source's own feeds), under its full-title key and, for invented instruments, its year-less key too.

  The checks caught one wrong label while building: the Bribery Act 2010 does have a section 20.
- **`misroute` sample:** 1,000 citations drawn with seed 20260928 from the harvest's **held-out** 20 % (roadmap D3; the split rule is in `reports/harvest-split.json`), restricted to those whose target coordinate the index holds.
  - The query is the clause of the source text that holds the citation (`eval.sweep.replay_query`).
  - The expected answer is the source's own link target.
  - `notes` names the harvested citation (`harvest <source> #<citation_id>`), so anyone with the harvest can recompute its split.
- **`false_abstention` sample:** 700 provisions from the index with seed 20260928, 350 from Acts and 350 from SIs. SIs are 85 % of the instruments with structure, so an unstratified draw gave only 54 Act rows.
  - Each draw picks an instrument, then one of its sections, regulations, articles, rules or schedule paragraphs (up to two levels of subdivision).
  - It skips instruments whose full title isn't unique, longer than 20 words, or PDF-only, and provisions the source publishes twice.
  - The provision is phrased with a template picked by the same generator: by title, by title with its chapter or SI number, or by number alone.
- **Typo split (roadmap D2):** a row is `dev` when `int(sha256("lrr-typo-split-v1|" + id)[:8], 16) % 100 < 30`. Only `dev` may be used for tuning.
  - On 28 Sept the router was run on the 22 `dev` rows only, and matched all 22.
  - The typo thresholds (`typo.TypoPolicy`) are therefore unchanged, and are frozen with the seal. The `test` slice has not been run.

Rebuild with `uv run python -m batteries.build_uk` (build machine: needs `data/`). The output is deterministic for a given index, harvest and catalogue.

## Absence of invented instruments

Each invented instrument carries `absence_verified_via`:

- **Offline check:** done. The row names the index snapshot and the catalogue hash.
- **Source's own search:** done on 29 Sept, by your run of `batteries.verify_absence` with your contact. Every one of the 52 is absent.
  - **51 title searches** (`/all/data.feed?title=…&year=…`) found no instrument with the same full-title key. The site matches by containment, so "Employment Rights Act" 1995 returned 20 other titles and none of them is that one. They were recorded from your fetched responses with `verify_absence --from-cache`, which makes no request. Your run had stopped before saving, on the last row.
  - **`SI 2011/9999`:** the source answered `400 Bad Request`, its answer for an SI number it has no record of. The fetch layer caches only 200, 404 and 410, so this one was recorded from your run's log (the row's `notes` say so). The script now treats 400, 404 and 410 as absent for number-cited rows, and saves after every row.
  - To redo it: `build_uk` rewrites the rows without dates, then `verify_absence --contact …` (or `--from-cache`) fills them again.

## Intended scoring (implemented by M10's `eval/run.py`)

- **A `ROUTE_BOUNDED` row is met** when each expected coordinate is bound, or something above or beneath it is. The source's links are often to the whole instrument (the same `_related` rule as the sweep).
  - Bound but with no coordinate in an expected instrument: a **collision** (`collision`) or **misroute** (other batteries).
  - A refusal: a **false abstention**.
  - `ROUTE_UNRESOLVED`: a **miss**.
- **An `invented` row that is bound** is bound-on-invented, which must be 0.
- **An `ambiguous` typo row** scores clarify recall: its first expected coordinate should be the top candidate.
- Other rows compare the status only.

## Review points (approved 29 Sept 2026)

These are the labels where the plan, grammar.md and the data could be read more than one way. You approved all six as written.

1. **Year-less "Employment Rights Act" is ambiguous.** The plan's informal example (`employment rights act section 124`) assumed one Act. The index also holds the **Employment Rights Act 2025**, which has ss. 98 and 124. Those rows are labelled **A**, per the plan's own rule (bound only when one instrument fits). Likewise "Working Time Regulations" (1998 and 1999) and "the equality act" (2006 and 2010).
2. **`Employment Right Act 1996` (singular) is labelled B.** The plan lists singular/plural among small typos. "right" is itself a word in other titles, so this tests whether a known word one edit from the right one is corrected.
3. **`the explanatory notes to the Equality Act 2010` is labelled U**, as grammar.md UK-U-03 says for explanatory notes and preambles.
4. **Injection-shaped identifiers are labelled B** with only the safe key bound (`uk/ukpga/1996/18' or '1'=='1` → the Act). That is what the code guarantees. grammar.md said the input "fails the grammar"; that wording is now corrected.
5. **Stratified `false_abstention` draw** (half Acts, half SIs), explained above.
6. **UK-C-17 has no row**, because it is an API argument.

## Seal

`uv run python -m eval.seal battery` writes `seals/battery-YYYY-MM-DD.json` (plan step 9). It records the canonical-JSON SHA-256 (sorted keys, no spaces, UTF-8) of:
- every battery file;
- every index file, since the index is not in git;
- the alias TOMLs;
- the harvest split manifest (`reports/harvest-split.json`: which citations are held out);
- the frozen typo thresholds (`TypoPolicy`);
- the package version;
- the git commit the batteries were sealed at.

The seal needs a committed tree. It is committed, then tagged locally as `battery-seal-YYYY-MM-DD` (`git tag -a`; never pushed without your go).

`uv run python -m eval.seal verify seals/battery-….json` recomputes all of it and names every file that differs. M10's `eval/run.py` refuses to start on any difference. `tests/test_seal.py` checks this with one changed byte in a battery, index or alias file, an added battery file, and an edited seal.
