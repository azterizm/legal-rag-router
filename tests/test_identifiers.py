"""Structured identifiers (grammar.md UK-X-01 to UK-X-05)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from legal_rag_router.identifiers import scan_identifiers


@pytest.mark.parametrize(
    ("query", "kind", "key"),
    [
        ("see uk/ukpga/1996/18/s124/1ZA/a please", "coordinate", "uk/ukpga/1996/18/s124/1za/a"),
        ("UK/UKPGA/1996/18", "coordinate", "uk/ukpga/1996/18"),
        ("uk_ukpga_1996_18", "instrument_id", "uk/ukpga/1996/18"),
        ("uk_ukpga_Geo5_15-16_20", "instrument_id", "uk/ukpga/geo5/15-16/20"),
        (
            "https://www.legislation.gov.uk/ukpga/1996/18/section/124",
            "url",
            "uk/ukpga/1996/18/s124",
        ),
        (
            "legislation.gov.uk/id/ukpga/1996/18/section/124/1ZA/2020-01-01",
            "url",
            "uk/ukpga/1996/18/s124/1za",
        ),
        ("www.legislation.gov.uk/ukpga/1996/18/contents", "url", "uk/ukpga/1996/18"),
        ("http://www.legislation.gov.uk/uksi/2011/3006/made", "url", "uk/uksi/2011/3006"),
        (
            "legislation.gov.uk/ukpga/1996/18/schedule/2/paragraph/4",
            "url",
            "uk/ukpga/1996/18/sch2/para4",
        ),
        ("legislation.gov.uk/ukpga/Eliz2/8-9/69/section/1", "url", "uk/ukpga/eliz2/8-9/69/s1"),
    ],
)
def test_identifier_forms(query: str, kind: str, key: str) -> None:
    [mention] = scan_identifiers(query)
    assert (mention.kind, mention.key) == (kind, key)


@pytest.mark.parametrize(
    "query",
    [
        "uk/ukpga/1996",
        "uk_ukpga_1996",
        "ukpga/1996/18",
        "legislation.gov.uk/ukpga",
        "uk/ukpga/96/18/extra",
    ],
)
def test_partial_paths_are_not_identifiers(query: str) -> None:
    assert scan_identifiers(query) == []


def test_injection_shaped_input_yields_only_a_safe_key() -> None:
    [mention] = scan_identifiers("uk/ukpga/1996/18' or '1'=='1")
    assert mention.key == "uk/ukpga/1996/18"


@given(st.text(max_size=300))
def test_keys_use_the_safe_alphabet(text: str) -> None:
    for mention in scan_identifiers(text):
        assert set(mention.key) <= set("abcdefghijklmnopqrstuvwxyz0123456789./-")
