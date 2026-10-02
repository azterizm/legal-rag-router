# Contributing

Thank you for helping. Bug reports, citation forms the router misreads, and fixes are all
welcome.

## Reporting a misread citation

Open an issue with the query, what the router returned (`status`, `coordinates`, `reason`),
what you expected, and the index snapshot (`result.index_snapshot`). A citation copied from a
real document is the most useful kind. Security issues go by email, never as an issue: see
[SECURITY.md](SECURITY.md).

## Making a change

```bash
uv sync
uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest
```

All four must pass. The rules the checks enforce, and a few they can't:

- **No runtime dependencies.** Code under `src/` uses the standard library only.
- **100 % test coverage** of `src/`, branches included, and `mypy --strict`.
- **Grammar first.** A new citation form gets a row in [`docs/grammar.md`](docs/grammar.md),
  with a stable ID, and a test that cites it.
- **Sealed batteries and results never change.** Files covered by a seal in `seals/` are
  fixed. A correction is a new seal and a new run, published beside the old one.
- **No corpus data in the repository.** The index is built locally and published as a release
  asset; the scraped source data is never committed.
- **Public API changes are discussed first.** The stable surface is
  `legal_rag_router.__all__`, the statuses, the coordinate format and the index format.

Commits follow [Conventional Commits](https://www.conventionalcommits.org/) (`fix(router): …`,
`docs(readme): …`).

## Licence of contributions

The project is licensed under AGPL-3.0-only. By submitting a contribution you agree that it is
licensed under the same terms.
