"""Жадные алгоритмы для задачи с пороговыми групповыми эффектами."""

from __future__ import annotations

from itertools import product
from time import perf_counter

from ..evaluation import Evaluation, evaluate_selection
from ..instance import Instance
from .common import AlgorithmResult

_TOLERANCE = 1e-9


def _empty_evaluation(instance: Instance) -> Evaluation:
    return evaluate_selection(instance, ())


def _finish(
    instance: Instance,
    method: str,
    selected: list[int] | tuple[int, ...],
    started: float,
    evaluated: int,
) -> AlgorithmResult:
    evaluation = evaluate_selection(instance, selected)
    return AlgorithmResult(
        method=method,
        selected_item_ids=tuple(selected),
        evaluation=evaluation,
        elapsed_seconds=perf_counter() - started,
        evaluated_candidates=evaluated,
    )


def solve_greedy_ratio(instance: Instance) -> AlgorithmResult:
    """Жадный алгоритм по исходному отношению полезности к весу.

    Предметы сортируются по ``utility / weight`` и добавляются, пока набор
    укладывается в рюкзак. Если до Q предметов добрать не удалось, оставшиеся
    места заполняются самыми лёгкими предметами. Групповые эффекты напрямую
    в критерии не участвуют, но проверяются через ``evaluate_selection``.
    """
    started = perf_counter()
    selected: list[int] = []
    evaluated = 0
    q = instance.target_item_count
    capacity = instance.capacity

    ordered = sorted(
        instance.items,
        key=lambda item: (-(item.utility / item.weight), item.item_id),
    )
    for item in ordered:
        if len(selected) >= q:
            break
        evaluation = evaluate_selection(instance, selected + [item.item_id])
        evaluated += 1
        if evaluation.total_weight <= capacity + _TOLERANCE:
            selected.append(item.item_id)

    if len(selected) < q:
        remaining = [
            item
            for item in sorted(instance.items, key=lambda item: (item.weight, item.item_id))
            if item.item_id not in selected
        ]
        for item in remaining:
            if len(selected) >= q:
                break
            evaluation = evaluate_selection(instance, selected + [item.item_id])
            evaluated += 1
            if evaluation.total_weight <= capacity + _TOLERANCE:
                selected.append(item.item_id)

    if len(selected) < q:
        # Даже если допустимый набор не собирается, возвращаем ровно Q
        # предметов: это позволяет увидеть, где именно эвристика не справилась.
        for item in sorted(instance.items, key=lambda item: (item.weight, item.item_id)):
            if len(selected) >= q:
                break
            if item.item_id not in selected:
                selected.append(item.item_id)

    return _finish(instance, "greedy_ratio", selected, started, evaluated)


def _greedy_actions(instance: Instance) -> tuple[list[int], Evaluation, int]:
    """Жадный выбор по одному предмету или сразу по групповому пакету.

    Одиночный ход добавляет один предмет. Групповой ход добавляет столько
    предметов группы, сколько нужно для достижения порога. Каждый ход
    оценивается через ``evaluate_selection``, поэтому активация скидки и
    бонуса учитывается по фактическому изменению веса и полезности.
    """
    selected: list[int] = []
    current = _empty_evaluation(instance)
    evaluated = 1
    q = instance.target_item_count
    capacity = instance.capacity

    while len(selected) < q:
        selected_set = set(selected)
        slots = q - len(selected)
        actions: list[list[int]] = []

        for item in instance.items:
            if item.item_id not in selected_set:
                actions.append([item.item_id])

        for group in instance.groups:
            selected_in_group = sum(item_id in selected_set for item_id in group.item_ids)
            need = group.min_selected_for_discount - selected_in_group
            if need <= 0 or need > slots:
                continue
            candidates = sorted(
                (
                    item
                    for item in instance.items
                    if item.item_id in group.item_ids and item.item_id not in selected_set
                ),
                key=lambda item: (-(item.utility / item.weight), item.item_id),
            )
            if len(candidates) >= need:
                actions.append([item.item_id for item in candidates[:need]])

        unique_actions = list({tuple(action): action for action in actions}.values())
        scored: list[tuple[bool, tuple[float, float, float, int], list[int], Evaluation]] = []
        for action in unique_actions:
            evaluation = evaluate_selection(instance, selected + action)
            evaluated += 1
            fits = evaluation.total_weight <= capacity + _TOLERANCE
            delta_utility = evaluation.total_utility - current.total_utility
            delta_weight = evaluation.total_weight - current.total_weight
            if delta_weight <= _TOLERANCE:
                score = (1.0, delta_utility, -evaluation.total_weight, -len(action))
            else:
                score = (
                    0.0,
                    delta_utility / delta_weight,
                    delta_utility,
                    -evaluation.total_weight,
                )
            scored.append((fits, score, action, evaluation))

        feasible = [candidate for candidate in scored if candidate[0]]
        if feasible:
            chosen = max(feasible, key=lambda candidate: candidate[1])
        else:
            chosen = min(
                scored,
                key=lambda candidate: (candidate[3].total_weight, candidate[1]),
            )

        selected.extend(chosen[2])
        current = chosen[3]

    return selected, current, evaluated


