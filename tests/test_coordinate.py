"""Coordinate grammar: every example in docs/grammar.md §UK-C round-trips (M1)."""

import contextlib

import pytest
from hypothesis import given
from hypothesis import strategies as st

from legal_rag_router import Coordinate, CoordinateError
from legal_rag_router.coordinate import MAX_COORDINATE_LENGTH, CoordinateScheme, register_scheme
from legal_rag_router.grammars.uk import (
    legislation_path,
    provision_from_legislation_tokens,
)

# (canonical string, instrument_id, is_instrument) — mirrors the examples table in docs/grammar.md
EXAMPLES = [
    ("uk/ukpga/1996/18", "uk_ukpga_1996_18", True),
    ("uk/ukpga/1996/18/s124", "uk_ukpga_1996_18", False),
    ("uk/ukpga/1996/18/s124A", "uk_ukpga_1996_18", False),
    ("uk/ukpga/1996/18/s124/1ZA/a", "uk_ukpga_1996_18", False),
    ("uk/ukpga/1996/18/s124/1ZA/a/ii", "uk_ukpga_1996_18", False),
    ("uk/ukpga/1996/18/ptI", "uk_ukpga_1996_18", False),
    ("uk/ukpga/1996/18/pt2A/ch1", "uk_ukpga_1996_18", False),
    ("uk/ukpga/1996/18/sch1/para2/2/b/i", "uk_ukpga_1996_18", False),
    ("uk/ukpga/2010/15/schA1/para1", "uk_ukpga_2010_15", False),
    ("uk/uksi/2011/3006/art2", "uk_uksi_2011_3006", False),
    ("uk/uksi/2020/1343/reg4/1C", "uk_uksi_2020_1343", False),
    ("uk/uksi/1998/3132/rule3.1/1", "uk_uksi_1998_3132", False),
    ("uk/uksi/2024/1226/sch/para10", "uk_uksi_2024_1226", False),
    ("uk/wsi/2013/2729", "uk_wsi_2013_2729", True),
    ("uk/ukpga/Eliz2/8-9/69", "uk_ukpga_Eliz2_8-9_69", True),
    ("uk/ukpga/Eliz2/8-9/69/s1", "uk_ukpga_Eliz2_8-9_69", False),
    ("uk/ukpga/Geo3Sess2/47/78", "uk_ukpga_Geo3Sess2_47_78", True),
    ("uk/ukpga/Edw7and1Geo5/10/15", "uk_ukpga_Edw7and1Geo5_10_15", True),
    ("uk/ukpga/Geo6and1Eliz2/15-16/2/s3", "uk_ukpga_Geo6and1Eliz2_15-16_2", False),
    ("uk/ukpga/VictSess2/63/2", "uk_ukpga_VictSess2_63_2", True),
    ("uk/ukpga/Will4and1Vict/7/40", "uk_ukpga_Will4and1Vict_7_40", True),
]


@pytest.mark.parametrize(("text", "instrument_id", "is_instrument"), EXAMPLES)
def test_examples_round_trip(text: str, instrument_id: str, *, is_instrument: bool) -> None:
    c = Coordinate.parse(text)
    assert str(c) == text
    assert Coordinate.parse(str(c)) == c
    assert c.instrument_id == instrument_id
    assert c.is_instrument is is_instrument
    assert c.key == text.casefold()


@pytest.mark.parametrize(
    "text",
    [
        "",
        "uk",
        "uk/",
        "uk/ukpga",
        "uk/ukpga/1996",  # partial path: not a complete instrument
        "uk/ukpga/1996/18/",
        "uk//1996/18",
        "UK/ukpga/1996/18",
        "uk/UKPGA/1996/18",
        "uk/ukpga/96/18",
        "uk/ukpga/1996/018",  # leading zero is never canonical
        "uk/ukpga/1996/0",
        "uk/ukpga/Eliz2/69",  # regnal needs a session segment
        "uk/ukpga/eliz2/8-9/69",
        "uk/ukpga/1996/18/124",  # first provision segment must name a unit
        "uk/ukpga/1996/18/a/s124",
        "uk/ukpga/1996/18/s124/1ZA'",
        'uk/ukpga/1996/18/s124" or "1"=="1',
        "uk/ukpga/1996/18/s124/%",
        "uk/ukpga/1996/18/s124 ",
        "uk/ukpga/1996/18/s1..2",
        "xx/ukpga/1996/18",
        "uk/ukpga/1996/18/" + "/".join(["a"] * 20),
        "uk/ukpga/1996/18/s" + "1" * MAX_COORDINATE_LENGTH,
    ],
)
def test_malformed_coordinates_are_rejected(text: str) -> None:
    with pytest.raises(CoordinateError):
        Coordinate.parse(text)
    assert Coordinate.try_parse(text) is None


