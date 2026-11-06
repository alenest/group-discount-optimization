"""Полный перебор всех наборов ровно из Q предметов."""

from __future__ import annotations

from itertools import combinations
from time import perf_counter

from ..evaluation import Evaluation, evaluate_selection
from ..instance import Instance
from .common import AlgorithmResult


def _is_better(candidate: Evaluation, current: Evaluation) -> bool:
    """Сравнить два допустимых решения: полезность, затем меньший вес."""
    if candidate.total_utility > current.total_utility + 1e-9:
        return True
    if abs(candidate.total_utility - current.total_utility) <= 1e-9:
        return candidate.total_weight < current.total_weight - 1e-9
    return False


def solve_exhaustive(instance: Instance) -> AlgorithmResult:
    """Найти точный оптимум перебором сочетаний из Q предметов.

    Каждый набор оценивается через ``evaluate_selection``, поэтому пороговые
    эффекты групп учитываются ровно так же, как в остальных алгоритмах.
    """
    item_ids = tuple(item.item_id for item in instance.items)
    q = instance.target_item_count
    if q > len(item_ids):
        raise ValueError("Q не может превышать число предметов.")

    started = perf_counter()
    best_evaluation: Evaluation | None = None
    best_ids: tuple[int, ...] | None = None
    evaluated = 0

    for combination in combinations(item_ids, q):
        evaluated += 1
        evaluation = evaluate_selection(instance, combination)
        if not evaluation.feasible:
            continue
        if best_evaluation is None or _is_better(evaluation, best_evaluation):
            best_evaluation = evaluation
            best_ids = tuple(combination)

    if best_evaluation is None or best_ids is None:
        raise ValueError(
            f"Для экземпляра n={instance.n} не найдено допустимого решения ровно из Q предметов."
        )

    return AlgorithmResult(
        method="exhaustive",
        selected_item_ids=best_ids,
        evaluation=best_evaluation,
        elapsed_seconds=perf_counter() - started,
        evaluated_candidates=evaluated,
    )
