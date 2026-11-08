/**
 * Predicat «l'assignació `a` (amb la sessió `s`) pertany a la setmana»: una recuperació (`a.data`)
 * compta a la setmana de la seva data; la resta, a la setmana de la sessió.
 * Paràmetres: @setmana, @dilluns, @divendres.
 */
export const ASSIGNACIO_A_SETMANA_SQL = `((a.data IS NULL AND s.setmana = @setmana) OR (a.data BETWEEN @dilluns AND @divendres))`;

/** Data efectiva (AAAA-MM-DD) de l'assignació `a` de la sessió `s`; equival a `dataEfectiva` del domini. */
export const DATA_EFECTIVA_SQL = `COALESCE(a.data, date(s.data_partida, printf('%+d days', instr('LMXJV', a.dia) - instr('LMXJV', s.dia_partida))))`;
