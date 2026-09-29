"""Concept discovery (roadmap D4): candidates for citation-less queries, never bound."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from ingest.build_concept_index import (
    build_concepts,
    citation_in_degree,
    compile_thesaurus,
    instrument_flags,
    write_concepts,
)
from legal_rag_router import DiscoveryResult, NextAction, Router
from legal_rag_router.concepts import (
    CONCEPTS_MANIFEST,
    PRIOR_FLAGS,
    ConceptIndex,
    ConceptIndexError,
    load_concepts,
)
from legal_rag_router.coordinate import Coordinate
from legal_rag_router.discovery import (
    DEFAULT_DISCOVERY,
    DiscoveryPolicy,
    discover,
    provision_label,
)
from legal_rag_router.index import load_index
from tests.conftest import FIXTURE_INDEX

ERA = "uk/ukpga/1996/18"
THEFT = "uk/ukpga/1968/60"
EQA = "uk/ukpga/2010/15"
# A 9-document corpus: the common-word cut-off (a share of all documents) would skip
# almost every word, so these tests turn it off.
POLICY = replace(DEFAULT_DISCOVERY, max_df_share=1.0)


def _write(data: Path, instrument: dict[str, object], provisions: list[dict[str, object]]) -> None:
    coordinate = str(instrument["coordinate"])
    parts = coordinate.split("/")
    path = data / "uk" / parts[1] / parts[2] / f"{'_'.join(parts)}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [{"record_type": "instrument", **instrument}, *provisions]
    path.write_text("".join(json.dumps(line) + "\n" for line in lines))


@pytest.fixture(scope="module")
def concepts_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("discovery")
    data = root / "data"
    _write(
        data,
        {"coordinate": ERA, "title": "Employment Rights Act 1996",
         "long_title": "An Act to consolidate enactments relating to employment rights.",
         "groups": {"ptX": ["s124", "s98"]}},
        [
            {"coordinate": f"{ERA}/ptX", "title": "Unfair dismissal"},
            {"coordinate": f"{ERA}/s98", "title": "General", "crossheading": "Fairness"},
            {"coordinate": f"{ERA}/s98/1", "text": "reason for the dismissal conduct capability"},
            {"coordinate": f"{ERA}/s124", "title": "Limit of compensatory award etc.",
             "crossheading": "Compensation"},
            {"coordinate": f"{ERA}/s124/1", "text": "shall not exceed the amount specified"},
            {"coordinate": f"{ERA}/s9999", "title": "Limit of compensatory award phantom"},
            {"coordinate": f"{ERA}/sch1", "title": None},
            {"coordinate": f"{ERA}/sch1/para1", "title": None, "text": "untitled transitional"},
        ],
    )  # fmt: skip
    _write(  # a repealed Act whose section heading matches the query better, word for word
        data,
        {"coordinate": THEFT, "title": "Theft Act 1968", "repealed": True},
        [{"coordinate": f"{THEFT}/s1", "title": "Unfair dismissal compensation limit cap award"}],
    )
    _write(  # flagged Northern Ireland by title
        data,
        {"coordinate": EQA, "title": "Equality (Northern Ireland) Act 2010"},
        [{"coordinate": f"{EQA}/s13", "title": "Direct discrimination rules"}],
    )
    thesaurus = root / "thesaurus.toml"
    thesaurus.write_text('[synonyms]\ncap = ["limit", "maximum"]\nsacked = ["dismissal"]\n')
    harvest = root / "harvest.jsonl"
    harvest.write_text(
        "".join(
            json.dumps(
                {"target_coordinate": f"{ERA}/s{n}", "in_commentary": n == 0, "kind": "citation"}
            )
            + "\n"
            for n in range(40)
        )
        + json.dumps({"target_coordinate": None})
        + "\n"
        + json.dumps({"target_coordinate": "not a coordinate"})
        + "\n"
    )
    out = root / "concepts"
    write_concepts(
        build_concepts(data),
        out,
        snapshot="2026-09-28",
        thesaurus=compile_thesaurus(thesaurus),
        in_degree=citation_in_degree(harvest),
    )
    return out


@pytest.fixture(scope="module")
def router(concepts_dir: Path) -> Router:
    return Router.from_path(FIXTURE_INDEX, concepts=concepts_dir, discovery_policy=POLICY)


@pytest.fixture(scope="module")
def concepts(concepts_dir: Path) -> ConceptIndex:
    return load_concepts(concepts_dir)


def test_a_concept_query_finds_the_provision_and_never_binds(router: Router) -> None:
    result = router.discover("unfair dismissal compensation cap")
    assert isinstance(result, DiscoveryResult)
    assert result.next_action is NextAction.ASK_USER
    top = result.candidates[0]
    assert str(top.coordinate) == f"{ERA}/s124"
    assert top.label == "Employment Rights Act 1996, s. 124: Limit of compensatory award etc."
    assert set(top.matched) >= {"unfair", "dismiss", "compens", "cap"}
    assert result.confident
    assert result.index_snapshot == "2026-09-28"
    # discovery changes nothing about routing: the same query still cites nothing
    assert router.route("unfair dismissal compensation cap").status.value == "ROUTE_UNRESOLVED"


def test_a_candidate_the_router_cannot_bind_is_never_offered(router: Router) -> None:
    found = [str(c.coordinate) for c in router.discover("compensatory award phantom").candidates]
    assert f"{ERA}/s9999" not in found


def test_repealed_law_is_demoted_but_still_offered(router: Router) -> None:
    found = [str(c.coordinate) for c in router.discover("unfair dismissal compensation").candidates]
    assert found.index(f"{ERA}/s124") < found.index(f"{THEFT}/s1")


def test_naming_the_territory_lifts_its_penalty(concepts: ConceptIndex) -> None:
    index = load_index(FIXTURE_INDEX)
    penalties = list(POLICY.prior_penalties)
    penalties[PRIOR_FLAGS.index("northern_ireland")] = 1.0
    unpenalised = replace(POLICY, prior_penalties=tuple(penalties))

    def top(query: str, policy: DiscoveryPolicy = POLICY) -> float:
        return discover(concepts, index, query, policy).candidates[0].score

    plain, named = "direct discrimination rules", "direct discrimination rules northern ireland"
    assert top(plain) < top(plain, unpenalised)  # penalised when the query doesn't name it
    assert top(named) == top(named, unpenalised)  # lifted when it does


@pytest.mark.parametrize(
    ("query", "reason"),
    [
        (None, "not_a_string"),
        ("x" * 5000, "query_too_long"),
        ("the of and", "no_terms"),
        ("zzzqqq", "no_match"),
    ],
)
def test_unhelpful_queries_say_why(router: Router, query: object, reason: str) -> None:
    result = router.discover(query)
    assert result.reason == reason
    assert not result.confident


def test_a_weak_top_candidate_is_not_confident(concepts: ConceptIndex) -> None:
    index = load_index(FIXTURE_INDEX)
    strict = replace(POLICY, min_share=0.99)
    result = discover(concepts, index, "dismissal direct discrimination", strict)
    assert result.candidates
    assert (result.confident, result.reason) == (False, "low_confidence")


def test_without_a_concept_index_discovery_says_so() -> None:
    result = Router.from_path(FIXTURE_INDEX).discover("unfair dismissal")
    assert (result.reason, result.candidates) == ("no_concept_index", ())


def test_limit_and_instrument_documents(concepts: ConceptIndex, router: Router) -> None:
    assert len(router.discover("dismissal", limit=1).candidates) == 1
    index = load_index(FIXTURE_INDEX)
    with_instruments = replace(POLICY, instruments=True)
    result = discover(concepts, index, "employment rights", with_instruments)
    found = [str(c.coordinate) for c in result.candidates]
    assert ERA in found
    result = discover(concepts, index, "employment rights", POLICY)
    found = [str(c.coordinate) for c in result.candidates]
    assert ERA not in found


def test_when_every_word_is_common_the_two_rarest_are_scored(concepts: ConceptIndex) -> None:
    index = load_index(FIXTURE_INDEX)
    strict = replace(POLICY, max_df_share=0.0)  # every word is "common" now
    words = ["dismiss", "compens", "employ"]
    rarest = sorted(words, key=concepts.document_frequency)[:2]
    result = discover(concepts, index, "dismissal compensation employment", strict)
    assert result.candidates
    assert set().union(*(c.matched for c in result.candidates)) <= set(rarest)


@pytest.mark.parametrize(
    ("coordinate", "label"),
    [
        ("uk/ukpga/1996/18/s124", "s. 124"),
        ("uk/uksi/1998/1833/reg4", "reg. 4"),
        ("uk/uksi/2011/3006/art3", "art. 3"),
        ("uk/uksi/1998/3132/rule3.1", "r. 3.1"),
        ("uk/ukpga/1996/18/sch2/para3", "Sch. 2 para. 3"),
        ("uk/ukpga/1991/29/sch/para3", "Schedule para. 3"),
        ("uk/ukpga/1996/18/ptX/chII", "pt. X ch. II"),
        ("uk/ukpga/1996/18/grp1", "grp1"),
    ],
)
def test_provision_label(coordinate: str, label: str) -> None:
    assert provision_label(Coordinate.parse(coordinate)) == label


def test_instrument_flags_and_in_degree(concepts: ConceptIndex) -> None:
    flags = instrument_flags(
        {"coordinate": "uk/nisr/2020/1", "title": "The Pensions (Amendment) (Commencement) Rules",
         "authority_type": "SECONDARY_INSTRUMENT", "repealed": True}
    )  # fmt: skip
    assert {n for i, n in enumerate(PRIOR_FLAGS) if flags >> i & 1} == {
        "repealed", "northern_ireland", "amending", "commencement", "secondary",
    }  # fmt: skip
    assert citation_in_degree(None) == Counter()
    s124 = next(d for d in range(concepts.doc_count) if concepts.doc(d).coordinate == f"{ERA}/s124")
    assert concepts.prior(s124) == (0, round(16 * math.log2(1 + 39)))  # s0 is a note


def test_the_thesaurus_compiles_to_stemmed_terms(tmp_path: Path) -> None:
    assert compile_thesaurus(None) == {}
    path = tmp_path / "t.toml"
    path.write_text('[synonyms]\nsacked = ["dismissal", "dismissed"]\n')
    assert compile_thesaurus(path) == {"sack": ["dismiss"]}
    path.write_text('[synonyms]\n"two words" = ["x"]\n')
    with pytest.raises(ValueError, match="one indexable word"):
        compile_thesaurus(path)


def test_a_match_through_the_thesaurus_alone_is_never_confident(router: Router) -> None:
    result = router.discover("sacked")  # unknown to the index; its synonym "dismissal" is not
    assert result.candidates
    assert (result.confident, result.reason) == (False, "low_confidence")


def test_a_candidate_without_a_heading_is_labelled_by_its_number(router: Router) -> None:
    [top, *_] = router.discover("untitled transitional").candidates
    assert (top.label, top.heading) == ("Employment Rights Act 1996, Sch. 1 para. 1", None)


def test_naming_scotland_lifts_its_penalty(concepts: ConceptIndex) -> None:
    index = load_index(FIXTURE_INDEX)
    penalties = list(POLICY.prior_penalties)
    penalties[PRIOR_FLAGS.index("scotland")] = 0.1
    policy = replace(POLICY, prior_penalties=tuple(penalties))
    assert discover(concepts, index, "direct discrimination scottish", policy).candidates


def test_a_damaged_thesaurus_is_refused(concepts_dir: Path, tmp_path: Path) -> None:
    copy = tmp_path / "concepts"
    shutil.copytree(concepts_dir, copy)
    (copy / "thesaurus.json").write_text("{")
    manifest = json.loads((copy / CONCEPTS_MANIFEST).read_text())
    manifest["files"]["thesaurus.json"]["sha256"] = hashlib.sha256(b"{").hexdigest()
    (copy / CONCEPTS_MANIFEST).write_text(json.dumps(manifest))
    with pytest.raises(ConceptIndexError, match=r"thesaurus\.json is not valid JSON"):
        load_concepts(copy)
