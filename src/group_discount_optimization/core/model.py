"""Data structures for the group-discount single-knapsack problem."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


def _require_int(name: str, value: Any, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer, got {type(value).__name__}")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


def _require_nonnegative_number(name: str, value: Any) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number, got {type(value).__name__}")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _require_percent(name: str, value: Any) -> int | float:
    result = _require_nonnegative_number(name, value)
    if result > 50:
        raise ValueError(f"{name} must be between 0 and 50 percent")
    return result


@dataclass(frozen=True, slots=True)
class Item:
    """An indivisible candidate belonging to exactly one group."""

    item_id: str
    weight: int
    utility: int | float

    def __post_init__(self) -> None:
        if not isinstance(self.item_id, str) or not self.item_id.strip():
            raise ValueError("item_id must be a non-empty string")
        _require_int("weight", self.weight, minimum=0)
        _require_nonnegative_number("utility", self.utility)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Item":
        return cls(item_id=str(data["item_id"]), weight=data["weight"], utility=data["utility"])

    def to_dict(self) -> dict[str, Any]:
        return {"item_id": self.item_id, "weight": self.weight, "utility": self.utility}


@dataclass(frozen=True, slots=True)
class Group:
    """A category with its own weight discount and utility bonus percentages."""

    group_id: str
    weight_discount_percent: int | float
    utility_bonus_percent: int | float
    items: tuple[Item, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.group_id, str) or not self.group_id.strip():
            raise ValueError("group_id must be a non-empty string")
        _require_percent("weight_discount_percent", self.weight_discount_percent)
        _require_percent("utility_bonus_percent", self.utility_bonus_percent)
        ids = [item.item_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError(f"item_id values must be unique within group {self.group_id}")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Group":
        return cls(
            group_id=str(data["group_id"]),
            weight_discount_percent=data["weight_discount_percent"],
            utility_bonus_percent=data["utility_bonus_percent"],
            items=tuple(Item.from_dict(item) for item in data["items"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "weight_discount_percent": self.weight_discount_percent,
            "utility_bonus_percent": self.utility_bonus_percent,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass(frozen=True, slots=True)
class ProblemInstance:
    """One knapsack, one global capacity, an exact selected-item count and grouped items."""

    instance_id: str
    max_weight: int
    target_item_count: int
    groups: tuple[Group, ...]
    seed: int | None = None
    generation: dict[str, Any] | None = None
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.instance_id, str) or not self.instance_id.strip():
            raise ValueError("instance_id must be a non-empty string")
        _require_int("max_weight", self.max_weight, minimum=0)
        _require_int("target_item_count", self.target_item_count, minimum=0)
        _require_int("schema_version", self.schema_version, minimum=1)
        if self.seed is not None:
            _require_int("seed", self.seed, minimum=0)
        if not self.groups:
            raise ValueError("An instance must contain at least one group")
        group_ids = [group.group_id for group in self.groups]
        if len(group_ids) != len(set(group_ids)):
            raise ValueError("group_id values must be unique")
        total_items = sum(len(group.items) for group in self.groups)
        if self.target_item_count > total_items:
            raise ValueError(
                f"target_item_count ({self.target_item_count}) cannot exceed total item count ({total_items})"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProblemInstance":
        return cls(
            instance_id=str(data["instance_id"]),
            max_weight=data["max_weight"],
            target_item_count=data["target_item_count"],
            groups=tuple(Group.from_dict(group) for group in data["groups"]),
            seed=data.get("seed"),
            generation=data.get("generation"),
            schema_version=data.get("schema_version", 1),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": self.schema_version,
            "instance_id": self.instance_id,
            "seed": self.seed,
            "max_weight": self.max_weight,
            "target_item_count": self.target_item_count,
            "groups": [group.to_dict() for group in self.groups],
        }
        if self.generation is not None:
            data["generation"] = self.generation
        return data
