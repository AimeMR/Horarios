/**
 * SERVICIO DE FILTRADO DE HORARIOS Y AULAS
 *
 * Determina qué franjas horarias y qué aulas coinciden con los filtros aplicados:
 * - Fecha (día concreto o día de la semana)
 * - Grado (GEI, GIA, GCIB, GCID, GIS, etc.)
 * - Curso (1º a 5º)
 * - Asignatura (código o nombre)
 * - Grupo (número o identificador de grupo, ej. 450)
 */

import { generateMockParrillaResponse } from './scheduleService.js';

// Catálogo de aulas distribuidas por planta
export const FLOOR_ROOMS = {
  0: [
    'Q4/0003', 'Q4/0007', 'Q4/0011', 'Q3/0003', 'Q3/0007', 'Q3/0011',
    'Q6/0005', 'Q2/0003', 'Q2/0007', 'Q2/0011', 'Q2/0013', 'Q2/0017',
    'Q2/0019', 'Q5/0003', 'Q5/0004', 'Q1/0003', 'Q1/0005', 'Q1/0019',
    'QC/0011', 'QC/0019', 'QC/0067', 'QC/0075', 'QC/0081', 'QC/0085',
    'QC/0089', 'QC/0091', 'QC/0107', 'QC/0109', 'QC/0113', 'QC/0069',
    'QC/0073', 'QC/0077', 'QC/0079', 'QC/0083', 'QC/0087', 'QC/0111'
  ],
  1: [
    'Q4/1003', 'Q4/1005', 'Q4/1009', 'Q4/1013', 'Q3/1003', 'Q3/1007',
    'Q3/1011', 'Q6/1006', 'Q6/1011', 'Q6/1012', 'Q2/1003', 'Q2/1005',
    'Q2/1009', 'Q2/1013', 'Q5/1005', 'Q5/1006', 'Q5/1009', 'Q5/1010',
    'Q5/1011', 'Q1/1003', 'Q1/1005', 'Q1/1007', 'QC/1086', 'QC/1088',
    'QC/1031', 'QC/1033', 'QC/1041'
  ],
  2: [
    'Q6/2004', 'Q6/2005', 'Q6/2007', 'Q6/2008', 'Q6/2009', 'Q5/2003',
    'Q5/2006', 'Q5/2007', 'Q5/2008', 'Q5/2009', 'QC/2090', 'QC/2080',
    'QC/2082', 'QC/2004', 'QC/2011', 'QC/2015', 'QC/2101', 'QC/2099',
    'QC/2149', 'QC/2161', 'QC/2165', 'QC/2147', 'QC/2159'
  ],
  3: [
    'QC/3088', 'QC/3078', 'QC/3042', 'QC/3010', 'QC/3012', 'QC/3047', 'QC/3049'
  ]
};

/**
 * Obtiene información detallada de una semana ISO (YYYY-Www):
 * - Año y número de semana
 * - Fecha del Lunes y del Viernes
 * - Lista de los 5 días lectivos (Lunes a Viernes)
 * - Etiquetas formateadas para interfaz
 */
export function getWeekInfo(weekStr) {
  if (!weekStr) return null;
  const match = String(weekStr).trim().match(/^(\d{4})-W(\d{2})$/);
  if (!match) return null;

  const year = parseInt(match[1], 10);
  const week = parseInt(match[2], 10);

  // El 4 de enero siempre cae dentro de la semana 1 según la norma ISO 8601
  const jan4 = new Date(Date.UTC(year, 0, 4));
  const dayOfWeek = jan4.getUTCDay() || 7; // 1 = Lunes, 7 = Domingo
  const mondayWeek1 = new Date(jan4.getTime() - (dayOfWeek - 1) * 86400000);
  const targetMonday = new Date(mondayWeek1.getTime() + (week - 1) * 7 * 86400000);

  const dayNames = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'];
  const dayKeys = ['L', 'M', 'X', 'J', 'V'];
  const days = [];

  for (let i = 0; i < 5; i++) {
    const d = new Date(targetMonday.getTime() + i * 86400000);
    const dateStr = d.toISOString().split('T')[0];
    const parts = dateStr.split('-');
    const shortFormatted = `${parts[2]}/${parts[1]}`;
    days.push({
      key: dayKeys[i],
      name: dayNames[i],
      date: dateStr,
      shortDate: shortFormatted,
      fullLabel: `${dayNames[i]} (${shortFormatted})`
    });
  }

  const mondayStr = days[0].date;
  const fridayStr = days[4].date;
  const rangeLabel = `${days[0].shortDate} – ${days[4].shortDate}`;
  const badgeLabel = `Sem. ${week} (${rangeLabel})`;

  return {
    year,
    week,
    isoWeek: weekStr,
    monday: mondayStr,
    friday: fridayStr,
    rangeLabel,
    badgeLabel,
    days
  };
}

