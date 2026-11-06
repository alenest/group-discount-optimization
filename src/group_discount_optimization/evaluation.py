"""Единый расчёт выбранного набора с учётом порогов групп."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .instance import Instance


class AmbiguousGroupBenefitError(ValueError):
    """Предмет одновременно попал под эффекты нескольких групп без заданного правила."""


@dataclass(frozen=True, slots=True)
class GroupEvaluation:
    group_id: int
    selected_count: int
    threshold: int
    discount_active: bool
    weight_discount_percent: int


@dataclass(frozen=True, slots=True)
class ItemEvaluation:
    item_id: int
    original_weight: int
    effective_weight: float
    original_utility: int
    effective_utility: float
    discount_group_id: int | None
    bonus_group_id: int | None


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
        return tuple(group.group_id for group in self.groups if group.discount_active)

    @property
    def group_selected_counts(self) -> dict[int, int]:
        return {group.group_id: group.selected_count for group in self.groups}


def evaluate_selection(instance: Instance, selected_item_ids: Iterable[int]) -> Evaluation:
    """Оценить набор выбранных ID.

    Правило порога: при выборе не менее min_selected_for_discount предметов
    скидка активируется и применяется ко ВСЕМ выбранным предметам этой группы,
    включая предметы, которыми порог был достигнут.

    Бонус к полезности сохранён как отдельный коэффициент прежней модели и,
    пока он не будет отдельно уточнён, применяется к предметам группы без
    порогового условия. В текущем наборе данных бонус равен нулю.

    Пересечения групп в структуре данных поддерживаются. Если один выбранный
    предмет одновременно попадает под скидки двух активных групп (или под два
    ненулевых бонуса), функция выдаёт ошибку: правило объединения эффектов
    преподавателем пока не задано, и выбирать его самостоятельно нельзя.
    """

    raw_ids = tuple(int(value) for value in selected_item_ids)
    if len(set(raw_ids)) != len(raw_ids):
        raise ValueError("Один и тот же предмет нельзя выбирать повторно.")

    items_by_id = instance.items_by_id
    unknown = set(raw_ids).difference(items_by_id)
    if unknown:
        raise ValueError(f"Выбраны неизвестные ID предметов: {sorted(unknown)}.")

    selected = set(raw_ids)
    group_selected_counts = {
        group.group_id: sum(item_id in selected for item_id in group.item_ids)
        for group in instance.groups
    }
    active_groups = {
        group.group_id: group
        for group in instance.groups
        if group_selected_counts[group.group_id] >= group.min_selected_for_discount
    }

    memberships: dict[int, list] = {item_id: [] for item_id in raw_ids}
    for group in instance.groups:
        for item_id in group.item_ids:
            if item_id in selected:
                memberships[item_id].append(group)

    item_results: list[ItemEvaluation] = []
    total_weight = 0.0
    total_utility = 0.0

    for item_id in raw_ids:
        item = items_by_id[item_id]
        item_groups = memberships[item_id]
        active_for_item = [group for group in item_groups if group.group_id in active_groups]
        nonzero_bonus_groups = [group for group in item_groups if group.utility_bonus_percent > 0]

        if len(active_for_item) > 1:
            ids = [group.group_id for group in active_for_item]
            raise AmbiguousGroupBenefitError(
                f"Предмет {item_id} входит в несколько активных групп {ids}. "
                "Правило объединения скидок для пересекающихся групп ещё не задано."
            )
        if len(nonzero_bonus_groups) > 1:
            ids = [group.group_id for group in nonzero_bonus_groups]
            raise AmbiguousGroupBenefitError(
                f"Предмет {item_id} получает бонусы нескольких групп {ids}; "
                "правило объединения бонусов ещё не задано."
            )

        discount_group = active_for_item[0] if active_for_item else None
        bonus_group = nonzero_bonus_groups[0] if nonzero_bonus_groups else None
        discount = discount_group.weight_discount_percent if discount_group else 0
        bonus = bonus_group.utility_bonus_percent if bonus_group else 0
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
                discount_group_id=None if discount_group is None else discount_group.group_id,
                bonus_group_id=None if bonus_group is None else bonus_group.group_id,
            )
        )

    group_results = tuple(
        GroupEvaluation(
            group_id=group.group_id,
            selected_count=group_selected_counts[group.group_id],
            threshold=group.min_selected_for_discount,
            discount_active=group.group_id in active_groups,
            weight_discount_percent=group.weight_discount_percent,
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
