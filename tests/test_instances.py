"""Проверки фиксированного набора сырых экземпляров и генератора."""

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


def test_committed_raw_arrays_and_metadata_are_valid():
    for path in instance_dirs():
        instance = load_instance(path)
        assert instance.weights.dtype.kind in "iu"
        assert instance.profits.dtype.kind in "iu"
        assert instance.group_ids.dtype.kind in "iu"
        assert instance.item_count == len(instance.weights)
        assert instance.weights.shape == instance.profits.shape == instance.group_ids.shape
        assert 1 <= instance.target_item_count <= instance.item_count
        assert all(1 <= int(value) <= 100 for value in instance.weights)
        assert all(1 <= int(value) <= 100 for value in instance.profits)
        assert all(0 <= group.weight_discount_percent <= 50 for group in instance.groups)
        assert all(0 <= group.utility_bonus_percent <= 50 for group in instance.groups)


def test_smallest_instances_select_five_items():
    for path in (DATA_DIR / "n_10").glob("instance_*"):
        assert load_instance(path).target_item_count == 5


def test_generator_creates_npz_and_metadata_without_text_or_config_inputs(tmp_path):
    output = tmp_path / "instances"
    created = generate_dataset(output, sizes=(10, 20), instances_per_size=2, group_count=3, seed=123)
    assert len(created) == 4
    for path in created:
        assert (path / "data.npz").is_file()
        assert (path / "meta.json").is_file()
        assert not list(path.glob("*.txt"))
        instance = load_instance(path)
        assert instance.item_count in (10, 20)
    assert (output / "manifest.csv").is_file()


def test_generator_is_reproducible(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    generate_dataset(first, sizes=(20,), instances_per_size=1, seed=7)
    generate_dataset(second, sizes=(20,), instances_per_size=1, seed=7)
    with np.load(first / "n_20/instance_001/data.npz") as a, np.load(second / "n_20/instance_001/data.npz") as b:
        for key in ("weights", "profits", "group_ids"):
            np.testing.assert_array_equal(a[key], b[key])
    assert json.loads((first / "n_20/instance_001/meta.json").read_text()) == json.loads(
        (second / "n_20/instance_001/meta.json").read_text()
    )


def test_loader_rejects_missing_instance(tmp_path):
    with pytest.raises(ValueError):
        load_instance(tmp_path / "missing")
