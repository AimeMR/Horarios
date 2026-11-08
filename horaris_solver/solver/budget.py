"""Time budget splitting and deadline tracking for the solver strategies."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass

PORTFOLIO_MIN_TOTAL_S: float = 20.0

_GREEDY_SHARE = 0.2
_GREEDY_MIN_S = 2.0
_GREEDY_MAX_S = 120.0
_REPAIR_MAX_S = 45.0
_CPSAT_SHARE = 0.5
_FIRST_CPSAT_SHARE = 0.6


@dataclass(frozen=True)
class PortfolioBudget:
    greedy_s: float
    repair_s: float
    cpsat_s: float
    first_cpsat_s: float
    phase2_s: float


def split_hybrid(total_s: float) -> tuple[float, float]:
    """Split the hybrid budget evenly between phase 1 and phase 2."""
    if not total_s > 0:
        raise ValueError(f"total_s must be > 0, got {total_s}")
    half = total_s / 2
    return half, total_s - half


def split_portfolio(total_s: float) -> PortfolioBudget:
    """Split the portfolio budget into greedy pool, CP-SAT and phase 2 shares."""
    if not total_s >= PORTFOLIO_MIN_TOTAL_S:
        raise ValueError(f"portfolio needs total_s >= {PORTFOLIO_MIN_TOTAL_S:g}, got {total_s}")
    greedy = min(max(float(math.floor(_GREEDY_SHARE * total_s)), _GREEDY_MIN_S), _GREEDY_MAX_S)
    cpsat = float(math.floor(_CPSAT_SHARE * total_s))
    return PortfolioBudget(
        greedy_s=greedy,
        repair_s=min(_REPAIR_MAX_S, greedy / 4),
        cpsat_s=cpsat,
        first_cpsat_s=_FIRST_CPSAT_SHARE * cpsat,
        phase2_s=total_s - greedy - cpsat,
    )


def next_cpsat_slice(remaining_s: float, attempts_left: int) -> float:
    """Share the remaining CP-SAT time evenly across the attempts still to run."""
    if attempts_left <= 0:
        raise ValueError(f"attempts_left must be > 0, got {attempts_left}")
    return max(0.0, remaining_s) / attempts_left


class Deadline:
    """Wall-clock deadline measured with an injectable monotonic clock."""

    def __init__(self, total_s: float, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._end = clock() + total_s

    def remaining(self) -> float:
        return max(0.0, self._end - self._clock())

    def cap(self, wanted_s: float) -> float:
        return min(wanted_s, self.remaining())