/**
 * Calcula la semana siguiente o anterior sumando el desplazamiento de semanas.
 */
export function getAdjacentWeek(weekStr, offset = 1) {
  const current = getWeekInfo(weekStr) || getWeekInfo('2026-W45');
  const targetMonday = new Date(`${current.monday}T12:00:00Z`);
  targetMonday.setUTCDate(targetMonday.getUTCDate() + offset * 7);

  const target = new Date(Date.UTC(targetMonday.getUTCFullYear(), targetMonday.getUTCMonth(), targetMonday.getUTCDate()));
  const dayNr = (target.getUTCDay() + 6) % 7;
  target.setUTCDate(target.getUTCDate() - dayNr + 3);
  const firstThursday = target.getTime();
  target.setUTCMonth(0, 1);
  if (target.getUTCDay() !== 4) {
    target.setUTCMonth(0, 1 + ((4 - target.getUTCDay()) + 7) % 7);
  }
  const weekNum = 1 + Math.ceil((firstThursday - target.getTime()) / 604800000);
  const yearNum = new Date(firstThursday).getUTCFullYear();
  return `${yearNum}-W${String(weekNum).padStart(2, '0')}`;
}

/**
 * Catálogo de semanas del cuatrimestre universitario (Septiembre - Enero)
 */
export const SEMESTER_WEEKS = [
  { isoWeek: '2026-W38', label: 'Semana 38 (14/09 – 18/09)' },
  { isoWeek: '2026-W39', label: 'Semana 39 (21/09 – 25/09)' },
  { isoWeek: '2026-W40', label: 'Semana 40 (28/09 – 02/10)' },
  { isoWeek: '2026-W41', label: 'Semana 41 (05/10 – 09/10)' },
  { isoWeek: '2026-W42', label: 'Semana 42 (12/10 – 16/10)' },
  { isoWeek: '2026-W43', label: 'Semana 43 (19/10 – 23/10)' },
  { isoWeek: '2026-W44', label: 'Semana 44 (26/10 – 30/10)' },
  { isoWeek: '2026-W45', label: 'Semana 45 (02/11 – 06/11) · Actual' },
  { isoWeek: '2026-W46', label: 'Semana 46 (09/11 – 13/11)' },
  { isoWeek: '2026-W47', label: 'Semana 47 (16/11 – 20/11)' },
  { isoWeek: '2026-W48', label: 'Semana 48 (23/11 – 27/11)' },
  { isoWeek: '2026-W49', label: 'Semana 49 (30/11 – 04/12)' },
  { isoWeek: '2026-W50', label: 'Semana 50 (07/12 – 11/12)' },
  { isoWeek: '2026-W51', label: 'Semana 51 (14/12 – 18/12)' },
  { isoWeek: '2026-W52', label: 'Semana 52 (21/12 – 25/12)' }
];

/**
 * Comprueba si hay al menos un filtro activo.
 */
