"""Запуск полного перебора и жадных алгоритмов на сохранённом наборе."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable

from .algorithms import (
    AlgorithmResult,
    BaselineResult,
    solve_exhaustive,
    solve_exhaustive_no_groups,
    solve_greedy_group_aware,
    solve_greedy_no_groups,
    solve_greedy_ratio,
)
from .instance import Instance, load_instance

FIELDNAMES = [
    "n",
    "instance",
    "method",
    "utility",
    "weight",
    "capacity",
    "selected_count",
    "feasible",
    "active_groups",
    "group_counts",
    "elapsed_seconds",
    "evaluated_candidates",
    "optimum_utility",
    "gap_percent",
    "is_optimal",
]


def _instance_dirs(data_dir: str | Path) -> list[Path]:
    root = Path(data_dir)
    return sorted(
        (path.parent for path in root.glob("n_*/instance_*/meta.json")),
        key=lambda path: (int(path.parent.name.removeprefix("n_")), path.name),
    )


def _group_counts(instance: Instance, selected_ids: Iterable[int]) -> str:
    selected = set(selected_ids)
    grouped = {item_id for group in instance.groups for item_id in group.item_ids}
    parts = []
    for group in instance.groups:
        count = sum(item_id in selected for item_id in group.item_ids)
        parts.append(f"{group.group_id}={count}")
    parts.append(f"outside={sum(item_id not in grouped for item_id in selected)}")
    return ";".join(parts)


def _row(
    instance: Instance,
    method: str,
    selected_ids: tuple[int, ...],
    utility: float,
    weight: float,
    feasible: bool,
    elapsed_seconds: float,
    evaluated_candidates: int,
    optimum_utility: float | None,
    active_groups: str = "",
) -> dict[str, object]:
    gap = ""
    is_optimal = ""
    if optimum_utility is not None and feasible and optimum_utility > 0:
        gap_value = (optimum_utility - utility) / optimum_utility * 100.0
        gap = f"{gap_value:.6f}"
        is_optimal = str(abs(gap_value) <= 1e-9)
    return {
        "n": instance.n,
        "instance": instance.instance_id or "",
        "method": method,
        "utility": f"{utility:.6f}",
        "weight": f"{weight:.6f}",
        "capacity": f"{instance.capacity:.6f}",
        "selected_count": len(selected_ids),
        "feasible": str(feasible),
        "active_groups": active_groups,
        "group_counts": _group_counts(instance, selected_ids),
        "elapsed_seconds": f"{elapsed_seconds:.6f}",
        "evaluated_candidates": evaluated_candidates,
        "optimum_utility": "" if optimum_utility is None else f"{optimum_utility:.6f}",
        "gap_percent": gap,
        "is_optimal": is_optimal,
    }


def _algorithm_row(
    instance: Instance, result: AlgorithmResult, optimum_utility: float | None
) -> dict[str, object]:
    return _row(
        instance=instance,
        method=result.method,
        selected_ids=result.selected_item_ids,
        utility=result.total_utility,
        weight=result.total_weight,
        feasible=result.feasible,
        elapsed_seconds=result.elapsed_seconds,
        evaluated_candidates=result.evaluated_candidates,
        optimum_utility=optimum_utility,
        active_groups=";".join(str(group_id) for group_id in result.active_group_ids),
    )


def _baseline_row(
    instance: Instance, result: BaselineResult, optimum_utility: float | None
) -> dict[str, object]:
    return _row(
        instance=instance,
        method=result.method,
        selected_ids=result.selected_item_ids,
        utility=result.total_utility,
        weight=result.total_weight,
        feasible=result.feasible,
        elapsed_seconds=result.elapsed_seconds,
        evaluated_candidates=result.evaluated_candidates,
        optimum_utility=optimum_utility,
    )


def run_experiment(
    data_dir: str | Path = "data",
    output_dir: str | Path = "reports",
    exhaustive_max_n: int = 25,
) -> Path:
    """Прогнать алгоритмы на всех экземплярах и сохранить CSV с результатами."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    results_path = output_path / "results.csv"
    rows: list[dict[str, object]] = []

    for path in _instance_dirs(data_dir):
        instance = load_instance(path)
        print(f"n={instance.n:3d}  {path.as_posix()}")

        optimum_utility: float | None = None
        exhaustive: AlgorithmResult | None = None
        if instance.n <= exhaustive_max_n:
            exhaustive = solve_exhaustive(instance)
            optimum_utility = exhaustive.total_utility
            print(
                f"  exhaustive: utility={exhaustive.total_utility:.3f}, "
                f"time={exhaustive.elapsed_seconds:.2f}s"
            )
            rows.append(_algorithm_row(instance, exhaustive, optimum_utility))

        greedy_ratio = solve_greedy_ratio(instance)
        greedy_aware = solve_greedy_group_aware(instance)
        print(
            f"  greedy_ratio: utility={greedy_ratio.total_utility:.3f}, "
            f"feasible={greedy_ratio.feasible}, time={greedy_ratio.elapsed_seconds:.4f}s"
        )
        print(
            f"  greedy_group_aware: utility={greedy_aware.total_utility:.3f}, "
            f"feasible={greedy_aware.feasible}, time={greedy_aware.elapsed_seconds:.4f}s"
        )
        rows.append(_algorithm_row(instance, greedy_ratio, optimum_utility))
        rows.append(_algorithm_row(instance, greedy_aware, optimum_utility))

        baseline_greedy = solve_greedy_no_groups(instance)
        rows.append(_baseline_row(instance, baseline_greedy, optimum_utility))
        if instance.n <= exhaustive_max_n:
            baseline_exhaustive = solve_exhaustive_no_groups(instance)
            print(
                f"  exhaustive_no_groups: utility={baseline_exhaustive.total_utility:.3f}, "
                f"feasible={baseline_exhaustive.feasible}, "
                f"time={baseline_exhaustive.elapsed_seconds:.2f}s"
            )
            rows.append(_baseline_row(instance, baseline_exhaustive, optimum_utility))

    with results_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    config = {
        "data_dir": Path(data_dir).as_posix(),
        "exhaustive_max_n": exhaustive_max_n,
        "instances": len({row["n"] for row in rows}),
        "rows": len(rows),
    }
    (output_path / "experiment_config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Результаты: {results_path.resolve()}")
    return results_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Запуск полного перебора и жадных алгоритмов на наборе data/."
    )
    parser.add_argument("--data", default="data", help="Каталог с экземплярами.")
    parser.add_argument("--output", default="reports", help="Каталог для результатов.")
    parser.add_argument(
        "--exhaustive-max-n",
        type=int,
        default=25,
        help="Максимальное n, для которого запускается полный перебор.",
    )
    args = parser.parse_args()
    run_experiment(args.data, args.output, args.exhaustive_max_n)


if __name__ == "__main__":
    main()
