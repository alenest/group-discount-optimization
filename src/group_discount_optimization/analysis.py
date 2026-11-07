"""Сводные таблицы и графики по результатам экспериментов.

Модуль рассчитан на несколько экземпляров одного размера n. Для каждого n
строятся средние значения, а на графиках показывается разброс между
экземплярами. Это делает кривые устойчивее, чем при одном экземпляре на n.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402

_GROUP_KEYS = ("1", "2", "3", "outside")


def _to_float(value: str) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _to_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def load_results(paths: str | Path | list[str | Path]) -> list[dict[str, object]]:
    if isinstance(paths, (str, Path)):
        paths = [paths]
    rows: list[dict[str, object]] = []
    for path in paths:
        with Path(path).open(encoding="utf-8", newline="") as stream:
            for raw in csv.DictReader(stream):
                row: dict[str, object] = dict(raw)
                row["n"] = int(raw["n"])
                row["group_count"] = int(raw.get("group_count", 0) or 0)
                row["utility"] = float(raw["utility"])
                row["weight"] = float(raw["weight"])
                row["capacity"] = float(raw["capacity"])
                row["selected_count"] = int(raw["selected_count"])
                row["feasible"] = _to_bool(raw["feasible"])
                row["elapsed_seconds"] = float(raw["elapsed_seconds"])
                row["evaluated_candidates"] = int(raw["evaluated_candidates"])
                row["optimum_utility"] = _to_float(raw["optimum_utility"])
                row["gap_percent"] = _to_float(raw["gap_percent"])
                rows.append(row)
    return rows


def merge_results(paths: list[str | Path], output_path: str | Path) -> Path:
    """Объединить несколько results.csv в один файл с общим заголовком."""
    merged_path = Path(output_path)
    merged_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] | None = None
    rows: list[dict[str, str]] = []
    for path in paths:
        with Path(path).open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if fieldnames is None:
                fieldnames = list(reader.fieldnames or [])
            for row in reader:
                rows.append(dict(row))
    if fieldnames is None:
        raise ValueError("Не удалось прочитать заголовок results.csv.")
    with merged_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return merged_path


def _group_by_method(rows: list[dict[str, object]]) -> dict[tuple[int, str], list[dict[str, object]]]:
    grouped: dict[tuple[int, str], list[dict[str, object]]] = {}
    for row in rows:
        key = (int(row["n"]), str(row["method"]))
        grouped.setdefault(key, []).append(row)
    return grouped


def _values(
    rows: list[dict[str, object]],
    key: str,
    *,
    feasible_only: bool = False,
    gap_only: bool = False,
) -> list[float]:
    values: list[float] = []
    for row in rows:
        if feasible_only and not bool(row["feasible"]):
            continue
        if gap_only and row.get("gap_percent") is None:
            continue
        value = row.get(key)
        if value is None:
            continue
        values.append(float(value))
    return values


def _mean_or_empty(values: list[float]) -> object:
    return "" if not values else mean(values)


def _max_or_empty(values: list[float]) -> object:
    return "" if not values else max(values)


def _feasible_share(rows: list[dict[str, object]]) -> object:
    if not rows:
        return ""
    return sum(1 for row in rows if bool(row["feasible"])) / len(rows)


def _parse_group_counts(value: str) -> dict[str, int]:
    result: dict[str, int] = {}
    if not value:
        return result
    for part in value.split(";"):
        key, _, count = part.partition("=")
        if key:
            result[key] = int(count)
    return result


def _mean_group_counts(rows: list[dict[str, object]]) -> str:
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for row in rows:
        parsed = _parse_group_counts(str(row.get("group_counts", "")))
        for key, value in parsed.items():
            sums[key] = sums.get(key, 0.0) + value
            counts[key] = counts.get(key, 0) + 1
    parts = []
    for key in _GROUP_KEYS:
        if key in sums and counts[key]:
            parts.append(f"{key}={sums[key] / counts[key]:.2f}")
    return ";".join(parts)


def _mean_active_groups(rows: list[dict[str, object]]) -> object:
    if not rows:
        return ""
    values = [
        len([part for part in str(row.get("active_groups", "")).split(";") if part])
        for row in rows
    ]
    return mean(values)


def build_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped = _group_by_method(rows)
    n_values = sorted({int(row["n"]) for row in rows})
    instances_by_n: dict[int, set[str]] = {}
    for row in rows:
        instances_by_n.setdefault(int(row["n"]), set()).add(str(row["instance"]))

    summary: list[dict[str, object]] = []
    for n in n_values:
        exhaustive = grouped.get((n, "exhaustive"), [])
        ratio = grouped.get((n, "greedy_ratio"), [])
        aware = grouped.get((n, "greedy_group_aware"), [])
        no_group_greedy = grouped.get((n, "greedy_no_groups"), [])
        no_group_exhaustive = grouped.get((n, "exhaustive_no_groups"), [])

        exhaustive_utility = _values(exhaustive, "utility", feasible_only=True)
        exhaustive_time = _values(exhaustive, "elapsed_seconds")
        exhaustive_candidates = _values(exhaustive, "evaluated_candidates")
        ratio_utility = _values(ratio, "utility", feasible_only=True)
        ratio_gaps = _values(ratio, "gap_percent", gap_only=True)
        ratio_time = _values(ratio, "elapsed_seconds")
        aware_utility = _values(aware, "utility", feasible_only=True)
        aware_gaps = _values(aware, "gap_percent", gap_only=True)
        aware_time = _values(aware, "elapsed_seconds")
        no_group_greedy_utility = _values(no_group_greedy, "utility", feasible_only=True)
        no_group_exhaustive_utility = _values(
            no_group_exhaustive, "utility", feasible_only=True
        )

        summary.append(
            {
                "n": n,
                "instances": len(instances_by_n[n]),
                "optimum_utility_mean": _mean_or_empty(exhaustive_utility),
                "exhaustive_time_mean_sec": _mean_or_empty(exhaustive_time),
                "exhaustive_time_max_sec": _max_or_empty(exhaustive_time),
                "exhaustive_candidates_mean": _mean_or_empty(exhaustive_candidates),
                "greedy_ratio_utility_mean": _mean_or_empty(ratio_utility),
                "greedy_ratio_gap_mean_percent": _mean_or_empty(ratio_gaps),
                "greedy_ratio_gap_max_percent": _max_or_empty(ratio_gaps),
                "greedy_ratio_feasible_share": _feasible_share(ratio),
                "greedy_ratio_time_mean_sec": _mean_or_empty(ratio_time),
                "greedy_group_aware_utility_mean": _mean_or_empty(aware_utility),
                "greedy_group_aware_gap_mean_percent": _mean_or_empty(aware_gaps),
                "greedy_group_aware_gap_max_percent": _max_or_empty(aware_gaps),
                "greedy_group_aware_feasible_share": _feasible_share(aware),
                "greedy_group_aware_time_mean_sec": _mean_or_empty(aware_time),
                "greedy_group_aware_time_max_sec": _max_or_empty(aware_time),
                "greedy_group_aware_active_groups_mean": _mean_active_groups(aware),
                "greedy_group_aware_group_counts_mean": _mean_group_counts(aware),
                "greedy_no_groups_utility_mean": _mean_or_empty(no_group_greedy_utility),
                "greedy_no_groups_feasible_share": _feasible_share(no_group_greedy),
                "exhaustive_no_groups_utility_mean": _mean_or_empty(no_group_exhaustive_utility),
                "exhaustive_no_groups_feasible_share": _feasible_share(no_group_exhaustive),
            }
        )
    return summary


def _write_summary(summary: list[dict[str, object]], output_dir: Path) -> Path:
    path = output_dir / "summary.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)
    return path


def _series(
    rows: list[dict[str, object]],
    method: str,
    key: str,
    *,
    feasible_only: bool = False,
    gap_only: bool = False,
) -> list[tuple[int, float, float, float, int]]:
    """Вернуть по каждому n: n, среднее, минимум, максимум, число наблюдений."""
    grouped = _group_by_method(rows)
    points: list[tuple[int, float, float, float, int]] = []
    for (n, name), group in grouped.items():
        if name != method:
            continue
        values = _values(group, key, feasible_only=feasible_only, gap_only=gap_only)
        if not values:
            continue
        points.append((n, mean(values), min(values), max(values), len(values)))
    return sorted(points)


def _plot_series_with_band(
    ax: Axes,
    rows: list[dict[str, object]],
    method: str,
    key: str,
    label: str,
    color: str,
    marker: str,
    *,
    feasible_only: bool = False,
    gap_only: bool = False,
) -> None:
    points = _series(
        rows,
        method,
        key,
        feasible_only=feasible_only,
        gap_only=gap_only,
    )
    if not points:
        return
    x = [point[0] for point in points]
    y = [point[1] for point in points]
    low = [point[2] for point in points]
    high = [point[3] for point in points]
    ax.plot(x, y, marker=marker, linewidth=2, markersize=6, label=label, color=color)
    if any(abs(high_value - low_value) > 1e-12 for low_value, high_value in zip(low, high)):
        ax.fill_between(x, low, high, color=color, alpha=0.13, linewidth=0)


def _plot_utility(rows: list[dict[str, object]], output_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 5.6))
    _plot_series_with_band(
        ax, rows, "exhaustive", "utility", "Полный перебор", "#1f4e79", "o",
        feasible_only=True,
    )
    _plot_series_with_band(
        ax, rows, "greedy_group_aware", "utility", "Жадный с учётом групп",
        "#c55a11", "s", feasible_only=True,
    )
    _plot_series_with_band(
        ax, rows, "greedy_ratio", "utility", "Жадный по отношению u/w",
        "#548235", "^", feasible_only=True,
    )
    ax.set_title("Средняя полезность решения по экземплярам")
    ax.set_xlabel("Число предметов n")
    ax.set_ylabel("Полезность")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    path = output_dir / "utility_by_n.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def _plot_gap(rows: list[dict[str, object]], output_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 5.4))
    _plot_series_with_band(
        ax, rows, "greedy_ratio", "gap_percent",
        "Жадный по отношению u/w (только допустимые)", "#548235", "^",
        gap_only=True,
    )
    _plot_series_with_band(
        ax, rows, "greedy_group_aware", "gap_percent",
        "Жадный с учётом групп", "#c55a11", "s", gap_only=True,
    )
    ax.set_title("Среднее отклонение от оптимума")
    ax.set_xlabel("Число предметов n")
    ax.set_ylabel("Отклонение от оптимума, %")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    path = output_dir / "gap_by_n.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def _plot_runtime(rows: list[dict[str, object]], output_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 5.6))
    _plot_series_with_band(
        ax, rows, "exhaustive", "elapsed_seconds", "Полный перебор", "#1f4e79", "o"
    )
    _plot_series_with_band(
        ax, rows, "greedy_group_aware", "elapsed_seconds", "Жадный с учётом групп",
        "#c55a11", "s",
    )
    _plot_series_with_band(
        ax, rows, "greedy_ratio", "elapsed_seconds", "Жадный по отношению u/w",
        "#548235", "^",
    )
    ax.set_title("Среднее время работы")
    ax.set_xlabel("Число предметов n")
    ax.set_ylabel("Время, секунды (логарифмическая шкала)")
    ax.set_yscale("log")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    path = output_dir / "runtime_by_n.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def _plot_feasibility(rows: list[dict[str, object]], output_dir: Path) -> Path:
    grouped = _group_by_method(rows)
    n_values = sorted({int(row["n"]) for row in rows})
    methods = (
        ("greedy_group_aware", "Жадный с учётом групп", "#c55a11", "s"),
        ("greedy_ratio", "Жадный по отношению u/w", "#548235", "^"),
        ("greedy_no_groups", "Жадный без групп", "#7f7f7f", "x"),
    )

    fig, ax = plt.subplots(figsize=(10, 5.2))
    for method, label, color, marker in methods:
        x: list[int] = []
        y: list[float] = []
        for n in n_values:
            group = grouped.get((n, method), [])
            if not group:
                continue
            share = _feasible_share(group)
            if share == "":
                continue
            x.append(n)
            y.append(float(share) * 100.0)
        if x:
            ax.plot(x, y, marker=marker, linewidth=2, markersize=6, label=label, color=color)

    ax.set_title("Доля допустимых решений")
    ax.set_xlabel("Число предметов n")
    ax.set_ylabel("Допустимые решения, %")
    ax.set_ylim(-5, 105)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    path = output_dir / "feasibility_by_n.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def _plot_group_distribution(rows: list[dict[str, object]], output_dir: Path) -> Path:
    grouped = _group_by_method(rows)
    n_values = sorted(
        n for (n, method) in grouped if method == "greedy_group_aware"
    )
    labels = {
        "1": "Группа 1",
        "2": "Группа 2",
        "3": "Группа 3",
        "outside": "Вне групп",
    }
    colors = {
        "1": "#1f4e79",
        "2": "#c55a11",
        "3": "#548235",
        "outside": "#a6a6a6",
    }

    fig, ax = plt.subplots(figsize=(10, 5.8))
    bottom = [0.0] * len(n_values)
    for key in _GROUP_KEYS:
        values: list[float] = []
        for n in n_values:
            group = [
                row
                for row in grouped.get((n, "greedy_group_aware"), [])
                if bool(row["feasible"])
            ]
            parsed_values = [
                _parse_group_counts(str(row.get("group_counts", ""))).get(key, 0)
                for row in group
            ]
            values.append(mean(parsed_values) if parsed_values else 0.0)
        ax.bar(
            [str(n) for n in n_values],
            values,
            bottom=bottom,
            label=labels[key],
            color=colors[key],
        )
        bottom = [left + value for left, value in zip(bottom, values, strict=True)]

    ax.set_title("Среднее распределение выбранных предметов по группам")
    ax.set_xlabel("Число предметов n")
    ax.set_ylabel("Выбрано предметов")
    ax.tick_params(axis="x", labelrotation=45, labelsize=8)
    ax.legend(ncol=2)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    path = output_dir / "group_distribution.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def _plot_group_effect(rows: list[dict[str, object]], output_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 5.6))
    _plot_series_with_band(
        ax, rows, "greedy_group_aware", "utility", "Жадный с группами",
        "#c55a11", "s", feasible_only=True,
    )
    _plot_series_with_band(
        ax, rows, "greedy_no_groups", "utility", "Жадный без групп",
        "#7f7f7f", "x", feasible_only=True,
    )
    _plot_series_with_band(
        ax, rows, "exhaustive", "utility", "Оптимум с группами",
        "#1f4e79", "o", feasible_only=True,
    )
    _plot_series_with_band(
        ax, rows, "exhaustive_no_groups", "utility", "Оптимум без групп",
        "#404040", ".", feasible_only=True,
    )

    ax.set_title("Вклад групповых скидок и бонусов")
    ax.set_xlabel("Число предметов n")
    ax.set_ylabel("Полезность")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    path = output_dir / "group_effect.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def _plot_active_groups(rows: list[dict[str, object]], output_dir: Path) -> Path:
    grouped = _group_by_method(rows)
    n_values = sorted(
        n for (n, method) in grouped if method == "greedy_group_aware"
    )
    means: list[float] = []
    lows: list[float] = []
    highs: list[float] = []
    for n in n_values:
        group = [
            row
            for row in grouped.get((n, "greedy_group_aware"), [])
            if bool(row["feasible"])
        ]
        values = [
            len([part for part in str(row.get("active_groups", "")).split(";") if part])
            for row in group
        ]
        if not values:
            means.append(0.0)
            lows.append(0.0)
            highs.append(0.0)
            continue
        means.append(mean(values))
        lows.append(min(values))
        highs.append(max(values))

    fig, ax = plt.subplots(figsize=(10, 5.0))
    ax.plot(n_values, means, marker="s", linewidth=2, markersize=6, color="#c55a11")
    ax.fill_between(n_values, lows, highs, color="#c55a11", alpha=0.13, linewidth=0)
    ax.set_title("Среднее число активных групп в решении жадного алгоритма")
    ax.set_xlabel("Число предметов n")
    ax.set_ylabel("Активных групп")
    ax.set_yticks(range(0, 4))
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    path = output_dir / "active_groups.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def analyze(
    results_path: str | Path | list[str | Path],
    output_dir: str | Path = "reports",
) -> dict[str, Path]:
    rows = load_results(results_path)
    output_path = Path(output_dir)
    figures_dir = output_path / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    summary = build_summary(rows)
    summary_path = _write_summary(summary, output_path)

    paths = {
        "summary": summary_path,
        "utility": _plot_utility(rows, figures_dir),
        "gap": _plot_gap(rows, figures_dir),
        "runtime": _plot_runtime(rows, figures_dir),
        "feasibility": _plot_feasibility(rows, figures_dir),
        "group_distribution": _plot_group_distribution(rows, figures_dir),
        "group_effect": _plot_group_effect(rows, figures_dir),
        "active_groups": _plot_active_groups(rows, figures_dir),
    }
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Построить сводку и графики по results.csv.")
    parser.add_argument(
        "--results",
        nargs="+",
        default=["reports/results.csv"],
        help="Один или несколько файлов results.csv.",
    )
    parser.add_argument("--output", default="reports")
    parser.add_argument(
        "--merge-output",
        default="",
        help="Если указан, объединить входные CSV в этот файл.",
    )
    args = parser.parse_args()
    if args.merge_output:
        merge_results(args.results, args.merge_output)
    paths = analyze(args.results, args.output)
    for name, path in paths.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
