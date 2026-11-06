"""Генератор небольшого набора тестов с пороговыми групповыми скидками."""

from __future__ import annotations

import argparse
import csv
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


def _choose_thresholds(n: int, group_count: int, rng: np.random.Generator) -> list[int]:
    if group_count == 2:
        return [int(value) for value in rng.integers(4, 6, size=2)]
    if group_count == 3 and n == 12:
        return [4, 4, 4]
    if group_count == 3:
        # Две группы с порогом 4 можно активировать при Q=10;
        # у третьей порог 5, поэтому одновременно активировать все три нельзя.
        return [4, 4, 5]
    raise ValueError("Для начального набора поддерживаются 2 или 3 группы.")


def _allocate_group_sizes(n: int, thresholds: list[int], rng: np.random.Generator) -> list[int]:
    base = np.asarray(thresholds, dtype=np.int64)
    remaining = n - int(base.sum())
    if remaining < 0:
        raise ValueError("Сумма порогов превышает число предметов; невозможно создать группы.")
    if remaining:
        base += rng.multinomial(remaining, np.full(len(base), 1.0 / len(base)))
    return [int(value) for value in base]


def _build_witness_counts(
    q: int, thresholds: list[int], group_sizes: list[int], rng: np.random.Generator
) -> list[int]:
    """Распределить Q выбранных предметов, гарантированно достигнув порога хотя бы одной группы."""
    k = len(thresholds)
    order = [int(value) for value in rng.permutation(k)]
    counts = np.zeros(k, dtype=np.int64)
    first = order[0]
    if q < thresholds[first]:
        raise ValueError("Q должен позволять достигнуть хотя бы одного группового порога.")
    counts[first] = thresholds[first]
    remaining = q - int(counts.sum())

    # Сначала заполняем другие группы, затем при необходимости продолжаем первую.
    for index in order[1:] + [first]:
        if remaining <= 0:
            break
        available = group_sizes[index] - int(counts[index])
        addition = min(remaining, available)
        counts[index] += addition
        remaining -= addition

    if remaining:
        raise ValueError("Не удалось сформировать контрольный набор ровно из Q предметов.")
    return [int(value) for value in counts]


def _effective_weight_for_counts(
    weights: np.ndarray,
    group_ids: list[np.ndarray],
    discounts: list[int],
    thresholds: list[int],
    counts: list[int],
    *,
    choose_heaviest: bool,
) -> float:
    total = 0.0
    for ids, discount, threshold, count in zip(
        group_ids, discounts, thresholds, counts, strict=True
    ):
        group_weights = weights[ids - 1]
        ordered = np.sort(group_weights)
        chosen = (ordered[-count:] if count else np.asarray([], dtype=np.int64)) if choose_heaviest else ordered[:count]
        applied_discount = discount if count >= threshold else 0
        total += float(chosen.sum()) * (1.0 - applied_discount / 100.0)
    return total


