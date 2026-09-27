from __future__ import annotations

import pytest

from legal_rag_router.grammars.uk import INSTRUMENT_TYPE_WORDS
from legal_rag_router.index import RouterIndex
from legal_rag_router.typo import analyse_title, damerau, suggestions


@pytest.mark.parametrize(
    ("a", "b", "distance"),
    [
        ("rights", "rights", 0),
        ("rihgts", "rights", 1),  # transposition
        ("rigts", "rights", 1),  # deletion
        ("rightss", "rights", 1),  # insertion
        ("righto", "rights", 1),  # substitution
        ("emplyment", "employment", 1),
        ("abc", "xyz", 3),
        ("a", "abcdefgh", 4),  # capped at limit + 1
    ],
)
def test_damerau(a: str, b: str, distance: int) -> None:
    assert damerau(a, b) == distance


def verdict(
    index: RouterIndex, words: list[str], year: int | None
) -> tuple[str, tuple[str, ...], str | None]:
    v = analyse_title(index, words, year, type_words=INSTRUMENT_TYPE_WORDS)
    return v.verdict, v.ids or v.suggestions, v.reason


def test_single_small_typo_binds(fixture_index: RouterIndex) -> None:
    v = analyse_title(
        fixture_index, ["employment", "rihgts", "act"], 1996, type_words=INSTRUMENT_TYPE_WORDS
    )
    assert (v.verdict, v.ids, v.corrections) == (
        "bound",
        ("uk_ukpga_1996_18",),
        (("rihgts", "rights"),),
    )


def test_two_misspelled_words_ask(fixture_index: RouterIndex) -> None:
    assert verdict(fixture_index, ["emplyment", "rihgts", "act"], 1996)[:2] == (
        "ambiguous",
        ("uk_ukpga_1996_18",),
    )


def test_short_words_are_never_corrected(fixture_index: RouterIndex) -> None:
    assert verdict(fixture_index, ["therft", "act"], 1968)[0] == "bound"  # 6 letters: corrected
    assert verdict(fixture_index, ["thft", "act"], 1968)[0] == "not_found"  # 4 letters: never


def test_reordered_title_binds(fixture_index: RouterIndex) -> None:
    assert verdict(fixture_index, ["rights", "employment", "act"], 1996) == (
        "bound", ("uk_ukpga_1996_18",), "reordered",
    )  # fmt: skip


def test_wrong_year_refuses_with_suggestion(fixture_index: RouterIndex) -> None:
    state, ids, reason = verdict(fixture_index, ["employment", "rights", "act"], 1995)
    assert (state, reason) == ("not_found", "wrong_year")
    assert ids[0] == "uk_ukpga_1996_18"


def test_invented_title_is_not_found(fixture_index: RouterIndex) -> None:
    assert (
        verdict(fixture_index, ["marchwood", "commercial", "arbitration", "order"], 2022)[0]
        == "not_found"
    )


def test_suggestions_need_half_the_words(fixture_index: RouterIndex) -> None:
    assert (
        suggestions(
            fixture_index, ["zebra", "crossing", "act"], 1990, type_words=INSTRUMENT_TYPE_WORDS
        )
        == ()
    )
    found = suggestions(
        fixture_index, ["arbitration", "zebra", "act"], 1996, type_words=INSTRUMENT_TYPE_WORDS
    )
    assert found[0] == "uk_ukpga_1996_23"
