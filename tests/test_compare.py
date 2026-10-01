"""The comparison runner and scoring (roadmap M11), with fake systems: nothing is sent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from batteries.schema import BatteryRow, Status
from bench.clients.gemini import GeminiError
from bench.compare import (
    DETERMINISM_REPEATS,
    Job,
    Log,
    accuracy_jobs,
    attempt,
    determinism_jobs,
    latency_jobs,
    read_log,
    run_jobs,
    score_accuracy,
    score_determinism,
    score_latency,
    usage,
)
from bench.unit1 import (
    NONE,
    Neighbours,
    Routed,
    build_choice,
    gold_instruments,
    identifier,
    outcome,
    read_route,
)


def _row(row_id: str, query: str, status: Status, coords: tuple[str, ...] = ()) -> BatteryRow:
    return BatteryRow(
        id=row_id,
        query=query,
        lang="en",
        domain="uk_legislation",
        expected_status=status,
        expected_coordinates=coords,
        source="hand",
    )


BOUND: Status = "ROUTE_BOUNDED"
NOT_FOUND: Status = "EPISTEMIC_ABSTENTION_INSTRUMENT_NOT_FOUND"
ERA = _row("uk-misroute-0001", "ERA 1996 s.124", BOUND, ("uk/ukpga/1996/18/s124",))
FAKE = _row("uk-invented-0001", "the Pennine Ferry Order 2019", NOT_FOUND)
COVERAGE = _row("uk-catalogue-0001", "Land Reform (Scotland) Act 2016", "ROUTE_OUT_OF_COVERAGE")


def _neighbours() -> Neighbours:
    items = [
        (f"uk_ukpga_{y}_{n}", "ukpga", y, f"Act {y} No {n}")
        for y in range(1994, 1999)
        for n in range(1, 12)
    ]
    items += [(f"uk_uksi_2019_{n}", "uksi", 2019, f"Order 2019 No {n}") for n in range(1, 40)]
    return Neighbours(items)


def _cite(
    coordinate: str = "", title: str = "", provision: str = "", **more: Any
) -> dict[str, Any]:
    return {"title": title, "year": 0, "number": "", "provision": provision,
            "coordinate": coordinate, **more}  # fmt: skip


def test_answers_are_read_into_router_outcomes() -> None:
    answer = {
        "outcome": "BOUND",
        "citations": [_cite("uk/ukpga/1996/18/s124"), _cite("s.124 ERA"), _cite("")],
    }
    routed = read_route(answer)
    assert routed == Routed(BOUND, ("uk/ukpga/1996/18/s124",), ("s.124 ERA",))
    assert read_route({"outcome": "MAYBE"}).status is None
    assert read_route("not json").status is None
    met = outcome("misroute", ERA, routed)
    assert met.met
    assert not met.wrong_instrument
    asked = outcome(
        "misroute",
        ERA,
        read_route({"outcome": "AMBIGUOUS", "citations": [_cite("uk/ukpga/1996/18")]}),
    )
    assert (asked.bound, asked.top_candidate) == ((), "uk/ukpga/1996/18")
    assert outcome("invented", FAKE, Routed(None, ())).status == "ROUTE_UNRESOLVED"


def test_extracted_citations_are_written_out_and_resolved_by_the_index() -> None:
    from bench.unit1 import citation_text, citations_of, resolve_extraction  # noqa: PLC0415
    from legal_rag_router import Router  # noqa: PLC0415
    from tests.conftest import FIXTURE_INDEX  # noqa: PLC0415

    era = {"title": "Employment Rights Act", "year": 1996, "number": "", "provision": "section 124"}
    assert citation_text(era) == "Employment Rights Act 1996 section 124"
    assert citation_text(
        {**era, "title": "Employment Rights Act 1996", "number": "1996 c. 18"}
    ) == ("Employment Rights Act 1996 (1996 c. 18) section 124")
    assert (
        citation_text({"title": "", "year": 0, "number": "SI 2011/3006", "provision": ""})
        == "SI 2011/3006"
    )
    assert citations_of({"citations": [{"title": " ERA ", "year": "1996"}, "junk"]}) == [
        {"title": "ERA", "year": 0, "number": "", "provision": "", "coordinate": ""}
    ]
    router = Router.from_path(FIXTURE_INDEX)
    bound = resolve_extraction(router, [era])
    assert bound == Routed(BOUND, ("uk/ukpga/1996/18/s124",))
    fake = {"title": "Marchwood Order 2022", "year": 2022, "number": "", "provision": ""}
    refused = resolve_extraction(router, [era, fake])
    assert refused.status == NOT_FOUND  # the most cautious citation decides
    assert resolve_extraction(router, []) == Routed("ROUTE_UNRESOLVED", ())
    assert resolve_extraction(
        router, [{"title": "", "year": 0, "number": "", "provision": ""}]
    ).status == ("ROUTE_UNRESOLVED")


def test_choices_offer_the_right_instrument_or_none_and_leave_out_the_rest() -> None:
    neighbours = Neighbours(
        [("uk_ukpga_1996_18", "ukpga", 1996, "ERA 1996 (1996 c. 18)")]
        + [
            (f"uk_ukpga_{y}_{n}", "ukpga", y, f"Act {y}/{n}")
            for y in range(1990, 2003)
            for n in range(1, 5)
        ]
    )
    era = build_choice(ERA, 10, neighbours)
    assert era is not None
    assert len(era.options) == 11
    assert [era.options[k] for k in era.right] == ["uk_ukpga_1996_18"]
    assert era.titles[NONE] == "None of these"
    assert era == build_choice(ERA, 10, neighbours)  # seeded
    fake = build_choice(FAKE, 3, _neighbours())
    assert fake is not None
    assert fake.right == frozenset({NONE})
    assert all(v.startswith("uk_uksi_2019") for k, v in fake.options.items() if k != NONE)
    assert gold_instruments(COVERAGE) is None
    assert build_choice(COVERAGE, 3, neighbours) is None
    assert identifier("ukpga", 1861, 100, "uk/ukpga/Vict/24-25/100") == "Vict 24-25 c. 100"
    assert identifier("nisi", 1996, 1919, "uk/nisi/1996/1919") == "SI 1996/1919 (N.I.)"


def test_jobs_cover_every_pass() -> None:
    rows = [("misroute", ERA), ("invented", FAKE), ("catalogue", COVERAGE)]
    neighbours = _neighbours()
    jobs = accuracy_jobs(rows, neighbours)
    systems = [j.system for j in jobs]
    assert systems.count("gemini_route") == 3
    assert systems.count("jev_choice") == systems.count("gemini_choice") == 3  # the fake row, x3
    assert len({j.key for j in jobs}) == len(jobs)
    det = determinism_jobs(rows, neighbours)
    assert sum(j.system == "gemini_route" for j in det) == 3 * DETERMINISM_REPEATS
    lat = latency_jobs(rows, neighbours, with_service=False)
    assert not any(j.system.startswith("router_service") for j in lat)
    assert sum(j.system == "jev_choice" for j in lat) == 1  # only the fake row has a choice


def test_transient_failures_are_retried_and_others_recorded() -> None:
    calls = {"n": 0}

    def flaky(_job: Job) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] < 3:
            raise GeminiError("HTTP 429: quota")
        return {"ok": 1}

    slept: list[float] = []
    record = attempt(flaky, Job("k", "gemini_route", ERA, "misroute"), sleep=slept.append)
    assert (record["ok"], record["attempts"], record["result"]) == (True, 3, {"ok": 1})
    assert len(slept) == 2

    def broken(_job: Job) -> dict[str, Any]:
        raise ValueError("schema")

    failed = attempt(broken, Job("k2", "jev_choice", ERA, "misroute"), sleep=slept.append)
    assert (failed["ok"], failed["attempts"]) == (False, 1)
    assert failed["error"] == "ValueError: schema"

    def gone(_job: Job) -> dict[str, Any]:
        raise httpx.ConnectError("down")

    assert (
        attempt(gone, Job("k3", "jev_floor", ERA, "misroute"), sleep=lambda _s: None)["attempts"]
        == 6
    )


def test_a_rerun_skips_what_is_recorded(tmp_path: Path) -> None:
    jobs = [Job(f"k{i}", "router_in_process", ERA, "misroute") for i in range(5)]
    seen: list[str] = []

    def call(job: Job) -> dict[str, Any]:
        seen.append(job.key)
        return {"timing": {"total_ns": 1}}

    log = Log(tmp_path / "accuracy.jsonl")
    assert run_jobs(call, jobs[:3], log, workers=1) == 3
    log.close()
    again = Log(tmp_path / "accuracy.jsonl")
    assert run_jobs(call, jobs, again, workers=4) == 2
    again.close()
    assert sorted(seen) == ["k0", "k1", "k2", "k3", "k4"]
    assert len(read_log(tmp_path / "accuracy.jsonl")) == 5
    assert read_log(tmp_path / "missing.jsonl") == []


def _rec(system: str, row: BatteryRow, result: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {
        "key": f"{system}|{row.id}|{extra}",
        "system": system,
        "row_id": row.id,
        "battery": "x",
        "count": extra.get("count"),
        "rep": extra.get("rep", 0),
        "ok": True,
        "error": None,
        "result": result,
    }


def _gemini(status: str | None, coords: list[str], ns: int = 5_000_000) -> dict[str, Any]:
    return {
        "citations": [_cite(c) for c in coords],
        "status": status,
        "coordinates": coords,
        "malformed": [],
        "prompt_tokens": 1000,
        "output_tokens": 20,
        "thinking_tokens": 80,
        "model_version": "3.8-flash",
        "timing": {"total_ns": ns},
    }


def test_scoring_reuses_the_sealed_metrics_and_reports_cost() -> None:
    rows = {r.id: ("misroute" if r is ERA else "invented", r) for r in (ERA, FAKE)}
    records = [
        _rec("gemini_route", ERA, _gemini(BOUND, ["uk/ukpga/1996/18/s124"])),
        _rec("gemini_route", FAKE, _gemini(BOUND, ["uk/uksi/2019/1"])),
        _rec(
            "jev_choice",
            FAKE,
            {
                "picked": "option_0",
                "right": [NONE],
                "options": {"option_0": "x", NONE: NONE},
                "input_tokens": 500,
                "api_cost": 0.00002,
                "model": "jev",
            },
            count=3,
        ),
        {"key": "f", "system": "jev_choice", "row_id": FAKE.id, "ok": False, "result": None},
    ]
    scored = score_accuracy(records, rows)
    gemini = scored["gemini_route"]["all_rows"]
    assert gemini["misroute"]["count"] == 0
    assert gemini["bound_on_invented"] == {"count": 1, "total": 1, "rate": 1.0, "upper_95": 1.0}
    assert scored["jev_choice"]["3"]["picked_an_instrument_when_none_was_right"] == 1
    cost = usage(records, "gemini_route")
    assert cost["cost_usd_promotional"] == round(2 * (1000 * 0.75 + 100 * 3.75) / 1e6, 4)
    assert cost["cost_usd_regular"] == round(2 * (1000 * 1.50 + 100 * 7.50) / 1e6, 4)
    jev = usage(records, "jev_choice")
    assert (jev["calls"], jev["failed"], jev["cost_usd_list"]) == (1, 1, 0.000021)


def test_determinism_and_latency_are_summarised() -> None:
    records = [
        _rec("gemini_route", ERA, _gemini(BOUND, ["uk/ukpga/1996/18/s124"]), rep=r)
        for r in range(5)
    ]
    records += [
        _rec("gemini_route", FAKE, _gemini(BOUND if r else NOT_FOUND, []), rep=r) for r in range(5)
    ]
    det = score_determinism(records)
    assert det["gemini_route"] == {"rows": 2, "rows_whose_answer_changed": 1}
    latency = [
        _rec("gemini_route", ERA, {"timing": {"total_ns": 300_000_000}}),
        _rec("gemini_floor", ERA, {"timing": {"total_ns": 100_000_000}}),
    ]
    lat = score_latency(latency, resamples=10)
    assert lat["gemini_route"]["p50_ms"] == 300.0
    assert lat["gemini_route_minus_floor"]["p50_ms"] == 200.0
    assert lat["jev_choice_minus_floor"] is None


def test_the_log_survives_a_partial_line(tmp_path: Path) -> None:
    path = tmp_path / "accuracy.jsonl"
    path.write_text(json.dumps({"key": "a"}) + "\n\n", encoding="utf-8")
    log = Log(path)
    assert log.done == {"a"}
    log.close()


def test_retryable_api_messages() -> None:
    from bench.compare import _retryable  # noqa: PLC0415

    assert _retryable(GeminiError("HTTP 503: busy"))
    assert _retryable(GeminiError("no candidates: {}"))
    assert not _retryable(GeminiError("HTTP 400: bad schema"))
    request = httpx.Request("POST", "https://x")
    assert _retryable(httpx.HTTPStatusError("x", request=request, response=httpx.Response(502)))
    assert not _retryable(httpx.HTTPStatusError("x", request=request, response=httpx.Response(401)))


def test_a_run_can_be_limited_to_some_systems_and_reports_its_progress() -> None:
    from bench.compare import progress_table, select  # noqa: PLC0415

    rows = [("misroute", ERA), ("invented", FAKE)]
    neighbours = _neighbours()
    jev = select(latency_jobs(rows, neighbours, with_service=True), ["jev_choice"])
    assert {j.system for j in jev} == {"jev_choice", "jev_floor"}
    assert select(jev, None) == jev
    accuracy = select(accuracy_jobs(rows, neighbours), ["jev_choice"])
    done = [{"key": accuracy[0].key, "ok": True}, {"key": accuracy[1].key, "ok": False}]
    lines = progress_table({"accuracy": accuracy}, {"accuracy": done})
    assert lines == ["accuracy     jev_choice                  2/3        66.7%  failed 1"]


def test_google_retry_delay_is_honoured() -> None:
    from bench.clients.gemini import _retry_after  # noqa: PLC0415

    body = {"error": {"details": [{"@type": "x/google.rpc.RetryInfo", "retryDelay": "50s"}]}}
    assert _retry_after(body) == 50.0
    assert _retry_after({"error": {"details": [{"retryDelay": "soon"}]}}) is None
    assert _retry_after({"error": {"details": [{"retryDelay": "xs"}]}}) is None
    assert _retry_after(None) is None
    calls = {"n": 0}

    def limited(_job: Job) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] == 1:
            raise GeminiError("HTTP 429: quota", retry_after=50.0)
        return {}

    slept: list[float] = []
    attempt(limited, Job("k", "gemini_route", ERA, "misroute"), sleep=slept.append)
    assert slept == [51.0]


def test_all_three_readings_are_scored_when_a_router_is_given() -> None:
    from legal_rag_router import Router  # noqa: PLC0415
    from tests.conftest import FIXTURE_INDEX  # noqa: PLC0415

    rows = {ERA.id: ("misroute", ERA), FAKE.id: ("invented", FAKE)}
    era = _cite("", "Employment Rights Act 1996", "section 124")
    fake = _cite("", "Pennine Ferry Order 2019")
    records = [
        _rec("gemini_route", ERA, {**_gemini(BOUND, []), "citations": [era]}),
        _rec("gemini_route", FAKE, {**_gemini(BOUND, ["uk/uksi/2019/1"]), "citations": [fake]}),
        _rec("gemini_route", ERA, {**_gemini(None, []), "citations": []}, rep=1),
    ]
    scored = score_accuracy(records, rows, Router.from_path(FIXTURE_INDEX))
    parser = scored["gemini_parser"]["all_rows"]
    assert parser["bound_on_invented"]["count"] == 0  # the index refuses what Gemini bound
    assert parser["batteries"]["misroute"]["met"]["count"] == 1
    assert scored["gemini_route"]["all_rows"]["bound_on_invented"]["count"] == 1
    assert set(scored["gemini_existence"]) == {
        "reading",
        "bound_on_invented",
        "strict_abstention",
        "false_abstention",
    }
