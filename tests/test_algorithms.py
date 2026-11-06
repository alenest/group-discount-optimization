"""Проверки полного перебора, жадных алгоритмов и базовых решений."""

from pathlib import Path

import pytest

from group_discount_optimization import Group, Instance, Item, evaluate_selection, load_instance
from group_discount_optimization.algorithms import (
    solve_exhaustive,
    solve_exhaustive_no_groups,
    solve_greedy_group_aware,
    solve_greedy_no_groups,
    solve_greedy_ratio,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def _group_instance() -> Instance:
    items = (
        Item(1, 10, 10),
        Item(2, 10, 10),
        Item(3, 10, 10),
        Item(4, 100, 100),
        Item(5, 100, 100),
    )
    group = Group(
        group_id=1,
        item_ids=(1, 2, 3),
        min_selected_for_discount=3,
        weight_discount_percent=50,
        utility_bonus_percent=20,
    )
    return Instance(items=items, groups=(group,), target_item_count=3, capacity=20)


def test_exhaustive_finds_group_activation_optimum():
    instance = _group_instance()
    result = solve_exhaustive(instance)

    assert result.selected_item_ids == (1, 2, 3)
    assert result.feasible
    assert result.total_weight == pytest.approx(15)
    assert result.total_utility == pytest.approx(36)
    assert result.active_group_ids == (1,)


def test_greedy_algorithms_return_exactly_q_items():
    instance = _group_instance()
    for solver in (solve_greedy_ratio, solve_greedy_group_aware):
        result = solver(instance)
        assert len(result.selected_item_ids) == instance.target_item_count
        assert len(set(result.selected_item_ids)) == instance.target_item_count
        assert result.feasible
        assert result.total_utility == pytest.approx(36)


def test_exhaustive_matches_evaluator_on_saved_instance():
    instance = load_instance(DATA / "n_12/instance_001")
    result = solve_exhaustive(instance)

    assert result.feasible
    assert len(result.selected_item_ids) == instance.target_item_count
    assert result.total_utility == pytest.approx(
        evaluate_selection(instance, result.selected_item_ids).total_utility
    )
    assert result.evaluated_candidates == 66


def test_group_aware_greedy_is_not_worse_than_ratio_on_saved_instance():
    instance = load_instance(DATA / "n_12/instance_001")
    ratio = solve_greedy_ratio(instance)
    aware = solve_greedy_group_aware(instance)

    assert aware.feasible
    if ratio.feasible:
        assert aware.total_utility >= ratio.total_utility - 1e-9


def test_no_group_baseline_can_be_infeasible_when_capacity_relies_on_discounts():
    instance = _group_instance()
    result = solve_exhaustive_no_groups(instance)

    assert not result.feasible
    assert result.selected_item_ids == ()


def test_no_group_greedy_returns_baseline_values():
    instance = _group_instance()
    result = solve_greedy_no_groups(instance)

    assert result.method == "greedy_no_groups"
    assert len(result.selected_item_ids) == instance.target_item_count
    assert result.total_weight == pytest.approx(30)
    assert result.total_utility == pytest.approx(30)
    assert not result.feasible