def _ranked(items: list, mode: str) -> list:
    if mode == "ratio":
        return sorted(items, key=lambda item: (-(item.utility / item.weight), item.item_id))
    if mode == "utility":
        return sorted(items, key=lambda item: (-item.utility, item.weight, item.item_id))
    if mode == "weight":
        return sorted(items, key=lambda item: (item.weight, -item.utility, item.item_id))
    raise ValueError(f"Неизвестный режим ранжирования: {mode}")


def _greedy_counts(
    instance: Instance, modes: tuple[str, ...] = ("ratio", "utility", "weight")
) -> tuple[list[int], Evaluation, int]:
    """Перебрать допустимые распределения числа предметов по группам.

    Для каждого распределения предметы внутри группы выбираются жадно по
    одному из правил: отношение полезности к весу, полезность или вес. Сам
    перебор идёт не по предметам, а по небольшим векторам counts, поэтому
    метод остаётся жадным и быстро работает на n до 100.
    """
    q = instance.target_item_count
    categories = [
        [instance.items_by_id[item_id] for item_id in group.item_ids]
        for group in instance.groups
    ]
    categories.append([instance.items_by_id[item_id] for item_id in instance.ungrouped_item_ids])

    rankings = [
        {mode: _ranked(items, mode) for mode in modes}
        for items in categories
    ]
    ranges = [range(0, min(len(items), q) + 1) for items in categories]
    best_evaluation: Evaluation | None = None
    best_selected: list[int] | None = None
    evaluated = 0

    for counts in product(*ranges):
        if sum(counts) != q:
            continue
        for selected_modes in product(modes, repeat=len(categories)):
            selected: list[int] = []
            for index, count in enumerate(counts):
                selected.extend(
                    item.item_id
                    for item in rankings[index][selected_modes[index]][:count]
                )
            evaluation = evaluate_selection(instance, selected)
            evaluated += 1
            if not evaluation.feasible:
                continue
            if (
                best_evaluation is None
                or evaluation.total_utility > best_evaluation.total_utility + _TOLERANCE
                or (
                    abs(evaluation.total_utility - best_evaluation.total_utility) <= _TOLERANCE
                    and evaluation.total_weight < best_evaluation.total_weight - _TOLERANCE
                )
            ):
                best_evaluation = evaluation
                best_selected = selected

    if best_evaluation is None or best_selected is None:
        return [], _empty_evaluation(instance), evaluated
    return best_selected, best_evaluation, evaluated


def solve_greedy_group_aware(instance: Instance) -> AlgorithmResult:
    """Улучшенный жадный алгоритм с явным учётом групповых порогов.

    Рассматриваются два конструктивных правила:

    1. последовательное добавление одного предмета или целого группового
       пакета до порога;
    2. перебор распределения Q мест по группам и жадное заполнение каждой
       группы по одному из трёх правил.

    Из полученных допустимых решений выбирается лучшее по полезности.
    """
    started = perf_counter()
    candidates: list[tuple[list[int], Evaluation, int]] = []
    candidates.append(_greedy_actions(instance))
    candidates.append(_greedy_counts(instance))
    evaluated = sum(candidate[2] for candidate in candidates)

    usable = [candidate for candidate in candidates if candidate[1].feasible]
    pool = usable or candidates
    selected, evaluation, _ = max(
        pool,
        key=lambda candidate: (candidate[1].total_utility, -candidate[1].total_weight),
    )

    return AlgorithmResult(
        method="greedy_group_aware",
        selected_item_ids=tuple(selected),
        evaluation=evaluation,
        elapsed_seconds=perf_counter() - started,
        evaluated_candidates=evaluated,
    )
