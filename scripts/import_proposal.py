"""Import a proposal CSV (e.g. out/s1.csv) into horaris.db as a version."""

import csv
import sqlite3
import sys
from pathlib import Path


def import_csv_to_db(db_path: Path, csv_path: Path, version_id: int, version_name: str) -> None:
    if not db_path.exists():
        print(f"Error: Database {db_path} does not exist.")
        sys.exit(1)
    if not csv_path.exists():
        print(f"Error: CSV {csv_path} does not exist.")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")

    # Check/upsert versio_horari
    existing = conn.execute("SELECT id_versio FROM versio_horari WHERE id_versio = ?", (version_id,)).fetchone()
    if existing:
        conn.execute(
            "UPDATE versio_horari SET nom = ?, mode = 'complet', semestre = 1 WHERE id_versio = ?",
            (version_name, version_id),
        )
    else:
        conn.execute(
            (
                "INSERT INTO versio_horari (id_versio, nom, mode, semestre, id_versio_referencia) "
                "VALUES (?, ?, 'complet', 1, 1)"
            ),
            (version_id, version_name),
        )

    # Clean old assignments for this version
    conn.execute("DELETE FROM assignacio WHERE id_versio = ?", (version_id,))

    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            aula = r["aula"].strip() if r.get("aula") and r["aula"].strip() else None
            rows.append((version_id, r["id_sessio"].strip(), r["dia"].strip(), r["h_ini"].strip(), aula, None))

    conn.executemany(
        "INSERT INTO assignacio (id_versio, id_sessio, dia, h_ini, aula, data) VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    print(f"Éxito: Versión {version_id} ('{version_name}') cargada en {db_path} con {len(rows)} asignaciones.")


if __name__ == "__main__":
    db = Path("horaris.db")
    csv_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out/s1.csv")
    v_id = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    v_nom = sys.argv[3] if len(sys.argv) > 3 else "s1"
    import_csv_to_db(db, csv_file, v_id, v_nom)
