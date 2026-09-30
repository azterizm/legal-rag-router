"""The Laya client (roadmap M11): options from real titles, calls timed, answers never read."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bench.clients.laya import (
    option_cut,
    plan_calls,
    question,
    report,
    time_calls,
    title_cuts,
    title_pool,
)
from legal_rag_router import Router
from tests.conftest import FIXTURE_INDEX


def test_options_are_real_titles_and_every_state_meets_every_count() -> None:
    router = Router.from_path(FIXTURE_INDEX)
    titles = title_pool(router, ["uk/ukpga/1996/18/s124", "uk/ukpga/1996/18", "not a coordinate"])
    assert titles == ["Employment Rights Act 1996"]
    pool = [f"Title {i}" for i in range(40)]
    calls = plan_calls(["a", "b"], pool, (3, 10, 30))
    assert [(n, s) for n, s, _ in calls] == [(3, "a"), (3, "b"), (10, "a"), (10, "b"),
                                             (30, "a"), (30, "b")]  # fmt: skip
    assert all(len(set(options)) == n for n, _, options in calls)
    assert calls == plan_calls(["a", "b"], pool, (3, 10, 30))
    assert list(question(["X", "Y"])["instrument"]["criteria"].values()) == ["X", "Y"]


def test_calls_that_do_not_fit_are_counted_not_timed() -> None:
    def predict(state: str, questions: Mapping[str, Any]) -> Mapping[str, Any]:
        options = questions["instrument"]["criteria"]
        if len(options) > 5:
            raise ValueError("only 5 of its 10 option markers fit")
        usage: dict[str, Any] = {"input_tokens": 40}
        if state == "collapse":
            usage["options"] = {"instrument": {"total": 3, "distinct": 2}}
        return {"answers": {"instrument": {"choice": "option_0"}}, "usage": usage}

    calls = plan_calls(["ok", "collapse"], [f"T{i}" for i in range(12)], (3, 10))
    timed = time_calls(predict, calls)
    out = report(timed, resamples=20)
    assert out["3"]["calls"] == 2
    assert out["3"]["not_fitting"] == 0
    assert out["3"]["collapsed_options"] == 1
    assert out["3"]["input_tokens_p50"] == 40
    assert out["3"]["latency"]["calls"] == 2
    assert out["10"] == {
        "calls": 2,
        "not_fitting": 2,
        "collapsed_options": 0,
        "input_tokens_p50": None,
        "latency": None,
    }


def test_the_option_cut_follows_laya_0_3_22() -> None:
    assert option_cut([10, 10, 10]) == (None, 1.0)  # 33 tokens: within the 192 budget
    assert option_cut([60]) == (None, 48 / 60)  # the 48-token cap per option
    per, kept = option_cut([20] * 30)  # 630 tokens: every option cut to 176 // 30 = 5
    assert per == 5
    assert kept == 4 / 20  # the marker takes one of the five
    assert option_cut([20] * 60)[0] == 4  # never below four tokens
    cuts = title_cuts(len, [(3, "s", ["abc", "de", "f"]), (30, "s", ["x" * 20] * 30)])
    assert cuts == {
        3: {"tokens_per_option": [None], "title_tokens_kept_p50": 1.0},
        30: {"tokens_per_option": [5], "title_tokens_kept_p50": 0.2},
    }
