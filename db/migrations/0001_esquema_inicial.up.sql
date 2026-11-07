-- =====================================================================================================
-- 0001_esquema_inicial (up) · Base de datos del reto de horarios (UAB THE HACK! 2026)
--
-- Crea el esquema inicial completo de la BD: 26 tablas con sus índices.
-- Motor: SQLite >= 3.35 (columnas generadas y json_valid).
-- Forma = esquema.sql acordado + cambios aprobados el 2026-11-07:
--   1 · Sin PRAGMA foreign_keys ni BEGIN/COMMIT: las FK las activa cada conexión y la transacción la abre el
--       runner (un PRAGMA dentro de la transacción de la migración no tiene efecto).
--   2 · Turno del grupo (grup.torn_requerit, y cohort.torn_requerit pasa a nullable): los dobles de 1º/2º van
--       de tarde y 'GEI:?' mezcla turnos, así que el turno es del grupo, no de la cohorte.
--   3 · Sin grup_cohort (ni su índice ix_grup_cohort_coh): los datos demuestran que la cohorte depende solo de
--       la asignatura (basta assignatura_cohort).
--   4 · FK en registre_canvi (de_aula y a_aula -> aula): integridad de las aulas de origen y destino.
--   5 · Índices nuevos (ix_sessio_escenari, ix_sessio_aules_addicionals, ix_indisp_escenari, ix_versio_escenari,
--       ix_registre_desti, y ix_registre_de_aula / ix_registre_a_aula para las FK nuevas del cambio 4):
--       toda FK nueva con índice (regla del proyecto).
-- Por qué una sola migración: no se ha aplicado nada en ningún sitio y su único tema es crear el esquema inicial.
-- Los comentarios PENDIENTE ya resueltos (motor, id_grup, cohortes, vigent_des_de, facultat/departament) se han
-- sustituido por la decisión tomada.
--
-- Origen de cada tabla (ver docs/04-propuesta-base-de-datos.md):
--   [paquet]     se llena con los CSV/JSON del paquete
--   [sin datos]  estaba en el boceto del equipo, el paquete no trae datos
--   [extensión]  característica propia del equipo
--   [trabajo]    la genera el sistema
--
-- Convenciones: fechas TEXT ISO 'AAAA-MM-DD'; horas TEXT 'HH:MM'; semanas ISO TEXT 'AAAA-Www';
-- booleanos INTEGER 0/1; días 'L','M','X','J','V'.
-- =====================================================================================================

