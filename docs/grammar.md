# Coordinate and citation grammar

**Grammar version:** 1 (draft; frozen with the battery seal).
**Scope of this version:** United Kingdom. Spain is added in Stage C (see `docs/ROADMAP.md` §U).

This file is the source of truth for the router's tests:
- **Coordinate grammar (§1–§3):** the only strings the router ever emits as coordinates.
- **Surface-form table (§4):** every written citation form the router accepts, and what it produces.
- **Unsupported forms (§5):** forms the router deliberately does not bind, and what it does instead.
- **Case catalogue (§6):** the edge cases.

Every row has a stable ID. Battery rows cite these IDs in `surface_form_ids`, and a CI test checks that every supported row is exercised by at least one battery row.

---

## 1. Coordinates in general

```ebnf
coordinate   = jurisdiction "/" instrument [ "/" provision ] ;
jurisdiction = lower , { lower } ;                       (* registered per plugin: "uk", later "es" *)
instrument   = segment , { "/" , segment } ;             (* arity declared per jurisdiction, §2 *)
provision    = unit-seg , { "/" , seg } ;                 (* first segment must name a unit *)
seg          = alnum{1,24} , { "." , alnum{1,24} } ;      (* at most 3 dots; no quotes, spaces, %, / *)
```

Rules shared by every jurisdiction:

| Rule | Detail |
|---|---|
| Canonical form | The canonical string keeps the source's case (`1ZA`, `ptI`, `schSECOND`) |
| Lookup key | `key` = the casefolded canonical string |
| Instrument-level coordinates | Valid endpoints. `uk/ukpga/1996/18` binds the whole Act |
| `instrument_id` | Jurisdiction plus instrument segments, joined with `_`: `uk_ukpga_1996_18`, `uk_ukpga_Eliz2_8-9_69`. This is the vector-store partition key |
| Limits | ≤ 256 characters; ≤ 16 provision segments |
| Parsing | `Coordinate.parse` is exact: case-sensitive, no normalisation. User input is resolved to canonical form through the index's casefolded lookup, never by the parser |
| Safety | The segment alphabet (`[0-9A-Za-z.]`) cannot express a quote, space, wildcard or path separator. That is what makes coordinates safe to put into a filter expression (`filters.py`) |

## 2. United Kingdom coordinates (`uk`)

Coordinates mirror legislation.gov.uk's identifier URIs (`IdURI`). This is decided in the roadmap, §U1.

```ebnf
uk-instrument = series "/" year "/" number                    (* arity 3 after "uk" *)
              | series "/" regnal "/" session "/" number ;    (* arity 4 after "uk": Acts before 1963 *)
series   = lower{2,6} ;                        (* ukpga, uksi, wsi, nisi, asp, ssi, nisr, eur … *)
year     = ( "1" | "2" ) digit{3} ;
number   = nonzero-digit , digit{0,5} ;        (* no leading zeros *)
regnal   = reign , { "and" , digit{0,2} , reign } , [ "Sess" , digit ] ;
reign    = upper , lower{1,5} , digit{0,2} ;   (* Vict, Geo3, Will4, Edw7, Eliz2, WillandMar *)
session  = digit{1,3} , { "-" , digit{1,3} } ; (* regnal year(s): 47, 8-9, 12-13-14; at most 4 *)
```

The arity is chosen from the second instrument segment. A four-digit year means the calendar layout; a reign token means the regnal layout.

