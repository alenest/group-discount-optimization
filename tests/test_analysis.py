"""Проверки сводки по нескольким экземплярам одного размера."""

from group_discount_optimization.analysis import build_summary


def _row(
    *,
    n: int,
    instance: str,
    method: str,
    utility: float,
    feasible: bool,
    gap: float | None,
    elapsed: float,
    evaluated: int,
    active: str = "",
    counts: str = "",
) -> dict[str, object]:
    return {
        "n": n,
        "instance": instance,
        "method": method,
        "utility": utility,
        "feasible": feasible,
        "gap_percent": gap,
        "elapsed_seconds": elapsed,
        "evaluated_candidates": evaluated,
        "active_groups": active,
        "group_counts": counts,
    }


def test_summary_averages_instances_and_keeps_feasibility_share():
    rows = [
        _row(
            n=12,
            instance="instance_001",
            method="exhaustive",
            utility=100.0,
            feasible=True,
            gap=0.0,
            elapsed=1.0,
            evaluated=10,
        ),
        _row(
            n=12,
            instance="instance_002",
            method="exhaustive",
            utility=120.0,
            feasible=True,
            gap=0.0,
            elapsed=2.0,
            evaluated=10,
        ),
        _row(
            n=12,
            instance="instance_001",
            method="greedy_group_aware",
            utility=100.0,
            feasible=True,
            gap=0.0,
            elapsed=0.1,
            evaluated=20,
            active="1;2",
            counts="1=5;2=4;outside=1",
        ),
        _row(
            n=12,
            instance="instance_002",
            method="greedy_group_aware",
            utility=108.0,
            feasible=True,
            gap=10.0,
            elapsed=0.3,
            evaluated=20,
            active="1",
            counts="1=6;2=3;outside=1",
        ),
        _row(
            n=12,
            instance="instance_001",
            method="greedy_ratio",
            utility=80.0,
            feasible=True,
            gap=20.0,
            elapsed=0.01,
            evaluated=5,
        ),
        _row(
            n=12,
            instance="instance_002",
            method="greedy_ratio",
            utility=0.0,
            feasible=False,
            gap=None,
            elapsed=0.01,
            evaluated=5,
        ),
    ]

    summary = build_summary(rows)
    assert len(summary) == 1
    row = summary[0]

    assert row["n"] == 12
    assert row["instances"] == 2
    assert row["optimum_utility_mean"] == 110.0
    assert row["exhaustive_time_mean_sec"] == 1.5
    assert row["greedy_group_aware_gap_mean_percent"] == 5.0
    assert row["greedy_group_aware_gap_max_percent"] == 10.0
    assert row["greedy_group_aware_feasible_share"] == 1.0
    assert row["greedy_ratio_gap_mean_percent"] == 20.0
    assert row["greedy_ratio_feasible_share"] == 0.5
    assert row["greedy_group_aware_active_groups_mean"] == 1.5
    assert row["greedy_group_aware_group_counts_mean"] == "1=5.50;2=3.50;outside=1.00"
