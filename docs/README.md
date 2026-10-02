# Documentation

Start with the [project README](../README.md): install, the index download and the library
guide. This page maps everything else.

## Using the router

| Document | What it covers |
|---|---|
| [`contract.md`](contract.md) | The downstream contract: what each status obliges the caller to do, the partition filter, live checks (strict and confirm mode), discover-then-bind, follow-ups, failure behaviour |
| [`grammar.md`](grammar.md) | The coordinate format and every citation form the router reads or refuses to read, each with a stable test ID. The source of truth for the router's tests |
| [`sources.md`](sources.md) | Where the index data comes from, its licence and fair-use terms, how it was built, and what is known to be missing |

## How it was built and tested

| Document | What it covers |
|---|---|
| [`batteries.md`](batteries.md) | The labelled test batteries (2,112 UK queries), how each row was made, how they are scored, and how they were sealed |
| [`discovery.md`](discovery.md) | Concept discovery for queries that cite nothing: the evidence, the concept battery, the concept index and `discover()` |
| [`measurements.md`](measurements.md) | Build, load and latency measurements, each dated, with the machine and conditions disclosed |

## Results

Every result was produced once against sealed batteries. The seals (`../seals/`) hold the
SHA-256 of each battery and result file:

```bash
# the current battery seal, against the batteries and the full index in data/index
uv run python -m eval.seal verify seals/battery-2026-09-29-v2.json
# a results seal, against the committed result files
uv run python -c "from pathlib import Path; from eval.seal import verify_results_seal as v; \
  v(Path('seals/results-compare-2026-10-01.json'), Path('.')); print('OK')"
```

The v1 battery seal and the concept seal pin index files that the v2 fixes rebuilt, so they
verify only at their own commits (tags `battery-seal-2026-09-29` and `concept-seal-2026-09-29`).

| Report | What it covers |
|---|---|
| [`../reports/sealed-run-uk.md`](../reports/sealed-run-uk.md) | The sealed UK runs (v1 blind, v2 after fixes): accuracy against the plan's targets, and latency |
| [`../reports/comparison-uk.md`](../reports/comparison-uk.md) | The router against Gemini 3.8 Flash (high), Jev and Laya: accuracy, determinism, cost, latency, data leaving the network, and how to reproduce it |
| [`../reports/discovery-uk.md`](../reports/discovery-uk.md) | The sealed test run of concept discovery |
| [`../reports/coverage-sweep-uk.md`](../reports/coverage-sweep-uk.md) | 100,000 real citations from the statute book, routed, with the shapes the router misses ([Stage A version](../reports/coverage-sweep-uk-stageA.md)) |

The raw outputs sit beside them: `../results/` (sealed runs and the comparison) and
`../bench/results/` (latency, Row B and Laya measurements).

## Project record

| Document | What it covers |
|---|---|
| [`ROADMAP.md`](ROADMAP.md) | The Phase 1 build: status and stop log, milestones, halt points and every decision taken |
| [`vault-proposals-discovery.md`](vault-proposals-discovery.md) | Proposed changes to the architecture documents that the discovery work implies (not yet applied) |
| [`../CHANGELOG.md`](../CHANGELOG.md) | Release notes |
| [`../CONTRIBUTING.md`](../CONTRIBUTING.md) · [`../SECURITY.md`](../SECURITY.md) | How to contribute; how to report a vulnerability |
