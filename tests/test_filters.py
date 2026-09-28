from __future__ import annotations

import pytest

from legal_rag_router import (
    Coordinate,
    FilterError,
    NextAction,
    RouteResult,
    RouteStatus,
    partition_filter,
)


def bound(*coordinates: str, excluded: tuple[str, ...] = ()) -> RouteResult:
    return RouteResult(
        status=RouteStatus.BOUNDED,
        next_action=NextAction.RETRIEVE_BOUNDED,
        coordinates=tuple(Coordinate.parse(c) for c in coordinates),
        excluded=tuple(Coordinate.parse(c) for c in excluded),
    )


def test_provision_filter() -> None:
    assert partition_filter(bound("uk/ukpga/1996/18/s124")) == (
        'instrument_id in ["uk_ukpga_1996_18"] and '
        '((coordinate == "uk/ukpga/1996/18/s124" or coordinate like "uk/ukpga/1996/18/s124/%"))'
    )


def test_instrument_filter() -> None:
    assert partition_filter(bound("uk/ukpga/1996/18")) == 'instrument_id in ["uk_ukpga_1996_18"]'


def test_multi_citation_filter() -> None:
    expression = partition_filter(bound("uk/ukpga/1996/18/s124", "uk/ukpga/2010/15/s124"))
    assert expression.startswith('instrument_id in ["uk_ukpga_1996_18", "uk_ukpga_2010_15"] and (')
    assert 'coordinate like "uk/ukpga/2010/15/s124/%"' in expression


def test_whole_instrument_with_provision_of_another() -> None:
    expression = partition_filter(bound("uk/ukpga/1996/18", "uk/ukpga/2010/15/s124"))
    assert 'instrument_id == "uk_ukpga_1996_18"' in expression
    assert 'coordinate == "uk/ukpga/2010/15/s124"' in expression


def test_exclusions() -> None:
    expression = partition_filter(bound("uk/ukpga/1996/18", excluded=("uk/ukpga/1996/18/s124",)))
    assert expression == (
        'instrument_id in ["uk_ukpga_1996_18"] and not '
        '((coordinate == "uk/ukpga/1996/18/s124" or coordinate like "uk/ukpga/1996/18/s124/%"))'
    )


@pytest.mark.parametrize(
    "status",
    [s for s in RouteStatus if s is not RouteStatus.BOUNDED],
)
def test_only_bound_results_get_a_filter(status: RouteStatus) -> None:
    result = RouteResult(status=status, next_action=NextAction.ASK_USER)
    with pytest.raises(FilterError, match="no retrieval filter"):
        partition_filter(result)


def test_bound_without_coordinates_is_refused() -> None:
    with pytest.raises(FilterError, match="without coordinates"):
        partition_filter(
            RouteResult(status=RouteStatus.BOUNDED, next_action=NextAction.RETRIEVE_BOUNDED)
        )


def test_values_outside_the_safe_alphabet_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    # The coordinate grammar keeps this unreachable today; the check guards future grammars.
    import re  # noqa: PLC0415

    from legal_rag_router import filters  # noqa: PLC0415

    monkeypatch.setattr(filters, "_SAFE", re.compile(r"[a-z]+"))
    with pytest.raises(FilterError, match="safe alphabet"):
        partition_filter(bound("uk/ukpga/1996/18/s124"))
