# Recuentos esperados · paquet_fals

Filas que deben quedar en cada tabla de `db/migrations/0001_esquema_inicial.up.sql` (ya sin `grup_cohort`) tras cargar estas fixtures con el extractor (`extractor/load/`). Los usan los tests de carga.

| Tabla | Filas | Cómo sale |
|---|---:|---|
| facultat | 1 | constante `EE` |
| departament | 0 | sin carga |
| aula | 12 | 7 de `aules.csv` + 5 externas fijas (J/012, J/102, J/124, B3/0021, QC/1082). J/012 cuenta una sola vez |
| titulacio | 5 | GFA, GFB, GFC, MFA (de `plans.csv` y `titulacions_curs`) + GNOU (grado nuevo) |
| pla_estudis | 5 | 9001, 9002, 9003, 9004 + NOU (decisión 2) |
| pla_titulacio | 6 | (9001,GFA), (9002,GFB), (9002,GFC), (9003,MFA), (9004,GFA), (NOU,GNOU) |
| cohort | 6 | GFA:1r, GFA:?, GFB:2n, GFC:2n, MFA:M, GNOU:1r |
| assignatura | 8 | 900001…900006 + 900091, 900092 (grado nuevo) |
| assignatura_cohort | 9 | 7 de las sesiones base + 2 del grado nuevo |
| assignatura_pla | 9 | 7 de las sesiones base (900002 tiene 9001 y 9004) + 2 NOU |
| grup | 16 | 13 base + 3 del grado nuevo |
| profe | 10 | D901, D903, D904, D905, D906, D907, D908, D909 + N901, N902 |
| docencia | 16 | 13 de los grupos base (PAUL/812 sin docente; TE/31 con dos) + 3 del grado nuevo |
| escenari | 2 | contingencies, grau-nou-40 |
| indisponibilitat_profe | 0 | sin carga |
| activitat | 13 | una por (codi, grup, semestre, dia, h_ini, h_fi) de las 28 sesiones base |
| sessio | 34 | 28 de `sessions.csv` + 6 de `sessions_extra.csv` |
| calendari | 4 | festiu, no_lectiu, aturada (con horas), avaluacio |
| tancament_aula | 2 | `aules_tancades` de contingencies |
| cancellacio | 1 | `cancellades` de contingencies (S90014) |
| canvi_alumnes | 1 | `alumnes` de contingencies (900001 · TE/81 → 70) |
| versio_horari | 1 | `partida` |
| assignacio | 28 | una por sesión base (`proposta_partida.csv`); 4 con aula vacía (S90021, S90022, S90025, S90026) |
| relaxacio | 0 | sin carga |
| relaxacio_sessio | 0 | sin carga |
| registre_canvi | 0 | sin carga |

Notas de carga:

- `aula` vacía en la asignación: S90021, S90022 (TE/51, `sense_espai = 1`) y S90025, S90026 (PLAB/61). Son las únicas
  filas de `proposta_partida.csv` sin aula; la proposta tiene 28 filas y 24 con aula.
- Sesiones con `aules_addicionals_partida`: S90020 (Q8/8206).
- Pareja compartida: S90023 (P) y S90027 (S) comparten `id_compartida` `CP9001`; igual S90024 y S90028.
- Sesiones en aula externa: S90017, S90018 (J/012).
- Sesiones del grado nuevo: N90001…N90006, sin aula, sin `activitat_id` y con `id_escenari` = `grau-nou-40`.

## `grup.id_grup_teoria`

Regla (criterio del verificador, `horaris/check.py`): primero la TE de la misma asignatura cuyo número es exactamente
la línea del subgrupo; si no existe, la única TE de esa línea; si no hay ninguna de la línea, la TE con el mismo
número que el subgrupo (regla «/challenge H2»: TE/415 y PAUL/415 son el mismo alumnado); si no, NULL. Los `id_grup`
van como `codi·grup`.

| Subgrupo | id_grup_teoria | Motivo |
|---|---|---|
| 900001·PAUL/811 | 900001·TE/81 | línea 81 |
| 900001·PAUL/812 | 900001·TE/81 | línea 81 |
| 900002·PAUL/311 | 900002·TE/31 | línea 31; hay TE/31 y TE/310, gana la de número exacto 31 |
| 900002·PLAB/311 | 900002·TE/31 | línea 31; mismo caso ambiguo |
| 900091·PAUL/911 | 900091·TE/91 | línea 91 |
| 900003·PAUL/415 | 900003·TE/415 | línea 41 sin TE; regla H2: TE/415 tiene su mismo número |
| 900006·PLAB/61 | NULL | línea 61; la asignatura no tiene TE |
| 900092·PAUL/921 | NULL | línea 92; la asignatura no tiene TE/92 |

Subgrupos con `id_grup_teoria`: 6. Subgrupos sin él: 2. Los grupos TE nunca lo tienen (CHECK del esquema).
