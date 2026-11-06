"""Единый расчёт выбранного набора с пороговой активацией двух эффектов."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .instance import Instance


@dataclass(frozen=True, slots=True)
class GroupEvaluation:
    group_id: int
    selected_count: int
    threshold: int
    effects_active: bool
    weight_discount_percent: int
    utility_bonus_percent: int

    @property
    def discount_active(self) -> bool:
        """Оба групповых эффекта включаются одним и тем же порогом."""
        return self.effects_active

    @property
    def utility_bonus_active(self) -> bool:
        return self.effects_active


@dataclass(frozen=True, slots=True)
class ItemEvaluation:
    item_id: int
    original_weight: int
    effective_weight: float
    original_utility: int
    effective_utility: float
    group_id: int | None
    effects_active: bool

    @property
    def discount_group_id(self) -> int | None:
        return self.group_id if self.effects_active else None

    @property
    def bonus_group_id(self) -> int | None:
        return self.group_id if self.effects_active else None


@dataclass(frozen=True, slots=True)
class Evaluation:
    selected_item_ids: tuple[int, ...]
    selected_count: int
    target_item_count: int
    groups: tuple[GroupEvaluation, ...]
    items: tuple[ItemEvaluation, ...]
    total_weight: float
    capacity: float
    total_utility: float
    count_constraint_satisfied: bool
    capacity_constraint_satisfied: bool

    @property
    def feasible(self) -> bool:
        return self.count_constraint_satisfied and self.capacity_constraint_satisfied

    @property
    def active_group_ids(self) -> tuple[int, ...]:
        return tuple(group.group_id for group in self.groups if group.effects_active)

    @property
    def group_selected_counts(self) -> dict[int, int]:
        return {group.group_id: group.selected_count for group in self.groups}


def evaluate_selection(instance: Instance, selected_item_ids: Iterable[int]) -> Evaluation:
    """Рассчитать вес и полезность набора предметов.

    Если из группы выбрано не меньше её порога, одновременно активируются
    снижение веса и бонус полезности. Оба коэффициента применяются ко всем
    выбранным предметам этой группы. Предметы вне групп не получают эффектов.
    """

    raw_ids = tuple(int(value) for value in selected_item_ids)
    if len(set(raw_ids)) != len(raw_ids):
        raise ValueError("Один и тот же предмет нельзя выбирать повторно.")

    items_by_id = instance.items_by_id
    selected = set(raw_ids)
    unknown = selected.difference(items_by_id)
    if unknown:
        raise ValueError(f"Выбраны неизвестные ID предметов: {sorted(unknown)}.")

    item_to_group = {
        item_id: group
        for group in instance.groups
        for item_id in group.item_ids
    }
    selected_counts = {
        group.group_id: sum(item_id in selected for item_id in group.item_ids)
        for group in instance.groups
    }
    active = {
        group.group_id: selected_counts[group.group_id] >= group.min_selected_for_discount
        for group in instance.groups
    }

    item_results: list[ItemEvaluation] = []
    total_weight = 0.0
    total_utility = 0.0
    for item_id in sorted(raw_ids):
        item = items_by_id[item_id]
        group = item_to_group.get(item_id)
        effects_active = group is not None and active[group.group_id]

        discount = group.weight_discount_percent if effects_active and group is not None else 0
        bonus = group.utility_bonus_percent if effects_active and group is not None else 0
        effective_weight = item.weight * (1.0 - discount / 100.0)
        effective_utility = item.utility * (1.0 + bonus / 100.0)
        total_weight += effective_weight
        total_utility += effective_utility

        item_results.append(
            ItemEvaluation(
                item_id=item_id,
                original_weight=item.weight,
                effective_weight=effective_weight,
                original_utility=item.utility,
                effective_utility=effective_utility,
                group_id=None if group is None else group.group_id,
                effects_active=bool(effects_active),
            )
        )

    group_results = tuple(
        GroupEvaluation(
            group_id=group.group_id,
            selected_count=selected_counts[group.group_id],
            threshold=group.min_selected_for_discount,
            effects_active=active[group.group_id],
            weight_discount_percent=group.weight_discount_percent,
            utility_bonus_percent=group.utility_bonus_percent,
        )
        for group in instance.groups
    )

    count_ok = len(raw_ids) == instance.target_item_count
    capacity_ok = total_weight <= instance.capacity + 1e-9
    return Evaluation(
        selected_item_ids=tuple(sorted(raw_ids)),
        selected_count=len(raw_ids),
        target_item_count=instance.target_item_count,
        groups=group_results,
        items=tuple(item_results),
        total_weight=total_weight,
        capacity=instance.capacity,
        total_utility=total_utility,
        count_constraint_satisfied=count_ok,
        capacity_constraint_satisfied=capacity_ok,
    )
