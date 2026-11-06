"""Модели предметов и групп, а также загрузка экземпляров формата v3."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np


@dataclass(frozen=True, slots=True)
class Item:
    """Уникальный предмет. Один и тот же Item может входить в несколько групп."""

    item_id: int
    weight: int
    utility: int


@dataclass(frozen=True, slots=True)
class Group:
    """Группа ссылается на предметы по ID; списки разных групп могут пересекаться."""

    group_id: int
    item_ids: tuple[int, ...]
    min_selected_for_discount: int
    weight_discount_percent: int
    utility_bonus_percent: int = 0

    @property
    def item_count(self) -> int:
        """Число предметов, перечисленных в этой группе (не порог скидки)."""
        return len(self.item_ids)


@dataclass(frozen=True, slots=True)
class Instance:
    """Полный экземпляр: уникальные предметы, группы и ограничения рюкзака."""

    items: tuple[Item, ...]
    groups: tuple[Group, ...]
    target_item_count: int
    capacity: float
    seed: int | None = None
    instance_id: str | None = None

    @property
    def item_count(self) -> int:
        """Количество уникальных предметов n, без повторного счёта по группам."""
        return len(self.items)

    @property
    def n(self) -> int:
        return self.item_count

    @property
    def group_count(self) -> int:
        return len(self.groups)

    @property
    def group_membership_count(self) -> int:
        """Сумма размеров списков групп; может быть больше n при пересечениях."""
        return sum(group.item_count for group in self.groups)

    @property
    def has_overlapping_groups(self) -> bool:
        seen: set[int] = set()
        for group in self.groups:
            current = set(group.item_ids)
            if seen.intersection(current):
                return True
            seen.update(current)
        return False

    @property
    def items_by_id(self) -> Mapping[int, Item]:
        return {item.item_id: item for item in self.items}

    @property
    def max_weight(self) -> float:
        """Совместимое имя вместимости рюкзака."""
        return self.capacity


def load_instance(path: str | Path) -> Instance:
    """Загрузить экземпляр v3 по каталогу экземпляра или пути к data.npz.

    В отличие от прежнего формата, предметы хранятся один раз в общих массивах
    item_ids/weights/utilities, а группы содержат только ссылки item_ids.
    Старые версии v1/v2 намеренно не преобразуются автоматически: в них скидка
    не имела пороговой семантики, поэтому такое преобразование меняло бы смысл.
    """

    path = Path(path)
    if path.is_file() and path.name == "data.npz":
        instance_dir = path.parent
        data_path = path
    else:
        instance_dir = path
        data_path = instance_dir / "data.npz"
    meta_path = instance_dir / "meta.json"

    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        version = int(metadata.get("format_version", 1))
        if version != 3:
            raise ValueError(
                f"Неподдерживаемая версия данных: {version}. Ожидался формат v3 "
                "с уникальными ID предметов и порогами скидок. Старые данные "
                "нужно пересоздать генератором v3."
            )

        with np.load(data_path, allow_pickle=False) as arrays:
            required_keys = {
                metadata["items"]["ids_key"],
                metadata["items"]["weights_key"],
                metadata["items"]["utilities_key"],
            }
            missing = required_keys.difference(arrays.files)
            if missing:
                raise ValueError(f"В data.npz отсутствуют массивы: {', '.join(sorted(missing))}.")

            item_ids = np.asarray(arrays[metadata["items"]["ids_key"]], dtype=np.int64)
            weights = np.asarray(arrays[metadata["items"]["weights_key"]], dtype=np.int64)
            utilities = np.asarray(arrays[metadata["items"]["utilities_key"]], dtype=np.int64)
            if not (item_ids.ndim == weights.ndim == utilities.ndim == 1):
                raise ValueError("Массивы предметов должны быть одномерными.")
            if not (item_ids.size == weights.size == utilities.size):
                raise ValueError("Массивы ID, весов и полезностей имеют разную длину.")

            items = tuple(
                Item(int(item_id), int(weight), int(utility))
                for item_id, weight, utility in zip(item_ids, weights, utilities, strict=True)
            )

            groups_list: list[Group] = []
            for entry in metadata["groups"]:
                key = entry["item_ids_key"]
                if key not in arrays.files:
                    raise ValueError(f"В data.npz отсутствует список предметов группы: {key}.")
                group_item_ids = np.asarray(arrays[key], dtype=np.int64)
                if group_item_ids.ndim != 1:
                    raise ValueError(f"Список предметов группы {entry['id']} должен быть одномерным.")
                if int(entry["item_count"]) != int(group_item_ids.size):
                    raise ValueError(
                        f"Размер списка группы {entry['id']} не совпадает с item_count в meta.json."
                    )
                groups_list.append(
                    Group(
                        group_id=int(entry["id"]),
                        item_ids=tuple(int(value) for value in group_item_ids),
                        min_selected_for_discount=int(entry["min_selected_for_discount"]),
                        weight_discount_percent=int(entry["weight_discount_percent"]),
                        utility_bonus_percent=int(entry.get("utility_bonus_percent", 0)),
                    )
                )
            groups = tuple(groups_list)

    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Не удалось загрузить экземпляр '{instance_dir}': {exc}") from exc

    _validate_instance_parts(
        instance_dir=instance_dir,
        items=items,
        groups=groups,
        metadata=metadata,
    )

    return Instance(
        items=items,
        groups=groups,
        target_item_count=int(metadata["target_item_count"]),
        capacity=float(metadata["capacity"]),
        seed=None if metadata.get("seed") is None else int(metadata["seed"]),
        instance_id=metadata.get("instance_id"),
    )


def _validate_instance_parts(
    *, instance_dir: Path, items: tuple[Item, ...], groups: tuple[Group, ...], metadata: dict
) -> None:
    n = int(metadata["n"])
    q = int(metadata["target_item_count"])
    capacity = float(metadata["capacity"])

    if n != len(items):
        raise ValueError(f"'{instance_dir}': n не совпадает с числом уникальных предметов.")
    if len({item.item_id for item in items}) != len(items):
        raise ValueError(f"'{instance_dir}': ID предметов должны быть уникальными.")
    if any(item.item_id <= 0 for item in items):
        raise ValueError(f"'{instance_dir}': ID предметов должны быть положительными.")
    if not 1 <= q <= n:
        raise ValueError(f"'{instance_dir}': Q должно находиться в диапазоне 1..n.")
    if not np.isfinite(capacity) or capacity < 0:
        raise ValueError(f"'{instance_dir}': вместимость должна быть конечной и неотрицательной.")
    if not groups:
        raise ValueError(f"'{instance_dir}': в экземпляре должна быть хотя бы одна группа.")
    if len({group.group_id for group in groups}) != len(groups):
        raise ValueError(f"'{instance_dir}': ID групп должны быть уникальными.")
    if int(metadata.get("group_count", len(groups))) != len(groups):
        raise ValueError(f"'{instance_dir}': group_count не совпадает с числом групп в meta.json.")
    if any(group.group_id <= 0 for group in groups):
        raise ValueError(f"'{instance_dir}': ID групп должны быть положительными.")
    declared_memberships = metadata.get("group_membership_count")
    if declared_memberships is not None and int(declared_memberships) != sum(group.item_count for group in groups):
        raise ValueError(f"'{instance_dir}': group_membership_count не совпадает с данными групп.")
    if any(item.weight <= 0 or item.utility <= 0 for item in items):
        raise ValueError(f"'{instance_dir}': веса и полезности должны быть положительными.")

    known_ids = {item.item_id for item in items}
    for group in groups:
        if not group.item_ids:
            raise ValueError(f"'{instance_dir}': группа {group.group_id} не содержит предметов.")
        if len(set(group.item_ids)) != group.item_count:
            raise ValueError(f"'{instance_dir}': в группе {group.group_id} повторяются ID предметов.")
        unknown_ids = set(group.item_ids).difference(known_ids)
        if unknown_ids:
            raise ValueError(
                f"'{instance_dir}': группа {group.group_id} ссылается на неизвестные ID: {sorted(unknown_ids)}."
            )
        if not 1 <= group.min_selected_for_discount <= group.item_count:
            raise ValueError(
                f"'{instance_dir}': порог группы {group.group_id} должен быть в диапазоне "
                f"1..{group.item_count}."
            )
        if not 0 <= group.weight_discount_percent <= 50:
            raise ValueError(f"'{instance_dir}': скидка группы {group.group_id} должна быть в диапазоне 0..50%." )
        if not 0 <= group.utility_bonus_percent <= 50:
            raise ValueError(f"'{instance_dir}': бонус группы {group.group_id} должен быть в диапазоне 0..50%." )
