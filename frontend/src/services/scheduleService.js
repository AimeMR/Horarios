/**
 * SERVICIO DE HORARIOS SEMANALES (PARRILLA DE SESIONES DE LUNES A VIERNES)
 *
 * Conectado con el endpoint oficial del backend (contracte-fase2.md):
 * GET /versions/:id/parrilla?aula=:aula&setmana=:setmana
 */

/**
 * URL base del backend Node/Express (según contracte-fase2.md, puerto por defecto 3000).
 * Configurable mediante variable de entorno VITE_BACKEND_URL o VITE_API_URL.
 */
export const API_BASE_URL =
  (typeof import.meta !== 'undefined' && (import.meta.env?.VITE_BACKEND_URL || import.meta.env?.VITE_API_URL)) ||
  'http://localhost:3000';

/**
 * Consulta la parrilla de sesiones para un aula llamando al endpoint real del backend:
 * GET /versions/:id/parrilla?aula=:aula&setmana=:setmana
 *
 * @param {string} aula - Código identificador del aula (ej. "Q4/0003").
 * @param {string} setmana - Código de semana ISO (ej. "2026-W45" o "2026-W38").
 * @param {number} versionId - Identificador de la versión (por defecto 1).
 * @returns {Promise<{ data: Object|null, source: string, error?: string }>}
 */
export async function getRoomSchedule(aula, setmana = '2026-W45', versionId = 2) {
  const targetWeek = typeof setmana === 'string' && setmana.includes('-W') ? setmana : '2026-W45';
  let url = `${API_BASE_URL}/versions/${versionId}/parrilla?aula=${encodeURIComponent(aula)}&setmana=${encodeURIComponent(targetWeek)}`;

  try {
    let response = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json'
      }
    });

    // Si la versión 2 no existiera, probar versión 1 como alternativa
    if (response.status === 404 && versionId !== 1) {
      url = `${API_BASE_URL}/versions/1/parrilla?aula=${encodeURIComponent(aula)}&setmana=${encodeURIComponent(targetWeek)}`;
      response = await fetch(url, {
        method: 'GET',
        headers: {
          'Accept': 'application/json'
        }
      });
    }

    if (!response.ok) {
      const errorText = await response.text();
      console.warn(`[getRoomSchedule] Error HTTP ${response.status} en ${url}:`, errorText);
      return {
        data: null,
        error: `HTTP ${response.status}: ${errorText}`,
        source: 'backend-error'
      };
    }

    const data = await response.json();
    return {
      data,
      source: 'backend'
    };
  } catch (err) {
    console.warn(`[getRoomSchedule] Error de conexión con el backend en ${url}:`, err.message);
    return {
      data: null,
      error: err.message,
      source: 'network-error'
    };
  }
}

/**
 * Función compatibilizadora para imports existentes.
 * Los datos falsos/mocks han sido comentados y deshabilitados abajo.
 */
export function generateMockParrillaResponse(aula, data = '2026-11-07', versionId = 1) {
  // Mocks deshabilitados: se utiliza el endpoint real GET /versions/:id/parrilla
  return {
    idVersio: versionId,
    setmana: '2026-W45',
    dies: [
      { dia: 'L', data: '2026-11-02' },
      { dia: 'M', data: '2026-11-03' },
      { dia: 'X', data: '2026-11-04' },
      { dia: 'J', data: '2026-11-05' },
      { dia: 'V', data: '2026-11-06' }
    ],
    filtre: { aula: aula },
    calendari: [],
    items: [],
    truncat: false
  };
}

