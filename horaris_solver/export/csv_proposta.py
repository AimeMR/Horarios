"""Write / read jury proposal CSV: id_sessio,dia,h_ini,aula."""

from __future__ import annotations

import csv
from pathlib import Path

from horaris_solver.domain.models import ONLINE_ROOM, Assignment, fmt, hm


def read_proposta_csv(path: Path) -> list[Assignment]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"id_sessio", "dia", "h_ini", "aula"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f"proposta CSV must have columns {sorted(required)}")
        out: list[Assignment] = []
        for line, row in enumerate(reader, start=2):
            if any(row.get(column) is None for column in ("id_sessio", "dia", "h_ini")):
                raise ValueError(f"proposta CSV line {line} is missing columns")
            out.append(
                Assignment(
                    session_id=row["id_sessio"].strip(),
                    day=row["dia"].strip(),
                    start_min=hm(row["h_ini"]),
                    room=(row.get("aula") or "").strip(),
                )
            )
        return out


def write_proposta_csv(
    path: Path,
    assignments: list[Assignment],
    order: tuple[str, ...] | None = None,
    *,
    online_ids: frozenset[str] = frozenset(),
) -> None:
    """Write the proposal to CSV."""
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