def _make_instance(n: int, q: int, group_count: int, seed: int) -> tuple[dict[str, np.ndarray], dict]:
    if n < 1 or not 1 <= q <= n:
        raise ValueError("Требуется 1 <= Q <= n.")
    if group_count not in (2, 3):
        raise ValueError("Для начального набора group_count должен быть 2 или 3.")

    rng = np.random.default_rng(seed)
    thresholds = _choose_thresholds(n, group_count, rng)
    group_sizes = _allocate_group_sizes(n, thresholds, rng)

    item_ids = np.arange(1, n + 1, dtype=np.int64)
    weights = rng.integers(1, 101, size=n, dtype=np.int64)
    utilities = rng.integers(1, 101, size=n, dtype=np.int64)
    shuffled_ids = rng.permutation(item_ids)

    arrays: dict[str, np.ndarray] = {
        "item_ids": item_ids,
        "weights": weights,
        "utilities": utilities,
    }
    groups: list[dict] = []
    group_item_ids: list[np.ndarray] = []
    discounts: list[int] = []
    bonuses: list[int] = []
    offset = 0

    for group_id, item_count in enumerate(group_sizes, start=1):
        ids = np.sort(shuffled_ids[offset : offset + item_count]).astype(np.int64)
        offset += item_count
        item_ids_key = f"group_{group_id:03d}_item_ids"
        arrays[item_ids_key] = ids
        discount = int(rng.integers(25, 51))
        bonus = 0  # На первом наборе изолируем влияние именно весовой скидки.
        discounts.append(discount)
        bonuses.append(bonus)
        group_item_ids.append(ids)
        groups.append(
            {
                "id": group_id,
                "item_count": int(item_count),
                "item_ids_key": item_ids_key,
                "min_selected_for_discount": int(thresholds[group_id - 1]),
                "weight_discount_percent": discount,
                "utility_bonus_percent": bonus,
            }
        )

    witness_counts = _build_witness_counts(q, thresholds, group_sizes, rng)
    light_weight = _effective_weight_for_counts(
        weights, group_item_ids, discounts, thresholds, witness_counts, choose_heaviest=False
    )
    heavy_weight = _effective_weight_for_counts(
        weights, group_item_ids, discounts, thresholds, witness_counts, choose_heaviest=True
    )
    # Есть заведомо допустимый контрольный набор (из лёгких предметов),
    # но набор из самых тяжёлых предметов при том же распределении по группам
    # не помещается. Это создаёт реальное ограничение вместимости.
    if heavy_weight > light_weight + 1e-9:
        capacity = math.ceil(light_weight + 0.25 * (heavy_weight - light_weight))
    else:
        capacity = math.ceil(light_weight)

    metadata = {
        "format_version": 3,
        "instance_id": None,
        "n": int(n),
        "target_item_count": int(q),
        "group_count": int(group_count),
        "group_membership_count": int(sum(group_sizes)),
        "capacity": int(capacity),
        "seed": int(seed),
        "items": {
            "ids_key": "item_ids",
            "weights_key": "weights",
            "utilities_key": "utilities",
        },
        "groups": groups,
        "generation": {
            "weight_range": [1, 100],
            "utility_range": [1, 100],
            "discount_percent_range": [25, 50],
            "utility_bonus_percent_range": [0, 0],
            "threshold_range": [4, 5],
            "group_membership_overlap": False,
            "capacity_rule": "Between a low-weight feasible witness and a high-weight witness with the same per-group selection counts.",
            "witness_selected_counts_by_group": witness_counts,
        },
        "notes": [
            "n is the number of unique items, not the sum of group item_count values.",
            "Each item has one stable item_id and is stored once.",
            "Groups refer to items by item_id; the format permits overlapping memberships.",
            "This initial generated set uses disjoint groups to isolate threshold discount behavior.",
            "The overlap discount-combination rule is not set; see docs/mathematical_model.md.",
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
    """Создать готовые экземпляры формата v3 и manifest.csv."""

    output_dir = Path(output_dir)
    if not sizes or any(int(n) < 1 for n in sizes):
        raise ValueError("Размеры n должны быть положительными.")
    if instances_per_size < 1:
        raise ValueError("instances_per_size должно быть не меньше 1.")
    if not 2 <= min_groups <= max_groups <= 3:
        raise ValueError("Для текущего набора требуется 2 <= min_groups <= max_groups <= 3.")
    if q < 5:
        raise ValueError("Для проверки порогов 4–5 в начальном наборе требуется Q >= 5.")
    if any(n < q for n in sizes):
        raise ValueError(f"Каждый размер n должен быть не меньше Q={q}.")

    output_dir.mkdir(parents=True, exist_ok=True)
    if overwrite:
        # Удаляем устаревшие каталоги экземпляров (например, старые n_1000/n_5000),
        # чтобы после смены набора в data/ не оставались данные прежней модели.
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
            group_count = int(rng.integers(min_groups, max_groups + 1))
            # На n=12 три группы возможны только с минимальными порогами 4/4/4.
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
                    "seed": instance_seed,
                    "format_version": 3,
                    "path": str(instance_dir.as_posix()),
                }
            )

    manifest_path = output_dir / "manifest.csv"
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(manifest_rows[0].keys()))
        writer.writeheader()
        writer.writerows(manifest_rows)
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Генератор экземпляров с пороговыми групповыми скидками.")
    parser.add_argument("--output", default="data", help="Каталог для сохранения экземпляров.")
    parser.add_argument("--sizes", nargs="+", type=int, default=list(DEFAULT_SIZES), help="Количество уникальных предметов n.")
    parser.add_argument("--instances-per-size", type=int, default=DEFAULT_INSTANCES_PER_SIZE)
    parser.add_argument("--min-groups", type=int, default=DEFAULT_MIN_GROUPS)
    parser.add_argument("--max-groups", type=int, default=DEFAULT_MAX_GROUPS)
    parser.add_argument("--q", type=int, default=DEFAULT_Q, help="Точное количество предметов, выбираемых из всех групп.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-overwrite", action="store_true", help="Не перезаписывать существующие каталоги экземпляров.")
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