/* ==============================================================================
   CÓDIGO DE MOCKS DESHABILITADO (COMMENTED OUT)
   Para volver a activar los datos falsos/locales de prueba sin backend,
   descomentar este bloque.
   ==============================================================================

// Catálogo de asignaturas de muestra conforme a titulaciones universitarias
const SAMPLE_SUBJECTS = [
  { codi: '240011', nom: 'Física I', tipus: 'TE', duradaDef: 120, profe: 'D101 - Dr. Joan Garcia', cohort: 'GEI:1r' },
  { codi: '240012', nom: 'Càlcul I', tipus: 'TE', duradaDef: 120, profe: 'D102 - Dra. Marta Vila', cohort: 'GEI:1r' },
  { codi: '240013', nom: 'Programació I', tipus: 'PLAB', duradaDef: 120, profe: 'D103 - Dr. Albert Soler', cohort: 'GEI:1r' },
  { codi: '240021', nom: 'Àlgebra Lineal', tipus: 'TE', duradaDef: 60, profe: 'D104 - Dr. Carles Puig', cohort: 'GEI:1r' },
  { codi: '240022', nom: 'Estructures de Dades', tipus: 'TE', duradaDef: 120, profe: 'D105 - Dra. Nuria Riera', cohort: 'GEI:2n' },
  { codi: '240023', nom: 'Sistemes Operatius', tipus: 'PLAB', duradaDef: 120, profe: 'D106 - Dr. Jordi Mas', cohort: 'GEI:2n' },
  { codi: '240031', nom: 'Bases de Dades', tipus: 'TE', duradaDef: 120, profe: 'D107 - Dra. Elena Grau', cohort: 'GEI:2n' },
  { codi: '240032', nom: 'Xarxes de Computadors', tipus: 'PLAB', duradaDef: 120, profe: 'D108 - Dr. Pau Bosch', cohort: 'GEI:3r' },
  { codi: '240041', nom: 'Enginyeria del Software', tipus: 'TE', duradaDef: 120, profe: 'D109 - Dra. Laura Serra', cohort: 'GEI:3r' },
  { codi: '240051', nom: 'Intel·ligència Artificial', tipus: 'TE', duradaDef: 120, profe: 'D110 - Dr. Sergi Pons', cohort: 'GEI:4t' },
  { codi: '240052', nom: 'Aprenentatge Automàtic', tipus: 'SEM', duradaDef: 60, profe: 'D111 - Dr. Marc Valls', cohort: 'GEI:4t' },
  { codi: '240061', nom: 'Ciberseguretat Avançada', tipus: 'TE', duradaDef: 120, profe: 'D112 - Dra. Cristina Ramos', cohort: 'M:1r' }
];

function hashString(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

// Horario semanal completo (Lunes a Viernes) para el aula Q4/0003
function getQ40003WeeklySchedule(versionId = 1, targetWeek = '2026-W45') {
  const items = [
    // ==========================================
    // LUNES (L)
    // ==========================================
    // 08:30 - 10:30 (Càlcul I - 2h consecutivas)
    {
      idSessio: 'Q4-L-01', data: '2026-11-02', dia: 'L', hIni: '08:30', hFi: '09:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240012', nom: 'Càlcul I' },
      grup: { idGrup: '240012·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 65, profes: ['D102 - Dra. Marta Vila'], cohorts: ['GEI:1r']
    },
    {
      idSessio: 'Q4-L-02', data: '2026-11-02', dia: 'L', hIni: '09:30', hFi: '10:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240012', nom: 'Càlcul I' },
      grup: { idGrup: '240012·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 65, profes: ['D102 - Dra. Marta Vila'], cohorts: ['GEI:1r']
    },
    // 11:30 - 13:30 (Programació I - 2h consecutivas)
    {
      idSessio: 'Q4-L-03', data: '2026-11-02', dia: 'L', hIni: '11:30', hFi: '12:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240013', nom: 'Programació I' },
      grup: { idGrup: '240013·PLAB/450', grup: 'PLAB/450', tipus: 'PLAB' },
      alumnes: 45, profes: ['D103 - Dr. Albert Soler'], cohorts: ['GEI:1r']
    },
    {
      idSessio: 'Q4-L-04', data: '2026-11-02', dia: 'L', hIni: '12:30', hFi: '13:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240013', nom: 'Programació I' },
      grup: { idGrup: '240013·PLAB/450', grup: 'PLAB/450', tipus: 'PLAB' },
      alumnes: 45, profes: ['D103 - Dr. Albert Soler'], cohorts: ['GEI:1r']
    },
    // 13:30 - 14:30 (Àlgebra Lineal - 1h)
    {
      idSessio: 'Q4-L-05', data: '2026-11-02', dia: 'L', hIni: '13:30', hFi: '14:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240021', nom: 'Àlgebra Lineal' },
      grup: { idGrup: '240021·SEM/450', grup: 'SEM/450', tipus: 'SEM' },
      alumnes: 30, profes: ['D104 - Dr. Carles Puig'], cohorts: ['GEI:1r']
    },
    // 15:00 - 16:00 (Estructures de Dades - 1h)
    {
      idSessio: 'Q4-L-06', data: '2026-11-02', dia: 'L', hIni: '15:00', hFi: '16:00', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240022', nom: 'Estructures de Dades' },
      grup: { idGrup: '240022·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 55, profes: ['D105 - Dra. Nuria Riera'], cohorts: ['GEI:2n']
    },
    // 16:00 - 18:00 (Sistemes Operatius - 2h consecutivas)
    {
      idSessio: 'Q4-L-07', data: '2026-11-02', dia: 'L', hIni: '16:00', hFi: '17:00', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240023', nom: 'Sistemes Operatius' },
      grup: { idGrup: '240023·PLAB/450', grup: 'PLAB/450', tipus: 'PLAB' },
      alumnes: 42, profes: ['D106 - Dr. Jordi Mas'], cohorts: ['GEI:2n']
    },
    {
      idSessio: 'Q4-L-08', data: '2026-11-02', dia: 'L', hIni: '17:00', hFi: '18:00', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240023', nom: 'Sistemes Operatius' },
      grup: { idGrup: '240023·PLAB/450', grup: 'PLAB/450', tipus: 'PLAB' },
      alumnes: 42, profes: ['D106 - Dr. Jordi Mas'], cohorts: ['GEI:2n']
    },
    // 19:00 - 21:00 (Bases de Dades - 2h consecutivas)
    {
      idSessio: 'Q4-L-09', data: '2026-11-02', dia: 'L', hIni: '19:00', hFi: '20:00', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240031', nom: 'Bases de Dades' },
      grup: { idGrup: '240031·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 50, profes: ['D107 - Dra. Elena Grau'], cohorts: ['GEI:2n']
    },
    {
      idSessio: 'Q4-L-10', data: '2026-11-02', dia: 'L', hIni: '20:00', hFi: '21:00', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240031', nom: 'Bases de Dades' },
      grup: { idGrup: '240031·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 50, profes: ['D107 - Dra. Elena Grau'], cohorts: ['GEI:2n']
    },

    // ==========================================
    // MARTES (M)
    // ==========================================
    // 08:30 - 10:30 (Física I - 2h consecutivas)
    {
      idSessio: 'Q4-M-01', data: '2026-11-03', dia: 'M', hIni: '08:30', hFi: '09:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240011', nom: 'Física I' },
      grup: { idGrup: '240011·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 70, profes: ['D101 - Dr. Joan Garcia'], cohorts: ['GEI:1r']
    },
    {
      idSessio: 'Q4-M-02', data: '2026-11-03', dia: 'M', hIni: '09:30', hFi: '10:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240011', nom: 'Física I' },
      grup: { idGrup: '240011·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 70, profes: ['D101 - Dr. Joan Garcia'], cohorts: ['GEI:1r']
    },
    // 10:30 - 12:30 (Àlgebra Lineal - 2h consecutivas)
    {
      idSessio: 'Q4-M-03', data: '2026-11-03', dia: 'M', hIni: '10:30', hFi: '11:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240021', nom: 'Àlgebra Lineal' },
      grup: { idGrup: '240021·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 65, profes: ['D104 - Dr. Carles Puig'], cohorts: ['GEI:1r']
    },
    {
      idSessio: 'Q4-M-04', data: '2026-11-03', dia: 'M', hIni: '11:30', hFi: '12:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240021', nom: 'Àlgebra Lineal' },
      grup: { idGrup: '240021·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 65, profes: ['D104 - Dr. Carles Puig'], cohorts: ['GEI:1r']
    },
    // 12:30 - 14:30 (Programació I - 2h consecutivas)
    {
      idSessio: 'Q4-M-05', data: '2026-11-03', dia: 'M', hIni: '12:30', hFi: '13:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240013', nom: 'Programació I' },
      grup: { idGrup: '240013·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 60, profes: ['D103 - Dr. Albert Soler'], cohorts: ['GEI:1r']
    },
    {
      idSessio: 'Q4-M-06', data: '2026-11-03', dia: 'M', hIni: '13:30', hFi: '14:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240013', nom: 'Programació I' },
      grup: { idGrup: '240013·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 60, profes: ['D103 - Dr. Albert Soler'], cohorts: ['GEI:1r']
    },
    // 15:00 - 17:00 (Intel·ligència Artificial - 2h consecutivas)
    {
      idSessio: 'Q4-M-07', data: '2026-11-03', dia: 'M', hIni: '15:00', hFi: '16:00', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240051', nom: 'Intel·ligència Artificial' },
      grup: { idGrup: '240051·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 48, profes: ['D110 - Dr. Sergi Pons'], cohorts: ['GEI:4t']
    },
    {
      idSessio: 'Q4-M-08', data: '2026-11-03', dia: 'M', hIni: '16:00', hFi: '17:00', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240051', nom: 'Intel·ligència Artificial' },
      grup: { idGrup: '240051·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 48, profes: ['D110 - Dr. Sergi Pons'], cohorts: ['GEI:4t']
    },
    // 17:00 - 19:00 (Aprenentatge Automàtic - 2h consecutivas)
    {
      idSessio: 'Q4-M-09', data: '2026-11-03', dia: 'M', hIni: '17:00', hFi: '18:00', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240052', nom: 'Aprenentatge Automàtic' },
      grup: { idGrup: '240052·SEM/450', grup: 'SEM/450', tipus: 'SEM' },
      alumnes: 35, profes: ['D111 - Dr. Marc Valls'], cohorts: ['GEI:4t']
    },
    {
      idSessio: 'Q4-M-10', data: '2026-11-03', dia: 'M', hIni: '18:00', hFi: '19:00', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240052', nom: 'Aprenentatge Automàtic' },
      grup: { idGrup: '240052·SEM/450', grup: 'SEM/450', tipus: 'SEM' },
      alumnes: 35, profes: ['D111 - Dr. Marc Valls'], cohorts: ['GEI:4t']
    },

    // ==========================================
    // MIÉRCOLES (X)
    // ==========================================
    // 08:30 - 10:30 (Càlcul I - 2h consecutivas)
    {
      idSessio: 'Q4-X-01', data: '2026-11-04', dia: 'X', hIni: '08:30', hFi: '09:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240012', nom: 'Càlcul I' },
      grup: { idGrup: '240012·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 65, profes: ['D102 - Dra. Marta Vila'], cohorts: ['GEI:1r']
    },
    {
      idSessio: 'Q4-X-02', data: '2026-11-04', dia: 'X', hIni: '09:30', hFi: '10:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240012', nom: 'Càlcul I' },
      grup: { idGrup: '240012·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 65, profes: ['D102 - Dra. Marta Vila'], cohorts: ['GEI:1r']
    },
    // 10:30 - 11:30 (Física I - 1h)
    {
      idSessio: 'Q4-X-03', data: '2026-11-04', dia: 'X', hIni: '10:30', hFi: '11:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240011', nom: 'Física I' },
      grup: { idGrup: '240011·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 68, profes: ['D101 - Dr. Joan Garcia'], cohorts: ['GEI:1r']
    },
    // 11:30 - 13:30 (Enginyeria del Software - 2h consecutivas)
    {
      idSessio: 'Q4-X-04', data: '2026-11-04', dia: 'X', hIni: '11:30', hFi: '12:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240041', nom: 'Enginyeria del Software' },
      grup: { idGrup: '240041·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 55, profes: ['D109 - Dra. Laura Serra'], cohorts: ['GEI:3r']
    },
    {
      idSessio: 'Q4-X-05', data: '2026-11-04', dia: 'X', hIni: '12:30', hFi: '13:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240041', nom: 'Enginyeria del Software' },
      grup: { idGrup: '240041·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 55, profes: ['D109 - Dra. Laura Serra'], cohorts: ['GEI:3r']
    },
    // 13:30 - 14:30 (Ciberseguretat Avançada - 1h)
    {
      idSessio: 'Q4-X-06', data: '2026-11-04', dia: 'X', hIni: '13:30', hFi: '14:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240061', nom: 'Ciberseguretat Avançada' },
      grup: { idGrup: '240061·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 38, profes: ['D112 - Dra. Cristina Ramos'], cohorts: ['M:1r']
    },
    // 15:00 - 17:00 (Xarxes de Computadors - 2h consecutivas)
    {
      idSessio: 'Q4-X-07', data: '2026-11-04', dia: 'X', hIni: '15:00', hFi: '16:00', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240032', nom: 'Xarxes de Computadors' },
      grup: { idGrup: '240032·PLAB/450', grup: 'PLAB/450', tipus: 'PLAB' },
      alumnes: 40, profes: ['D108 - Dr. Pau Bosch'], cohorts: ['GEI:3r']
    },
    {
      idSessio: 'Q4-X-08', data: '2026-11-04', dia: 'X', hIni: '16:00', hFi: '17:00', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240032', nom: 'Xarxes de Computadors' },
      grup: { idGrup: '240032·PLAB/450', grup: 'PLAB/450', tipus: 'PLAB' },
      alumnes: 40, profes: ['D108 - Dr. Pau Bosch'], cohorts: ['GEI:3r']
    },
    // 17:00 - 19:00 (Bases de Dades - 2h consecutivas)
    {
      idSessio: 'Q4-X-09', data: '2026-11-04', dia: 'X', hIni: '17:00', hFi: '18:00', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240031', nom: 'Bases de Dades' },
      grup: { idGrup: '240031·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 52, profes: ['D107 - Dra. Elena Grau'], cohorts: ['GEI:2n']
    },
    {
      idSessio: 'Q4-X-10', data: '2026-11-04', dia: 'X', hIni: '18:00', hFi: '19:00', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240031', nom: 'Bases de Dades' },
      grup: { idGrup: '240031·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 52, profes: ['D107 - Dra. Elena Grau'], cohorts: ['GEI:2n']
    },

    // ==========================================
    // JUEVES (J)
    // ==========================================
    // 08:30 - 10:30 (Física I - 2h consecutivas)
    {
      idSessio: 'Q4-J-01', data: '2026-11-05', dia: 'J', hIni: '08:30', hFi: '09:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240011', nom: 'Física I' },
      grup: { idGrup: '240011·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 70, profes: ['D101 - Dr. Joan Garcia'], cohorts: ['GEI:1r']
    },
    {
      idSessio: 'Q4-J-02', data: '2026-11-05', dia: 'J', hIni: '09:30', hFi: '10:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240011', nom: 'Física I' },
      grup: { idGrup: '240011·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 70, profes: ['D101 - Dr. Joan Garcia'], cohorts: ['GEI:1r']
    },
    // 10:30 - 12:30 (Àlgebra Lineal - 2h consecutivas)
    {
      idSessio: 'Q4-J-03', data: '2026-11-05', dia: 'J', hIni: '10:30', hFi: '11:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240021', nom: 'Àlgebra Lineal' },
      grup: { idGrup: '240021·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 65, profes: ['D104 - Dr. Carles Puig'], cohorts: ['GEI:1r']
    },
    {
      idSessio: 'Q4-J-04', data: '2026-11-05', dia: 'J', hIni: '11:30', hFi: '12:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240021', nom: 'Àlgebra Lineal' },
      grup: { idGrup: '240021·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 65, profes: ['D104 - Dr. Carles Puig'], cohorts: ['GEI:1r']
    },
    // 12:30 - 14:30 (Programació I - 2h consecutivas)
    {
      idSessio: 'Q4-J-05', data: '2026-11-05', dia: 'J', hIni: '12:30', hFi: '13:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240013', nom: 'Programació I' },
      grup: { idGrup: '240013·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 60, profes: ['D103 - Dr. Albert Soler'], cohorts: ['GEI:1r']
    },
    {
      idSessio: 'Q4-J-06', data: '2026-11-05', dia: 'J', hIni: '13:30', hFi: '14:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240013', nom: 'Programació I' },
      grup: { idGrup: '240013·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 60, profes: ['D103 - Dr. Albert Soler'], cohorts: ['GEI:1r']
    },
    // 15:00 - 17:00 (Estructures de Dades - 2h consecutivas)
    {
      idSessio: 'Q4-J-07', data: '2026-11-05', dia: 'J', hIni: '15:00', hFi: '16:00', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240022', nom: 'Estructures de Dades' },
      grup: { idGrup: '240022·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 55, profes: ['D105 - Dra. Nuria Riera'], cohorts: ['GEI:2n']
    },
    {
      idSessio: 'Q4-J-08', data: '2026-11-05', dia: 'J', hIni: '16:00', hFi: '17:00', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240022', nom: 'Estructures de Dades' },
      grup: { idGrup: '240022·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 55, profes: ['D105 - Dra. Nuria Riera'], cohorts: ['GEI:2n']
    },
    // 17:00 - 19:00 (Ciberseguretat Avançada - 2h consecutivas)
    {
      idSessio: 'Q4-J-09', data: '2026-11-05', dia: 'J', hIni: '17:00', hFi: '18:00', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240061', nom: 'Ciberseguretat Avançada' },
      grup: { idGrup: '240061·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 40, profes: ['D112 - Dra. Cristina Ramos'], cohorts: ['M:1r']
    },
    {
      idSessio: 'Q4-J-10', data: '2026-11-05', dia: 'J', hIni: '18:00', hFi: '19:00', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240061', nom: 'Ciberseguretat Avançada' },
      grup: { idGrup: '240061·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 40, profes: ['D112 - Dra. Cristina Ramos'], cohorts: ['M:1r']
    },

    // ==========================================
    // VIERNES (V)
    // ==========================================
    // 08:30 - 10:30 (Càlcul I - 2h consecutivas)
    {
      idSessio: 'Q4-V-01', data: '2026-11-06', dia: 'V', hIni: '08:30', hFi: '09:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240012', nom: 'Càlcul I' },
      grup: { idGrup: '240012·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 65, profes: ['D102 - Dra. Marta Vila'], cohorts: ['GEI:1r']
    },
    {
      idSessio: 'Q4-V-02', data: '2026-11-06', dia: 'V', hIni: '09:30', hFi: '10:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240012', nom: 'Càlcul I' },
      grup: { idGrup: '240012·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 65, profes: ['D102 - Dra. Marta Vila'], cohorts: ['GEI:1r']
    },
    // 10:30 - 12:30 (Sistemes Operatius - 2h consecutivas)
    {
      idSessio: 'Q4-V-03', data: '2026-11-06', dia: 'V', hIni: '10:30', hFi: '11:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240023', nom: 'Sistemes Operatius' },
      grup: { idGrup: '240023·PLAB/450', grup: 'PLAB/450', tipus: 'PLAB' },
      alumnes: 45, profes: ['D106 - Dr. Jordi Mas'], cohorts: ['GEI:2n']
    },
    {
      idSessio: 'Q4-V-04', data: '2026-11-06', dia: 'V', hIni: '11:30', hFi: '12:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240023', nom: 'Sistemes Operatius' },
      grup: { idGrup: '240023·PLAB/450', grup: 'PLAB/450', tipus: 'PLAB' },
      alumnes: 45, profes: ['D106 - Dr. Jordi Mas'], cohorts: ['GEI:2n']
    },
    // 12:30 - 14:30 (Intel·ligència Artificial - 2h consecutivas)
    {
      idSessio: 'Q4-V-05', data: '2026-11-06', dia: 'V', hIni: '12:30', hFi: '13:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240051', nom: 'Intel·ligència Artificial' },
      grup: { idGrup: '240051·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 50, profes: ['D110 - Dr. Sergi Pons'], cohorts: ['GEI:4t']
    },
    {
      idSessio: 'Q4-V-06', data: '2026-11-06', dia: 'V', hIni: '13:30', hFi: '14:30', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240051', nom: 'Intel·ligència Artificial' },
      grup: { idGrup: '240051·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 50, profes: ['D110 - Dr. Sergi Pons'], cohorts: ['GEI:4t']
    },
    // 15:00 - 17:00 (Enginyeria del Software - 2h consecutivas)
    {
      idSessio: 'Q4-V-07', data: '2026-11-06', dia: 'V', hIni: '15:00', hFi: '16:00', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240041', nom: 'Enginyeria del Software' },
      grup: { idGrup: '240041·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 45, profes: ['D109 - Dra. Laura Serra'], cohorts: ['GEI:3r']
    },
    {
      idSessio: 'Q4-V-08', data: '2026-11-06', dia: 'V', hIni: '16:00', hFi: '17:00', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240041', nom: 'Enginyeria del Software' },
      grup: { idGrup: '240041·TE/450', grup: 'TE/450', tipus: 'TE' },
      alumnes: 45, profes: ['D109 - Dra. Laura Serra'], cohorts: ['GEI:3r']
    },
    // 17:00 - 19:00 (Xarxes de Computadors - 2h consecutivas)
    {
      idSessio: 'Q4-V-09', data: '2026-11-06', dia: 'V', hIni: '17:00', hFi: '18:00', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240032', nom: 'Xarxes de Computadors' },
      grup: { idGrup: '240032·PLAB/450', grup: 'PLAB/450', tipus: 'PLAB' },
      alumnes: 38, profes: ['D108 - Dr. Pau Bosch'], cohorts: ['GEI:3r']
    },
    {
      idSessio: 'Q4-V-10', data: '2026-11-06', dia: 'V', hIni: '18:00', hFi: '19:00', duradaMin: 60,
      aula: 'Q4/0003', assignatura: { codi: '240032', nom: 'Xarxes de Computadors' },
      grup: { idGrup: '240032·PLAB/450', grup: 'PLAB/450', tipus: 'PLAB' },
      alumnes: 38, profes: ['D108 - Dr. Pau Bosch'], cohorts: ['GEI:3r']
    }
  ];

  return {
    idVersio: versionId,
    setmana: '2026-W45',
    dies: [
      { dia: 'L', data: '2026-11-02' },
      { dia: 'M', data: '2026-11-03' },
      { dia: 'X', data: '2026-11-04' },
      { dia: 'J', data: '2026-11-05' },
      { dia: 'V', data: '2026-11-06' }
    ],
    filtre: { aula: 'Q4/0003' },
    calendari: [],
    items: items,
    truncat: false
  };
}

// Generador de horario realista para cualquier aula (MOCK LEGACY)
function generateMockParrillaResponseLegacy(aula, data = '2026-11-07', versionId = 1) {
  const targetWeek = typeof data === 'string' && data.includes('-W') ? data : '2026-W45';
  if (aula === 'Q4/0003' || aula?.replace(/[\s\-_]/g, '').toUpperCase().includes('Q4/0003')) {
    return getQ40003WeeklySchedule(versionId, targetWeek);
  }

  const days = ['L', 'M', 'X', 'J', 'V'];
  const items = [];

  days.forEach((day, dayIndex) => {
    const seed = hashString(`${aula}-${day}`);
    const subIdx1 = (seed + dayIndex * 2) % SAMPLE_SUBJECTS.length;
    const subIdx2 = (seed + dayIndex * 3 + 4) % SAMPLE_SUBJECTS.length;
    const subIdx3 = (seed + dayIndex * 5 + 7) % SAMPLE_SUBJECTS.length;

    const s1 = SAMPLE_SUBJECTS[subIdx1];
    const s2 = SAMPLE_SUBJECTS[subIdx2];
    const s3 = SAMPLE_SUBJECTS[subIdx3];
    
    const isSpecialGroupRoom = ['Q4/1003', 'Q6/2004', 'QC/3088'].includes(aula);
    const groupNum = isSpecialGroupRoom ? 450 : (10 + (seed % 30));

    // Mañana: 08:30 - 10:30 (2 horas combinadas)
    items.push({
      idSessio: `S-${day}-01`, data: `2026-11-0${2 + dayIndex}`, dia: day,
      hIni: '08:30', hFi: '09:30', duradaMin: 60, aula: aula,
      assignatura: { codi: s1.codi, nom: s1.nom },
      grup: { idGrup: `${s1.codi}·${s1.tipus}/${groupNum}`, grup: `${s1.tipus}/${groupNum}`, tipus: s1.tipus },
      alumnes: 45, profes: [s1.profe], cohorts: [s1.cohort]
    });
    items.push({
      idSessio: `S-${day}-02`, data: `2026-11-0${2 + dayIndex}`, dia: day,
      hIni: '09:30', hFi: '10:30', duradaMin: 60, aula: aula,
      assignatura: { codi: s1.codi, nom: s1.nom },
      grup: { idGrup: `${s1.codi}·${s1.tipus}/${groupNum}`, grup: `${s1.tipus}/${groupNum}`, tipus: s1.tipus },
      alumnes: 45, profes: [s1.profe], cohorts: [s1.cohort]
    });

    // Mañana: 11:30 - 13:30 (2 horas combinadas)
    if (dayIndex % 2 === 0) {
      items.push({
        idSessio: `S-${day}-03`, data: `2026-11-0${2 + dayIndex}`, dia: day,
        hIni: '11:30', hFi: '12:30', duradaMin: 60, aula: aula,
        assignatura: { codi: s2.codi, nom: s2.nom },
        grup: { idGrup: `${s2.codi}·${s2.tipus}/${groupNum + 1}`, grup: `${s2.tipus}/${groupNum + 1}`, tipus: s2.tipus },
        alumnes: 50, profes: [s2.profe], cohorts: [s2.cohort]
      });
      items.push({
        idSessio: `S-${day}-04`, data: `2026-11-0${2 + dayIndex}`, dia: day,
        hIni: '12:30', hFi: '13:30', duradaMin: 60, aula: aula,
        assignatura: { codi: s2.codi, nom: s2.nom },
        grup: { idGrup: `${s2.codi}·${s2.tipus}/${groupNum + 1}`, grup: `${s2.tipus}/${groupNum + 1}`, tipus: s2.tipus },
        alumnes: 50, profes: [s2.profe], cohorts: [s2.cohort]
      });
    }

    // Tarde: 15:00 - 17:00 (2 horas combinadas)
    items.push({
      idSessio: `S-${day}-05`, data: `2026-11-0${2 + dayIndex}`, dia: day,
      hIni: '15:00', hFi: '16:00', duradaMin: 60, aula: aula,
      assignatura: { codi: s3.codi, nom: s3.nom },
      grup: { idGrup: `${s3.codi}·${s3.tipus}/${groupNum + 2}`, grup: `${s3.tipus}/${groupNum + 2}`, tipus: s3.tipus },
      alumnes: 40, profes: [s3.profe], cohorts: [s3.cohort]
    });
    items.push({
      idSessio: `S-${day}-06`, data: `2026-11-0${2 + dayIndex}`, dia: day,
      hIni: '16:00', hFi: '17:00', duradaMin: 60, aula: aula,
      assignatura: { codi: s3.codi, nom: s3.nom },
      grup: { idGrup: `${s3.codi}·${s3.tipus}/${groupNum + 2}`, grup: `${s3.tipus}/${groupNum + 2}`, tipus: s3.tipus },
      alumnes: 40, profes: [s3.profe], cohorts: [s3.cohort]
    });
  });

  return {
    idVersio: versionId,
    setmana: targetWeek,
    dies: [
      { dia: 'L', data: '2026-11-02' },
      { dia: 'M', data: '2026-11-03' },
      { dia: 'X', data: '2026-11-04' },
      { dia: 'J', data: '2026-11-05' },
      { dia: 'V', data: '2026-11-06' }
    ],
    filtre: { aula: aula },
    calendari: [],
    items: items,
    truncat: false
  };
}

============================================================================== */
