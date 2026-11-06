"""Генерация фиксируемых небольших экземпляров v4."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np

DEFAULT_SIZES = (12, 15, 18, 20, 22, 25, 30, 40, 50, 60, 75, 100)
DEFAULT_Q = 10
DEFAULT_INSTANCES_PER_SIZE = 1
DEFAULT_MIN_GROUPS = 2
DEFAULT_MAX_GROUPS = 3


def _choose_thresholds(group_count: int, rng: np.random.Generator) -> list[int]:
    if group_count == 2:
        # Не берём 5/5: при Q=10 оставляем место и для проверки предметов вне групп.
        choices = ((4, 4), (4, 5), (5, 4))
        return list(choices[int(rng.integers(0, len(choices)))])
    if group_count == 3:
        # При Q=10 можно активировать две такие группы, но не все три.
        return [4, 4, 5]
    raise ValueError("Для начального набора поддерживаются 2 или 3 группы.")


def _allocate_group_sizes(
    n: int, thresholds: list[int], rng: np.random.Generator
) -> tuple[list[int], int]:
    """Выделить минимум под пороги, оставить предметы вне групп и распределить остаток."""
    minimum_grouped = sum(thresholds)
    available = n - minimum_grouped
    # В начальных данных оставляем несколько предметов вне групп, если размер позволяет.
    ungrouped_count = min(available, max(1, int(n * 0.10)))
    extra_grouped = available - ungrouped_count
    sizes = np.asarray(thresholds, dtype=np.int64)
    if extra_grouped:
        # Первый групповой набор гарантированно содержит хотя бы один
        # невыбранный в контрольном решении запасной предмет.
        sizes[0] += 1
        extra_grouped -= 1
        if extra_grouped:
            sizes += rng.multinomial(extra_grouped, np.full(len(thresholds), 1 / len(thresholds)))
    return [int(value) for value in sizes], int(ungrouped_count)


def _build_witness_counts(
    q: int,
    thresholds: list[int],
    group_sizes: list[int],
    ungrouped_count: int,
) -> tuple[list[int], int]:
    """Создать контрольное распределение ровно Q предметов с двумя активными группами."""
    if q < thresholds[0]:
        raise ValueError("Q должно позволять достигнуть хотя бы одного группового порога.")

    counts = [0] * len(thresholds)
    counts[0] = thresholds[0]
    remaining = q - counts[0]

    # В стандартном профиле Q=10 хватает, чтобы достичь порога ещё одной группы.
    if len(thresholds) > 1 and remaining >= thresholds[1]:
        counts[1] = thresholds[1]
        remaining -= thresholds[1]

    # Оставшиеся места в контрольном решении заполняем предметами вне групп.
    selected_ungrouped = min(remaining, ungrouped_count)
    remaining -= selected_ungrouped

    # Если Q больше, чем сумма двух порогов и числа свободных предметов,
    # добираем оставшиеся места из уже задействованных групп, затем из следующих.
    for index in list(range(1, len(thresholds))) + [0]:
        if remaining <= 0:
            break
        room = group_sizes[index] - counts[index]
        addition = min(remaining, room)
        counts[index] += addition
        remaining -= addition

    if remaining:
        raise ValueError("Не удалось сформировать контрольный набор ровно из Q предметов.")
    return counts, selected_ungrouped


def _weight_for_witness(
    weights: np.ndarray,
    groups: list[np.ndarray],
    ungrouped_ids: np.ndarray,
    discounts: list[int],
    thresholds: list[int],
    counts: list[int],
    selected_ungrouped: int,
    *,
    choose_heaviest: bool,
) -> float:
    """Посчитать скорректированный вес контрольного набора."""
    total = 0.0
    for ids, discount, threshold, count in zip(groups, discounts, thresholds, counts, strict=True):
        values = np.sort(weights[ids - 1])
        chosen = values[-count:] if choose_heaviest and count else values[:count]
        if count == 0:
            chosen = np.asarray([], dtype=np.int64)
        active_discount = discount if count >= threshold else 0
        total += float(chosen.sum()) * (1.0 - active_discount / 100.0)

    ungrouped_values = np.sort(weights[ungrouped_ids - 1]) if ungrouped_ids.size else np.asarray([], dtype=np.int64)
    if selected_ungrouped:
        chosen_ungrouped = (
            ungrouped_values[-selected_ungrouped:]
            if choose_heaviest
            else ungrouped_values[:selected_ungrouped]
        )
        total += float(chosen_ungrouped.sum())
    return total


def _make_instance(
    n: int, q: int, group_count: int, seed: int
) -> tuple[dict[str, np.ndarray], dict]:
    if n < 1 or not 1 <= q <= n:
        raise ValueError("Требуется 1 <= Q <= n.")
    if group_count not in (2, 3):
        raise ValueError("Для начального набора group_count должен быть 2 или 3.")

    rng = np.random.default_rng(seed)
    thresholds = _choose_thresholds(group_count, rng)
    group_sizes, ungrouped_count = _allocate_group_sizes(n, thresholds, rng)

    item_ids = np.arange(1, n + 1, dtype=np.int64)
    weights = rng.integers(1, 101, size=n, dtype=np.int64)
    utilities = rng.integers(1, 101, size=n, dtype=np.int64)
    shuffled_ids = rng.permutation(item_ids)

    arrays: dict[str, np.ndarray] = {
        "item_ids": item_ids,
        "weights": weights,
        "utilities": utilities,
    }
    groups_meta: list[dict] = []
    group_arrays: list[np.ndarray] = []
    discounts: list[int] = []
    bonuses: list[int] = []
    offset = 0

    for group_id, item_count in enumerate(group_sizes, start=1):
        ids = np.sort(shuffled_ids[offset : offset + item_count]).astype(np.int64)
        offset += item_count
        ids_key = f"group_{group_id:03d}_item_ids"
        arrays[ids_key] = ids
        discount = int(rng.integers(25, 51))
        bonus = int(rng.integers(0, 51))
        discounts.append(discount)
        bonuses.append(bonus)
        group_arrays.append(ids)
        groups_meta.append(
            {
                "id": group_id,
                "item_count": int(item_count),
                "item_ids_key": ids_key,
                "min_selected_for_discount": int(thresholds[group_id - 1]),
                "weight_discount_percent": discount,
                "utility_bonus_percent": bonus,
            }
        )

    ungrouped_ids = np.sort(shuffled_ids[offset:]).astype(np.int64)
    first_group_ids = group_arrays[0]
    first_group_weights = weights[first_group_ids - 1]
    if np.unique(first_group_weights).size == 1:
        first_item_index = int(first_group_ids[0] - 1)
        weights[first_item_index] = 1 if weights[first_item_index] == 100 else int(weights[first_item_index] + 1)
    if len(ungrouped_ids) != ungrouped_count:
        raise RuntimeError("Внутренняя ошибка распределения предметов по группам.")

    witness_counts, witness_ungrouped = _build_witness_counts(
        q, thresholds, group_sizes, ungrouped_count
    )
    light_weight = _weight_for_witness(
        weights, group_arrays, ungrouped_ids, discounts, thresholds,
        witness_counts, witness_ungrouped, choose_heaviest=False,
    )
    heavy_weight = _weight_for_witness(
        weights, group_arrays, ungrouped_ids, discounts, thresholds,
        witness_counts, witness_ungrouped, choose_heaviest=True,
    )
    if heavy_weight <= light_weight:
        # При случайных совпадениях весов создаём строгое различие без изменения
        # исходных диапазонов и самих параметров групп.
        item_with_min = int(np.argmin(weights))
        item_with_max = int(np.argmax(weights))
        if weights[item_with_min] == weights[item_with_max]:
            weights[item_with_max] += 1
        light_weight = _weight_for_witness(
            weights, group_arrays, ungrouped_ids, discounts, thresholds,
            witness_counts, witness_ungrouped, choose_heaviest=False,
        )
        heavy_weight = _weight_for_witness(
            weights, group_arrays, ungrouped_ids, discounts, thresholds,
            witness_counts, witness_ungrouped, choose_heaviest=True,
        )
    if heavy_weight <= light_weight:
        raise RuntimeError("Не удалось сформировать контрольные наборы с разным весом.")
    capacity = light_weight + 0.25 * (heavy_weight - light_weight)

    metadata = {
        "format_version": 4,
        "instance_id": None,
        "n": int(n),
        "target_item_count": int(q),
        "group_count": int(group_count),
        "group_membership_count": int(sum(group_sizes)),
        "ungrouped_item_count": int(ungrouped_count),
        "capacity": float(capacity),
        "seed": int(seed),
        "items": {
            "ids_key": "item_ids",
            "weights_key": "weights",
            "utilities_key": "utilities",
        },
        "groups": groups_meta,
        "generation": {
            "weight_range": [1, 100],
            "utility_range": [1, 100],
            "discount_percent_range": [25, 50],
            "utility_bonus_percent_range": [0, 50],
            "threshold_range": [4, 5],
            "group_membership_overlap": False,
            "ungrouped_items_included": True,
            "capacity_rule": (
                "25 percent of the interval above a low-weight feasible witness with a fixed "
                "group-count distribution and a heavier infeasible witness with the same distribution."
            ),
            "witness_selected_counts_by_group": witness_counts,
            "witness_selected_ungrouped_count": witness_ungrouped,
        },
        "notes": [
            "n is the number of unique items; each item is stored exactly once.",
            "Every item belongs to at most one group; items in no group receive no group effects.",
            "Both the weight discount and utility bonus activate at the same group threshold.",
            "When a threshold is reached, both effects apply to every selected item in that group.",
            "Group size (item_count) and activation threshold are separate values.",
        ],
    }
    return arrays, metadata


def generate_dataset(
    output_dir: str | Path = "data",
    sizes: tuple[int, ...] = DEFAULT_SIZES,
    instances_per_size: int = DEFAULT_INSTANCES_PER_SIZE,
    min_groups: int = DEFAULT_MIN_GROUPS,
    max_groups: int = DEFAULT_MAX_GROUPS,
    seed: int = 42,
    overwrite: bool = True,
    q: int = DEFAULT_Q,
) -> list[Path]:
    """Создать набор экземпляров v4 и индекс manifest.csv."""

    output_dir = Path(output_dir)
    if not sizes or any(int(n) < 1 for n in sizes):
        raise ValueError("Размеры n должны быть положительными.")
    if instances_per_size < 1:
        raise ValueError("instances_per_size должно быть не меньше 1.")
    if not 2 <= min_groups <= max_groups <= 3:
        raise ValueError("Для текущего профиля требуется 2 <= min_groups <= max_groups <= 3.")
    if q < 5:
        raise ValueError("Для начального профиля с порогами 4–5 требуется Q >= 5.")
    if any(n < q for n in sizes):
        raise ValueError(f"Каждый размер n должен быть не меньше Q={q}.")

    output_dir.mkdir(parents=True, exist_ok=True)
    if overwrite:
        for stale_dir in output_dir.glob("n_*"):
            if stale_dir.is_dir():
                shutil.rmtree(stale_dir)
        stale_manifest = output_dir / "manifest.csv"
        if stale_manifest.exists():
            stale_manifest.unlink()

    created: list[Path] = []
    manifest_rows: list[dict[str, object]] = []

    for size_index, n in enumerate(sizes):
        for instance_index in range(1, instances_per_size + 1):
            instance_seed = seed + size_index * instances_per_size + instance_index - 1
            rng = np.random.default_rng(instance_seed + 7_919)
            feasible_max_groups = min(max_groups, (int(n) - 2) // 4)
            if feasible_max_groups < min_groups:
                raise ValueError(
                    f"Для n={n} недостаточно предметов, чтобы создать {min_groups} группы "
                    "с порогами 4–5 и сохранить предметы вне групп."
                )
            group_count = int(rng.integers(min_groups, feasible_max_groups + 1))
            instance_dir = output_dir / f"n_{n}" / f"instance_{instance_index:03d}"
            if instance_dir.exists() and not overwrite:
                raise FileExistsError(f"Каталог уже существует: {instance_dir}")
            instance_dir.mkdir(parents=True, exist_ok=True)

            arrays, metadata = _make_instance(int(n), int(q), group_count, instance_seed)
            metadata["instance_id"] = f"instance_{instance_index:03d}"
            (instance_dir / "meta.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            np.savez_compressed(instance_dir / "data.npz", **arrays)
            created.append(instance_dir)
            manifest_rows.append(
                {
                    "n": int(n),
                    "instance": f"instance_{instance_index:03d}",
                    "target_item_count": int(q),
                    "group_count": group_count,
                    "ungrouped_item_count": metadata["ungrouped_item_count"],
                    "seed": instance_seed,
                    "format_version": 4,
                    "path": instance_dir.as_posix(),
                }
            )

    manifest_path = output_dir / "manifest.csv"
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(manifest_rows[0].keys()))
        writer.writeheader()
        writer.writerows(manifest_rows)

    # Фиксируем контрольные суммы набора, чтобы случайное изменение исходных
    # данных обнаруживалось тестами до запуска алгоритмов.
    checksum_path = output_dir / "checksums.sha256"
    checksum_files = sorted(
        file_path for file_path in output_dir.rglob("*")
        if file_path.is_file() and file_path != checksum_path
    )
    with checksum_path.open("w", encoding="utf-8", newline="\n") as stream:
        for file_path in checksum_files:
            digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
            relative_path = file_path.relative_to(output_dir).as_posix()
            stream.write(f"{digest}  {relative_path}\n")
    return created


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Генератор тестовых экземпляров с пороговыми групповыми эффектами (формат v4)."
    )
    parser.add_argument("--output", default="data", help="Каталог для сохранения экземпляров.")
    parser.add_argument("--sizes", nargs="+", type=int, default=list(DEFAULT_SIZES), help="Число предметов n.")
    parser.add_argument("--instances-per-size", type=int, default=DEFAULT_INSTANCES_PER_SIZE)
    parser.add_argument("--min-groups", type=int, default=DEFAULT_MIN_GROUPS)
    parser.add_argument("--max-groups", type=int, default=DEFAULT_MAX_GROUPS)
    parser.add_argument("--q", type=int, default=DEFAULT_Q, help="Ровно столько предметов выбирается в решении.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-overwrite", action="store_true", help="Не перезаписывать существующие каталоги.")
    args = parser.parse_args()

    created = generate_dataset(
        output_dir=args.output,
        sizes=tuple(args.sizes),
        instances_per_size=args.instances_per_size,
        min_groups=args.min_groups,
        max_groups=args.max_groups,
        q=args.q,
        seed=args.seed,
        overwrite=not args.no_overwrite,
    )
    print(f"Создано экземпляров: {len(created)}")
    print(f"Каталог: {Path(args.output).resolve()}")
    print(f"Индекс: {Path(args.output).resolve() / 'manifest.csv'}")


if __name__ == "__main__":
    main()
