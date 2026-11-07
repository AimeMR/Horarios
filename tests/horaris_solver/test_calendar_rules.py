from datetime import date

from horaris_solver.solver.calendar_rules import remap_date, same_iso_week, week_monday


def test_remap_stays_in_iso_week() -> None:
    monday = date(2026, 9, 14)  # Monday
    assert remap_date(monday, "X") == date(2026, 9, 16)
    assert week_monday(remap_date(monday, "V")) == monday


def test_same_weekday_different_weeks_not_same_iso_week() -> None:
    assert not same_iso_week(date(2026, 9, 14), date(2026, 9, 21))
