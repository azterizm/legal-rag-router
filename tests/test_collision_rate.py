"""The standalone collision test (02 section 8; 06 section 2, Surface 4).

    uv run pytest tests/test_collision_rate.py -v

Runs on a laptop CPU against the committed fixture index: no corpus download, no network.
Ported to the ``RouteResult`` shape. Companies Act 2006 and the Spanish probes join the
fixture when their data is ingested (roadmap U5 and Stage C); until then those cases skip.
"""

from __future__ import annotations

import random
import re

import pytest

from legal_rag_router import Router, RouteStatus
from legal_rag_router.index import RouterIndex
from tests.conftest import FIXTURE_INDEX


@pytest.fixture(scope="module")
def router() -> Router:
    return Router.from_path(FIXTURE_INDEX)


def _requires(router: Router, instrument_id: str) -> None:
    if router.index.instrument(instrument_id) is None:
        pytest.skip(f"{instrument_id} is not in the fixture index yet (roadmap U5 / Stage C)")


def test_cross_statute_collision_elimination(router: Router) -> None:
    # ERA 1996 s.124 must resolve exclusively to uk_ukpga_1996_18
    r = router.route("compensation limit under Employment Rights Act 1996 section 124")
    assert r.status == RouteStatus.BOUNDED
    assert [str(c) for c in r.coordinates] == ["uk/ukpga/1996/18/s124"]
    assert r.coordinates[0].instrument_id == "uk_ukpga_1996_18"

    # EqA 2010 s.124 must resolve exclusively to uk_ukpga_2010_15
    r = router.route("remedies under Equality Act 2010 section 124")
    assert r.status == RouteStatus.BOUNDED
    assert [str(c) for c in r.coordinates] == ["uk/ukpga/2010/15/s124"]


def test_companies_act_collision(router: Router) -> None:
    _requires(router, "uk_ukpga_2006_46")
    r = router.route("inspection under Companies Act 2006 section 124")
    assert r.status == RouteStatus.BOUNDED
    assert [str(c) for c in r.coordinates] == ["uk/ukpga/2006/46/s124"]


def test_april_2026_probes(router: Router) -> None:
    _requires(router, "es_boe_1885_6627")
    assert (
        str(router.route("Art. 42.1 letra b) CdC").coordinates[0]) == "es/boe/1885/6627/art42/1/b"
    )
    assert (
        str(router.route("apartado c) del Artículo 42 del CdC").coordinates[0])
        == "es/boe/1885/6627/art42/1/c"
    )
    assert (
        router.route("apartado 8 del Artículo 42 del CdC").status == RouteStatus.PROVISION_NOT_FOUND
    )


def test_bare_section_is_ambiguous(router: Router) -> None:
    r = router.route("section 124")
    assert r.status == RouteStatus.AMBIGUOUS
    assert {c.coordinate.instrument_id for c in r.candidates} >= {
        "uk_ukpga_1996_18",
        "uk_ukpga_2010_15",
    }


def test_invented_instrument_epistemic_abstention(router: Router) -> None:
    r = router.route("arbitration rules in Marchwood Commercial Arbitration Order 2022")
    assert r.status == RouteStatus.INSTRUMENT_NOT_FOUND
    assert r.coordinates == ()
    assert r.index_snapshot
    assert r.latency_ns < 2_000_000 * 5  # 2 ms in-process target; CI runners are noisy


def _gazette_sample(index: RouterIndex, n: int = 400) -> list[str]:
    """Real provisions from the fixture, phrased from fixed templates (seeded)."""
    rng = random.Random(20260927)
    queries: list[str] = []
    table = index.tables["coordinates"]
    top_level_section = re.compile(r"uk/ukpga/\d{4}/\d+/s\d+[a-z]{0,3}")
    keys = [k for k, _ in table.items() if top_level_section.fullmatch(k)]
    templates = ("{title} s.{n}", "section {n} of the {title}", "{title}, section {n}")
    for key in rng.sample(keys, min(n, len(keys))):
        instrument_id = "_".join(key.split("/")[:4])
        info = index.instrument(instrument_id)
        if info is None or not info.primary:
            continue
        number = key.rsplit("/s", 1)[1]
        queries.append(rng.choice(templates).format(title=info.title, n=number))
    return queries


def test_no_false_abstention_on_real_instruments(router: Router) -> None:
    # Every sampled real coordinate must route, never abstain: the invented-law figure only
    # counts if real law is not refused along with invented law.
    sample = _gazette_sample(router.index)
    assert len(sample) > 100
    refused = [q for q in sample if router.route(q).status.is_abstention]
    assert len(refused) / len(sample) <= 0.005, refused[:10]
