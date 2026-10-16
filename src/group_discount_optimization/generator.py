"""Генерация фиксируемых тестовых экземпляров в формате data.npz + meta.json."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

DEFAULT_SIZES = (10, 20, 50, 1000, 5000)
DEFAULT_INSTANCES_PER_SIZE = 5
DEFAULT_GROUP_COUNT = 3


def _make_instance(n: int, q: int, group_count: int, seed: int) -> tuple[dict[str, np.ndarray], dict]:
    if n < 1:
        raise ValueError("Число предметов n должно быть положительным.")
    if not 1 <= q <= n:
        raise ValueError(f"Q должно быть в диапазоне 1..n (получено Q={q}, n={n}).")
    if not 1 <= group_count <= n:
        raise ValueError("Число групп должно быть в диапазоне 1..n.")

    rng = np.random.default_rng(seed)
    weights = rng.integers(1, 101, size=n, dtype=np.int64)
    profits = rng.integers(1, 101, size=n, dtype=np.int64)

    # Каждая группа получает хотя бы один предмет; затем распределение перемешивается.
    group_ids = np.arange(n, dtype=np.int64) % group_count + 1
    rng.shuffle(group_ids)

    groups = []
    discounts: dict[int, int] = {}
    bonuses: dict[int, int] = {}
    adjusted_weights = np.empty(n, dtype=np.float64)
    for group_id in range(1, group_count + 1):
        discount = int(rng.integers(0, 51))
        bonus = int(rng.integers(0, 51))
        discounts[group_id] = discount
        bonuses[group_id] = bonus
        adjusted_weights[group_ids == group_id] = weights[group_ids == group_id] * (1 - discount / 100)
        groups.append({
            "id": group_id,
            "weight_discount_percent": discount,
            "utility_bonus_percent": bonus,
            "item_count": int(np.count_nonzero(group_ids == group_id)),
        })

    # Вместимость делает экземпляр допустимым (помещаются хотя бы Q самых лёгких
    # предметов после скидок), но не позволяет безусловно выбрать любые Q предметов.
    min_feasible_weight = float(np.sort(adjusted_weights)[:q].sum())
    typical_q_weight = float(np.sort(adjusted_weights)[-q:].mean() * q)
    capacity = max(1, math.ceil(max(min_feasible_weight, typical_q_weight * 0.55)))

    metadata = {
        "format_version": 1,
        "n": n,
        "target_item_count": q,
        "group_count": group_count,
        "capacity": capacity,
        "seed": seed,
        "weight_range": [1, 100],
        "utility_range": [1, 100],
        "discount_percent_range": [0, 50],
        "bonus_percent_range": [0, 50],
        "groups": groups,
        "arrays": {
            "weights": "Исходные целочисленные веса предметов.",
            "profits": "Исходная полезность предметов (ключ profits сохранён по аналогии со старым репозиторием).",
            "group_ids": "ID группы для каждого предмета; индексы массивов соответствуют друг другу.",
        },
    }
    arrays = {"weights": weights, "profits": profits, "group_ids": group_ids}
    return arrays, metadata


def generate_dataset(
    output_dir: str | Path = "data",
    sizes: tuple[int, ...] = DEFAULT_SIZES,
    instances_per_size: int = DEFAULT_INSTANCES_PER_SIZE,
    group_count: int = DEFAULT_GROUP_COUNT,
    seed: int = 42,
    overwrite: bool = True,
) -> list[Path]:
    """Создать готовые экземпляры: n_<size>/instance_NNN/{data.npz, meta.json}."""
    output_dir = Path(output_dir)
    if instances_per_size < 1:
        raise ValueError("instances_per_size должно быть не меньше 1.")
    if not sizes or any(n < 1 for n in sizes):
        raise ValueError("Размеры должны быть положительными числами.")

    created: list[Path] = []
    manifest_rows = ["size,instance,n,target_item_count,group_count,seed,format"]
    for size_index, n in enumerate(sizes):
        q = 5 if n == 10 else min(10, n)
        for instance_index in range(1, instances_per_size + 1):
            instance_seed = seed + size_index * instances_per_size + instance_index - 1
            instance_dir = output_dir / f"n_{n}" / f"instance_{instance_index:03d}"
            if instance_dir.exists() and not overwrite:
                raise FileExistsError(f"Каталог уже существует: {instance_dir}")
            instance_dir.mkdir(parents=True, exist_ok=True)
            arrays, metadata = _make_instance(n, q, group_count, instance_seed)
            metadata["instance_id"] = f"instance_{instance_index:03d}"
            np.savez_compressed(instance_dir / "data.npz", **arrays)
            (instance_dir / "meta.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            created.append(instance_dir)
            manifest_rows.append(
                f"{n},instance_{instance_index:03d},{n},{q},{group_count},{instance_seed},npz+json"
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.csv").write_text("\n".join(manifest_rows) + "\n", encoding="utf-8")
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Генератор сырых тестовых экземпляров задачи групповых скидок.")
    parser.add_argument("--output", default="data", help="Каталог для готовых экземпляров.")
    parser.add_argument("--sizes", nargs="+", type=int, default=list(DEFAULT_SIZES), help="Размеры n.")
    parser.add_argument("--instances-per-size", type=int, default=DEFAULT_INSTANCES_PER_SIZE)
    parser.add_argument("--groups", type=int, default=DEFAULT_GROUP_COUNT)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-overwrite", action="store_true", help="Не перезаписывать существующие экземпляры.")
    args = parser.parse_args()
    created = generate_dataset(
        output_dir=args.output,
        sizes=tuple(args.sizes),
        instances_per_size=args.instances_per_size,
        group_count=args.groups,
        seed=args.seed,
        overwrite=not args.no_overwrite,
    )
    print(f"Создано экземпляров: {len(created)}")
    print(f"Каталог: {Path(args.output).resolve()}")
    for path in created:
        print(f"- {path / 'data.npz'}")
        print(f"  {path / 'meta.json'}")


if __name__ == "__main__":
    main()
