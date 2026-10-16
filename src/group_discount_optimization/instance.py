"""Загрузка готовых экземпляров из data.npz и meta.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class Group:
    group_id: int
    weight_discount_percent: int
    utility_bonus_percent: int
    item_count: int


@dataclass(frozen=True)
class Instance:
    weights: np.ndarray
    profits: np.ndarray
    group_ids: np.ndarray
    target_item_count: int
    capacity: int
    groups: tuple[Group, ...]
    seed: int | None = None

    @property
    def item_count(self) -> int:
        return int(self.weights.size)

    @property
    def group_count(self) -> int:
        return len(self.groups)

    @property
    def max_weight(self) -> int:
        """Совместимое имя вместимости рюкзака."""
        return self.capacity

    @property
    def utilities(self) -> np.ndarray:
        """Алиас для profits: полезность в формулировке новой задачи."""
        return self.profits


def load_instance(path: str | Path) -> Instance:
    """Загрузить экземпляр по каталогу или пути к data.npz.

    Ожидается data.npz с массивами weights, profits, group_ids и соседний meta.json.
    Для обратной совместимости с формулировкой задачи массив полезности называется
    profits, как в старом проекте.
    """
    path = Path(path)
    instance_dir = path.parent if path.name == "data.npz" else path
    data_path = instance_dir / "data.npz" if path.is_dir() or path.name != "data.npz" else path
    meta_path = instance_dir / "meta.json"
    try:
        with np.load(data_path, allow_pickle=False) as data:
            required = {"weights", "profits", "group_ids"}
            missing = required.difference(data.files)
            if missing:
                raise ValueError(f"В '{data_path}' отсутствуют массивы: {', '.join(sorted(missing))}.")
            weights = np.asarray(data["weights"], dtype=np.int64)
            profits = np.asarray(data["profits"], dtype=np.int64)
            group_ids = np.asarray(data["group_ids"], dtype=np.int64)
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("В '"):
            raise
        raise ValueError(f"Не удалось загрузить экземпляр '{instance_dir}': {exc}") from exc

    if weights.ndim != 1 or profits.ndim != 1 or group_ids.ndim != 1:
        raise ValueError(f"'{instance_dir}': массивы должны быть одномерными.")
    if not (weights.size == profits.size == group_ids.size == metadata.get("n")):
        raise ValueError(f"'{instance_dir}': длины массивов не соответствуют n в meta.json.")
    n = int(weights.size)
    q = int(metadata["target_item_count"])
    capacity = int(metadata["capacity"])
    if not 1 <= q <= n:
        raise ValueError(f"'{instance_dir}': target_item_count должен находиться в диапазоне 1..n.")
    if capacity < 0 or np.any(weights <= 0) or np.any(profits <= 0):
        raise ValueError(f"'{instance_dir}': вместимость должна быть неотрицательной, веса и полезности — положительными.")

    groups = tuple(
        Group(
            group_id=int(group["id"]),
            weight_discount_percent=int(group["weight_discount_percent"]),
            utility_bonus_percent=int(group["utility_bonus_percent"]),
            item_count=int(group["item_count"]),
        )
        for group in metadata["groups"]
    )
    expected_ids = {group.group_id for group in groups}
    if set(map(int, np.unique(group_ids))) != expected_ids:
        raise ValueError(f"'{instance_dir}': ID групп в массивах не совпадают с meta.json.")
    if any(not 0 <= g.weight_discount_percent <= 50 or not 0 <= g.utility_bonus_percent <= 50 for g in groups):
        raise ValueError(f"'{instance_dir}': проценты скидок и бонусов должны находиться в диапазоне 0..50.")
    if any(int(np.count_nonzero(group_ids == g.group_id)) != g.item_count for g in groups):
        raise ValueError(f"'{instance_dir}': число предметов в группе не совпадает с meta.json.")

    return Instance(weights, profits, group_ids, q, capacity, groups, metadata.get("seed"))