def test_parse_rejects_non_string() -> None:
    with pytest.raises(CoordinateError):
        Coordinate.parse(123)  # type: ignore[arg-type]


def test_hierarchy() -> None:
    c = Coordinate.parse("uk/ukpga/1996/18/s124/1ZA/a")
    assert str(c.parent) == "uk/ukpga/1996/18/s124/1ZA"
    assert str(c.instrument_coordinate) == "uk/ukpga/1996/18"
    assert c.instrument_coordinate.parent is None
    instrument = c.instrument_coordinate
    assert instrument.instrument_coordinate is instrument
    assert c.series == "ukpga"
    s124 = Coordinate.parse("uk/ukpga/1996/18/s124")
    assert s124.is_ancestor_of(c)
    assert not c.is_ancestor_of(s124)
    assert not s124.is_ancestor_of(s124)
    assert not s124.is_ancestor_of(Coordinate.parse("uk/ukpga/1996/18/s124A"))
    assert str(s124.child("1ZA", "a")) == str(c)


def test_of_validates() -> None:
    assert str(Coordinate.of("uk", ("ukpga", "1996", "18"), ("s124",))) == "uk/ukpga/1996/18/s124"
    with pytest.raises(CoordinateError):
        Coordinate.of("uk", ("ukpga", "1996"))
    with pytest.raises(CoordinateError):
        Coordinate.of("uk", ("ukpga", "1996", "18", "19"))


def test_coordinates_are_hashable_and_ordered() -> None:
    a = Coordinate.parse("uk/ukpga/1996/18/s124")
    b = Coordinate.parse("uk/ukpga/1996/18/s124")
    assert a == b
    assert hash(a) == hash(b)
    assert len({a, b}) == 1
    assert sorted([Coordinate.parse("uk/ukpga/2006/46"), a])[0] == a


def test_scheme_registration_guards() -> None:
    from legal_rag_router.grammars.uk import SCHEME  # noqa: PLC0415

    with pytest.raises(ValueError, match="already registered"):
        register_scheme(SCHEME)
    bad = CoordinateScheme(
        "UK1", SCHEME.instrument_arity, SCHEME.instrument_pattern, SCHEME.first_provision_pattern
    )
    with pytest.raises(ValueError, match="invalid jurisdiction"):
        register_scheme(bad)


# ---------------------------------------------------------------- legislation.gov.uk mapping

MAPPING = [
    ("section-124", ("s124",)),
    ("section-124-1ZA-a", ("s124", "1ZA", "a")),
    ("section-124-1ZA-a-ii", ("s124", "1ZA", "a", "ii")),
    ("section-3-b", ("s3", "b")),
    ("section-16-8-c-iia", ("s16", "8", "c", "iia")),
    ("section-5-2-aza", ("s5", "2", "aza")),
    ("schedule-1-paragraph-2-2-b-i", ("sch1", "para2", "2", "b", "i")),
    ("schedule-A1-paragraph-1-1", ("schA1", "para1", "1")),
    ("schedule-paragraph-10", ("sch", "para10")),
    ("schedule-1", ("sch1",)),
    ("schedule", ("sch",)),
    ("schedule-1-part-2", ("sch1", "pt2")),
    ("schedule-2-part-1-chapter-3-rule-4", ("sch2", "pt1", "ch3", "rule4")),
    ("part-I", ("ptI",)),
    ("part-2A-chapter-1", ("pt2A", "ch1")),
    ("article-2-1", ("art2", "1")),
    ("regulation-4-1C", ("reg4", "1C")),
    ("rule-1.1-1", ("rule1.1", "1")),
    ("schedule-1-appendix-2-paragraph-3", ("sch1", "app2", "para3")),
    ("schedule-3-group-1-part-2", ("sch3", "grp1", "pt2")),
    ("schedule-13-paragraph-b", ("sch13", "parab")),
    ("schedule-paragraph-b", ("sch", "parab")),
    ("schedule-n1", ("schn1",)),
    ("schedule-SECOND-paragraph-1", ("schSECOND", "para1")),
]


