"""Базовые решения без групповых эффектов.

Эти алгоритмы нужны только для сравнения: они показывают, что даёт учёт
пороговых скидок и бонусов. В основной постановке задачи группы учитываются
через ``evaluate_selection``.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from time import perf_counter

from ..instance import Instance


@dataclass(frozen=True, slots=True)
class BaselineResult:
    method: str
    selected_item_ids: tuple[int, ...]
    total_weight: float
    total_utility: float
    feasible: bool
    elapsed_seconds: float
    evaluated_candidates: int = 0


def _raw_values(instance: Instance, selected_ids: tuple[int, ...]) -> tuple[float, float]:
    by_id = instance.items_by_id
    weight = sum(by_id[item_id].weight for item_id in selected_ids)
    utility = sum(by_id[item_id].utility for item_id in selected_ids)
    return float(weight), float(utility)


def solve_exhaustive_no_groups(instance: Instance) -> BaselineResult:
    """Точный перебор без групповых скидок и бонусов."""
    started = perf_counter()
    item_ids = tuple(item.item_id for item in instance.items)
    q = instance.target_item_count
    weights = {item.item_id: item.weight for item in instance.items}
    utilities = {item.item_id: item.utility for item in instance.items}

    best_ids: tuple[int, ...] | None = None
    best_utility = -1.0
    best_weight = float("inf")
    evaluated = 0

    for combination in combinations(item_ids, q):
        evaluated += 1
        weight = sum(weights[item_id] for item_id in combination)
        if weight > instance.capacity + 1e-9:
            continue
        utility = sum(utilities[item_id] for item_id in combination)
        if (
            utility > best_utility + 1e-9
            or (abs(utility - best_utility) <= 1e-9 and weight < best_weight - 1e-9)
        ):
            best_ids = tuple(combination)
            best_utility = float(utility)
            best_weight = float(weight)

    if best_ids is None:
        return BaselineResult(
            method="exhaustive_no_groups",
            selected_item_ids=(),
            total_weight=0.0,
            total_utility=0.0,
            feasible=False,
            elapsed_seconds=perf_counter() - started,
            evaluated_candidates=evaluated,
        )

    return BaselineResult(
        method="exhaustive_no_groups",
        selected_item_ids=best_ids,
        total_weight=best_weight,
        total_utility=best_utility,
        feasible=True,
        elapsed_seconds=perf_counter() - started,
        evaluated_candidates=evaluated,
    )


def solve_greedy_no_groups(instance: Instance) -> BaselineResult:
    """Жадный алгоритм по исходному отношению полезности к весу без групп."""
    started = perf_counter()
    selected: list[int] = []
    weight = 0.0
    utility = 0.0
    evaluated = 0
    q = instance.target_item_count

    ordered = sorted(
        instance.items,
        key=lambda item: (-(item.utility / item.weight), item.item_id),
    )
    for item in ordered:
        if len(selected) >= q:
            break
        evaluated += 1
        if weight + item.weight <= instance.capacity + 1e-9:
            selected.append(item.item_id)
            weight += item.weight
            utility += item.utility

    if len(selected) < q:
        for item in sorted(instance.items, key=lambda item: (item.weight, item.item_id)):
            if len(selected) >= q:
                break
            if item.item_id in selected:
                continue
            evaluated += 1
            if weight + item.weight <= instance.capacity + 1e-9:
                selected.append(item.item_id)
                weight += item.weight
                utility += item.utility

    if len(selected) < q:
        for item in sorted(instance.items, key=lambda item: (item.weight, item.item_id)):
            if len(selected) >= q:
                break
            if item.item_id not in selected:
                selected.append(item.item_id)
                weight += item.weight
                utility += item.utility

    return BaselineResult(
        method="greedy_no_groups",
        selected_item_ids=tuple(selected),
        total_weight=weight,
        total_utility=utility,
        feasible=len(selected) == q and weight <= instance.capacity + 1e-9,
        elapsed_seconds=perf_counter() - started,
        evaluated_candidates=evaluated,
    )
