"""Morning / afternoon slot windows."""

from horaris_solver.domain.models import MATI, TARDA, fmt, hm
from horaris_solver.solver import slots as slots_mod
from horaris_solver.solver.slots import slots_for_duration


def test_turn_windows() -> None:
    assert fmt(MATI[0]) == "08:30"
    assert fmt(MATI[1]) == "14:30"
    assert fmt(TARDA[0]) == "15:00"
    assert fmt(TARDA[1]) == "21:00"


def test_morning_slots_fit_window() -> None:
    starts = slots_for_duration(120, "mati")
    assert starts[0] == MATI[0]
    assert all(s + 120 <= MATI[1] for s in starts)
    assert TARDA[0] not in starts


def test_afternoon_slots_start_at_1500() -> None:
    starts = slots_for_duration(60, "tarda")
    assert starts[0] == TARDA[0]
    assert all(s >= TARDA[0] and s + 60 <= TARDA[1] for s in starts)
    assert MATI[1] not in starts  # 14:30 is not an afternoon start


def test_start_fits_turn_rejects_morning_lab_past_window() -> None:
    """A 180-min lab at 12:30 ends at 15:30, after the 14:30 morning close."""
    assert hasattr(slots_mod, "start_fits_turn")
    assert slots_mod.start_fits_turn(hm("12:30"), 180, "mati") is False


def test_start_fits_turn_accepts_exact_morning_end() -> None:
    assert hasattr(slots_mod, "start_fits_turn")
    assert slots_mod.start_fits_turn(hm("12:30"), 120, "mati") is True


def test_start_fits_turn_afternoon_bounds() -> None:
    assert hasattr(slots_mod, "start_fits_turn")
    assert slots_mod.start_fits_turn(hm("15:00"), 180, "tarda") is True
    assert slots_mod.start_fits_turn(hm("18:30"), 180, "tarda") is False