| Example | Kind |
|---|---|
| `uk/ukpga/1996/18` | Act, calendar-numbered (1963 onwards) |
| `uk/uksi/2011/3006` | Statutory Instrument |
| `uk/wsi/2013/2729` | Welsh SI (legislation.gov.uk's canonical series, although it also carries a UK SI number) |
| `uk/ukpga/Eliz2/8-9/69` | Act of the 8 & 9 Eliz. 2 session (1960), chapter 69 |
| `uk/ukpga/Geo3Sess2/47/78` | 47 Geo. 3 Sess. 2 c. 78 (1807) |
| `uk/ukpga/Edw7and1Geo5/10/15` | 10 Edw. 7 & 1 Geo. 5 c. 15 (1910) |
| `uk/ukpga/Geo6/12-13-14/1` | 12, 13 & 14 Geo. 6 c. 1 (1948–49 session) |

Regnal Acts are still cited by title and calendar year in practice ("Law of Property Act 1925"). The title tables resolve these to the regnal coordinate. Their chapter numbers restart every session, so a calendar year plus chapter number is **not** unique before 1963.

### UK provision segments

| Unit (legislation.gov.uk) | Segment | Example coordinate |
|---|---|---|
| `section` | `s{d}` | `…/s124`, `…/s124A` |
| `article` | `art{d}` | `…/art2` |
| `regulation` | `reg{d}` | `…/reg4/1C` |
| `rule` | `rule{d}` | `…/rule3.1/1` (CPR-style dotted numbers) |
| `schedule` | `sch{d}`, or `sch` for a sole unnumbered schedule | `…/sch2/para4`, `…/sch/para10` |
| `paragraph` | `para{d}` | `…/sch1/para2/2/b/i` |
| `part` | `pt{d}` | `…/ptI`, `…/pt2A` |
| `chapter` | `ch{d}` | `…/pt2A/ch1` |
| `group` | `grp{d}` | `…/sch3/grp1/pt2` |
| `appendix` | `app{d}` | `…/sch1/app2/para3` |

Rules for designators and sub-divisions:
- `{d}` is a designator: `124`, `124A`, `1ZA`, `A1`, `I`, `IV`, `2A`, `3.1`. It starts with a digit or a capital.
- **Exception:** schedules and paragraphs may also take a short lower-case designator (`parab`, `schn1`), because older Acts letter them.
- Bare segments after a unit are sub-divisions exactly as the source numbers them: `1`, `1ZA`, `a`, `aa`, `aza`, `i`, `iv`, `iia`.

### Mapping from legislation.gov.uk element ids and URLs

Element ids and URL paths use the same token sequence, with `-` and `/` as the separators respectively:

| Source | Coordinate provision |
|---|---|
| id `section-124-1ZA-a` / URL `…/section/124/1ZA/a` | `s124/1ZA/a` |
| `schedule-1-paragraph-2-2-b-i` | `sch1/para2/2/b/i` |
| `schedule-paragraph-10` | `sch/para10` |
| `part-2A-chapter-1` | `pt2A/ch1` |
| `rule-1.1-1` | `rule1.1/1` |

`grammars/uk.py: provision_from_legislation_tokens` and its inverse `legislation_path` implement this mapping, and round-trip it under a property test.

**Ingest indexes only citable elements.** The following are excluded:

| Excluded | Why |
|---|---|
| Everything inside `<BlockAmendment>` | Text quoted from the Act being amended, which carries generated ids such as `p03055` |
| Cross-heading ids (`…-crossheading-…`) | Not citable |
| Structural wrappers (`…-paragraph-wrapper1`) | Not citable |
| Alternative-version suffixes (`section-7-8n1`, `…-an1`) | The base id is indexed |
| Generated ids (`c00001`, `p00134`, `f00001`) | Not provision ids |
| Malformed source ids (`section-2930.`) | Reported by ingest, not indexed |
| Everything inside `<Versions>` | Alternative texts for other extents (e.g. the N.I. wording of a section whose main text is E+W). The main text is indexed; the count of alternatives is kept on the instrument record for Phase 2 |

On the corpus as scraped on 27 Sept 2026, 2,005,209 ids map. The 32,133 that don't all fall into the excluded kinds above.

### Case collisions (open: roadmap Q-M1-1)

In 5 of 33,788 instruments, siblings differ only by case. Examples:
- paragraphs `(a)` and `(A)` under one parent (`uk/uksi/1990/2145/sch1/para34/a` and `…/A`);
- `schSECOND` / `schSecond` in `ukpga/1950/39`.

The plan says the index build fails on any casefold collision, so a decision is needed before M6.

## 3. Spain (`es`) — Stage C

Reserved: `es/boe/{year}/{number}/art{N}/{apartado}/{letra}`, keyed on the BOE identifier (`BOE-A-1885-6627` → `es/boe/1885/6627/art42/1/b`). Disposiciones are `da3`, `dt1`, `dd1`, `df2`. This section is specified and tested in Stage C.

---

## 4. UK citation surface forms

Status keys:
- **B** = `ROUTE_BOUNDED`
- **A** = `ROUTE_AMBIGUOUS`
- **I** = `EPISTEMIC_ABSTENTION_INSTRUMENT_NOT_FOUND`
- **P** = `EPISTEMIC_ABSTENTION_PROVISION_NOT_FOUND`
- **O** = `ROUTE_OUT_OF_COVERAGE`
- **U** = `ROUTE_UNRESOLVED`

Every form is matched case-insensitively after normalisation (§6, R-rows).

### 4.1 Provision markers

| ID | Written form | Produces | Notes |
|---|---|---|---|
| UK-P-01 | `s.124`, `s 124`, `s124`, `S.124` | `s124` | |
| UK-P-02 | `section 124`, `sec. 124`, `sect. 124`, `§124`, `§ 124` | `s124` | |
| UK-P-03 | `s.124(1ZA)(a)`, `section 124(1ZA)(a)`, `s124(1ZA)(a)(ii)` | `s124/1ZA/a[/ii]` | |
| UK-P-04 | `subsection (2) of section 124`, `s.124 subsection (2)` | `s124/2` | |
| UK-P-05 | `ss.124–126`, `ss 124-126`, `sections 124 to 126` | `s124`, `s125`, `s126` | **B** only if every endpoint exists and the range spans ≤ 20; otherwise **A** |
| UK-P-06 | `sections 94, 95 and 98`, `ss. 94 & 98` | one coordinate per item | |
| UK-P-07 | `s.98 et seq.`, `section 98 onwards` | — | **A**: an open range |
| UK-P-08 | `Sch. 2 para 4`, `Schedule 2, paragraph 4`, `para 4 of Schedule 2`, `Sch 2 para 4(1)(b)` | `sch2/para4[/1/b]` | |
| UK-P-09 | `the Schedule, para 3`, `Sch. para 3` | `sch/para3` | Sole unnumbered schedule |
| UK-P-10 | `reg. 3`, `regulation 3(1)`, `reg 3(1)(a)` | `reg3[/1/a]` | |
| UK-P-11 | `art. 2`, `article 2(1)` | `art2[/1]` | |
| UK-P-12 | `r. 3.1`, `rule 3.1(2)` | `rule3.1[/2]` | |
| UK-P-13 | `Part 4A`, `Part X`, `Pt 2`, `Part II` | the part's section list | Arabic and Roman are both tried against the index (`Part 2` ↔ `ptII`). A part binds to its list of sections (ingest records the part → sections map) |
| UK-P-14 | `Part 2, Chapter 1`, `Pt 2 Ch 1` | `pt2/ch1` | |
| UK-P-15 | Mixed-up provision words: `article 124` of an Act; `section 2` of an SI | Act: `art`→`s`. SI: `s`→`art`/`reg`/`rule` (whichever exists) | The number is never changed |
| UK-P-16 | Provision-word typos: `secton 124`, `sectoin`, `artcle`, `regualtion` | as UK-P-02 / 10 / 11 | Fixed variant list, not the fuzzy tier |
| UK-P-17 | A four-digit number after a provision word: `section 1996` | `s1996` | Always a provision number, never a year |

### 4.2 Instrument forms

| ID | Written form | Resolves to | Notes |
|---|---|---|---|
| UK-I-01 | `Employment Rights Act 1996` | the Act | Exact title + year |
| UK-I-02 | `employment rights act 1996`, `EMPLOYMENT RIGHTS ACT 1996` | the Act | Lower case and ALL CAPS follow the lower-case rules |
| UK-I-03 | `the 1996 Employment Rights Act` | the Act | Year first |
| UK-I-04 | `Employment Rights Act of 1996`, `Employment Rights Act (1996)` | the Act | |
| UK-I-05 | `ERA 1996`, `ERA 96`, `ERA '96`, `CA 2006` | the Act | Alias table (`aliases/uk.toml`) |
| UK-I-06 | `employment rights 1996` | the Act | No type word: **B** if the key fits one instrument, else **A**. Never **I** |
| UK-I-07 | `Employment Rights Act` | the Act if unique, else **A** | No year. `Finance Act` → **A** |
| UK-I-08 | `1996 c. 18`, `1996 c 18`, `c. 18 of 1996` | `uk/ukpga/1996/18` | Chapter citation. A bare `c.18` → **A** |
| UK-I-09 | `SI 2011/3006`, `S.I. 2011/3006`, `S.I. 2011 No. 3006`, `SI 2011 No 3006`, `2011 No. 3006` | `uk/uksi/2011/3006` (or `wsi`/`nisi` if that is canonical) | Official number |
| UK-I-10 | `8 & 9 Eliz. 2 c. 69`, `47 Geo. 3 Sess. 2 c. 78`, `10 Edw. 7 & 1 Geo. 5 c. 15` | the regnal coordinate | Regnal citation |
| UK-I-11 | `the 1996 Act` | — | **A** across every indexed Act of 1996 |
| UK-I-12 | `the Act`, `that Act`, `the Regulations` | context instrument | With `context`: bound, `source="context"`. Without it: **A** |
| UK-I-13 | `The Employment Rights (Increase of Limits) Order 2011` | the SI | A leading `The` is optional. `(Amendment)`, `(No. 2)`, `(Commencement No. 3)` are distinguishing words and are never dropped |
| UK-I-14 | Several SIs sharing a title and year | — | **A**, asking for the SI number |
| UK-I-15 | Title + year where no such instrument exists: `Marchwood Commercial Arbitration Order 2022`, `Employment Rights Act 1995` | — | **I**, with suggestions (typo tiers, plan departure 7) |
| UK-I-16 | A real title with a small typo: `Employment Rihgts Act 1996` | the Act | **B** with `corrections=[("rihgts","rights")]` |
| UK-I-17 | A bigger typo: `Emplyment Rihgts Act 1996` | — | **A**: "did you mean …?" |
| UK-I-18 | Reordered title: `Rights of Employment Act 1996` | the Act | **B** with the reordering recorded, if exactly one real title has that word set |
| UK-I-19 | Capitalised invented words in front of a real title: `Marchwood Commercial Arbitration Act 1996` | — | **I**, suggesting "Arbitration Act 1996" |
| UK-I-20 | The same in lower case: `marchwood commercial arbitration act 1996` | — | **A**: "Did you mean the Arbitration Act 1996?" |

### 4.3 Structured identifiers (read first, never typo-corrected)

| ID | Written form | Produces |
|---|---|---|
| UK-X-01 | Canonical coordinate `uk/ukpga/1996/18/s124/1ZA/a` (any case) | itself (canonical case from the index) |
| UK-X-02 | `instrument_id` `uk_ukpga_1996_18` | `uk/ukpga/1996/18` |
| UK-X-03 | legislation.gov.uk URL: `https://www.legislation.gov.uk/ukpga/1996/18/section/124`, also `/id/…`, `/contents`, `/enacted`, `/made`, `/data.xml`, `/{yyyy-mm-dd}`, `http:`, no scheme | the mapped coordinate |
| UK-X-04 | An identifier followed by a provision word: `uk/ukpga/1996/18 section 124` | `…/s124` |
| UK-X-05 | A partial path: `uk/ukpga/1996` | not a citation; falls through to the grammars |

Outcomes:
- The identifier exists → **B**.
- The instrument is missing → **I**.
- The provision is missing → **P**.
- An injection-shaped identifier (`uk/ukpga/1996/18' or '1'=='1`) fails the grammar and never reaches the filter.

### 4.4 Out of coverage

| ID | Cue | Result |
|---|---|---|
| UK-O-01 | A title found in the other-series listing: devolved Acts and SIs (`asp`, `anaw`, `asc`, `nia`, `ssi`, `wsi`, `nisr`, `nisi`), local Acts (`ukla`), Church measures (`ukcm`), pre-1801 and old series (`apgb`, `aep`, `aosp`, `aip`, `apni`, `mnia`, `mwa`), `uksro`/`nisro` | **O** |
| UK-O-02 | Retained EU law: `UK GDPR`, `Article 82 UK GDPR`, `Regulation (EU) 2016/679` | **O** |
| UK-O-03 | Bills: `Employment Rights Bill` | **O** |
| UK-O-04 | Case citations: `[2020] UKSC 1`, `[2019] EWCA Civ 123` | **O** |
| UK-O-05 | Foreign-law cues: `Code civil`, `BGB §`, `U.S.C.`, `C.F.R.` | **O** |
| UK-O-06 | Spanish citations before Stage C: `art. 42 CdC`, `Ley 58/2003` | **O** (jurisdiction not loaded) |

`live_checkable` and `next_action` for these follow the contract (`docs/contract.md`, M9).

## 5. Unsupported forms (documented; never bound)

| ID | Form | Result |
|---|---|---|
| UK-U-01 | Concept-only queries: "the unfair dismissal law" | **U** (discover-then-bind) |
| UK-U-02 | Relative references: "subsection (2) above" | **U** |
| UK-U-03 | Pinpoints to recitals, preambles, explanatory notes | **U** |
| UK-U-04 | Popular names not in the alias table: "the Bribery law" | **U** |

## 6. Case catalogue

| ID | Case | Expected |
|---|---|---|
| UK-C-01 | Snapshot on every refusal | `index_snapshot` is always set |
| UK-C-02 | A repealed instrument | **B** with `repealed=True`, never refused |
| UK-C-03 | Follow-up with context: "what about section 125?" + `context=[uk/ukpga/1996/18/s124]` | **B** `…/s125`, `source="context"` |
| UK-C-04 | An instrument named in the query beats context | Bound to the named instrument |
| UK-C-05 | Context coordinates are re-validated against the index | An invalid context coordinate is ignored |
| UK-C-06 | Negation: "s.124, not the Companies Act one, the ERA" | **B** ERA s.124. The negated instrument is never in the filter |
| UK-C-07 | Unclear negation scope | **A** |
| UK-C-19 | Provision-level exclusion: "In the ERA 1996, what applies across all sections except section 124?" | **B** to `uk/ukpga/1996/18` with `excluded=[…/s124]`. The filter removes s.124 and its subtree (decision 15) |
| UK-C-20 | A provision with no connector, when the query names exactly one (non-negated) instrument: "In the Employment Rights Act 1996, what does section 124 cover?" | Linked to that instrument (decision 15). With two or more instruments: **A** |
| UK-C-21 | A citation resolving to a coordinate the source publishes twice (`duplicated_provisions`) | **A**: "which Part?" (decision 13) |
| UK-C-22 | One covered and one out-of-coverage citation: "ERA 1996 s.124 and Article 82 UK GDPR" | **O**, with both citations listed (decision 14) |
| UK-C-08 | Time qualifiers: "as it stood in 2012", "original version", "as enacted" | Raw `temporal_hint`; never read as the instrument year |
| UK-C-09 | Several citations in one query | **B** with every coordinate |
| UK-C-10 | Several citations where one abstains | The whole query abstains |
| UK-C-11 | A bare provision with no instrument or context: `section 124` | **A** over the salient instruments that contain it |
| UK-C-12 | Numbers that aren't citations: `£124`, `124 employees`, `1 April 1996` | No binding. A number binds only after a provision word or inside an identifier |
| UK-C-13 | Unicode: NBSP, en/em dashes, curly quotes, full-width characters | NFKC-normalised |
| UK-C-14 | Look-alike letters (Cyrillic `а` in "Act") | Mapped to a fixed skeleton before title lookup |
| UK-C-15 | ALL CAPS | Lower-case rules (UK-I-02) |
| UK-C-16 | Over-long query (> 4 KB) | **U**, flagged |
| UK-C-17 | `jurisdictions=["uk"]` scoping | Only UK candidates |
| UK-C-18 | A provision cited in a PDF-only instrument (`structure: metadata_only`): "art. 3 of the Sugar Beet (Research and Education) Order 1981" | **O**, reason "provision structure not available", `next_action` `VERIFY_LIVE`. Citing the instrument itself binds (**B**) |

### Robustness (normalisation)

| ID | Rule |
|---|---|
| UK-R-01 | NFKC, then casefold |
| UK-R-02 | `§`, `s.`, `sec.`, `sect.`, `section` canonicalised; `art.`, `reg.`, `r.`, `para.`, `Sch.`, `Pt` likewise |
| UK-R-03 | Dashes (`–`, `—`, `‐`) → `-`; curly quotes → straight |
| UK-R-04 | Every token keeps its character offsets into the original query |
