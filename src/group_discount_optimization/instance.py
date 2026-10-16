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
    weights: np.ndarray
    profits: np.ndarray


@dataclass(frozen=True)
class Instance:
    target_item_count: int
    capacity: int
    groups: tuple[Group, ...]
    seed: int | None = None

    @property
    def item_count(self) -> int:
        return sum(group.item_count for group in self.groups)

    @property
    def group_count(self) -> int:
        return len(self.groups)

    @property
    def max_weight(self) -> int:
        """Совместимое имя вместимости рюкзака."""
        return self.capacity

    @property
    def weights(self) -> np.ndarray:
        """Общий массив весов для алгоритмов, которым удобен плоский формат."""
        return np.concatenate([group.weights for group in self.groups])

    @property
    def profits(self) -> np.ndarray:
        """Общий массив полезностей для алгоритмов, которым удобен плоский формат."""
        return np.concatenate([group.profits for group in self.groups])

    @property
    def utilities(self) -> np.ndarray:
        """Алиас для profits: полезность в формулировке новой задачи."""
        return self.profits

    @property
    def group_ids(self) -> np.ndarray:
        """Плоский массив ID групп, соответствующий объединённым массивам."""
        return np.concatenate([
            np.full(group.item_count, group.group_id, dtype=np.int64) for group in self.groups
        ])


def load_instance(path: str | Path) -> Instance:
    """Загрузить экземпляр по каталогу или пути к data.npz.

    В формате v2 каждый список группы физически хранится отдельно в data.npz:
    group_NNN_weights и group_NNN_profits. Также читается старый плоский формат v1.
    """
    path = Path(path)
    instance_dir = path.parent if path.name == "data.npz" else path
    data_path = instance_dir / "data.npz" if path.is_dir() or path.name != "data.npz" else path
    meta_path = instance_dir / "meta.json"
    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        with np.load(data_path, allow_pickle=False) as data:
            if int(metadata.get("format_version", 1)) >= 2:
                groups = tuple(
                    Group(
                        group_id=int(group["id"]),
                        weight_discount_percent=int(group["weight_discount_percent"]),
                        utility_bonus_percent=int(group["utility_bonus_percent"]),
                        item_count=int(group["item_count"]),
                        weights=np.asarray(data[group["weights_key"]], dtype=np.int64),
                        profits=np.asarray(data[group["profits_key"]], dtype=np.int64),
                    )
                    for group in metadata["groups"]
                )
            else:
                required = {"weights", "profits", "group_ids"}
                missing = required.difference(data.files)
                if missing:
                    raise ValueError(f"В '{data_path}' отсутствуют массивы: {', '.join(sorted(missing))}.")
                weights = np.asarray(data["weights"], dtype=np.int64)
                profits = np.asarray(data["profits"], dtype=np.int64)
                group_ids = np.asarray(data["group_ids"], dtype=np.int64)
                if not (weights.ndim == profits.ndim == group_ids.ndim == 1):
                    raise ValueError(f"'{instance_dir}': массивы должны быть одномерными.")
                groups = tuple(
                    Group(
                        group_id=int(group["id"]),
                        weight_discount_percent=int(group["weight_discount_percent"]),
                        utility_bonus_percent=int(group["utility_bonus_percent"]),
                        item_count=int(group["item_count"]),
                        weights=weights[group_ids == int(group["id"])],
                        profits=profits[group_ids == int(group["id"])],
                    )
                    for group in metadata["groups"]
                )
    except (OSError, KeyError, json.JSONDecodeError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("В '"):
            raise
        raise ValueError(f"Не удалось загрузить экземпляр '{instance_dir}': {exc}") from exc

    n = int(metadata["n"])
    q = int(metadata["target_item_count"])
    capacity = int(metadata["capacity"])
    if not groups or sum(group.item_count for group in groups) != n:
        raise ValueError(f"'{instance_dir}': сумма размеров групп не совпадает с n в meta.json.")
    if not 1 <= q <= n:
        raise ValueError(f"'{instance_dir}': target_item_count должен находиться в диапазоне 1..n.")
    if capacity < 0:
        raise ValueError(f"'{instance_dir}': вместимость должна быть неотрицательной.")
    for group in groups:
        if group.weights.ndim != 1 or group.profits.ndim != 1:
            raise ValueError(f"'{instance_dir}': массивы группы должны быть одномерными.")
        if group.weights.size != group.item_count or group.profits.size != group.item_count:
            raise ValueError(f"'{instance_dir}': длины списков группы не совпадают с item_count.")
        if np.any(group.weights <= 0) or np.any(group.profits <= 0):
            raise ValueError(f"'{instance_dir}': веса и полезности должны быть положительными.")
        if not 0 <= group.weight_discount_percent <= 50 or not 0 <= group.utility_bonus_percent <= 50:
            raise ValueError(f"'{instance_dir}': проценты скидок и бонусов должны находиться в диапазоне 0..50.")

    return Instance(q, capacity, groups, metadata.get("seed"))
