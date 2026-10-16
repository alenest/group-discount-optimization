"""Проверки фиксированного набора экземпляров и генератора."""

import json
from pathlib import Path

import numpy as np
import pytest

from group_discount_optimization.generator import generate_dataset
from group_discount_optimization.instance import load_instance

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
EXPECTED_SIZES = (10, 20, 50, 1000, 5000)


def instance_dirs(root=DATA_DIR):
    return sorted(path.parent for path in root.glob("n_*/instance_*/meta.json"))


def test_dataset_contains_five_fixed_instances_for_every_size():
    assert len(instance_dirs()) == len(EXPECTED_SIZES) * 5
    for n in EXPECTED_SIZES:
        cases = sorted((DATA_DIR / f"n_{n}").glob("instance_*/data.npz"))
        assert len(cases) == 5
        assert all((case.parent / "meta.json").is_file() for case in cases)


def test_committed_arrays_are_separate_for_each_group_and_valid():
    for path in instance_dirs():
        instance = load_instance(path)
        assert instance.item_count == sum(group.item_count for group in instance.groups)
        assert instance.weights.size == instance.profits.size == instance.group_ids.size == instance.item_count
        assert 1 <= instance.target_item_count <= instance.item_count
        assert all(1 <= int(value) <= 100 for value in instance.weights)
        assert all(1 <= int(value) <= 100 for value in instance.profits)
        assert all(0 <= group.weight_discount_percent <= 50 for group in instance.groups)
        assert all(0 <= group.utility_bonus_percent <= 50 for group in instance.groups)
        with np.load(path / "data.npz", allow_pickle=False) as data:
            assert "weights" not in data.files
            assert "profits" not in data.files
            assert "group_ids" not in data.files
            for group in instance.groups:
                assert f"group_{group.group_id:03d}_weights" in data.files
                assert f"group_{group.group_id:03d}_profits" in data.files
                assert group.weights.size == group.profits.size == group.item_count


def test_q_and_group_count_vary_between_instances_of_same_size():
    for n in EXPECTED_SIZES:
        instances = [load_instance(path) for path in sorted((DATA_DIR / f"n_{n}").glob("instance_*"))]
        assert len({item.target_item_count for item in instances}) > 1
        assert len({item.group_count for item in instances}) > 1


def test_generator_creates_separate_group_lists_and_varied_parameters(tmp_path):
    output = tmp_path / "instances"
    created = generate_dataset(
        output, sizes=(10, 20), instances_per_size=4,
        min_groups=2, max_groups=4, q_min=1, q_max=None, seed=123,
    )
    assert len(created) == 8
    for path in created:
        assert (path / "data.npz").is_file()
        assert (path / "meta.json").is_file()
        instance = load_instance(path)
        assert instance.item_count in (10, 20)
        assert sum(group.item_count for group in instance.groups) == instance.item_count
    for n in (10, 20):
        items = [load_instance(path) for path in sorted((output / f"n_{n}").glob("instance_*"))]
        assert len({item.target_item_count for item in items}) > 1
        assert len({item.group_count for item in items}) > 1
    assert (output / "manifest.csv").is_file()


def test_generator_is_reproducible(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    generate_dataset(first, sizes=(20,), instances_per_size=3, seed=7)
    generate_dataset(second, sizes=(20,), instances_per_size=3, seed=7)
    for instance_id in ("instance_001", "instance_002", "instance_003"):
        with np.load(first / f"n_20/{instance_id}/data.npz") as a, np.load(second / f"n_20/{instance_id}/data.npz") as b:
            assert a.files == b.files
            for key in a.files:
                np.testing.assert_array_equal(a[key], b[key])
        assert json.loads((first / f"n_20/{instance_id}/meta.json").read_text()) == json.loads(
            (second / f"n_20/{instance_id}/meta.json").read_text()
        )


def test_loader_rejects_missing_instance(tmp_path):
    with pytest.raises(ValueError):
        load_instance(tmp_path / "missing")
