"""Проверки модели, оценщика и неизменяемого стандартного набора данных."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from group_discount_optimization import Group, Instance, Item, evaluate_selection, load_instance
from group_discount_optimization.generator import DEFAULT_SIZES, generate_dataset

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def _manual_instance(*, q=5, capacity=10_000):
    items = tuple(
        Item(item_id, weight, utility)
        for item_id, weight, utility in (
            (1, 10, 50),
            (2, 20, 60),
            (3, 30, 70),
            (4, 40, 80),
            (5, 50, 90),
            (6, 60, 100),
        )
    )
    group = Group(
        group_id=1,
        item_ids=(1, 2, 3, 4, 5),
        min_selected_for_discount=4,
        weight_discount_percent=50,
        utility_bonus_percent=20,
    )
    return Instance(items=items, groups=(group,), target_item_count=q, capacity=capacity)


def _instance_paths(root=DATA):
    return sorted(path.parent for path in root.glob("n_*/instance_*/meta.json"))


def test_standard_dataset_contains_twelve_fixed_instances():
    paths = _instance_paths()
    assert len(paths) == 12
    assert {int(path.parent.name.removeprefix("n_")) for path in paths} == set(DEFAULT_SIZES)
    assert (DATA / "manifest.csv").is_file()
    assert (DATA / "checksums.sha256").is_file()


def test_committed_dataset_files_match_their_checksums():
    checksum_path = DATA / "checksums.sha256"
    records = [line.split("  ", 1) for line in checksum_path.read_text(encoding="utf-8").splitlines()]
    recorded_paths = {relative_path for _, relative_path in records}
    expected_paths = {
        file_path.relative_to(DATA).as_posix()
        for file_path in DATA.rglob("*")
        if file_path.is_file() and file_path != checksum_path
    }
    assert recorded_paths == expected_paths
    for expected, relative_path in records:
        actual = hashlib.sha256((DATA / relative_path).read_bytes()).hexdigest()
        assert actual == expected, f"Изменился файл тестовых данных: {relative_path}"


def test_standard_dataset_matches_initial_experiment_profile():
    for path in _instance_paths():
        instance = load_instance(path)
        metadata = json.loads((path / "meta.json").read_text(encoding="utf-8"))

        assert 12 <= instance.n <= 100
        assert instance.target_item_count == 10
        assert instance.group_count in (2, 3)
        assert instance.ungrouped_item_count >= 1
        assert instance.group_membership_count + instance.ungrouped_item_count == instance.n
        assert metadata["format_version"] == 4
        assert metadata["ungrouped_item_count"] == instance.ungrouped_item_count
        assert all(group.min_selected_for_discount in (4, 5) for group in instance.groups)
        assert all(25 <= group.weight_discount_percent <= 50 for group in instance.groups)
        assert all(0 <= group.utility_bonus_percent <= 50 for group in instance.groups)
        assert all(1 <= item.weight <= 100 for item in instance.items)
        assert all(1 <= item.utility <= 100 for item in instance.items)
        assert not metadata["generation"]["group_membership_overlap"]


def test_fixed_dataset_contains_nonzero_utility_bonuses():
    bonuses = [group.utility_bonus_percent for path in _instance_paths() for group in load_instance(path).groups]
    assert any(value > 0 for value in bonuses)


def test_each_item_is_in_at_most_one_group_and_unassigned_items_are_preserved():
    for path in _instance_paths():
        instance = load_instance(path)
        memberships = [item_id for group in instance.groups for item_id in group.item_ids]
        assert len(memberships) == len(set(memberships))
        assert len(instance.ungrouped_item_ids) == instance.ungrouped_item_count
        assert set(memberships).isdisjoint(instance.ungrouped_item_ids)
        assert set(memberships) | set(instance.ungrouped_item_ids) == set(instance.items_by_id)


def test_below_threshold_neither_weight_discount_nor_utility_bonus_is_applied():
    instance = _manual_instance(q=4)
    result = evaluate_selection(instance, {1, 2, 3, 6})

    assert result.groups[0].selected_count == 3
    assert not result.groups[0].effects_active
    assert not result.groups[0].discount_active
    assert not result.groups[0].utility_bonus_active
    assert result.total_weight == pytest.approx(10 + 20 + 30 + 60)
    assert result.total_utility == pytest.approx(50 + 60 + 70 + 100)
    ungrouped = next(item for item in result.items if item.item_id == 6)
    assert ungrouped.group_id is None
    assert ungrouped.effective_weight == 60
    assert ungrouped.effective_utility == 100


def test_at_threshold_both_effects_apply_to_every_selected_item_in_group():
    instance = _manual_instance(q=5)
    result = evaluate_selection(instance, {1, 2, 3, 4, 6})

    assert result.groups[0].selected_count == 4
    assert result.groups[0].effects_active
    assert result.groups[0].discount_active
    assert result.groups[0].utility_bonus_active
    # Скидка 50% и бонус 20% действуют на все четыре выбранных предмета группы.
    assert result.total_weight == pytest.approx((10 + 20 + 30 + 40) * 0.5 + 60)
    assert result.total_utility == pytest.approx((50 + 60 + 70 + 80) * 1.2 + 100)
    assert all(item.effects_active for item in result.items if item.item_id in {1, 2, 3, 4})
    ungrouped = next(item for item in result.items if item.item_id == 6)
    assert ungrouped.effective_weight == 60
    assert ungrouped.effective_utility == 100


def test_effects_remain_active_when_selected_count_exceeds_threshold():
    instance = _manual_instance(q=5)
    result = evaluate_selection(instance, {1, 2, 3, 4, 5})

    assert result.groups[0].selected_count == 5
    assert result.groups[0].effects_active
    assert result.total_weight == pytest.approx((10 + 20 + 30 + 40 + 50) * 0.5)
    assert result.total_utility == pytest.approx((50 + 60 + 70 + 80 + 90) * 1.2)


def test_group_size_and_threshold_are_separate_fields():
    group = Group(7, (1, 2, 3, 4, 5), 3, 25, 10)
    assert group.item_count == 5
    assert group.min_selected_for_discount == 3


def test_exact_q_capacity_and_duplicate_selection_are_checked():
    instance = _manual_instance(q=5, capacity=10)
    result = evaluate_selection(instance, {1, 2, 3, 6})
    assert not result.count_constraint_satisfied
    assert not result.capacity_constraint_satisfied
    assert not result.feasible
    with pytest.raises(ValueError, match="нельзя выбирать повторно"):
        evaluate_selection(instance, [1, 1, 2, 3, 4])
    with pytest.raises(ValueError, match="неизвестные ID"):
        evaluate_selection(instance, {1, 2, 3, 4, 999})


def test_instance_rejects_overlapping_groups():
    items = (Item(1, 10, 10), Item(2, 20, 20), Item(3, 30, 30))
    groups = (
        Group(1, (1, 2), 1, 25, 10),
        Group(2, (2, 3), 1, 50, 20),
    )
    with pytest.raises(ValueError, match="пересечения групп запрещены"):
        Instance(items=items, groups=groups, target_item_count=2, capacity=100)


def test_loader_rejects_overlapping_group_memberships(tmp_path: Path):
    path = tmp_path / "overlap"
    path.mkdir()
    np.savez_compressed(
        path / "data.npz",
        item_ids=np.array([1, 2, 3]),
        weights=np.array([10, 20, 30]),
        utilities=np.array([40, 50, 60]),
        group_001_item_ids=np.array([1, 2]),
        group_002_item_ids=np.array([2, 3]),
    )
    metadata = {
        "format_version": 4,
        "n": 3,
        "target_item_count": 2,
        "capacity": 100,
        "group_count": 2,
        "group_membership_count": 4,
        "ungrouped_item_count": 0,
        "items": {"ids_key": "item_ids", "weights_key": "weights", "utilities_key": "utilities"},
        "groups": [
            {"id": 1, "item_count": 2, "item_ids_key": "group_001_item_ids", "min_selected_for_discount": 1, "weight_discount_percent": 25, "utility_bonus_percent": 10},
            {"id": 2, "item_count": 2, "item_ids_key": "group_002_item_ids", "min_selected_for_discount": 1, "weight_discount_percent": 50, "utility_bonus_percent": 20},
        ],
    }
    (path / "meta.json").write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="пересечения групп запрещены"):
        load_instance(path)


def test_committed_dataset_contains_feasible_and_infeasible_witnesses():
    for path in _instance_paths():
        instance = load_instance(path)
        metadata = json.loads((path / "meta.json").read_text(encoding="utf-8"))
        by_id = instance.items_by_id
        witness_counts = metadata["generation"]["witness_selected_counts_by_group"]
        witness_ungrouped = metadata["generation"]["witness_selected_ungrouped_count"]
        light_ids: set[int] = set()
        heavy_ids: set[int] = set()

        for group, count in zip(instance.groups, witness_counts, strict=True):
            ordered = sorted(group.item_ids, key=lambda item_id: by_id[item_id].weight)
            light_ids.update(ordered[:count])
            heavy_ids.update(ordered[-count:] if count else [])
        ordered_ungrouped = sorted(instance.ungrouped_item_ids, key=lambda item_id: by_id[item_id].weight)
        light_ids.update(ordered_ungrouped[:witness_ungrouped])
        heavy_ids.update(ordered_ungrouped[-witness_ungrouped:] if witness_ungrouped else [])

        light = evaluate_selection(instance, light_ids)
        heavy = evaluate_selection(instance, heavy_ids)
        assert len(light_ids) == instance.target_item_count
        assert light.feasible
        assert len(light.active_group_ids) >= 2
        assert len(heavy_ids) == instance.target_item_count
        assert not heavy.capacity_constraint_satisfied
        assert light.group_selected_counts == heavy.group_selected_counts


def test_generator_is_reproducible(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    generate_dataset(first, sizes=(12, 20), seed=91)
    generate_dataset(second, sizes=(12, 20), seed=91)

    for n in (12, 20):
        path_a = first / f"n_{n}/instance_001"
        path_b = second / f"n_{n}/instance_001"
        with np.load(path_a / "data.npz", allow_pickle=False) as a, np.load(
            path_b / "data.npz", allow_pickle=False
        ) as b:
            assert a.files == b.files
            for key in a.files:
                np.testing.assert_array_equal(a[key], b[key])
        assert json.loads((path_a / "meta.json").read_text()) == json.loads(
            (path_b / "meta.json").read_text()
        )


def test_generator_writes_reloadable_files_and_manifest(tmp_path: Path):
    output = tmp_path / "generated"
    created = generate_dataset(output, sizes=(15, 25), instances_per_size=2, seed=5)
    assert len(created) == 4
    assert (output / "manifest.csv").is_file()
    assert all(load_instance(path).target_item_count == 10 for path in created)


def test_generator_removes_stale_data_when_explicitly_regenerating(tmp_path: Path):
    output = tmp_path / "data"
    stale = output / "n_5000" / "instance_001"
    stale.mkdir(parents=True)
    (stale / "old.txt").write_text("old-format", encoding="utf-8")
    generate_dataset(output, sizes=(12,), seed=3, overwrite=True)
    assert not (output / "n_5000").exists()
    assert (output / "n_12/instance_001/meta.json").is_file()


def test_old_format_is_not_silently_interpreted_as_v4(tmp_path: Path):
    path = tmp_path / "old"
    path.mkdir()
    (path / "meta.json").write_text(json.dumps({"format_version": 3}), encoding="utf-8")
    np.savez(path / "data.npz", item_ids=np.array([1]), weights=np.array([1]), utilities=np.array([1]))
    with pytest.raises(ValueError, match="Ожидался формат v4"):
        load_instance(path)
