# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

The first release: the United Kingdom, routing and discovery.

### Added
- `Router.route`: reads the citations in a query and returns one `RouteResult` with one of six
  statuses (`ROUTE_BOUNDED`, `ROUTE_AMBIGUOUS`, two epistemic abstentions,
  `ROUTE_OUT_OF_COVERAGE`, `ROUTE_UNRESOLVED`) and the caller's `next_action`. No model, no
  network, no disk I/O per query; never raises for any input.
- UK citation grammar (`docs/grammar.md`): full and short titles, abbreviations, chapter and SI
  numbers, regnal Acts before 1963, pinpoints to paragraph level, lists, ranges, exclusions,
  former titles, and three typo tiers (correct, ask, refuse).
- Coverage: UK Public General Acts and UK Statutory Instruments to provision level (134,219
  instruments, snapshot 2026-09-28); other UK series, EU and retained EU law recognised and
  reported out of coverage.
- `partition_filter`: the retrieval filter for a bound result, validated against injection.
- `Router.discover`: candidate provisions for queries that cite nothing, from a separate concept
  index, offered for confirmation and never bound (discover-then-bind).
- Follow-ups (`context=`), jurisdiction scope (`jurisdictions=`), and opt-in miss logging that
  never logs query text unless a `redact` function is given.
- Index and concept-index loading with SHA-256 verification of every file.
- Sealed evaluation: 2,112 labelled UK queries, a 100,000-citation coverage sweep, controlled
  latency runs on two machines, and a comparison against Gemini 3.8 Flash (high), Jev and Laya
  (`reports/`).
- Packaging (hatchling, zero runtime dependencies), CI on Python 3.11–3.14, CodeQL, Dependabot.
