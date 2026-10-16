import pytest

from group_discount_optimization.core.model import Group, Item, ProblemInstance


def test_item_weight_is_integer_but_utility_need_not_be_integer():
    item = Item("item-1", weight=7, utility=3.5)
    assert item.weight == 7
    assert item.utility == 3.5


def test_percentages_must_be_between_zero_and_fifty():
    with pytest.raises(ValueError, match="between 0 and 50"):
        Group("g", 50.1, 10, (Item("i", 1, 2),))


def test_instance_requires_exact_count_not_greater_than_available_items():
    with pytest.raises(ValueError, match="cannot exceed total item count"):
        ProblemInstance(
            instance_id="invalid-count",
            max_weight=10,
            target_item_count=2,
            groups=(Group("g", 0, 0, (Item("i", 1, 1),)),),
        )


def test_unique_group_ids_are_required():
    with pytest.raises(ValueError, match="group_id values must be unique"):
        ProblemInstance(
            instance_id="duplicate-groups",
            max_weight=10,
            target_item_count=0,
            groups=(
                Group("g", 0, 0, (Item("i1", 1, 1),)),
                Group("g", 0, 0, (Item("i2", 1, 1),)),
            ),
        )
