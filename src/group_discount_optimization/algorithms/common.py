"""Общие структуры результатов алгоритмов."""

from __future__ import annotations

from dataclasses import dataclass

from ..evaluation import Evaluation
from ..instance import Instance


@dataclass(frozen=True, slots=True)
class AlgorithmResult:
    """Результат работы алгоритма над одним экземпляром."""

    method: str
    selected_item_ids: tuple[int, ...]
    evaluation: Evaluation
    elapsed_seconds: float
    evaluated_candidates: int = 0

    @property
    def total_utility(self) -> float:
        return self.evaluation.total_utility

    @property
    def total_weight(self) -> float:
        return self.evaluation.total_weight

    @property
    def feasible(self) -> bool:
        return self.evaluation.feasible

    @property
    def active_group_ids(self) -> tuple[int, ...]:
        return self.evaluation.active_group_ids

    def group_counts(self, instance: Instance) -> dict[str, int]:
        """Вернуть распределение выбранных предметов по группам и вне групп."""
        counts = {f"group_{group.group_id}": 0 for group in instance.groups}
        grouped_ids = {item_id for group in instance.groups for item_id in group.item_ids}
        outside = 0
        selected = set(self.selected_item_ids)
        for group in instance.groups:
            counts[f"group_{group.group_id}"] = sum(
                item_id in selected for item_id in group.item_ids
            )
        outside = sum(item_id not in grouped_ids for item_id in selected)
        counts["outside"] = outside
        return counts
