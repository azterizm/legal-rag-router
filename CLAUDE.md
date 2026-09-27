# Working rules for this repository

- **Progress and decisions live in `docs/ROADMAP.md`** (§S Status, §U UK-first, §4 Decisions).
  Read §S first; update it at every stop. Never keep progress in assistant memory.
- The build follows the Phase 1 plan (`~/.claude/plans/we-are-built-phase-moonlit-honey.md`)
  and the vault specs it cites. **Halt and ask** before any change to the public API, statuses,
  coordinate or index format, or battery methodology beyond what the plan specifies, and at every
  ⛔ halt point in the roadmap.
- Git: local commits only, one per milestone. Never create a remote, push, tag a release,
  publish to PyPI, make paid API calls or edit the vault without an explicit go.
- Order: UK first (Stages A–B), Spanish law only after UK is complete (Stage C).
- `uk_scrap_data/` is externally scraped raw data: read-only, git-ignored, never published.
  Read an instrument's identity from the file's own `IdURI`, never from its path (roadmap U2).
- Checks: `uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest`.
  The wheel has zero runtime dependencies; stdlib only under `src/`.
