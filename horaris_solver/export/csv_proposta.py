"""Write jury proposal CSV: id_sessio,dia,h_ini,aula."""

from __future__ import annotations

import csv
from pathlib import Path

from horaris_solver.domain.models import Assignment, fmt


def write_proposta_csv(
    path: Path,
    assignments: list[Assignment],
    order: tuple[str, ...] | None = None,
) -> None:
    by_id = {a.session_id: a for a in assignments}
    if order:
        ordered = [by_id[sid] for sid in order if sid in by_id]
        extras = [a for a in assignments if a.session_id not in set(order)]
        rows = ordered + extras
    else:
        rows = sorted(assignments, key=lambda a: a.session_id)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id_sessio", "dia", "h_ini", "aula"])
        writer.writeheader()
        for assignment in rows:
            writer.writerow(
                {
                    "id_sessio": assignment.session_id,
                    "dia": assignment.day,
                    "h_ini": fmt(assignment.start_min),
                    "aula": assignment.room,
                }
            )
