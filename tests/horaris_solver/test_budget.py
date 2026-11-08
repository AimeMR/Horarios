from __future__ import annotations

import math

import pytest

from horaris_solver.solver.budget import (
    PORTFOLIO_MIN_TOTAL_S,
    Deadline,
    next_cpsat_slice,
    split_hybrid,
    split_portfolio,
)

TOTALS = [1, 10, 20, 59, 300, 3600]


class FakeClock:
    def __init__(self, now: float = 100.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.mark.parametrize("total", TOTALS)
def test_split_hybrid_parts_positive_and_within_total(total: float) -> None:
    p1, p2 = split_hybrid(total)
    assert p1 > 0
    assert p2 > 0
    assert p1 + p2 <= total


@pytest.mark.parametrize("total", [0, -1, -0.5, math.nan])
def test_split_hybrid_rejects_non_positive(total: float) -> None:
    with pytest.raises(ValueError):
        split_hybrid(total)


@pytest.mark.parametrize("total", [t for t in TOTALS if t >= PORTFOLIO_MIN_TOTAL_S])
def test_split_portfolio_parts_within_total(total: float) -> None:
    b = split_portfolio(total)
    assert b.greedy_s + b.cpsat_s + b.phase2_s <= total
    assert b.phase2_s >= 0.3 * total - 1e-9
    assert 2 <= b.greedy_s <= 120
    assert 0 < b.repair_s <= min(45, b.greedy_s / 4)
    assert 0 < b.first_cpsat_s <= b.cpsat_s


def test_split_portfolio_formula_at_300() -> None:
    b = split_portfolio(300)
    assert b.greedy_s == 60
    assert b.repair_s == 15
    assert b.cpsat_s == 150
    assert b.first_cpsat_s == pytest.approx(90)
    assert b.phase2_s == 90


def test_split_portfolio_caps_greedy_and_repair() -> None:
    b = split_portfolio(3600)
    assert b.greedy_s == 120
    assert b.repair_s == 30
    assert b.cpsat_s == 1800


@pytest.mark.parametrize("total", [1, 10, 19.99, 0, -5, math.nan])
def test_split_portfolio_rejects_small_total(total: float) -> None:
    with pytest.raises(ValueError):
        split_portfolio(total)


def test_next_cpsat_slice_divides_remaining() -> None:
    assert next_cpsat_slice(90.0, 3) == pytest.approx(30.0)


def test_next_cpsat_slice_never_negative() -> None:
    assert next_cpsat_slice(-5.0, 2) == 0.0


@pytest.mark.parametrize("attempts", [0, -1])
def test_next_cpsat_slice_rejects_no_attempts(attempts: int) -> None:
    with pytest.raises(ValueError):
        next_cpsat_slice(10.0, attempts)


def test_deadline_remaining_decreases_and_never_negative() -> None:
    clock = FakeClock()
    deadline = Deadline(10.0, clock=clock)
    assert deadline.remaining() == pytest.approx(10.0)
    clock.now += 4.0
    assert deadline.remaining() == pytest.approx(6.0)
    clock.now += 100.0
    assert deadline.remaining() == 0.0


def test_deadline_cap_limits_to_remaining() -> None:
    clock = FakeClock()
    deadline = Deadline(10.0, clock=clock)
    assert deadline.cap(3.0) == pytest.approx(3.0)
    clock.now += 8.0
    assert deadline.cap(5.0) == pytest.approx(2.0)
    clock.now += 5.0
    assert deadline.cap(5.0) == 0.0
