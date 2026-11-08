"""Discrete start slots inside morning/afternoon windows."""

from __future__ import annotations

from horaris_solver.domain.models import MATI, TARDA


def start_fits_turn(start: int, duration_min: int, turn: str) -> bool:
    """True when [start, start+duration] sits entirely inside the required window."""
    end = start + duration_min
    if turn == "mati":
        return MATI[0] <= start and end <= MATI[1]
    if turn == "tarda":
        return TARDA[0] <= start and end <= TARDA[1]
    return (MATI[0] <= start and end <= MATI[1]) or (TARDA[0] <= start and end <= TARDA[1])


def slots_for_duration(duration_min: int, turn: str) -> list[int]:
    """Return candidate start minutes that fit entirely in the required window."""
    windows: list[tuple[int, int]]
    if turn == "mati":
        windows = [MATI]
    elif turn == "tarda":
        windows = [TARDA]
    else:
        windows = [MATI, TARDA]

    starts: list[int] = []
    for win_start, win_end in windows:
        # 30-minute grid matching typical school slots
        t = win_start
        while t + duration_min <= win_end:
            starts.append(t)
            t += 30
    return starts


def day_index(day: str) -> int:
    mapping = {"L": 0, "M": 1, "X": 2, "J": 3, "V": 4}
    return mapping[day]


def day_from_index(index: int) -> str:
    return ("L", "M", "X", "J", "V")[index]