export function hasActiveFilters(filters) {
  if (!filters) return false;
  return Boolean(
    (filters.week && String(filters.week).trim() !== '') ||
    (filters.date && String(filters.date).trim() !== '') ||
    (filters.degree && String(filters.degree).trim() !== '') ||
    (filters.course && String(filters.course).trim() !== '') ||
    (filters.subject && String(filters.subject).trim() !== '') ||
    (filters.group !== undefined && filters.group !== null && String(filters.group).trim() !== '')
  );
}

/**
 * Obtiene la letra del día ('L', 'M', 'X', 'J', 'V') a partir de una fecha YYYY-MM-DD.
 */
export function getDiaCode(dateStr) {
  if (!dateStr) return null;
  const d = new Date(`${dateStr}T12:00:00`);
  if (isNaN(d.getTime())) return null;
  const day = d.getDay(); // 0: Dom, 1: Lun, 2: Mar, 3: Mié, 4: Jue, 5: Vie, 6: Sáb
  const map = { 1: 'L', 2: 'M', 3: 'X', 4: 'J', 5: 'V' };
  return map[day] || null;
}

/**
 * Normaliza cadenas para comparación sin acentos ni mayúsculas.
 */
function normalizeStr(str) {
  if (!str) return '';
  return str
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim();
}

/**
 * Verifica si una sesión concreta cumple con todos los filtros activos (intersección AND).
 */
export function matchesSessionFilter(session, filters) {
  if (!session) return false;
  if (!hasActiveFilters(filters)) return true;

  // 1. FILTRO DE SEMANA LECTIVA (semana entera de Lunes a Viernes)
  const targetWeek = filters.week || (filters.date?.includes('-W') ? filters.date : null);
  if (targetWeek && String(targetWeek).trim() !== '') {
    const weekInfo = getWeekInfo(String(targetWeek).trim());
    if (weekInfo) {
      const sessionDate = session.data || '';
      const inDateRange = sessionDate >= weekInfo.monday && sessionDate <= weekInfo.friday;
      const inIsoWeek = session.setmana === weekInfo.isoWeek;

      // Si la sesión no pertenece al rango de lunes a viernes ni a la semana ISO
      if (!inDateRange && !inIsoWeek) {
        return false;
      }
    }
  } else if (filters.date && String(filters.date).trim() !== '') {
    // Modo de compatibilidad si se proporciona una fecha puntual
    const targetDate = String(filters.date).trim();
    const diaTarget = getDiaCode(targetDate);

    const matchesDate = session.data === targetDate;
    const matchesDia = diaTarget && session.dia === diaTarget;

    if (!matchesDate && !matchesDia) {
      return false;
    }
  }

  // 2. FILTRO DE GRADO
  if (filters.degree && String(filters.degree).trim() !== '') {
    const deg = normalizeStr(filters.degree);
    const degreeCohorts = {
      'ing-informatica': ['gei', 'inf', '24001', '24002', '24003', '24004'],
      'ia': ['gia', 'ia', '24005'],
      'ciberseguridad': ['gcib', 'cib', '24006', 'segur'],
      'ciencia-datos': ['gcid', 'datos', 'dades'],
      'ing-software': ['gis', 'software']
    };
    const validTokens = degreeCohorts[deg] || [deg];
    const sessionCohorts = (session.cohorts || []).map(c => normalizeStr(c));
    const subjectCode = normalizeStr(session.assignatura?.codi || '');

    const matchesCohort = sessionCohorts.some(c => validTokens.some(t => c.includes(t)));
    const matchesCode = validTokens.some(t => subjectCode.startsWith(t));

    if (!matchesCohort && !matchesCode) {
      return false;
    }
  }

  // 3. FILTRO DE CURSO (1º A 5º)
  if (filters.course && String(filters.course).trim() !== '') {
    const course = String(filters.course).trim();
    const courseMap = {
      '1': ['1r', '1'],
      '2': ['2n', '2'],
      '3': ['3r', '3'],
      '4': ['4t', '4'],
      '5': ['5', 'm', 'master', 'postgrau']
    };
    const validTokens = courseMap[course] || [course];
    const sessionCohorts = (session.cohorts || []).map(c => normalizeStr(c));
    const matchesCohort = sessionCohorts.some(c => validTokens.some(t => c.includes(t)));

    const subCode = session.assignatura?.codi || '';
    let matchesSubCode = false;
    if (course === '1') matchesSubCode = ['240011', '240012', '240013', '240021'].includes(subCode);
    if (course === '2') matchesSubCode = ['240022', '240023', '240031'].includes(subCode);
    if (course === '3') matchesSubCode = ['240032', '240041'].includes(subCode);
    if (course === '4') matchesSubCode = ['240051', '240052'].includes(subCode);
    if (course === '5') matchesSubCode = ['240061'].includes(subCode);

    if (!matchesCohort && !matchesSubCode) {
      return false;
    }
  }

  // 4. FILTRO DE ASIGNATURA
  if (filters.subject && String(filters.subject).trim() !== '') {
    const subFilter = normalizeStr(filters.subject);
    const codi = normalizeStr(session.assignatura?.codi || '');
    const nom = normalizeStr(session.assignatura?.nom || '');

    const subAliases = {
      'prog1': ['240013', 'programacio'],
      'calculo': ['240012', 'calcul'],
      'fisica': ['240011', 'fisica'],
      'algebra': ['240021', 'algebra'],
      'eda': ['240022', 'estructures'],
      'so': ['240023', 'sistemes'],
      'bd': ['240031', 'bases'],
      'redes': ['240032', 'xarxes'],
      'is': ['240041', 'software'],
      'ia': ['240051', 'inteligencia'],
      'ml': ['240052', 'aprenentatge'],
      'seguridad': ['240061', 'ciberseguretat', 'seguretat']
    };

    const aliases = subAliases[subFilter] || [subFilter];
    const matchesCodi = codi === subFilter || aliases.includes(codi);
    const matchesNom = nom.includes(subFilter) || aliases.some(a => nom.includes(a));

    if (!matchesCodi && !matchesNom) {
      return false;
    }
  }

  // 5. FILTRO DE GRUPO (NÚMERO IDENTIFICADOR)
  if (filters.group !== undefined && filters.group !== null && String(filters.group).trim() !== '') {
    const targetGroup = String(filters.group).trim().toLowerCase();
    const sessionGroup = (session.grup?.grup || '').toLowerCase();
    const sessionGroupId = (session.grup?.idGrup || '').toLowerCase();

    const matchesGroup = sessionGroup.includes(targetGroup) || sessionGroupId.includes(targetGroup);
    if (!matchesGroup) {
      return false;
    }
  }

  return true;
}

