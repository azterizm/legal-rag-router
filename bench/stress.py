"""Worst-case latency on 4 KB gibberish, by class (roadmap Q-M7-2).

Different noise strains different stages: folding (Unicode that expands or decomposes),
tokenising (dense punctuation), the provision and number patterns (citation-shaped soup),
title matching (years, type words and title vocabulary), identifiers and cues. Each class
is generated at the 4 KB cap with a fixed seed; every sample is routed several times warm
and its fastest run kept (the noise floor of the machine is removed, the algorithm's cost
is not). The worst class's worst sample is the published floor for 4 KB noise.

Usage::

    uv run python -m bench.stress [--index tests/fixtures/index] [--samples 40] [--json out.json]

Also checks linear scaling: doubling the input must not more than 2.5x the time.
"""

from __future__ import annotations

import argparse
import json
import platform
import random
import string
import sys
from collections.abc import Callable
from pathlib import Path

from legal_rag_router import Router
from legal_rag_router.normalise import MAX_QUERY_CHARS

Generator = Callable[[random.Random, int], str]

_TITLE_TEXT = (
    "Employment Rights Act Equality Companies Arbitration Finance Consolidated Fund Theft "
    "Human Data Protection Insolvency Trade Union Labour Relations Health Safety Work Law "
    "Property Offences against Person Partnership Order Regulations Rules Scheme Military Lands"
)
_CITATION_TEXT = (
    "Act 1996 s.124 of the Employment Rights ( ) Sch. 2 para 4 except not ERA SI 2011/3006 "
    "\u00a7 Part X , and 1ZA (a) ss.94-98 et seq. reg. 3 art. 2 r. 3.1 c. 18 8 & 9 Eliz. 2 "
    "c. 69 uk/ukpga/1996/18 legislation.gov.uk/ukpga/1996/18/section/124 that Act the "
    "1996 Act Bill"
)
_TITLE_WORDS = tuple(_TITLE_TEXT.split())
_CITATION_BITS = tuple(_CITATION_TEXT.split())


def _fill(rng: random.Random, size: int, pick: Callable[[], str], sep: str = " ") -> str:
    parts: list[str] = []
    length = 0
    while length < size:
        piece = pick()
        parts.append(piece)
        length += len(piece) + len(sep)
    return sep.join(parts)[:size]


def _chars(alphabet: str) -> Generator:
    return lambda r, n: "".join(r.choice(alphabet) for _ in range(n))


def _words(pick: Callable[[random.Random], str]) -> Generator:
    return lambda r, n: _fill(r, n, lambda: pick(r))


_EXPANDING = "\ufb01\u00bd\u00df\u2163\u3392\u00e9\u0301\u0430\u2019\u2013\u4e2d\u6587 "
_MIX = string.printable + "\u00e9\u00fc\u00df\u00a7\u2013\u2019\u201c\u201d\u00bd\ufb01\u4e2d\u0430"
_WHITESPACE = " \t\n\r\u00a0\u2003a1"

GENERATORS: dict[str, Generator] = {
    "printable": _chars(string.printable),
    "letters_digits": _chars(string.ascii_letters + string.digits + "  "),
    "dense_punctuation": _chars("()[]{}.,;:'\"-/\\&%$#@!?*"),
    "digits_and_years": _words(lambda r: str(r.choice([r.randint(0, 99), r.randint(1200, 2099)]))),
    "unicode_expanding": _chars(_EXPANDING),
    "unicode_mix": _chars(_MIX),
    "citation_soup": _words(lambda r: r.choice(_CITATION_BITS)),
    "title_vocabulary": _words(lambda r: r.choice([*_TITLE_WORDS, str(r.randint(1900, 2026))])),
    "type_words_and_years": _words(lambda r: r.choice(["Act", "Order", "Regulations", "1996"])),
    "provision_soup": _words(lambda r: f"s.{r.randint(1, 999)}({r.randint(1, 9)})"),
    "identifier_soup": _words(
        lambda r: f"uk/ukpga/{r.randint(1900, 2026)}/{r.randint(1, 99)}/s{r.randint(1, 300)}"
    ),
    "no_spaces": _chars(string.ascii_lowercase),
    "whitespace_heavy": _chars(_WHITESPACE),
}


def _time(router: Router, query: str, repeats: int) -> int:
    return min(router.route(query).latency_ns for _ in range(repeats))


def measure(
    router: Router, samples: int, repeats: int, seed: int = 20260927
) -> dict[str, dict[str, float]]:
    results: dict[str, dict[str, float]] = {}
    for name, generate in GENERATORS.items():
        rng = random.Random(f"{seed}:{name}")
        timings = sorted(
            _time(router, generate(rng, MAX_QUERY_CHARS), repeats) for _ in range(samples)
        )
        results[name] = {
            "p50_ms": timings[len(timings) // 2] / 1e6,
            "p99_ms": timings[min(len(timings) - 1, int(len(timings) * 0.99))] / 1e6,
            "max_ms": timings[-1] / 1e6,
        }
    return results


def scaling(router: Router, repeats: int, seed: int = 20260927) -> dict[str, float]:
    """Worst ratio of time(2n) / time(n) per class, for n = 1 KB and 2 KB."""
    ratios: dict[str, float] = {}
    for name, generate in GENERATORS.items():
        rng = random.Random(f"{seed}:{name}:scaling")
        text = generate(rng, MAX_QUERY_CHARS)
        worst = 0.0
        for n in (MAX_QUERY_CHARS // 4, MAX_QUERY_CHARS // 2):
            small, large = _time(router, text[:n], repeats), _time(router, text[: 2 * n], repeats)
            worst = max(worst, large / max(small, 1))
        ratios[name] = worst
    return ratios


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--index", type=Path, default=Path("tests/fixtures/index"))
    parser.add_argument("--samples", type=int, default=40)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)

    router = Router.from_path(args.index)
    results = measure(router, args.samples, args.repeats)
    ratios = scaling(router, args.repeats)
    floor = max(r["max_ms"] for r in results.values())
    print(f"{'class':24} {'p50 ms':>8} {'p99 ms':>8} {'max ms':>8} {'2x ratio':>9}")
    for name, r in sorted(results.items(), key=lambda kv: -kv[1]["max_ms"]):
        row = f"{r['p50_ms']:8.2f} {r['p99_ms']:8.2f} {r['max_ms']:8.2f} {ratios[name]:9.2f}"
        print(f"{name:24} {row}")
    print(f"\n4 KB noise floor (worst class, worst sample): {floor:.2f} ms")
    print(f"platform: {platform.platform()} / Python {platform.python_version()}")
    if args.json:
        payload = {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "index": str(args.index),
            "samples": args.samples,
            "repeats": args.repeats,
            "floor_ms": floor,
            "classes": results,
            "doubling_ratio": ratios,
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0 if max(ratios.values()) <= 2.5 else 1  # noqa: PLR2004 - linear-time guard


if __name__ == "__main__":
    sys.exit(main())
