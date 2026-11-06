"""Алгоритмы решения задачи с пороговыми групповыми эффектами."""

from .baseline import BaselineResult, solve_exhaustive_no_groups, solve_greedy_no_groups
from .common import AlgorithmResult
from .exhaustive import solve_exhaustive
from .greedy import solve_greedy_group_aware, solve_greedy_ratio

__all__ = [
    "AlgorithmResult",
    "BaselineResult",
    "solve_exhaustive",
    "solve_exhaustive_no_groups",
    "solve_greedy_group_aware",
    "solve_greedy_no_groups",
    "solve_greedy_ratio",
]