/**
 * Evalúa todas las aulas de todas las plantas frente a los filtros aplicados.
 * Devuelve un mapa con las aulas coincidentes por planta y el recuento total.
 */
export function evaluateAllFloorsFilters(appliedFilters) {
  const result = {
    matchingRoomsByFloor: { 0: [], 1: [], 2: [], 3: [] },
    countsByFloor: { 0: 0, 1: 0, 2: 0, 3: 0 },
    hasActiveFilters: hasActiveFilters(appliedFilters),
    totalMatches: 0
  };

  if (!result.hasActiveFilters) {
    return result;
  }

  // Recorrer las plantas 0, 1, 2 y 3
  [0, 1, 2, 3].forEach((floorNum) => {
    const rooms = FLOOR_ROOMS[floorNum] || [];
    const matchingInFloor = [];

    rooms.forEach((roomName) => {
      const schedule = generateMockParrillaResponse(roomName);
      if (schedule && Array.isArray(schedule.items)) {
        const hasMatch = schedule.items.some((session) => matchesSessionFilter(session, appliedFilters));
        if (hasMatch) {
          matchingInFloor.push(roomName);
        }
      }
    });

    result.matchingRoomsByFloor[floorNum] = matchingInFloor;
    result.countsByFloor[floorNum] = matchingInFloor.length;
    result.totalMatches += matchingInFloor.length;
  });

  return result;
}
