from decimal import Decimal

import pytest

from group_discount_optimization.core.evaluation import evaluate_solution
from group_discount_optimization.core.model import Group, Item, ProblemInstance


def make_instance() -> ProblemInstance:
    return ProblemInstance(
        instance_id="manual-test",
        max_weight=13,
        target_item_count=2,
        groups=(
            Group("g1", 20, 10, (Item("a", 10, 10), Item("b", 6, 8))),
            Group("g2", 50, 50, (Item("c", 10, 10), Item("d", 5, 7))),
        ),
        seed=1,
    )


def test_group_specific_percentages_apply_to_selected_items():
    result = evaluate_solution(make_instance(), {"g1": ["a"], "g2": ["c"]})
    assert result["feasible"] is True
    assert result["selected_count"] == 2
    assert result["adjusted_weight_total"] == 13.0
    assert result["utility_total"] == 26.0


def test_exact_item_count_is_a_global_constraint():
    result = evaluate_solution(make_instance(), {"g1": ["a"]})
    assert result["count_feasible"] is False
    assert result["feasible"] is False


def test_global_weight_limit_is_checked_after_group_discount():
    instance = ProblemInstance(
        instance_id="discount-capacity",
        max_weight=12,
        target_item_count=2,
        groups=(
            Group("g1", 20, 0, (Item("a", 10, 1),)),
            Group("g2", 50, 0, (Item("b", 10, 1),)),
        ),
    )
    result = evaluate_solution(instance, {"g1": ["a"], "g2": ["b"]})
    assert result["adjusted_weight_total"] == 13.0
    assert result["weight_feasible"] is False
    assert result["feasible"] is False


def test_decimal_percentages_are_evaluated_without_rounding_item_weights():
    instance = ProblemInstance(
        instance_id="decimal-percent",
        max_weight=9,
        target_item_count=1,
        groups=(Group("g", 12.5, 0, (Item("a", 10, 1.5),)),),
    )
    result = evaluate_solution(instance, {"g": ["a"]})
    assert result["adjusted_weight_total"] == 8.75
    assert result["utility_total"] == 1.5
    assert result["feasible"] is True


def test_unknown_groups_and_items_are_rejected():
    instance = make_instance()
    with pytest.raises(ValueError, match="Unknown group"):
        evaluate_solution(instance, {"not-a-group": ["a"]})
    with pytest.raises(ValueError, match="Unknown item"):
        evaluate_solution(instance, {"g1": ["missing"], "g2": ["c"]})


def test_duplicate_selected_items_are_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        evaluate_solution(make_instance(), {"g1": ["a", "a"], "g2": []})
