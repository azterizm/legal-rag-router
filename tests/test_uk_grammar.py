"""UK citation grammar (grammar.md section 4): one case per surface-form row where possible."""

from __future__ import annotations

import pytest

from legal_rag_router.grammars.base import ProvisionRef
from legal_rag_router.grammars.uk import number_keys
from legal_rag_router.grammars.uk_grammar import (
    GRAMMAR,
    int_to_roman,
    numeral_variants,
    roman_to_int,
)
from legal_rag_router.normalise import fold


def provisions(query: str) -> list[tuple[str, list[str], bool, bool]]:
    return [
        (query[p.start : p.end], [r.label() for r in p.refs], p.is_range, p.open_ended)
        for p in GRAMMAR.provisions(query, fold(query))
    ]


@pytest.mark.parametrize(
    ("row", "query", "expected"),
    [
        ("UK-P-01", "s.124", [("s.124", ["s.124"], False, False)]),
        ("UK-P-01", "s 124", [("s 124", ["s.124"], False, False)]),
        ("UK-P-01", "s124", [("s124", ["s.124"], False, False)]),
        ("UK-P-02", "section 124", [("section 124", ["s.124"], False, False)]),
        ("UK-P-02", "sec. 124", [("sec. 124", ["s.124"], False, False)]),
        ("UK-P-02", "\u00a7124", [("\u00a7124", ["s.124"], False, False)]),
        ("UK-P-03", "s.124(1ZA)(a)", [("s.124(1ZA)(a)", ["s.124(1ZA)(a)"], False, False)]),
        (
            "UK-P-03",
            "section 124(1ZA)(a)(ii)",
            [("section 124(1ZA)(a)(ii)", ["s.124(1ZA)(a)(ii)"], False, False)],
        ),
        (
            "UK-P-04",
            "subsection (2) of section 124",
            [("subsection (2) of section 124", ["s.124(2)"], False, False)],
        ),
        (
            "UK-P-04",
            "section 124 subsection (2)",
            [("section 124 subsection (2)", ["s.124(2)"], False, False)],
        ),
        ("UK-P-05", "ss.94\u201398", [("ss.94\u201398", ["s.94", "s.98"], True, False)]),
        (
            "UK-P-05",
            "sections 124 to 126",
            [("sections 124 to 126", ["s.124", "s.126"], True, False)],
        ),
        (
            "UK-P-06",
            "sections 94, 95 and 98",
            [("sections 94, 95 and 98", ["s.94", "s.95", "s.98"], False, False)],
        ),
        ("UK-P-07", "s.98 et seq.", [("s.98 et seq.", ["s.98"], False, True)]),
        (
            "UK-P-08",
            "Sch. 2 para 4(1)(b)",
            [("Sch. 2 para 4(1)(b)", ["Sch. 2 para. 4(1)(b)"], False, False)],
        ),
        (
            "UK-P-08",
            "para 4 of Schedule 2",
            [("para 4 of Schedule 2", ["Sch. 2 para. 4"], False, False)],
        ),
        (
            "UK-P-09",
            "the Schedule, para 3",
            [("the Schedule, para 3", ["Sch. para. 3"], False, False)],
        ),
        ("UK-P-10", "reg. 3(1)(a)", [("reg. 3(1)(a)", ["reg. 3(1)(a)"], False, False)]),
        ("UK-P-11", "art. 2(1)", [("art. 2(1)", ["art. 2(1)"], False, False)]),
        ("UK-P-12", "rule 3.1(2)", [("rule 3.1(2)", ["r. 3.1(2)"], False, False)]),
        ("UK-P-13", "Part X", [("Part X", ["Part X"], False, False)]),
        ("UK-P-13", "Part 4A", [("Part 4A", ["Part 4A"], False, False)]),
        ("UK-P-14", "Part 2, Chapter 1", [("Part 2, Chapter 1", ["Part 2 Ch. 1"], False, False)]),
        (
            "UK-P-14",
            "Chapter 1 of Part 2",
            [("Chapter 1 of Part 2", ["Part 2 Ch. 1"], False, False)],
        ),
        ("UK-P-16", "secton 124", [("secton 124", ["s.124"], False, False)]),
        ("UK-P-17", "section 1996", [("section 1996", ["s.1996"], False, False)]),
        ("UK-C-12", "\u00a3124", []),
        ("UK-C-12", "124 employees", []),
        ("UK-C-12", "part i think", []),
        ("UK-P-10", "Working Time Regulations 1998", []),
    ],
)
def test_provision_forms(
    row: str, query: str, expected: list[tuple[str, list[str], bool, bool]]
) -> None:
    assert provisions(query) == expected, row


