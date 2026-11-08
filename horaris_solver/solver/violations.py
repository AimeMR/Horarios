"""Hard-rule violation record shared by validators, greedy, CP-SAT and repair."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Violation:
    """One broken hard rule.

    rule is one of "D1-TURN", "D2-CALENDAR", "D3-PINNED", "D4-CLASH", "D5-SHARED",
    "D6-POOL", "D7-SAME-KIND-DAY" or "MISSING".
    """

    rule: str
    activity_ids: tuple[str, ...]
    detail: str = ""
