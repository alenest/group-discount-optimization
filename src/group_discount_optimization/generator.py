"""Генерация фиксируемых тестовых экземпляров с отдельными списками групп."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

DEFAULT_SIZES = (10, 20, 50, 1000, 5000)
DEFAULT_INSTANCES_PER_SIZE = 5
DEFAULT_MIN_GROUPS = 2
DEFAULT_MAX_GROUPS = 5


def _make_instance(
    n: int, q: int, group_count: int, seed: int
) -> tuple[dict[str, np.ndarray], dict]:
    """Создать экземпляр, в котором у каждой группы собственные массивы."""
    if n < 1:
        raise ValueError("Число предметов n должно быть положительным.")
    if not 1 <= q <= n:
        raise ValueError(f"Q должно быть в диапазоне 1..n (получено Q={q}, n={n}).")
    if not 1 <= group_count <= n:
        raise ValueError("Число групп должно быть в диапазоне 1..n.")

    rng = np.random.default_rng(seed)

    # Сначала гарантируем хотя бы один предмет в каждой группе, затем случайно
    # распределяем оставшиеся предметы. Сумма размеров списков всегда равна n.
    counts = np.ones(group_count, dtype=np.int64)
    if n > group_count:
        counts += rng.multinomial(n - group_count, np.full(group_count, 1 / group_count))
    rng.shuffle(counts)

    arrays: dict[str, np.ndarray] = {}
    groups: list[dict] = []
    adjusted_weights: list[np.ndarray] = []
    for group_id, item_count in enumerate(counts, start=1):
        weights_key = f"group_{group_id:03d}_weights"
        profits_key = f"group_{group_id:03d}_profits"
        weights = rng.integers(1, 101, size=int(item_count), dtype=np.int64)
        profits = rng.integers(1, 101, size=int(item_count), dtype=np.int64)
        discount = int(rng.integers(0, 51))
        bonus = int(rng.integers(0, 51))
        arrays[weights_key] = weights
        arrays[profits_key] = profits
        adjusted_weights.append(weights.astype(np.float64) * (1 - discount / 100))
        groups.append({
            "id": group_id,
            "weight_discount_percent": discount,
            "utility_bonus_percent": bonus,
            "item_count": int(item_count),
            "weights_key": weights_key,
            "profits_key": profits_key,
        })

    all_adjusted_weights = np.concatenate(adjusted_weights)
    min_feasible_weight = float(np.sort(all_adjusted_weights)[:q].sum())
    typical_q_weight = float(np.sort(all_adjusted_weights)[-q:].mean() * q)
    capacity = max(1, math.ceil(max(min_feasible_weight, typical_q_weight * 0.55)))

    metadata = {
        "format_version": 2,
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
            "description": "Каждая группа хранится в собственных массивах weights и profits; ключи указаны в метаданных группы."
        },
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
    q_min: int = 1,
    q_max: int | None = None,
) -> list[Path]:
    """Создать сохранённые экземпляры: n_<size>/instance_NNN/{data.npz,meta.json}."""
    output_dir = Path(output_dir)
    if instances_per_size < 1:
        raise ValueError("instances_per_size должно быть не меньше 1.")
    if not sizes or any(n < 1 for n in sizes):
        raise ValueError("Размеры должны быть положительными числами.")
    if min_groups < 1 or max_groups < min_groups:
        raise ValueError("Требуется 1 <= min_groups <= max_groups.")
    if q_min < 1 or (q_max is not None and q_max < q_min):
        raise ValueError("Требуется 1 <= q_min <= q_max.")

    created: list[Path] = []
    manifest_rows = ["size,instance,n,target_item_count,group_count,seed,format"]
    for size_index, n in enumerate(sizes):
        upper_q = n if q_max is None else min(n, q_max)
        lower_q = min(q_min, upper_q)
        upper_groups = min(max_groups, n)
        lower_groups = min(min_groups, upper_groups)
        if upper_groups < 1:
            raise ValueError(f"Для n={n} нельзя создать хотя бы одну группу.")

        # Без повторов, если диапазон позволяет: Q и число групп реально меняются
        # между экземплярами одного размера, а не только потенциально могут меняться.
        q_rng = np.random.default_rng(seed + size_index * 1_000_003 + 17)
        group_rng = np.random.default_rng(seed + size_index * 1_000_003 + 29)
        q_values = q_rng.choice(
            np.arange(lower_q, upper_q + 1),
            size=instances_per_size,
            replace=(instances_per_size > upper_q - lower_q + 1),
        )
        group_values = group_rng.choice(
            np.arange(lower_groups, upper_groups + 1),
            size=instances_per_size,
            replace=(instances_per_size > upper_groups - lower_groups + 1),
        )

        for instance_index in range(1, instances_per_size + 1):
            instance_seed = seed + size_index * instances_per_size + instance_index - 1
            q = int(q_values[instance_index - 1])
            group_count = int(group_values[instance_index - 1])
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
    parser = argparse.ArgumentParser(description="Генератор экземпляров задачи групповых скидок.")
    parser.add_argument("--output", default="data", help="Каталог для готовых экземпляров.")
    parser.add_argument("--sizes", nargs="+", type=int, default=list(DEFAULT_SIZES), help="Общее число предметов n в экземпляре.")
    parser.add_argument("--instances-per-size", type=int, default=DEFAULT_INSTANCES_PER_SIZE)
    parser.add_argument("--min-groups", type=int, default=DEFAULT_MIN_GROUPS)
    parser.add_argument("--max-groups", type=int, default=DEFAULT_MAX_GROUPS)
    parser.add_argument("--q-min", type=int, default=1, help="Минимальное число выбираемых предметов Q.")
    parser.add_argument("--q-max", type=int, default=None, help="Максимальное Q; по умолчанию равно n для каждого размера.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-overwrite", action="store_true", help="Не перезаписывать существующие экземпляры.")
    args = parser.parse_args()
    created = generate_dataset(
        output_dir=args.output,
        sizes=tuple(args.sizes),
        instances_per_size=args.instances_per_size,
        min_groups=args.min_groups,
        max_groups=args.max_groups,
        q_min=args.q_min,
        q_max=args.q_max,
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
