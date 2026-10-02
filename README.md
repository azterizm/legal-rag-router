# legal-rag-router

**Deterministic citation routing and epistemic abstention for legal RAG.**

[![CI](https://github.com/azterizm/legal-rag-router/actions/workflows/ci.yml/badge.svg)](https://github.com/azterizm/legal-rag-router/actions/workflows/ci.yml)
[![Python 3.11–3.14](https://img.shields.io/badge/python-3.11%E2%80%933.14-blue)](https://github.com/azterizm/legal-rag-router/blob/main/pyproject.toml)
[![Licence: AGPL-3.0-only](https://img.shields.io/badge/licence-AGPL--3.0--only-blue)](https://github.com/azterizm/legal-rag-router/blob/main/LICENSE)
![Runtime dependencies: none](https://img.shields.io/badge/runtime%20dependencies-none-brightgreen)

`legal-rag-router` sits in front of any vector search. It reads the legal citation in a user's
query, checks it against an index of the statute book, and returns exactly one decision: the
coordinate to retrieve from, a question for the user, or a refusal because the cited law does
not exist. It uses no model and no network, reads no disk per query, and gives the same answer
to the same input every time.

```text
"What is the cap in section 124 of the Employment Rights Act 1996?"
  → ROUTE_BOUNDED  uk/ukpga/1996/18/s124                     retrieve only from here

"section 3 of the Digital Privacy Rights Act 2021"
  → EPISTEMIC_ABSTENTION_INSTRUMENT_NOT_FOUND                 refuse: no such Act
```

*Built by [Abdullah Memon](https://memonsystems.com) at [Memon Systems Ltd](https://memonsystems.com).
Need it in your stack? See [Consultancy](#consultancy).*

## Contents

- [Why](#why) · [What it covers](#what-it-covers) · [Install](#install) · [Quick start](#quick-start)
- [Using it as a library](#using-it-as-a-library): [statuses](#the-six-statuses) ·
  [retrieval](#retrieval-the-partition-filter) · [discovery](#queries-that-cite-nothing-discover-then-bind) ·
  [follow-ups](#follow-ups-context) · [scope](#scope-jurisdictions) · [logging](#logging-and-privacy) ·
  [errors](#errors-and-failure-behaviour)
- [Evidence](#evidence) · [Documentation](#documentation) · [Development](#development) ·
  [Roadmap](#roadmap) · [Consultancy](#consultancy) · [Citing](#citing) · [Licence](#licence-and-attribution)

## Why

A RAG system asked about "section 124 of the Employment Rights Act 1996" should retrieve from
section 124, not from whatever text embeds closest to the question. Asked about an Act that
does not exist, it should say so, not answer from the nearest real one. Vector search can do
neither: it always returns something.

The router decides first, from the citation, and the rest of the pipeline obeys:

- **A real citation** binds to its coordinate, and retrieval is filtered to it.
- **An ambiguous one** ("the Companies Act") becomes a question, never a silent guess.
- **Invented law** is refused, with the index date it was checked against.
- **A query that cites nothing** is handed to discovery, which offers provisions for the user to
  confirm. Nothing reaches generation except through a bound coordinate.

## What it covers

| | |
|---|---|
| **Jurisdiction** | United Kingdom. Spain (BOE) is next ([roadmap](#roadmap)) |
| **Bound to provision level** | UK Public General Acts (`ukpga`, including regnal Acts before 1963) and UK Statutory Instruments (`uksi`): 134,219 instruments |
| **Recognised, reported out of coverage** | Scottish, Welsh and Northern Ireland legislation, local Acts, Church Measures, older series (244,564 titles), and EU or retained EU law |
| **Index snapshot** | 28 September 2026. "Not found" always means "not in the statute book as of that date", and every refusal says so |
| **Citation forms** | Full and short titles, abbreviations (ERA 1996, PACE), chapter numbers (1996 c. 18), SI numbers (SI 2010/1904), pinpoints down to paragraph, lists, ranges, exclusions, typos. Every form is in [`docs/grammar.md`](https://github.com/azterizm/legal-rag-router/blob/main/docs/grammar.md) |

The index holds coordinates, titles, numbers and lookup tables. It holds no provision text:
your retrieval store keeps the text.

## Install

```bash
pip install legal-rag-router        # or: uv add legal-rag-router
```

Python 3.11 or later. The package has no runtime dependencies.

The wheel ships code only. The index (and, optionally, the concept index used for discovery) is
a separate download, attached to each [GitHub release](https://github.com/azterizm/legal-rag-router/releases)
with a `SHA256SUMS` file. Fetch, verify and unpack it with the [GitHub CLI](https://cli.github.com/):

```bash
gh release download v0.1.0 -R azterizm/legal-rag-router -p 'index-*.tar.gz' -p 'SHA256SUMS' -D dist
(cd dist && sha256sum -c --ignore-missing SHA256SUMS) && mkdir -p data/index && tar -xzf dist/index-*.tar.gz -C data/index
```

On macOS use `shasum -a 256 -c` in place of `sha256sum -c`. For discovery, fetch
`concepts-*.tar.gz` the same way into `data/concepts`. Sizes unpacked: about 360 MB for the
index and 550 MB for the concept index.

The router checks every file against the SHA-256 hashes in the index manifest when it loads,
so a damaged or altered index fails at load time, never at query time.

## Quick start

```python
from legal_rag_router import Router, RouteStatus, partition_filter

router = Router.from_path("data/index")  # loads and verifies in well under a second

result = router.route("What is the cap in section 124 of the Employment Rights Act 1996?")
result.status  # RouteStatus.BOUNDED
result.coordinates  # (Coordinate('uk/ukpga/1996/18/s124'),)
partition_filter(result)
# 'instrument_id in ["uk_ukpga_1996_18"] and ((coordinate == "uk/ukpga/1996/18/s124"
#   or coordinate like "uk/ukpga/1996/18/s124/%"))'
```

Load the router once and share it: it is immutable and thread-safe.

## Using it as a library

### The six statuses

Every call returns one `RouteResult`. Its `status` says what the router found, and its
`next_action` says what your pipeline must do next. The outputs below are real, from the
28 September 2026 index.

| Query | `status` | `next_action` | What you get |
|---|---|---|---|
| `s. 124 ERA 1996` | `ROUTE_BOUNDED` | `RETRIEVE_BOUNDED` | `coordinates`: `uk/ukpga/1996/18/s124` |
| `section 1 of the Companies Act` | `ROUTE_AMBIGUOUS` | `ASK_USER` | `candidates` (Companies Act 1976, 1985, 1989, 2006 …) and a ready-made `clarification` question |
| `section 3 of the Digital Privacy Rights Act 2021` | `EPISTEMIC_ABSTENTION_INSTRUMENT_NOT_FOUND` | `REFUSE` | `messages`: "No instrument “Digital Privacy Rights Act 2021” is in the UK statute book as of the index snapshot 2026-09-28." |
| `section 999 of the Employment Rights Act 1996` | `EPISTEMIC_ABSTENTION_PROVISION_NOT_FOUND` | `REFUSE` | `messages`: "Employment Rights Act 1996 has no s.999 (index snapshot 2026-09-28)." |
| `Article 6 of the GDPR` | `ROUTE_OUT_OF_COVERAGE` | `DECLARE_OUT_OF_COVERAGE` | `messages`: "“GDPR” is EU or retained EU law: outside the indexed corpus." |
| `unfair dismissal compensatory award statutory cap` | `ROUTE_UNRESOLVED` | `DISCOVER_THEN_BIND` | No citation found: see [discovery](#queries-that-cite-nothing-discover-then-bind) |

A typical integration handles `next_action`, which is a closed set:

```python
from legal_rag_router import NextAction, Router, partition_filter

router = Router.from_path("data/index", concepts="data/concepts")


def answer(query: str) -> str:
    result = router.route(query)
    match result.next_action:
        case NextAction.RETRIEVE_BOUNDED:
            chunks = vector_store.search(query, filter=partition_filter(result))
            return generate(query, chunks)  # your retrieval and LLM
        case NextAction.ASK_USER:
            return result.clarification  # offer result.candidates
        case NextAction.REFUSE | NextAction.DECLARE_OUT_OF_COVERAGE:
            return " ".join(result.messages)  # never retry with open retrieval
        case NextAction.DISCOVER_THEN_BIND:
            found = router.discover(query)
            return offer_for_confirmation(found.candidates)
        case NextAction.VERIFY_LIVE:
            return ask_official_registry(result)  # not returned in 0.1.0 (strict mode)
```

`vector_store`, `generate`, `offer_for_confirmation` and `ask_official_registry` are yours. The
rules each branch must keep ("never widen the filter", "never pick a candidate silently",
"never answer from other law") are in the [downstream contract](https://github.com/azterizm/legal-rag-router/blob/main/docs/contract.md).

Other fields worth knowing (all on `RouteResult`):

| Field | Use |
|---|---|
| `corrections` | Typos the router fixed when it bound: `section 12 of the Employmnet Rights Act 1996` binds `s12` with `(('employmnet', 'employment'),)` |
| `suggestions` | Close real titles offered with a refusal |
| `excluded` | Provisions the query excludes: `the Companies Act 2006 except section 172` binds the Act and excludes `s172` |
| `citations` | Every citation found, with its character span and how it resolved |
| `repealed` | The bound instrument is repealed. It is still bound, never refused |
| `temporal_hint` | Text such as "as it stood in 2012", passed through for a point-in-time layer |
| `index_snapshot`, `latency_ns`, `reason` | The index date, the time taken, and a machine-readable detail for non-bound outcomes |

### Retrieval: the partition filter

`partition_filter(result)` turns a bound result into a boolean filter over two fields every
stored chunk must carry: `instrument_id` (`uk_ukpga_1996_18`) and `coordinate`
(`uk/ukpga/1996/18/s124/1`). It includes every sub-provision of what was bound, removes anything
excluded, and raises `FilterError` for any status other than `ROUTE_BOUNDED`, so there is never
an unbounded filter to fall back to. Values are validated against the coordinate grammar before
they are interpolated, so nothing from the query can inject into the expression.

The expression is written in Milvus's boolean-expression syntax (`in [...]`, `==`, `like`,
`and`/`or`/`not`). For other stores, build the same filter from `result.coordinates` and
`result.excluded`.

### Queries that cite nothing: discover, then bind

Most research questions cite no statute. They route `ROUTE_UNRESOLVED`, and `Router.discover`
offers candidate provisions from the concept index for the user to confirm. The confirmed
coordinate is then routed like any citation:

```python
router = Router.from_path("data/index", concepts="data/concepts")
found = router.discover("unfair dismissal compensatory award statutory cap", limit=3)
[c.label for c in found.candidates]
# ['Employment Rights Act 1996, s. 124: Limit of compensatory award etc.',
#  'Enterprise and Regulatory Reform Act 2013, s. 15: Power by order to increase or decrease limit of compensatory award',
#  'Employment Rights Act 1996, s. 227: Maximum amount.']

router.route(str(found.candidates[0].coordinate))  # only after the user confirms it
```

Discovery never returns text and never binds. On the sealed UK test set it puts the right
provision in the top 10 for 88 % of queries ([report](https://github.com/azterizm/legal-rag-router/blob/main/reports/discovery-uk.md)).

### Follow-ups: context

Pass the previous turn's bound coordinates, and a bare provision binds against them:

```python
router.route("what about section 125?", context=["uk/ukpga/1996/18/s124"])
# ROUTE_BOUNDED uk/ukpga/1996/18/s125, source="context"
```

Context coordinates are re-validated against the index, and an instrument named in the query
always beats context.

### Scope: jurisdictions

`router.route(query, jurisdictions=["uk"])` limits routing to the listed jurisdictions. A scope
that excludes every indexed jurisdiction returns `ROUTE_UNRESOLVED` with
`reason="no_jurisdiction_in_scope"`.

### Logging and privacy

The router never logs query text by default. With `Router(index, log_misses=True)` (or
`Router.from_path(path, log_misses=True)`), a query that looks like a citation but routes
`ROUTE_UNRESOLVED` emits one event on the `legal_rag_router.misses` logger, carrying only a hash
and the length. Pass `redact=` a function to log a redacted form of the text instead. Nothing
is sent anywhere: the package makes no network calls.

### Errors and failure behaviour

- `route` and `discover` never raise for any input. Non-strings, queries over 4 KB and queries
  too complex to read safely return `ROUTE_UNRESOLVED` with a `reason`.
- An internal error is logged and fails safe to `ROUTE_UNRESOLVED`. It never falls back to a
  guess.
- Loading raises `IndexLoadError` (or `ConceptIndexError`) when a file doesn't match its hash
  or the format version is unknown.

The public API is everything in `legal_rag_router.__all__`; it is typed (`py.typed`) and
documented in docstrings.

## Evidence

Every figure below comes from a sealed run: the test batteries were hashed and tagged before
the router was run on them once, and the results were hashed after. The seals are in
[`seals/`](https://github.com/azterizm/legal-rag-router/tree/main/seals).

**Accuracy** (2,112 labelled queries, 1,030 of them real citations taken from legislation and
held out from development; [report](https://github.com/azterizm/legal-rag-router/blob/main/reports/sealed-run-uk.md)):

| Measure | Result |
|---|---|
| Bound to the wrong instrument | **0 / 1,897** real citations (v1, blind: also 0 / 1,897) |
| Invented law bound | **0 / 68** (all 68 refused) |
| Same section number in different Acts, bound to the wrong Act | **0 / 40** |
| Real law refused | 82 / 1,897 (4.3 %) |
| Rows with the expected outcome | 1,916 / 2,112 (v1, blind: 1,903 / 2,112) |

**Speed** (306,336 calls per pass, 3 passes;
[measurements](https://github.com/azterizm/legal-rag-router/blob/main/docs/measurements.md)):

| Machine | p50 | p99 |
|---|---|---|
| Apple M4 | 0.14 ms | 2.10 ms |
| Intel i5-3570 (2012) | 0.50 ms | 9.21 ms |

The design target was a p99 under 2 ms. It is not met on either machine, and the report says
why.

**Against LLMs** ([report](https://github.com/azterizm/legal-rag-router/blob/main/reports/comparison-uk.md)):
on the same 2,112 queries, Gemini 3.8 Flash (high) routing on its own bound the wrong
instrument for 102 / 1,897 real citations, changed its answer between repeats on 34 / 200
rows, and took 13.5 s at p50. Used as a citation parser in front of the router's index, it was
the most accurate pipeline measured (1,972 / 2,112) with no wrong or invented bindings. The
report also covers Jev and Laya, cost per query, and what leaves your network.

## Documentation

| Document | What it covers |
|---|---|
| [Downstream contract](https://github.com/azterizm/legal-rag-router/blob/main/docs/contract.md) | What each status obliges the caller to do; the filter; discovery; context; failure behaviour |
| [Grammar](https://github.com/azterizm/legal-rag-router/blob/main/docs/grammar.md) | The coordinate format and every citation form the router reads, with test IDs |
| [Data sources](https://github.com/azterizm/legal-rag-router/blob/main/docs/sources.md) | Where the index comes from, its licence, and what is known to be missing |
| [All documentation](https://github.com/azterizm/legal-rag-router/blob/main/docs/README.md) | The full map: design, methodology, measurements and reports |

## Development

```bash
git clone https://github.com/azterizm/legal-rag-router && cd legal-rag-router
uv sync
uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest
```

The tests need no index download: they run on a small real-data fixture index committed under
`tests/fixtures/`. Tests marked `full_data` run only where the full index is present. See [CONTRIBUTING](https://github.com/azterizm/legal-rag-router/blob/main/CONTRIBUTING.md).

## Roadmap

`0.1.0` is the first release: the United Kingdom, routing and discovery. Planned:

- **Point-in-time phrasing (next release).** 0.1.0 passes "as it stood on 1 April 2012",
  "as in force on …", "as enacted" and "original version" through as `temporal_hint`, but not
  "as at 1 January 2012" or "as of 1 January 2012": those queries still bind, with no hint. The
  next release reads them too. Resolving a date to the version in force stays with your
  point-in-time layer.
- **Spain** (BOE): `es/boe/{year}/{number}/{provision…}`, e.g. `es/boe/1885/6627/art42/1/b`.
- **More domains** through grammar plugins that share the index, the abstention gate and the
  typo tiers: `eu/{reg|dir|dec|judgment}/{year}/{number}`, `us/usc/{title}/{section}`,
  `us/cfr/{title}/{part}/{section}`, `contract/edgar/{cik}/{accession}/{exhibit}`.
- **Live checks** against official registries (the `VERIFY_LIVE` action), for law newer than the
  index snapshot.

The build record, with every decision, is [`docs/ROADMAP.md`](https://github.com/azterizm/legal-rag-router/blob/main/docs/ROADMAP.md).

## Consultancy

`legal-rag-router` is built and maintained by **Abdullah Memon** at
**[Memon Systems Ltd](https://memonsystems.com)**, which designs and audits retrieval systems for
legal and other regulated domains. If you want help putting it into production, adding a
jurisdiction or document type, or testing whether your own legal RAG binds, refuses and isolates
as it should, see [engagements](https://memonsystems.com/engagements) or write to
abdullah@memonsystems.com.

Bug reports and questions about the library are welcome as
[GitHub issues](https://github.com/azterizm/legal-rag-router/issues). Security reports go by
email: see [SECURITY.md](https://github.com/azterizm/legal-rag-router/blob/main/SECURITY.md).

## Citing

If you use the router or its benchmark in research, please cite it. GitHub's "Cite this
repository" button gives the reference from
[`CITATION.cff`](https://github.com/azterizm/legal-rag-router/blob/main/CITATION.cff).

## Licence and attribution

Code: [AGPL-3.0-only](https://github.com/azterizm/legal-rag-router/blob/main/LICENSE), copyright
© 2026 Memon Systems Ltd. If you run a modified version as a network service, the AGPL requires
you to offer its source to that service's users.

Index data is derived from legislation.gov.uk and contains public sector information licensed
under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
Source: legislation.gov.uk, © Crown and database right. The full attribution is in
[`NOTICE`](https://github.com/azterizm/legal-rag-router/blob/main/NOTICE), shipped with every index
release.

`legal-rag-router` is a retrieval component, not legal advice.
