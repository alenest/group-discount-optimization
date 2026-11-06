"""Модели предметов и групп, загрузка и проверка готовых экземпляров v4."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np


@dataclass(frozen=True, slots=True)
class Item:
    """Уникальный предмет с постоянным ID, исходным весом и полезностью."""

    item_id: int
    weight: int
    utility: int


@dataclass(frozen=True, slots=True)
class Group:
    """Группа с непересекающимся набором ID и порогом активации эффектов."""

    group_id: int
    item_ids: tuple[int, ...]
    min_selected_for_discount: int
    weight_discount_percent: int
    utility_bonus_percent: int = 0

    @property
    def item_count(self) -> int:
        """Число предметов в группе; это не порог активации."""
        return len(self.item_ids)


@dataclass(frozen=True, slots=True)
class Instance:
    """Экземпляр задачи: уникальные предметы, группы и ограничения рюкзака."""

    items: tuple[Item, ...]
    groups: tuple[Group, ...]
    target_item_count: int
    capacity: float
    seed: int | None = None
    instance_id: str | None = None

    def __post_init__(self) -> None:
        _validate_instance(self)

    @property
    def n(self) -> int:
        return len(self.items)

    @property
    def item_count(self) -> int:
        """Количество уникальных предметов n."""
        return self.n

    @property
    def group_count(self) -> int:
        return len(self.groups)

    @property
    def group_membership_count(self) -> int:
        """Число предметов, состоящих в группах; не включает предметы вне групп."""
        return sum(group.item_count for group in self.groups)

    @property
    def ungrouped_item_ids(self) -> tuple[int, ...]:
        """ID предметов, не принадлежащих ни одной группе."""
        grouped = {item_id for group in self.groups for item_id in group.item_ids}
        return tuple(item.item_id for item in self.items if item.item_id not in grouped)

    @property
    def ungrouped_item_count(self) -> int:
        return self.n - self.group_membership_count

    @property
    def items_by_id(self) -> Mapping[int, Item]:
        return {item.item_id: item for item in self.items}

    @property
    def max_weight(self) -> float:
        """Совместимое имя вместимости рюкзака."""
        return self.capacity


def _validate_instance(instance: Instance) -> None:
    """Проверить ограничения модели независимо от способа создания экземпляра."""
    if not instance.items:
        raise ValueError("Экземпляр должен содержать хотя бы один предмет.")
    item_ids = [item.item_id for item in instance.items]
    if any(item_id <= 0 for item_id in item_ids):
        raise ValueError("ID предметов должны быть положительными.")
    if len(set(item_ids)) != len(item_ids):
        raise ValueError("ID предметов должны быть уникальными.")
    if any(item.weight <= 0 or item.utility <= 0 for item in instance.items):
        raise ValueError("Исходные веса и полезности предметов должны быть положительными.")

    if not 1 <= instance.target_item_count <= len(instance.items):
        raise ValueError("target_item_count должен находиться в диапазоне 1..n.")
    if not math.isfinite(float(instance.capacity)) or instance.capacity < 0:
        raise ValueError("Вместимость должна быть конечным неотрицательным числом.")
    if not instance.groups:
        raise ValueError("В экземпляре должна быть хотя бы одна группа.")

    known_item_ids = set(item_ids)
    group_ids = [group.group_id for group in instance.groups]
    if any(group_id <= 0 for group_id in group_ids):
        raise ValueError("ID групп должны быть положительными.")
    if len(set(group_ids)) != len(group_ids):
        raise ValueError("ID групп должны быть уникальными.")

    membership_owner: dict[int, int] = {}
    for group in instance.groups:
        if not group.item_ids:
            raise ValueError(f"Группа {group.group_id} не должна быть пустой.")
        if len(set(group.item_ids)) != group.item_count:
            raise ValueError(f"В группе {group.group_id} повторяются ID предметов.")
        unknown = set(group.item_ids) - known_item_ids
        if unknown:
            raise ValueError(
                f"Группа {group.group_id} ссылается на неизвестные ID предметов: {sorted(unknown)}."
            )
        if not 1 <= group.min_selected_for_discount <= group.item_count:
            raise ValueError(
                f"Порог группы {group.group_id} должен находиться в диапазоне "
                f"1..{group.item_count}."
            )
        if not 0 <= group.weight_discount_percent <= 50:
            raise ValueError(f"Скидка группы {group.group_id} должна быть в диапазоне 0..50%.")
        if not 0 <= group.utility_bonus_percent <= 50:
            raise ValueError(f"Бонус группы {group.group_id} должен быть в диапазоне 0..50%.")
        for item_id in group.item_ids:
            previous_group = membership_owner.get(item_id)
            if previous_group is not None:
                raise ValueError(
                    f"Предмет {item_id} одновременно входит в группы {previous_group} и "
                    f"{group.group_id}; в текущей модели пересечения групп запрещены."
                )
            membership_owner[item_id] = group.group_id


def load_instance(path: str | Path) -> Instance:
    """Загрузить экземпляр формата v4 по каталогу или пути к data.npz.

    Все предметы хранятся один раз в общих массивах item_ids/weights/utilities.
    У каждой группы есть отдельный список ссылок на ID предметов. Списки групп
    не пересекаются; предметы, не перечисленные ни в одном списке, не входят
    ни в одну группу и не получают групповых эффектов.
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
        if version != 4:
            raise ValueError(
                f"Неподдерживаемая версия данных: {version}. Ожидался формат v4 "
                "с пороговой активацией обоих эффектов и непересекающимися группами."
            )

        items_meta = metadata["items"]
        with np.load(data_path, allow_pickle=False) as arrays:
            item_keys = (
                items_meta["ids_key"],
                items_meta["weights_key"],
                items_meta["utilities_key"],
            )
            missing = set(item_keys).difference(arrays.files)
            if missing:
                raise ValueError(f"В data.npz отсутствуют массивы: {', '.join(sorted(missing))}.")

            item_ids = np.asarray(arrays[item_keys[0]], dtype=np.int64)
            weights = np.asarray(arrays[item_keys[1]], dtype=np.int64)
            utilities = np.asarray(arrays[item_keys[2]], dtype=np.int64)
            if not (item_ids.ndim == weights.ndim == utilities.ndim == 1):
                raise ValueError("Массивы ID, весов и полезностей должны быть одномерными.")
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
                    raise ValueError(f"В data.npz отсутствует список ID группы {entry['id']}: {key}.")
                group_item_ids = np.asarray(arrays[key], dtype=np.int64)
                if group_item_ids.ndim != 1:
                    raise ValueError(f"Список ID группы {entry['id']} должен быть одномерным.")
                if int(entry["item_count"]) != int(group_item_ids.size):
                    raise ValueError(
                        f"Число предметов группы {entry['id']} не совпадает с item_count в meta.json."
                    )
                groups_list.append(
                    Group(
                        group_id=int(entry["id"]),
                        item_ids=tuple(int(value) for value in group_item_ids),
                        min_selected_for_discount=int(entry["min_selected_for_discount"]),
                        weight_discount_percent=int(entry["weight_discount_percent"]),
                        utility_bonus_percent=int(entry["utility_bonus_percent"]),
                    )
                )
            groups = tuple(groups_list)

    except ValueError:
        raise
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Не удалось загрузить экземпляр '{instance_dir}': {exc}") from exc

    instance = Instance(
        items=items,
        groups=groups,
        target_item_count=int(metadata["target_item_count"]),
        capacity=float(metadata["capacity"]),
        seed=None if metadata.get("seed") is None else int(metadata["seed"]),
        instance_id=metadata.get("instance_id"),
    )

    if int(metadata.get("n", -1)) != instance.n:
        raise ValueError(f"'{instance_dir}': n не совпадает с числом уникальных предметов.")
    if int(metadata.get("group_count", -1)) != instance.group_count:
        raise ValueError(f"'{instance_dir}': group_count не совпадает с числом групп.")
    if int(metadata.get("group_membership_count", -1)) != instance.group_membership_count:
        raise ValueError(f"'{instance_dir}': group_membership_count не совпадает с данными групп.")
    if int(metadata.get("ungrouped_item_count", -1)) != instance.ungrouped_item_count:
        raise ValueError(f"'{instance_dir}': ungrouped_item_count не совпадает с данными групп.")

    return instance