def test_provision_designator_case_comes_from_the_original() -> None:
    [mention] = GRAMMAR.provisions("s.124(1ZA)", fold("s.124(1ZA)"))
    assert mention.refs[0].subs == ("1ZA",)


@pytest.mark.parametrize(
    ("query", "key"),
    [
        ("SI 2011/3006", "si/2011/3006"),
        ("S.I. 2011 No. 3006", "si/2011/3006"),
        ("2011 No. 3006", "si/2011/3006"),
        ("SSI 2003/623", "ssi/2003/623"),
        ("SR 1996/123", "sr/1996/123"),
        ("1996 c. 18", "c/1996/18"),
        ("c. 18 of 1996", "c/1996/18"),
        ("8 & 9 Eliz. 2 c. 69", "rc/eliz2/8-9/69"),
        ("47 Geo. 3 Sess. 2 c. 78", "rc/geo3sess2/47/78"),
        ("10 Edw. 7 & 1 Geo. 5 c. 15", "rc/edw7and1geo5/10/15"),
        ("15 & 16 Geo. 5 c. 20", "rc/geo5/15-16/20"),
        ("18 & 19 Vict. c. 76", "rc/vict/18-19/76"),
        ("12, 13 & 14 Geo. 6 c. 1", "rc/geo6/12-13-14/1"),
    ],
)
def test_number_forms(query: str, key: str) -> None:
    [mention] = GRAMMAR.numbers(query, fold(query))
    assert mention.key == key
    assert query[mention.start : mention.end].strip() == query.strip()


@pytest.mark.parametrize(
    ("coordinate", "keys"),
    [
        ("ukpga/Edw7/1/1", ("rc/edw7/1/1",)),
        ("apgb/Geo3/41/1", ("rc/geo3/41/1",)),
        ("aep/Ann/1/1", ("rc/ann/1/1",)),
        ("ukla/Edw7/1/1", ()),  # local Act: 1 Edw. 7 c. i
        ("ukppa/Edw7/3/1", ()),
        ("ukcm/Edw8and1Geo6/1/1", ()),
        ("aip/Ann/2/15", ()),
        ("apni/Geo5/15-16/2", ()),
        ("wsi/2025/10", ("si/2025/10",)),
        ("wsi/2026/10", ()),  # Welsh SIs have their own numbers from 2026
        ("nisi/1973/97", ("si/1973/97",)),
        ("ukla/1991/1", ()),
    ],
)
def test_number_keys_by_series(coordinate: str, keys: tuple[str, ...]) -> None:
    assert number_keys(coordinate.split("/")) == keys


@pytest.mark.parametrize(
    ("query", "kind", "detail"),
    [
        ("except section 124", "negation", None),
        ("other than the Act", "negation", None),
        ("that Act", "context_ref", None),
        ("the 1996 Act", "context_ref", "1996"),
        ("as it stood in 2012", "temporal", None),
        ("the original version", "temporal", None),
        ("in force on 1 April 2012", "temporal", None),
        ("Employment Rights Bill", "out_of_coverage", "bill"),
        ("[2020] UKSC 1", "out_of_coverage", "case"),
        ("Article 82 UK GDPR", "out_of_coverage", "eu"),
        ("Regulation (EU) 2016/679", "out_of_coverage", "eu"),
        ("section 1983 of the U.S.C.", "out_of_coverage", "foreign"),
        ("art. 42 CdC", "out_of_coverage", "es"),
        ("Ley 58/2003", "out_of_coverage", "es"),
    ],
)
def test_cues(query: str, kind: str, detail: str | None) -> None:
    cues = [(c.kind, c.detail) for c in GRAMMAR.cues(query, fold(query))]
    assert (kind, detail) in cues


def test_context_ref_is_not_a_title_with_a_year() -> None:
    assert not [
        c for c in GRAMMAR.cues("the Act 1996", fold("the Act 1996")) if c.kind == "context_ref"
    ]