-- -----------------------------------------------------------------------------------------------------
-- facultat [sin datos]
-- Una sola fila (Escola d'Enginyeria). Se mantiene: el extractor carga la fila 'EE'.
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE facultat (
    id_facultat     TEXT PRIMARY KEY,
    nom             TEXT NOT NULL
);

-- -----------------------------------------------------------------------------------------------------
-- departament [sin datos]
-- Ningún campo del paquete indica el departamento. Se mantiene (queda vacía).
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE departament (
    id_departament  TEXT PRIMARY KEY,
    nom             TEXT NOT NULL,
    id_facultat     TEXT NOT NULL REFERENCES facultat(id_facultat)
);
CREATE INDEX ix_departament_facultat ON departament(id_facultat);

-- -----------------------------------------------------------------------------------------------------
-- aula [paquet: aules.csv + códigos de sessions.aula_partida que no están en el inventario]
-- espina y planta se derivan del código ('Q4/1013' -> espina 'Q4', planta 1). Pasillo (R6) = espina + planta.
-- Fuera del aulario: J/012, J/102, J/124 (se llevan al aulario), B3/0021 y QC/1082 (se quedan, sin sesiones
-- nuevas). Para estas el paquete no da tipo ni capacidad, por eso tipus y capacitat admiten NULL.
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE aula (
    codi            TEXT PRIMARY KEY,
    id_facultat     TEXT REFERENCES facultat(id_facultat),
    edifici         TEXT,
    espina          TEXT GENERATED ALWAYS AS (substr(codi, 1, instr(codi, '/') - 1)) VIRTUAL,
    planta          INTEGER GENERATED ALWAYS AS (CAST(substr(codi, instr(codi, '/') + 1, 1) AS INTEGER)) VIRTUAL,
    tipus           TEXT CHECK (tipus IN ('Aules docents', 'Laboratoris docents', 'Seminaris', 'Aules informàtiques')),
    capacitat       INTEGER CHECK (capacitat >= 0),
    ordinaria       INTEGER NOT NULL DEFAULT 0 CHECK (ordinaria IN (0, 1)),   -- 'Aules docents': cuenta para R8
    integrat        INTEGER NOT NULL DEFAULT 0 CHECK (integrat IN (0, 1)),    -- lab integrado: admite PAUL
    nomes_plab      INTEGER NOT NULL DEFAULT 0 CHECK (nomes_plab IN (0, 1)),  -- labs de Q5 y Q6
    dins_aulari     INTEGER NOT NULL DEFAULT 1 CHECK (dins_aulari IN (0, 1)),
    admet_noves     INTEGER NOT NULL DEFAULT 1 CHECK (admet_noves IN (0, 1)), -- 0 fuera del aulario
    descripcio      TEXT,
    CHECK (instr(codi, '/') > 1),
    CHECK (ordinaria = 0 OR tipus = 'Aules docents'),
    CHECK (dins_aulari = 1 OR admet_noves = 0)
);
CREATE INDEX ix_aula_tipus ON aula(tipus, capacitat);
CREATE INDEX ix_aula_passadis ON aula(espina, planta);

-- -----------------------------------------------------------------------------------------------------
-- titulacio [paquet: derivado de titulacions_curs y plans.csv]  (sustituye a «Grau» del boceto)
-- GED, GEQ, GEI, GEET, GEST, GCIS, GIA, MRICSE, MEBA, MET; GNOU en el escenario 5.4.
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE titulacio (
    codi            TEXT PRIMARY KEY,
    nom             TEXT,
    nivell          TEXT NOT NULL CHECK (nivell IN ('grau', 'master')),     -- máster -> tarde
    id_facultat     TEXT REFERENCES facultat(id_facultat)
);

-- -----------------------------------------------------------------------------------------------------
-- pla_estudis [paquet: plans.csv]
-- data_extraccio viene en el CSV como DD/MM/AAAA: se guarda convertida a ISO.
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE pla_estudis (
    pla             TEXT PRIMARY KEY,
    descripcio      TEXT NOT NULL,
    fitxer_origen   TEXT NOT NULL,
    data_extraccio  TEXT NOT NULL CHECK (date(data_extraccio) = data_extraccio)
);

-- -----------------------------------------------------------------------------------------------------
-- pla_titulacio (N-N) [paquet]
-- GEI tiene dos planes (1626 y 958); GEET+GEST comparten plan (1640 y 1365).
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE pla_titulacio (
    pla             TEXT NOT NULL REFERENCES pla_estudis(pla),
    titulacio       TEXT NOT NULL REFERENCES titulacio(codi),
    PRIMARY KEY (pla, titulacio)
);
CREATE INDEX ix_pla_titulacio_tit ON pla_titulacio(titulacio);

-- -----------------------------------------------------------------------------------------------------
-- cohort [paquet: titulacions_curs, p. ej. 'GED:1r', 'MRICSE:M', '?' = curso desconocido]
-- torn_requerit: 1r y 2n -> mati; 3r, 4t, 5è y máster -> tarda (regla 1).
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE cohort (
    id_cohort       TEXT PRIMARY KEY,
    titulacio       TEXT NOT NULL REFERENCES titulacio(codi),
    curs            TEXT NOT NULL CHECK (curs IN ('1r', '2n', '3r', '4t', 'M', '?')),
    torn_requerit   TEXT CHECK (torn_requerit IN ('mati', 'tarda')),
    UNIQUE (titulacio, curs),
    CHECK (id_cohort = titulacio || ':' || curs)
);

-- -----------------------------------------------------------------------------------------------------
-- assignatura [paquet]
-- codi es numérico en el paquete, pero se trata como texto.
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE assignatura (
    codi            TEXT PRIMARY KEY,
    nom             TEXT NOT NULL,
    id_departament  TEXT REFERENCES departament(id_departament)              -- sin datos en el paquete
);

-- -----------------------------------------------------------------------------------------------------
-- assignatura_cohort (N-N) [paquet]  (sustituye a Grau–Assignatura)
-- Curso de la asignatura en cada titulación (102710: 3r de GEST y 4t de GEI+GEST).
-- Única relación con las cohortes: la cohorte depende solo de la asignatura (no hay grup_cohort).
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE assignatura_cohort (
    codi            TEXT NOT NULL REFERENCES assignatura(codi),
    id_cohort       TEXT NOT NULL REFERENCES cohort(id_cohort),
    PRIMARY KEY (codi, id_cohort)
);
CREATE INDEX ix_assignatura_cohort_coh ON assignatura_cohort(id_cohort);

-- -----------------------------------------------------------------------------------------------------
-- assignatura_pla (N-N) [paquet: sessions.plans]
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE assignatura_pla (
    codi            TEXT NOT NULL REFERENCES assignatura(codi),
    pla             TEXT NOT NULL REFERENCES pla_estudis(pla),
    PRIMARY KEY (codi, pla)
);
CREATE INDEX ix_assignatura_pla_pla ON assignatura_pla(pla);

-- -----------------------------------------------------------------------------------------------------
-- grup [paquet: sessions.csv]
-- id_grup = codi + grup (p. ej. '102397·TE/21'): el mismo TE/21 existe en muchas asignaturas.
-- id_grup no incluye el semestre: comprobado en el paquete (1.307 grupos, sin excepciones).
-- linia: TE/81 -> 81, PAUL/811 -> 81 (TE/310 -> 31). Define los choques de alumnado.
-- sense_espai = 1: grupo de doble titulación (número empieza por 5), sin aula, siempre de tarde.
-- fixada_motiu NULL = movible; si no, p. ej. 'R1: GEI 1r', 'R7: PLAB'.
-- torn_requerit: turno del grupo, cargado de los datos (manda sobre cohort.torn_requerit).
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE grup (
    id_grup         TEXT PRIMARY KEY,
    codi            TEXT NOT NULL REFERENCES assignatura(codi),
    grup            TEXT NOT NULL,
    tipus           TEXT NOT NULL CHECK (tipus IN ('TE', 'PAUL', 'PLAB', 'SEM')),
    numero          TEXT NOT NULL,
    linia           TEXT NOT NULL,
    id_grup_teoria  TEXT REFERENCES grup(id_grup),
    alumnes         INTEGER NOT NULL DEFAULT 0 CHECK (alumnes >= 0),
    alumnes_origen  TEXT NOT NULL CHECK (alumnes_origen IN ('sigma', 'estimat', 'sense_dada')),
    capacitat_grup  INTEGER CHECK (capacitat_grup >= 0),
    sense_espai     INTEGER NOT NULL DEFAULT 0 CHECK (sense_espai IN (0, 1)),
    fixada_motiu    TEXT,
    torn_requerit   TEXT NOT NULL CHECK (torn_requerit IN ('mati', 'tarda')),
    UNIQUE (codi, grup),
    CHECK (grup = tipus || '/' || numero),
    CHECK (id_grup_teoria IS NULL OR tipus <> 'TE')
);
CREATE INDEX ix_grup_codi ON grup(codi);
CREATE INDEX ix_grup_teoria ON grup(id_grup_teoria);
CREATE INDEX ix_grup_linia ON grup(linia);

-- -----------------------------------------------------------------------------------------------------
-- profe [paquet: docents]
-- id_profe = pseudónimo 'Dnnn' (o 'N…' en el escenario 5.4). No intentar identificar a nadie.
-- nomes_practiques [extensión]: solo puede dar grupos PAUL, PLAB o SEM.
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE profe (
    id_profe          TEXT PRIMARY KEY,
    nomes_practiques  INTEGER NOT NULL DEFAULT 0 CHECK (nomes_practiques IN (0, 1))
);

-- -----------------------------------------------------------------------------------------------------
-- docencia [paquet: docents]  (sustituye a «Tipus» del boceto: Profe × Grup, no Profe × Assignatura)
-- El docente del grupo hace todas sus sesiones. 81 grupos no tienen docente.
-- vigent_des_de / vigent_fins [extensión]: cambiar el profe de un grupo sin perder la historia.
-- Las docencias cargadas del paquete llevan vigent_des_de = '2026-09-01'.
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE docencia (
    id_profe        TEXT NOT NULL REFERENCES profe(id_profe),
    id_grup         TEXT NOT NULL REFERENCES grup(id_grup),
    vigent_des_de   TEXT NOT NULL CHECK (date(vigent_des_de) = vigent_des_de),
    vigent_fins     TEXT CHECK (vigent_fins IS NULL OR date(vigent_fins) = vigent_fins),
    PRIMARY KEY (id_profe, id_grup, vigent_des_de),
    CHECK (vigent_fins IS NULL OR vigent_fins >= vigent_des_de)
);
CREATE INDEX ix_docencia_grup ON docencia(id_grup);

-- -----------------------------------------------------------------------------------------------------
-- escenari [paquet: escenaris/*/escenari.json]
-- contingencies (5.3) y grau-nou-40 (5.4). Ambos ficticios.
-- Va antes que sessio e indisponibilitat_profe porque estas lo referencian.
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE escenari (
    id_escenari     TEXT PRIMARY KEY,
    nom             TEXT NOT NULL UNIQUE,
    ficticia        INTEGER NOT NULL DEFAULT 1 CHECK (ficticia IN (0, 1)),
    descripcio      TEXT
);

-- -----------------------------------------------------------------------------------------------------
-- indisponibilitat_profe [extensión]
-- Horas en las que un profe no puede dar clase: franja semanal, opcionalmente entre fechas.
-- Si la provoca un imprevisto («se pilla un profe»), apunta al escenario.
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE indisponibilitat_profe (
    id              INTEGER PRIMARY KEY,
    id_profe        TEXT NOT NULL REFERENCES profe(id_profe),
    dia             TEXT NOT NULL CHECK (dia IN ('L', 'M', 'X', 'J', 'V')),
    h_ini           TEXT NOT NULL CHECK (h_ini GLOB '[0-2][0-9]:[0-5][0-9]'),
    h_fi            TEXT NOT NULL CHECK (h_fi GLOB '[0-2][0-9]:[0-5][0-9]'),
    data_ini        TEXT CHECK (data_ini IS NULL OR date(data_ini) = data_ini),
    data_fi         TEXT CHECK (data_fi IS NULL OR date(data_fi) = data_fi),
    id_escenari     TEXT REFERENCES escenari(id_escenari),
    motiu           TEXT,
    CHECK (h_fi > h_ini),
    CHECK (data_fi IS NULL OR data_ini IS NULL OR data_fi >= data_ini)
);
CREATE INDEX ix_indisp_profe ON indisponibilitat_profe(id_profe, dia);
CREATE INDEX ix_indisp_escenari ON indisponibilitat_profe(id_escenari);

-- -----------------------------------------------------------------------------------------------------
-- activitat [paquet: activitats.csv]
-- Patrón semanal (grupo, día, hora). El solver puede decidir por actividad (1.930) y expandir a sesiones.
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE activitat (
    activitat_id    TEXT PRIMARY KEY,
    id_grup         TEXT NOT NULL REFERENCES grup(id_grup),
    dia             TEXT NOT NULL CHECK (dia IN ('L', 'M', 'X', 'J', 'V')),
    h_ini           TEXT NOT NULL CHECK (h_ini GLOB '[0-2][0-9]:[0-5][0-9]'),
    h_fi            TEXT NOT NULL CHECK (h_fi GLOB '[0-2][0-9]:[0-5][0-9]'),
    setmana_primera TEXT NOT NULL CHECK (setmana_primera GLOB '[0-9][0-9][0-9][0-9]-W[0-5][0-9]'),
    setmana_ultima  TEXT NOT NULL CHECK (setmana_ultima GLOB '[0-9][0-9][0-9][0-9]-W[0-5][0-9]'),
    n_sessions      INTEGER NOT NULL CHECK (n_sessions > 0),
    CHECK (h_fi > h_ini)
);
CREATE INDEX ix_activitat_grup ON activitat(id_grup);

-- -----------------------------------------------------------------------------------------------------
-- sessio (objetivo) [paquet: sessions.csv y escenaris/grau-nou-40/sessions_extra.csv]
-- Datos fijos de cada sesión y su situación de partida. Lo que se decide va en assignacio.
-- setmana y durada_min NO pueden cambiar. id_compartida agrupa la misma clase física (se mueve junta).
-- semestre se deduce por fecha (septiembre a enero = 1), no por el campo T/V de Sigma.
-- Las sesiones del grado nuevo (N00001…) no tienen actividad y llevan id_escenari.
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE sessio (
    id_sessio                  TEXT PRIMARY KEY,
    activitat_id               TEXT REFERENCES activitat(activitat_id),
    id_grup                    TEXT NOT NULL REFERENCES grup(id_grup),
    id_escenari                TEXT REFERENCES escenari(id_escenari),
    id_compartida              TEXT,
    dc                         TEXT CHECK (dc IN ('P', 'S')),
    setmana                    TEXT NOT NULL CHECK (setmana GLOB '[0-9][0-9][0-9][0-9]-W[0-5][0-9]'),
    durada_min                 INTEGER NOT NULL CHECK (durada_min > 0),
    data_partida               TEXT NOT NULL CHECK (date(data_partida) = data_partida),
    dia_partida                TEXT NOT NULL CHECK (dia_partida IN ('L', 'M', 'X', 'J', 'V')),
    h_ini_partida              TEXT NOT NULL CHECK (h_ini_partida GLOB '[0-2][0-9]:[0-5][0-9]'),
    aula_partida               TEXT REFERENCES aula(codi),
    aules_addicionals_partida  TEXT REFERENCES aula(codi),
    semestre                   INTEGER GENERATED ALWAYS AS (
                                   CASE WHEN CAST(strftime('%m', data_partida) AS INTEGER) IN (9, 10, 11, 12, 1)
                                        THEN 1 ELSE 2 END) VIRTUAL
);
CREATE INDEX ix_sessio_grup ON sessio(id_grup);
CREATE INDEX ix_sessio_activitat ON sessio(activitat_id);
CREATE INDEX ix_sessio_compartida ON sessio(id_compartida) WHERE id_compartida IS NOT NULL;
CREATE INDEX ix_sessio_setmana ON sessio(setmana);
CREATE INDEX ix_sessio_aula_partida ON sessio(aula_partida);
CREATE INDEX ix_sessio_escenari ON sessio(id_escenari);
CREATE INDEX ix_sessio_aules_addicionals ON sessio(aules_addicionals_partida);

-- -----------------------------------------------------------------------------------------------------
-- calendari [paquet: calendari.csv]
-- Festivos, no lectivos, paradas y semanas de evaluación (R2-CALENDARI). Sin FK: se cruza por fecha.
-- h_ini / h_fi NULL = todo el día.
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE calendari (
    id              INTEGER PRIMARY KEY,
    data            TEXT NOT NULL CHECK (date(data) = data),
    tipus           TEXT NOT NULL CHECK (tipus IN ('festiu', 'no_lectiu', 'aturada', 'avaluacio')),
    h_ini           TEXT CHECK (h_ini IS NULL OR h_ini GLOB '[0-2][0-9]:[0-5][0-9]'),
    h_fi            TEXT CHECK (h_fi IS NULL OR h_fi GLOB '[0-2][0-9]:[0-5][0-9]'),
    motiu           TEXT NOT NULL,
    font            TEXT NOT NULL,
    CHECK ((h_ini IS NULL) = (h_fi IS NULL)),
    CHECK (h_fi IS NULL OR h_fi > h_ini)
);
CREATE INDEX ix_calendari_data ON calendari(data);

-- -----------------------------------------------------------------------------------------------------
-- tancament_aula [paquet: escenari.json -> aules_tancades]
-- Sala reservada o avería (R3-TANCADA). Horas NULL = todo el día.
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE tancament_aula (
    id              INTEGER PRIMARY KEY,
    id_escenari     TEXT NOT NULL REFERENCES escenari(id_escenari),
    aula            TEXT NOT NULL REFERENCES aula(codi),
    data_ini        TEXT NOT NULL CHECK (date(data_ini) = data_ini),
    data_fi         TEXT NOT NULL CHECK (date(data_fi) = data_fi),
    h_ini           TEXT CHECK (h_ini IS NULL OR h_ini GLOB '[0-2][0-9]:[0-5][0-9]'),
    h_fi            TEXT CHECK (h_fi IS NULL OR h_fi GLOB '[0-2][0-9]:[0-5][0-9]'),
    motiu           TEXT,
    CHECK (data_fi >= data_ini),
    CHECK ((h_ini IS NULL) = (h_fi IS NULL))
);
CREATE INDEX ix_tancament_aula ON tancament_aula(aula, data_ini, data_fi);
CREATE INDEX ix_tancament_escenari ON tancament_aula(id_escenari);

-- -----------------------------------------------------------------------------------------------------
-- cancellacio [paquet: escenari.json -> cancellades]
-- Sesión cancelada que se recupera después de su fecha y como tarde en recuperar_fins (R5-RECUPERACIO).
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE cancellacio (
    id_escenari     TEXT NOT NULL REFERENCES escenari(id_escenari),
    id_sessio       TEXT NOT NULL REFERENCES sessio(id_sessio),
    recuperar_fins  TEXT NOT NULL CHECK (date(recuperar_fins) = recuperar_fins),
    PRIMARY KEY (id_escenari, id_sessio)
);
CREATE INDEX ix_cancellacio_sessio ON cancellacio(id_sessio);

-- -----------------------------------------------------------------------------------------------------
-- canvi_alumnes [paquet: escenari.json -> alumnes]
-- Un grupo crece o se reduce en el escenario: sobrescribe grup.alumnes al evaluar ese escenario.
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE canvi_alumnes (
    id_escenari     TEXT NOT NULL REFERENCES escenari(id_escenari),
    id_grup         TEXT NOT NULL REFERENCES grup(id_grup),
    alumnes         INTEGER NOT NULL CHECK (alumnes >= 0),
    PRIMARY KEY (id_escenari, id_grup)
);
CREATE INDEX ix_canvi_alumnes_grup ON canvi_alumnes(id_grup);

-- -----------------------------------------------------------------------------------------------------
-- versio_horari [trabajo]
-- Cada horario: 'partida', '5.1-aules', '5.2-torns', '5.3-imprevist'…
-- id_versio_referencia: la versión de la que parte (la 5.3 parte de la 5.2; un cambio de profe parte de la vigente).
-- informe_json: salida --json del verificador.
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE versio_horari (
    id_versio             INTEGER PRIMARY KEY,
    nom                   TEXT NOT NULL UNIQUE,
    id_versio_referencia  INTEGER REFERENCES versio_horari(id_versio),
    id_escenari           TEXT REFERENCES escenari(id_escenari),
    semestre              INTEGER CHECK (semestre IN (1, 2)),                -- NULL = curso completo
    mode                  TEXT NOT NULL DEFAULT 'complet' CHECK (mode IN ('complet', 'nomes_aules')),
    creada_el             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    veredicte             TEXT CHECK (veredicte IN ('VALIDA', 'VALIDA AMB RELAXACIONS DECLARADES', 'NO VALIDA')),
    informe_json          TEXT CHECK (informe_json IS NULL OR json_valid(informe_json)),
    CHECK (id_versio_referencia IS NULL OR id_versio_referencia <> id_versio)
);
CREATE INDEX ix_versio_referencia ON versio_horari(id_versio_referencia);
CREATE INDEX ix_versio_escenari ON versio_horari(id_escenari);

-- -----------------------------------------------------------------------------------------------------
-- assignacio (TABLA FINAL) [trabajo]
-- Una fila por versión y sesión. Exportar una versión da el CSV de entrega:
--   SELECT id_sessio, dia, h_ini, aula, data FROM assignacio WHERE id_versio = ? ORDER BY id_sessio;
-- dia dentro de la misma semana ISO de la sesión (la comprobación la hace el verificador).
-- aula NULL solo en PLAB sin aula y grupos sense_espai (lo comprueba el verificador: R5-SENSE-AULA).
-- data solo en la sesión cancelada y recuperada (5.3).
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE assignacio (
    id_versio       INTEGER NOT NULL REFERENCES versio_horari(id_versio) ON DELETE CASCADE,
    id_sessio       TEXT NOT NULL REFERENCES sessio(id_sessio),
    dia             TEXT NOT NULL CHECK (dia IN ('L', 'M', 'X', 'J', 'V')),
    h_ini           TEXT NOT NULL CHECK (h_ini GLOB '[0-2][0-9]:[0-5][0-9]'),
    aula            TEXT REFERENCES aula(codi),
    data            TEXT CHECK (data IS NULL OR date(data) = data),
    PRIMARY KEY (id_versio, id_sessio)
);
CREATE INDEX ix_assignacio_parrilla ON assignacio(id_versio, aula, dia, h_ini);   -- parrilla semanal por aula
CREATE INDEX ix_assignacio_franja ON assignacio(id_versio, dia, h_ini);
CREATE INDEX ix_assignacio_sessio ON assignacio(id_sessio);

-- -----------------------------------------------------------------------------------------------------
-- relaxacio [trabajo]
-- Regla declarada como incumplida, con justificación obligatoria.
-- totes = 1 es el comodín '*', que solo vale para R8-RESERVA.
-- No relajables: R0-FORMAT, R0-HORARI, R5-FALTA, R5-RECUPERACIO, R3-TANCADA.
-- Exportar = CSV restriccio,sessions,justificacio (sesiones unidas con '|').
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE relaxacio (
    id              INTEGER PRIMARY KEY,
    id_versio       INTEGER NOT NULL REFERENCES versio_horari(id_versio) ON DELETE CASCADE,
    restriccio      TEXT NOT NULL CHECK (restriccio NOT IN ('R0-FORMAT', 'R0-HORARI', 'R5-FALTA', 'R5-RECUPERACIO', 'R3-TANCADA')),
    justificacio    TEXT NOT NULL CHECK (length(trim(justificacio)) > 0),
    totes           INTEGER NOT NULL DEFAULT 0 CHECK (totes IN (0, 1)),
    UNIQUE (id_versio, restriccio),                                         -- «una fila por regla»
    CHECK (totes = 0 OR restriccio = 'R8-RESERVA')
);

-- -----------------------------------------------------------------------------------------------------
-- relaxacio_sessio (N-N) [trabajo]
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE relaxacio_sessio (
    id_relaxacio    INTEGER NOT NULL REFERENCES relaxacio(id) ON DELETE CASCADE,
    id_sessio       TEXT NOT NULL REFERENCES sessio(id_sessio),
    PRIMARY KEY (id_relaxacio, id_sessio)
);
CREATE INDEX ix_relaxacio_sessio_ses ON relaxacio_sessio(id_sessio);

-- -----------------------------------------------------------------------------------------------------
-- registre_canvi [trabajo, pedido en el nivel 3]
-- Sesión, de dónde a dónde, motivo, a quién afecta y fecha del aviso. El aviso se redacta, no se envía.
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE registre_canvi (
    id               INTEGER PRIMARY KEY,
    id_versio_origen INTEGER NOT NULL REFERENCES versio_horari(id_versio),
    id_versio_desti  INTEGER NOT NULL REFERENCES versio_horari(id_versio),
    id_sessio        TEXT NOT NULL REFERENCES sessio(id_sessio),
    de_data          TEXT CHECK (de_data IS NULL OR date(de_data) = de_data),
    de_h_ini         TEXT CHECK (de_h_ini IS NULL OR de_h_ini GLOB '[0-2][0-9]:[0-5][0-9]'),
    de_aula          TEXT REFERENCES aula(codi),
    a_data           TEXT CHECK (a_data IS NULL OR date(a_data) = a_data),
    a_h_ini          TEXT CHECK (a_h_ini IS NULL OR a_h_ini GLOB '[0-2][0-9]:[0-5][0-9]'),
    a_aula           TEXT REFERENCES aula(codi),
    motiu            TEXT NOT NULL,
    afectats         TEXT NOT NULL,                                           -- docente, cohortes, Gestió Acadèmica
    data_avis        TEXT NOT NULL CHECK (date(data_avis) = data_avis),
    CHECK (id_versio_origen <> id_versio_desti)
);
CREATE INDEX ix_registre_sessio ON registre_canvi(id_sessio);
CREATE INDEX ix_registre_versions ON registre_canvi(id_versio_origen, id_versio_desti);
CREATE INDEX ix_registre_desti ON registre_canvi(id_versio_desti);
CREATE INDEX ix_registre_de_aula ON registre_canvi(de_aula);
CREATE INDEX ix_registre_a_aula ON registre_canvi(a_aula);
