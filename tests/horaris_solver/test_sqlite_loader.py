"""SqliteTimetableSource against a tiny in-memory schema subset."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from horaris_solver.adapters.sqlite_loader import SqliteTimetableSource


def _create_mini_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE facultat (id_facultat TEXT PRIMARY KEY, nom TEXT NOT NULL);
        INSERT INTO facultat VALUES ('EE', 'Escola');

        CREATE TABLE aula (
            codi TEXT PRIMARY KEY,
            edifici TEXT,
            tipus TEXT,
            capacitat INTEGER,
            ordinaria INTEGER NOT NULL DEFAULT 0,
            integrat INTEGER NOT NULL DEFAULT 0,
            nomes_plab INTEGER NOT NULL DEFAULT 0,
            dins_aulari INTEGER NOT NULL DEFAULT 1,
            admet_noves INTEGER NOT NULL DEFAULT 1,
            descripcio TEXT,
            id_facultat TEXT
        );
        INSERT INTO aula (codi, edifici, tipus, capacitat, ordinaria, descripcio)
        VALUES ('Q1/1011', 'Q1', 'Aules docents', 40, 1, '');

        CREATE TABLE titulacio (
            codi TEXT PRIMARY KEY,
            nom TEXT,
            nivell TEXT NOT NULL,
            id_facultat TEXT
        );
        INSERT INTO titulacio VALUES ('GED', 'GED', 'grau', 'EE');

        CREATE TABLE cohort (
            id_cohort TEXT PRIMARY KEY,
            titulacio TEXT NOT NULL,
            curs TEXT NOT NULL,
            torn_requerit TEXT
        );
        INSERT INTO cohort VALUES ('GED:1r', 'GED', '1r', 'mati');

        CREATE TABLE assignatura (
            codi TEXT PRIMARY KEY,
            nom TEXT NOT NULL,
            id_departament TEXT
        );
        INSERT INTO assignatura VALUES ('COD1', 'Assig1', NULL);

        CREATE TABLE assignatura_cohort (
            codi TEXT NOT NULL,
            id_cohort TEXT NOT NULL,
            PRIMARY KEY (codi, id_cohort)
        );
        INSERT INTO assignatura_cohort VALUES ('COD1', 'GED:1r');

        CREATE TABLE grup (
            id_grup TEXT PRIMARY KEY,
            codi TEXT NOT NULL,
            grup TEXT NOT NULL,
            tipus TEXT NOT NULL,
            numero TEXT NOT NULL,
            linia TEXT NOT NULL,
            id_grup_teoria TEXT,
            alumnes INTEGER NOT NULL DEFAULT 0,
            alumnes_origen TEXT NOT NULL,
            capacitat_grup INTEGER,
            sense_espai INTEGER NOT NULL DEFAULT 0,
            fixada_motiu TEXT,
            torn_requerit TEXT NOT NULL
        );
        INSERT INTO grup VALUES (
            'COD1·TE/11', 'COD1', 'TE/11', 'TE', '11', '11', NULL,
            30, 'sigma', 40, 0, NULL, 'mati'
        );

        CREATE TABLE profe (id_profe TEXT PRIMARY KEY, nomes_practiques INTEGER NOT NULL DEFAULT 0);
        INSERT INTO profe VALUES ('D001', 0);

        CREATE TABLE docencia (
            id_profe TEXT NOT NULL,
            id_grup TEXT NOT NULL,
            vigent_des_de TEXT NOT NULL,
            vigent_fins TEXT,
            PRIMARY KEY (id_profe, id_grup, vigent_des_de)
        );
        INSERT INTO docencia VALUES ('D001', 'COD1·TE/11', '2026-09-01', NULL);

        CREATE TABLE activitat (
            activitat_id TEXT PRIMARY KEY,
            id_grup TEXT NOT NULL,
            dia TEXT NOT NULL,
            h_ini TEXT NOT NULL,
            h_fi TEXT NOT NULL,
            setmana_primera TEXT NOT NULL,
            setmana_ultima TEXT NOT NULL,
            n_sessions INTEGER NOT NULL
        );
        INSERT INTO activitat VALUES (
            'A1', 'COD1·TE/11', 'L', '08:30', '10:30', '2026-W38', '2026-W38', 1
        );

        CREATE TABLE sessio (
            id_sessio TEXT PRIMARY KEY,
            activitat_id TEXT,
            id_grup TEXT NOT NULL,
            id_escenari TEXT,
            id_compartida TEXT,
            dc TEXT,
            setmana TEXT NOT NULL,
            durada_min INTEGER NOT NULL,
            data_partida TEXT NOT NULL,
            dia_partida TEXT NOT NULL,
            h_ini_partida TEXT NOT NULL,
            aula_partida TEXT,
            aules_addicionals_partida TEXT,
            semestre INTEGER GENERATED ALWAYS AS (
                CASE WHEN CAST(strftime('%m', data_partida) AS INTEGER) IN (9, 10, 11, 12, 1)
                     THEN 1 ELSE 2 END) VIRTUAL
        );
        INSERT INTO sessio (
            id_sessio, activitat_id, id_grup, setmana, durada_min,
            data_partida, dia_partida, h_ini_partida, aula_partida
        ) VALUES (
            'S00001', 'A1', 'COD1·TE/11', '2026-W38', 120,
            '2026-09-14', 'L', '08:30', 'Q1/1011'
        );

        CREATE TABLE calendari (
            id INTEGER PRIMARY KEY,
            data TEXT NOT NULL,
            tipus TEXT NOT NULL,
            h_ini TEXT,
            h_fi TEXT,
            motiu TEXT NOT NULL,
            font TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


def test_sqlite_loader_reads_session(tmp_path: Path) -> None:
    db = tmp_path / "mini.db"
    _create_mini_db(db)
    data = SqliteTimetableSource(db).load(semestre=1)
    assert "S00001" in data.sessions
    assert data.sessions["S00001"].teachers == frozenset({"D001"})
    assert data.sessions["S00001"].cohorts == ("GED:1r",)
    assert "Q1/1011" in data.rooms
    assert "A1" in data.activities


def _add_online_activity(path: Path) -> None:
    """Add a second TE group whose activity is the online activity A0826."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        INSERT INTO grup VALUES (
            'COD1·TE/12', 'COD1', 'TE/12', 'TE', '12', '12', NULL,
            30, 'sigma', 40, 0, NULL, 'mati'
        );
        INSERT INTO activitat VALUES (
            'A0826', 'COD1·TE/12', 'M', '08:30', '10:30', '2026-W38', '2026-W38', 1
        );
        INSERT INTO sessio (
            id_sessio, activitat_id, id_grup, setmana, durada_min,
            data_partida, dia_partida, h_ini_partida, aula_partida
        ) VALUES (
            'S00002', 'A0826', 'COD1·TE/12', '2026-W38', 120,
            '2026-09-15', 'M', '08:30', 'Q1/1011'
        );
        """
    )
    conn.commit()
    conn.close()


def test_sqlite_loader_loads_a0826_as_regular(tmp_path: Path) -> None:
    db = tmp_path / "mini.db"
    _create_mini_db(db)
    _add_online_activity(db)
    data = SqliteTimetableSource(db).load(semestre=1)
    online = data.sessions["S00002"]
    assert online.online is False and online.sense_espai is False
    assert data.activities["A0826"].sense_espai is False
    regular = data.sessions["S00001"]
    assert regular.online is False and regular.sense_espai is False
    assert data.activities["A1"].sense_espai is False
