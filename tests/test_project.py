"""Проверки новой модели, загрузчика, генератора и оценки решений."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from group_discount_optimization.evaluation import (
    AmbiguousGroupBenefitError,
    evaluate_selection,
)
from group_discount_optimization.generator import (
    DEFAULT_SIZES,
    generate_dataset,
)
from group_discount_optimization.instance import Group, Instance, Item, load_instance

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def _manual_instance(
    *, groups: tuple[Group, ...], q: int, capacity: float = 10_000
) -> Instance:
    items = (
        Item(1, 10, 50),
        Item(2, 20, 60),
        Item(3, 30, 70),
        Item(4, 40, 80),
        Item(5, 50, 90),
        Item(6, 60, 100),
    )
    return Instance(items=items, groups=groups, target_item_count=q, capacity=capacity)


def test_default_data_has_twelve_small_instances():
    instances = sorted(DATA.glob("n_*/instance_*/meta.json"))
    assert len(instances) == 12
    assert {int(path.parent.parent.name.removeprefix("n_")) for path in instances} == set(DEFAULT_SIZES)


def test_generated_instances_follow_teacher_initial_parameters():
    for meta_path in sorted(DATA.glob("n_*/instance_*/meta.json")):
        instance = load_instance(meta_path.parent)
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))

        assert 12 <= instance.n <= 100
        assert instance.target_item_count == 10
        assert 2 <= instance.group_count <= 3
        assert not instance.has_overlapping_groups
        assert sum(group.item_count for group in instance.groups) == instance.n
        assert metadata["group_membership_count"] == instance.group_membership_count
        assert all(group.item_count >= group.min_selected_for_discount for group in instance.groups)
        assert all(group.min_selected_for_discount in (4, 5) for group in instance.groups)
        assert all(25 <= group.weight_discount_percent <= 50 for group in instance.groups)
        assert all(group.utility_bonus_percent == 0 for group in instance.groups)
        assert len({item.item_id for item in instance.items}) == instance.n
        assert all(1 <= item.weight <= 100 for item in instance.items)
        assert all(1 <= item.utility <= 100 for item in instance.items)
        assert metadata["format_version"] == 3


def test_items_are_stored_once_and_groups_reference_them_by_id():
    for meta_path in sorted(DATA.glob("n_*/instance_*/meta.json")):
        instance = load_instance(meta_path.parent)
        known_ids = {item.item_id for item in instance.items}
        with np.load(meta_path.parent / "data.npz", allow_pickle=False) as arrays:
            assert set(("item_ids", "weights", "utilities")).issubset(arrays.files)
            assert arrays["item_ids"].size == instance.n
            assert arrays["weights"].size == instance.n
            assert arrays["utilities"].size == instance.n
            for group in instance.groups:
                assert set(group.item_ids).issubset(known_ids)
                assert f"group_{group.group_id:03d}_item_ids" in arrays.files


def test_discount_is_off_below_threshold_and_applies_to_all_selected_items_at_threshold():
    group = Group(
        group_id=1,
        item_ids=(1, 2, 3, 4, 5),
        min_selected_for_discount=4,
        weight_discount_percent=50,
    )
    instance = _manual_instance(groups=(group,), q=4)

    below = evaluate_selection(instance, {1, 2, 3, 6})
    assert below.groups[0].selected_count == 3
    assert not below.groups[0].discount_active
    assert below.total_weight == pytest.approx(10 + 20 + 30 + 60)

    at_threshold = evaluate_selection(instance, {1, 2, 3, 4})
    assert at_threshold.groups[0].selected_count == 4
    assert at_threshold.groups[0].discount_active
    # Скидка применяется ко всем четырём предметам, а не только к четвёртому.
    assert at_threshold.total_weight == pytest.approx((10 + 20 + 30 + 40) * 0.5)


def test_item_count_and_discount_threshold_are_different_fields():
    group = Group(
        group_id=7,
        item_ids=(1, 2, 3, 4, 5),
        min_selected_for_discount=3,
        weight_discount_percent=25,
    )
    assert group.item_count == 5
    assert group.min_selected_for_discount == 3


def test_evaluator_checks_exact_q_and_capacity():
    group = Group(1, (1, 2, 3, 4, 5, 6), 4, 25)
    instance = _manual_instance(groups=(group,), q=3, capacity=15)
    result = evaluate_selection(instance, {1, 2})
    assert not result.count_constraint_satisfied
    assert not result.capacity_constraint_satisfied
    assert not result.feasible

    with pytest.raises(ValueError, match="повторно"):
        evaluate_selection(instance, [1, 1, 2])
    with pytest.raises(ValueError, match="неизвестные ID"):
        evaluate_selection(instance, {1, 2, 999})


def test_overlapping_groups_are_supported_when_only_one_discount_is_active():
    groups = (
        Group(1, (1, 2), min_selected_for_discount=2, weight_discount_percent=25),
        Group(2, (1, 3), min_selected_for_discount=2, weight_discount_percent=50),
    )
    instance = _manual_instance(groups=groups, q=2)
    result = evaluate_selection(instance, {1, 2})
    assert instance.has_overlapping_groups
    assert result.group_selected_counts == {1: 2, 2: 1}
    assert result.active_group_ids == (1,)
    assert result.items[0].discount_group_id == 1


def test_loader_accepts_overlapping_group_memberships(tmp_path: Path):
    path = tmp_path / "overlap"
    path.mkdir()
    np.savez_compressed(
        path / "data.npz",
        item_ids=np.array([1, 2, 3]),
        weights=np.array([10, 20, 30]),
        utilities=np.array([40, 50, 60]),
        group_001_item_ids=np.array([1, 2]),
        group_002_item_ids=np.array([1, 3]),
    )
    metadata = {
        "format_version": 3,
        "n": 3,
        "target_item_count": 2,
        "capacity": 100,
        "items": {"ids_key": "item_ids", "weights_key": "weights", "utilities_key": "utilities"},
        "groups": [
            {"id": 1, "item_count": 2, "item_ids_key": "group_001_item_ids", "min_selected_for_discount": 2, "weight_discount_percent": 25, "utility_bonus_percent": 0},
            {"id": 2, "item_count": 2, "item_ids_key": "group_002_item_ids", "min_selected_for_discount": 2, "weight_discount_percent": 50, "utility_bonus_percent": 0},
        ],
    }
    (path / "meta.json").write_text(json.dumps(metadata), encoding="utf-8")

    instance = load_instance(path)
    assert instance.n == 3
    assert instance.group_membership_count == 4
    assert instance.has_overlapping_groups
    result = evaluate_selection(instance, {1, 2})
    assert result.active_group_ids == (1,)


def test_overlapping_item_in_two_active_discount_groups_is_explicitly_rejected():
    groups = (
        Group(1, (1, 2), min_selected_for_discount=2, weight_discount_percent=25),
        Group(2, (1, 3), min_selected_for_discount=2, weight_discount_percent=50),
    )
    instance = _manual_instance(groups=groups, q=3)
    with pytest.raises(AmbiguousGroupBenefitError, match="несколько активных групп"):
        evaluate_selection(instance, {1, 2, 3})


def test_each_committed_instance_contains_feasible_and_infeasible_witnesses():
    for meta_path in sorted(DATA.glob("n_*/instance_*/meta.json")):
        instance = load_instance(meta_path.parent)
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        witness_counts = metadata["generation"]["witness_selected_counts_by_group"]
        by_id = instance.items_by_id
        light_ids: set[int] = set()
        heavy_ids: set[int] = set()
        for group, count in zip(instance.groups, witness_counts, strict=True):
            ordered = sorted(group.item_ids, key=lambda item_id: by_id[item_id].weight)
            light_ids.update(ordered[:count])
            heavy_ids.update(ordered[-count:] if count else [])
        light_result = evaluate_selection(instance, light_ids)
        heavy_result = evaluate_selection(instance, heavy_ids)
        assert len(light_ids) == instance.target_item_count
        assert light_result.feasible
        assert len(heavy_ids) == instance.target_item_count
        assert not heavy_result.capacity_constraint_satisfied


def test_generator_reproducibility(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    generate_dataset(first, sizes=(12, 20), seed=91)
    generate_dataset(second, sizes=(12, 20), seed=91)

    for n in (12, 20):
        a = first / f"n_{n}/instance_001"
        b = second / f"n_{n}/instance_001"
        with np.load(a / "data.npz", allow_pickle=False) as arrays_a, np.load(
            b / "data.npz", allow_pickle=False
        ) as arrays_b:
            assert arrays_a.files == arrays_b.files
            for key in arrays_a.files:
                np.testing.assert_array_equal(arrays_a[key], arrays_b[key])
        assert json.loads((a / "meta.json").read_text()) == json.loads((b / "meta.json").read_text())


def test_generator_writes_manifest_and_reloadable_files(tmp_path: Path):
    output = tmp_path / "generated"
    created = generate_dataset(output, sizes=(15, 25), instances_per_size=2, seed=5)
    assert len(created) == 4
    assert (output / "manifest.csv").is_file()
    assert all(load_instance(path).target_item_count == 10 for path in created)


def test_overwrite_removes_stale_old_size_directories(tmp_path: Path):
    output = tmp_path / "data"
    stale = output / "n_5000" / "instance_001"
    stale.mkdir(parents=True)
    (stale / "old.txt").write_text("old-format", encoding="utf-8")
    generate_dataset(output, sizes=(12,), seed=3, overwrite=True)
    assert not (output / "n_5000").exists()
    assert (output / "n_12/instance_001/meta.json").is_file()


def test_old_v2_data_is_not_silently_interpreted_as_threshold_model(tmp_path: Path):
    path = tmp_path / "old"
    path.mkdir()
    (path / "meta.json").write_text(json.dumps({"format_version": 2}), encoding="utf-8")
    np.savez(path / "data.npz", weights=np.array([1]), profits=np.array([1]), group_ids=np.array([1]))
    with pytest.raises(ValueError, match="Ожидался формат v3"):
        load_instance(path)
