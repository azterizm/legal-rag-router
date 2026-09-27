# legal-rag-router

Deterministic coordinate pre-routing and epistemic abstention for legal RAG.

`legal-rag-router` sits in front of any vector search. It reads the legal citation in a query
and returns exactly one decision:

| Status | Meaning |
|---|---|
| `ROUTE_BOUNDED` | The citation resolved to a real coordinate, e.g. `uk/ukpga/1996/18/s124` |
| `ROUTE_AMBIGUOUS` | The citation fits more than one instrument; candidates and a clarifying question are returned |
| `EPISTEMIC_ABSTENTION_INSTRUMENT_NOT_FOUND` | The cited instrument is not in the statute book (as of the index snapshot) |
| `EPISTEMIC_ABSTENTION_PROVISION_NOT_FOUND` | The instrument is real but the provision is not |
| `ROUTE_OUT_OF_COVERAGE` | The citation was recognised but belongs to a series or jurisdiction not indexed |
| `ROUTE_UNRESOLVED` | No citation found. The caller discovers candidate coordinates and binds one; it never generates from open retrieval |

The routing path uses no model, no network and no disk I/O per query. The same input always
gives the same output.

> **Status:** under active development towards `0.1.0`. See [`docs/ROADMAP.md`](docs/ROADMAP.md).

## Coordinates

A coordinate names one legal unit:

```
uk/{series}/{year}/{number}/{provision…}        uk/ukpga/1996/18/s124/1ZA/a
uk/{series}/{regnal}/{session}/{number}/{…}     uk/ukpga/Eliz2/8-9/69/s1   (Acts before 1963)
es/boe/{year}/{number}/{provision…}             es/boe/1885/6627/art42/1/b
```

The full grammar and every accepted citation form are in [`docs/grammar.md`](docs/grammar.md).

### Extension slots

Later domains add a grammar plugin and share the index, the abstention gate and the typo tiers:
`eu/{reg|dir|dec|judgment}/{year}/{number}`, `us/usc/{title}/{section}`,
`us/cfr/{title}/{part}/{section}`, `contract/edgar/{cik}/{accession}/{exhibit}`.

## Development

```bash
uv sync
uv run ruff check && uv run ruff format --check
uv run mypy
uv run pytest
```

## Licence

Code: [AGPL-3.0-only](LICENSE). Index data is derived from official sources under their own
licences (legislation.gov.uk: Open Government Licence v3.0); see `NOTICE` in each index release.