@pytest.mark.parametrize(
    ("ref", "primary", "expected"),
    [
        (ProvisionRef((("section", "124"),), ("1ZA", "a")), True, [("s124", "1ZA", "a")]),
        (ProvisionRef((("article", "124"),)), True, [("s124",), ("art124",)]),  # UK-P-15
        (ProvisionRef((("section", "2"),)), False, [("art2",), ("reg2",), ("rule2",), ("s2",)]),
        (
            ProvisionRef((("schedule", "2"), ("paragraph", "4")), ("1",)),
            True,
            [("sch2", "para4", "1")],
        ),
        (ProvisionRef((("schedule", ""), ("paragraph", "3"))), False, [("sch", "para3")]),
        (ProvisionRef((("part", "X"),)), True, [("ptX",), ("pt10",)]),
        (ProvisionRef((("part", "2"), ("chapter", "1"))), True, [("pt2", "ch1"), ("ptII", "ch1")]),
        (
            ProvisionRef((("rule", "3.1"),), ("2",)),
            False,
            [("rule3.1", "2"), ("reg3.1", "2"), ("art3.1", "2")],
        ),
    ],
)
def test_provision_paths(ref: ProvisionRef, primary: bool, expected: list[tuple[str, ...]]) -> None:
    assert GRAMMAR.provision_paths(ref, primary=primary) == expected


@pytest.mark.parametrize(
    ("text", "value"), [("i", 1), ("iv", 4), ("X", 10), ("xiv", 14), ("CCCXCIX", 399)]
)
def test_roman(text: str, value: int) -> None:
    assert roman_to_int(text) == value
    assert int_to_roman(value) == text.upper()


@pytest.mark.parametrize("text", ["", "iiii", "vx", "abc", "CD"])
def test_non_canonical_roman(text: str) -> None:
    assert roman_to_int(text) is None


def test_numeral_variants() -> None:
    assert numeral_variants("X") == ["X", "10"]
    assert numeral_variants("10") == ["10", "X"]
    assert numeral_variants("2A") == ["2A", "IIA"]
    assert numeral_variants("0") == ["0"]


# ---------------------------------------------------------------- rarer forms


def refs(query: str) -> list[list[tuple[tuple[tuple[str, str], ...], tuple[str, ...]]]]:
    return [[(r.units, r.subs) for r in m.refs] for m in GRAMMAR.provisions(query, fold(query))]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        # A unit word ends at a word boundary: "Part 1" is never "par" + "t".
        ("Schedule 2, Part 1", [[((("schedule", "2"), ("part", "1")), ())]]),
        ("Chapter 1 of Part 2", [[((("part", "2"), ("chapter", "1")), ())]]),
        # Letter-first designators.
        ("Sch. B1 para. 15(3)", [[((("schedule", "B1"), ("paragraph", "15")), ("3",))]]),
        # A list stops at a lower-case Roman numeral, and a range needs exactly two ends.
        ("Parts II and iv", [[((("part", "II"),), ())]]),
        ("ss. 1-3 and 5", [[((("section", n),), ()) for n in ("1", "3", "5")]]),
        # "of Part 2" belongs to a chapter, not to a section.
        ("s. 3 of Part 2", [[((("section", "3"),), ())], [((("part", "2"),), ())]]),
        # A paragraph is nested only under a schedule.
        ("s. 1, para. 2", [[((("section", "1"),), ())], [((("paragraph", "2"),), ())]]),
    ],
)
def test_rarer_provision_forms(query: str, expected: object) -> None:
    assert refs(query) == expected


def test_ranges_with_three_ends_are_lists() -> None:
    (mention,) = GRAMMAR.provisions("ss. 1-3 and 5", fold("ss. 1-3 and 5"))
    assert not mention.is_range


@pytest.mark.parametrize(
    ("ref", "paths"),
    [
        (ProvisionRef((("paragraph", "3"),)), [("para3",)]),
        (ProvisionRef((("chapter", "1"),)), [("ch1",)]),
        (ProvisionRef((("schedule", "2"),)), [("sch2",)]),
        (ProvisionRef((("schedule", "2"), ("part", "1"))), [("sch2", "pt1"), ("sch2", "ptI")]),
    ],
)
def test_more_provision_paths(ref: ProvisionRef, paths: list[tuple[str, ...]]) -> None:
    assert GRAMMAR.provision_paths(ref, primary=True) == paths


def test_invalid_roman_numerals_are_kept_as_written() -> None:
    assert numeral_variants("VV") == ["VV"]


def test_si_number_lists_are_bounded() -> None:
    query = "S.I. 2001/1, " + ", ".join(f"2001/{i}" for i in range(2, 40))
    assert len(GRAMMAR.numbers(query, fold(query))) == 25  # the first number and 24 more
