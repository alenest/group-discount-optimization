"""Evaluate a selection using group-specific percentages and one global knapsack."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from group_discount_optimization.core.model import Item, ProblemInstance


def _decimal(value: int | float) -> Decimal:
    # str() avoids importing the binary approximation of a float into Decimal.
    return Decimal(str(value))


def evaluate_solution(
    instance: ProblemInstance,
    selection: dict[str, Iterable[str]],
) -> dict[str, object]:
    """Evaluate a selection; percentages are applied using the original /100 formulas.

    ``selection`` maps each group ID to selected item IDs. Missing groups mean that
    no items were selected from them. The result is feasible only if exactly Q
    items were selected and the adjusted total weight is within the single capacity.
    """
    known_groups = {group.group_id for group in instance.groups}
    unknown_groups = sorted(set(selection) - known_groups)
    if unknown_groups:
        raise ValueError(f"Unknown group IDs: {unknown_groups}")

    group_results: list[dict[str, object]] = []
    total_count = 0
    total_raw_weight = 0
    total_adjusted_weight = Decimal(0)
    total_raw_utility = Decimal(0)
    total_adjusted_utility = Decimal(0)

    for group in instance.groups:
        selected_ids = list(selection.get(group.group_id, []))
        if len(selected_ids) != len(set(selected_ids)):
            raise ValueError(f"Duplicate selected item IDs in group {group.group_id}")

        by_id = {item.item_id: item for item in group.items}
        unknown_items = sorted(set(selected_ids) - set(by_id))
        if unknown_items:
            raise ValueError(f"Unknown item IDs for group {group.group_id}: {unknown_items}")

        selected: list[Item] = [by_id[item_id] for item_id in selected_ids]
        raw_weight = sum(item.weight for item in selected)
        raw_utility = sum((_decimal(item.utility) for item in selected), Decimal(0))
        weight_factor = Decimal(1) - _decimal(group.weight_discount_percent) / Decimal(100)
        utility_factor = Decimal(1) + _decimal(group.utility_bonus_percent) / Decimal(100)
        adjusted_weight = Decimal(raw_weight) * weight_factor
        adjusted_utility = raw_utility * utility_factor

        group_results.append({
            "group_id": group.group_id,
            "selected_item_ids": selected_ids,
            "selected_count": len(selected),
            "weight_discount_percent": group.weight_discount_percent,
            "utility_bonus_percent": group.utility_bonus_percent,
            "raw_weight": raw_weight,
            "adjusted_weight": float(adjusted_weight),
            "raw_utility": float(raw_utility),
            "adjusted_utility": float(adjusted_utility),
        })
        total_count += len(selected)
        total_raw_weight += raw_weight
        total_adjusted_weight += adjusted_weight
        total_raw_utility += raw_utility
        total_adjusted_utility += adjusted_utility

    count_feasible = total_count == instance.target_item_count
    weight_feasible = total_adjusted_weight <= Decimal(instance.max_weight)
    return {
        "instance_id": instance.instance_id,
        "groups": group_results,
        "selected_count": total_count,
        "target_item_count": instance.target_item_count,
        "count_feasible": count_feasible,
        "raw_weight_total": total_raw_weight,
        "adjusted_weight_total": float(total_adjusted_weight),
        "max_weight": instance.max_weight,
        "weight_feasible": weight_feasible,
        "raw_utility_total": float(total_raw_utility),
        "utility_total": float(total_adjusted_utility),
        "feasible": count_feasible and weight_feasible,
    }