@pytest.mark.parametrize(("element_id", "expected"), MAPPING)
def test_element_id_and_url_mapping(element_id: str, expected: tuple[str, ...]) -> None:
    assert provision_from_legislation_tokens(element_id.split("-")) == expected
    url_path = legislation_path(expected)
    assert provision_from_legislation_tokens(url_path.split("/")) == expected


@pytest.mark.parametrize(
    "element_id",
    [
        "",
        "crossheading-execution",
        "part-1-crossheading-general",
        "section",  # a section with no number
        "section-2-and-3",
        "1-2",
        "term-worker",
        "c00001",
        "section-5-sch",
        "section-124-Foo'",
        "section-a",  # lower-case designators only for schedules and paragraphs
        "section-2930.",
        "schedule-4-paragraph-wrapper1",
    ],
)
def test_non_citable_ids_are_rejected(element_id: str) -> None:
    tokens = element_id.split("-") if element_id else []
    assert provision_from_legislation_tokens(tokens) is None


def test_legislation_path_examples() -> None:
    assert legislation_path(("s124", "1ZA", "a")) == "section/124/1ZA/a"
    assert legislation_path(("sch", "para10")) == "schedule/paragraph/10"
    assert legislation_path(("ptI",)) == "part/I"


# ---------------------------------------------------------------- property tests

_DESIGNATOR = st.from_regex(r"[1-9][0-9]{0,2}[A-Z]{0,2}", fullmatch=True)
_SUB = st.one_of(
    st.from_regex(r"[1-9][0-9]{0,2}(ZA|A)?", fullmatch=True),
    st.sampled_from(["a", "b", "aa", "aza", "i", "ii", "iv", "xxvii", "iia"]),
)
_UNIT = st.sampled_from(["s", "art", "reg", "rule", "sch", "para", "pt", "ch"])
_PROVISION = st.builds(
    lambda u, d, subs: (u + d, *subs), _UNIT, _DESIGNATOR, st.lists(_SUB, max_size=4)
)
_CALENDAR = st.builds(
    lambda s, y, n: (s, str(y), str(n)),
    st.sampled_from(["ukpga", "uksi", "wsi", "nisi", "asp"]),
    st.integers(1801, 2026),
    st.integers(1, 99999),
)
_REGNAL = st.builds(
    lambda r, sess, n: ("ukpga", r, sess, str(n)),
    st.sampled_from(["Vict", "Geo3", "Geo3Sess2", "Edw7and1Geo5", "Geo6and1Eliz2", "Eliz2"]),
    st.sampled_from(["1", "47", "8-9", "15-16"]),
    st.integers(1, 200),
)


@given(instrument=st.one_of(_CALENDAR, _REGNAL), provision=st.one_of(st.just(()), _PROVISION))
def test_parse_str_round_trip(instrument: tuple[str, ...], provision: tuple[str, ...]) -> None:
    c = Coordinate.of("uk", instrument, provision)
    assert Coordinate.parse(str(c)) == c
    assert c.instrument_id == "_".join(("uk", *instrument))


@given(provision=_PROVISION)
def test_legislation_path_round_trip(provision: tuple[str, ...]) -> None:
    assert provision_from_legislation_tokens(legislation_path(provision).split("/")) == provision


@given(text=st.text(max_size=300))
def test_parse_never_raises_anything_but_coordinate_error(text: str) -> None:
    with contextlib.suppress(CoordinateError):
        Coordinate.parse(text)
