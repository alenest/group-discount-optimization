"""Сводные таблицы и графики по результатам экспериментов."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def _to_float(value: str) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _to_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def load_results(path: str | Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with Path(path).open(encoding="utf-8", newline="") as stream:
        for raw in csv.DictReader(stream):
            row: dict[str, object] = dict(raw)
            row["n"] = int(raw["n"])
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


def _by_method(rows: list[dict[str, object]]) -> dict[tuple[int, str], dict[str, object]]:
    return {(int(row["n"]), str(row["method"])): row for row in rows}


def _parse_group_counts(value: str) -> dict[str, int]:
    result: dict[str, int] = {}
    if not value:
        return result
    for part in value.split(";"):
        key, _, count = part.partition("=")
        if key:
            result[key] = int(count)
    return result


def build_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    indexed = _by_method(rows)
    n_values = sorted({int(row["n"]) for row in rows})
    summary: list[dict[str, object]] = []

    for n in n_values:
        exhaustive = indexed.get((n, "exhaustive"))
        ratio = indexed.get((n, "greedy_ratio"))
        aware = indexed.get((n, "greedy_group_aware"))
        no_group_greedy = indexed.get((n, "greedy_no_groups"))
        no_group_exhaustive = indexed.get((n, "exhaustive_no_groups"))

        def value(row: dict[str, object] | None, key: str) -> object:
            return "" if row is None else row[key]

        summary.append(
            {
                "n": n,
                "optimum_utility": value(exhaustive, "utility"),
                "exhaustive_time_sec": value(exhaustive, "elapsed_seconds"),
                "exhaustive_candidates": value(exhaustive, "evaluated_candidates"),
                "greedy_ratio_utility": value(ratio, "utility"),
                "greedy_ratio_gap_percent": value(ratio, "gap_percent"),
                "greedy_ratio_time_sec": value(ratio, "elapsed_seconds"),
                "greedy_group_aware_utility": value(aware, "utility"),
                "greedy_group_aware_gap_percent": value(aware, "gap_percent"),
                "greedy_group_aware_time_sec": value(aware, "elapsed_seconds"),
                "greedy_group_aware_feasible": value(aware, "feasible"),
                "greedy_group_aware_active_groups": value(aware, "active_groups"),
                "greedy_group_aware_group_counts": value(aware, "group_counts"),
                "greedy_no_groups_utility": value(no_group_greedy, "utility"),
                "greedy_no_groups_feasible": value(no_group_greedy, "feasible"),
                "exhaustive_no_groups_utility": value(no_group_exhaustive, "utility"),
                "exhaustive_no_groups_feasible": value(no_group_exhaustive, "feasible"),
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
    indexed: dict[tuple[int, str], dict[str, object]], method: str
) -> tuple[list[int], list[float]]:
    pairs = sorted(
        (n, float(row["utility"]))
        for (n, name), row in indexed.items()
        if name == method and bool(row.get("feasible", True))
    )
    return [pair[0] for pair in pairs], [pair[1] for pair in pairs]


def _plot_utility(indexed: dict[tuple[int, str], dict[str, object]], output_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 5.6))
    styles = {
        "exhaustive": ("Полный перебор", "o", "#1f4e79"),
        "greedy_group_aware": ("Жадный с учётом групп", "s", "#c55a11"),
        "greedy_ratio": ("Жадный по отношению u/w", "^", "#548235"),
    }
    for method, (label, marker, color) in styles.items():
        x, y = _series(indexed, method)
        if x:
            ax.plot(x, y, marker=marker, linewidth=2, markersize=6, label=label, color=color)
    ax.set_title("Суммарная полезность решения")
    ax.set_xlabel("Число предметов n")
    ax.set_ylabel("Полезность")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    path = output_dir / "utility_by_n.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def _plot_gap(indexed: dict[tuple[int, str], dict[str, object]], output_dir: Path) -> Path:
    n_values = sorted(
        n
        for (n, method) in indexed
        if method == "exhaustive"
    )
    ratio_gaps: list[float] = []
    aware_gaps: list[float] = []
    for n in n_values:
        ratio = indexed.get((n, "greedy_ratio"))
        aware = indexed.get((n, "greedy_group_aware"))
        ratio_gaps.append(
            math.nan
            if ratio is None or not bool(ratio["feasible"]) or ratio["gap_percent"] is None
            else float(ratio["gap_percent"])
        )
        aware_gaps.append(
            math.nan
            if aware is None or not bool(aware["feasible"]) or aware["gap_percent"] is None
            else float(aware["gap_percent"])
        )

    x = list(range(len(n_values)))
    width = 0.38
    fig, ax = plt.subplots(figsize=(10, 5.4))
    bars_ratio = ax.bar(
        [value - width / 2 for value in x], ratio_gaps, width,
        label="Жадный по отношению u/w", color="#548235",
    )
    bars_aware = ax.bar(
        [value + width / 2 for value in x], aware_gaps, width,
        label="Жадный с учётом групп", color="#c55a11",
    )
    ax.set_title("Отклонение от оптимума на малых n")
    ax.set_xlabel("Число предметов n")
    ax.set_ylabel("Отклонение от оптимума, %")
    ax.set_xticks(x, [str(n) for n in n_values])
    ax.set_xlim(-0.8, len(x) - 0.2)
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend()
    for bars, values in ((bars_ratio, ratio_gaps), (bars_aware, aware_gaps)):
        for bar, value in zip(bars, values, strict=True):
            if math.isnan(value):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    0.0,
                    "н/д",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                )
                continue
            ax.annotate(
                f"{value:.2f}",
                xy=(bar.get_x() + bar.get_width() / 2, value),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
            )
    fig.tight_layout()
    path = output_dir / "gap_by_n.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def _plot_runtime(indexed: dict[tuple[int, str], dict[str, object]], output_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 5.6))
    styles = {
        "exhaustive": ("Полный перебор", "o", "#1f4e79"),
        "greedy_group_aware": ("Жадный с учётом групп", "s", "#c55a11"),
        "greedy_ratio": ("Жадный по отношению u/w", "^", "#548235"),
    }
    for method, (label, marker, color) in styles.items():
        pairs = sorted(
            (n, float(row["elapsed_seconds"]))
            for (n, name), row in indexed.items()
            if name == method
        )
        if pairs:
            ax.plot(
                [pair[0] for pair in pairs], [pair[1] for pair in pairs],
                marker=marker, linewidth=2, markersize=6, label=label, color=color,
            )
    ax.set_title("Время работы алгоритмов")
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


def _plot_group_distribution(rows: list[dict[str, object]], output_dir: Path) -> Path:
    aware_rows = sorted(
        (row for row in rows if row["method"] == "greedy_group_aware"),
        key=lambda row: int(row["n"]),
    )
    n_values = [int(row["n"]) for row in aware_rows]
    group_keys = ["1", "2", "3", "outside"]
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

    fig, ax = plt.subplots(figsize=(10, 5.6))
    bottom = [0] * len(n_values)
    for key in group_keys:
        values = [_parse_group_counts(str(row["group_counts"])).get(key, 0) for row in aware_rows]
        ax.bar(
            [str(n) for n in n_values], values, bottom=bottom,
            label=labels[key], color=colors[key],
        )
        bottom = [left + value for left, value in zip(bottom, values, strict=True)]

    ax.set_title("Распределение выбранных предметов по группам")
    ax.set_xlabel("Число предметов n")
    ax.set_ylabel("Выбрано предметов")
    ax.legend(ncol=2)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    path = output_dir / "group_distribution.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def _plot_group_effect(indexed: dict[tuple[int, str], dict[str, object]], output_dir: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 5.6))

    greedy_x, greedy_y = _series(indexed, "greedy_group_aware")
    no_group_x, no_group_y = _series(indexed, "greedy_no_groups")
    ax.plot(
        greedy_x, greedy_y, marker="s", linewidth=2, label="Жадный с группами", color="#c55a11"
    )
    ax.plot(
        no_group_x, no_group_y, marker="x", linewidth=2, linestyle="--",
        label="Жадный без групп", color="#7f7f7f",
    )

    opt_x, opt_y = _series(indexed, "exhaustive")
    no_opt_x, no_opt_y = _series(indexed, "exhaustive_no_groups")
    if opt_x:
        ax.plot(
            opt_x, opt_y, marker="o", linewidth=2, label="Оптимум с группами", color="#1f4e79"
        )
    if no_opt_x:
        ax.plot(
            no_opt_x, no_opt_y, marker=".", linewidth=2, linestyle=":",
            label="Оптимум без групп", color="#404040",
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
    aware_rows = sorted(
        (row for row in rows if row["method"] == "greedy_group_aware"),
        key=lambda row: int(row["n"]),
    )
    n_values = [int(row["n"]) for row in aware_rows]
    active_counts = [
        len([part for part in str(row["active_groups"]).split(";") if part])
        for row in aware_rows
    ]

    fig, ax = plt.subplots(figsize=(10, 5.0))
    ax.bar([str(n) for n in n_values], active_counts, color="#c55a11")
    ax.set_title("Число активных групп в решении жадного алгоритма")
    ax.set_xlabel("Число предметов n")
    ax.set_ylabel("Активных групп")
    ax.set_yticks(range(0, max(active_counts, default=0) + 2))
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    path = output_dir / "active_groups.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def analyze(results_path: str | Path, output_dir: str | Path = "reports") -> dict[str, Path]:
    rows = load_results(results_path)
    output_path = Path(output_dir)
    figures_dir = output_path / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    summary = build_summary(rows)
    summary_path = _write_summary(summary, output_path)
    indexed = _by_method(rows)

    paths = {
        "summary": summary_path,
        "utility": _plot_utility(indexed, figures_dir),
        "gap": _plot_gap(indexed, figures_dir),
        "runtime": _plot_runtime(indexed, figures_dir),
        "group_distribution": _plot_group_distribution(rows, figures_dir),
        "group_effect": _plot_group_effect(indexed, figures_dir),
        "active_groups": _plot_active_groups(rows, figures_dir),
    }
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Построить сводку и графики по results.csv.")
    parser.add_argument("--results", default="reports/results.csv")
    parser.add_argument("--output", default="reports")
    args = parser.parse_args()
    paths = analyze(args.results, args.output)
    for name, path in paths.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
