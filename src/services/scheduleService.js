/**
 * Servicio de horarios (parrilla de sesiones) según el contrato de backend (contracte-fase2.md).
 * Endpoint esperado: GET /versions/:id/parrilla?aula=:aula&data=:data
 */

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

// Hash determinista simple basado en strings para generar horarios realistas por aula
function hashString(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

/**
 * Horario de prueba específico para el aula Q4/0003 (Planta 0)
 * Cubre de forma explícita las franjas de 8:30 a 14:30, la pausa hasta las 15:00
 * y de 15:00 a 21:00 con fusiones consecutivas reales bajo el contrato contracte-fase2.md.
 */
function getQ40003CustomSchedule(data, versionId) {
  return {
    idVersio: versionId,
    setmana: '2026-W45',
    dies: [{ dia: 'L', data: data }],
    filtre: { aula: 'Q4/0003' },
    calendari: [],
    items: [
      // 08:30 - 09:30 (Càlcul I - Franja 1 de 2 consecutivas)
      {
        idSessio: 'S-Q40003-01',
        data: data,
        dia: 'L',
        hIni: '08:30',
        hFi: '09:30',
        duradaMin: 60,
        aula: 'Q4/0003',
        assignatura: { codi: '240012', nom: 'Càlcul I' },
        grup: { idGrup: '240012·TE/450', grup: 'TE/450', tipus: 'TE' },
        alumnes: 65,
        profes: ['D102 - Dra. Marta Vila'],
        cohorts: ['GEI:1r'],
        idCompartida: null,
        fixadaMotiu: null,
        moguda: false,
        canviAula: false,
        recuperada: false
      },
      // 09:30 - 10:30 (Càlcul I - Franja 2 de 2 consecutivas -> Fusión visual de 08:30 a 10:30)
      {
        idSessio: 'S-Q40003-02',
        data: data,
        dia: 'L',
        hIni: '09:30',
        hFi: '10:30',
        duradaMin: 60,
        aula: 'Q4/0003',
        assignatura: { codi: '240012', nom: 'Càlcul I' },
        grup: { idGrup: '240012·TE/450', grup: 'TE/450', tipus: 'TE' },
        alumnes: 65,
        profes: ['D102 - Dra. Marta Vila'],
        cohorts: ['GEI:1r'],
        idCompartida: null,
        fixadaMotiu: null,
        moguda: false,
        canviAula: false,
        recuperada: false
      },

      // 10:30 - 11:30: Hueco libre / disponible

      // 11:30 - 12:30 (Programació I - Franja 1 de 2 consecutivas)
      {
        idSessio: 'S-Q40003-03',
        data: data,
        dia: 'L',
        hIni: '11:30',
        hFi: '12:30',
        duradaMin: 60,
        aula: 'Q4/0003',
        assignatura: { codi: '240013', nom: 'Programació I' },
        grup: { idGrup: '240013·PLAB/450', grup: 'PLAB/450', tipus: 'PLAB' },
        alumnes: 45,
        profes: ['D103 - Dr. Albert Soler'],
        cohorts: ['GEI:1r'],
        idCompartida: null,
        fixadaMotiu: null,
        moguda: false,
        canviAula: false,
        recuperada: false
      },
      // 12:30 - 13:30 (Programació I - Franja 2 de 2 consecutivas -> Fusión visual de 11:30 a 13:30)
      {
        idSessio: 'S-Q40003-04',
        data: data,
        dia: 'L',
        hIni: '12:30',
        hFi: '13:30',
        duradaMin: 60,
        aula: 'Q4/0003',
        assignatura: { codi: '240013', nom: 'Programació I' },
        grup: { idGrup: '240013·PLAB/450', grup: 'PLAB/450', tipus: 'PLAB' },
        alumnes: 45,
        profes: ['D103 - Dr. Albert Soler'],
        cohorts: ['GEI:1r'],
        idCompartida: null,
        fixadaMotiu: null,
        moguda: false,
        canviAula: false,
        recuperada: false
      },
      // 13:30 - 14:30 (Àlgebra Lineal - 1 hora individual)
      {
        idSessio: 'S-Q40003-05',
        data: data,
        dia: 'L',
        hIni: '13:30',
        hFi: '14:30',
        duradaMin: 60,
        aula: 'Q4/0003',
        assignatura: { codi: '240021', nom: 'Àlgebra Lineal' },
        grup: { idGrup: '240021·SEM/450', grup: 'SEM/450', tipus: 'SEM' },
        alumnes: 30,
        profes: ['D104 - Dr. Carles Puig'],
        cohorts: ['GEI:1r'],
        idCompartida: null,
        fixadaMotiu: null,
        moguda: false,
        canviAula: false,
        recuperada: false
      },

      // 14:30 - 15:00: FRANJA GRIS (PAUSA / ALMUERZO) - Se muestra automáticamente

      // 15:00 - 16:00 (Estructures de Dades - 1 hora individual)
      {
        idSessio: 'S-Q40003-06',
        data: data,
        dia: 'L',
        hIni: '15:00',
        hFi: '16:00',
        duradaMin: 60,
        aula: 'Q4/0003',
        assignatura: { codi: '240022', nom: 'Estructures de Dades' },
        grup: { idGrup: '240022·TE/450', grup: 'TE/450', tipus: 'TE' },
        alumnes: 55,
        profes: ['D105 - Dra. Nuria Riera'],
        cohorts: ['GEI:2n'],
        idCompartida: null,
        fixadaMotiu: null,
        moguda: false,
        canviAula: false,
        recuperada: false
      },
      // 16:00 - 17:00 (Sistemes Operatius - Franja 1 de 2 consecutivas)
      {
        idSessio: 'S-Q40003-07',
        data: data,
        dia: 'L',
        hIni: '16:00',
        hFi: '17:00',
        duradaMin: 60,
        aula: 'Q4/0003',
        assignatura: { codi: '240023', nom: 'Sistemes Operatius' },
        grup: { idGrup: '240023·PLAB/450', grup: 'PLAB/450', tipus: 'PLAB' },
        alumnes: 42,
        profes: ['D106 - Dr. Jordi Mas'],
        cohorts: ['GEI:2n'],
        idCompartida: null,
        fixadaMotiu: null,
        moguda: false,
        canviAula: false,
        recuperada: false
      },
      // 17:00 - 18:00 (Sistemes Operatius - Franja 2 de 2 consecutivas -> Fusión visual de 16:00 a 18:00)
      {
        idSessio: 'S-Q40003-08',
        data: data,
        dia: 'L',
        hIni: '17:00',
        hFi: '18:00',
        duradaMin: 60,
        aula: 'Q4/0003',
        assignatura: { codi: '240023', nom: 'Sistemes Operatius' },
        grup: { idGrup: '240023·PLAB/450', grup: 'PLAB/450', tipus: 'PLAB' },
        alumnes: 42,
        profes: ['D106 - Dr. Jordi Mas'],
        cohorts: ['GEI:2n'],
        idCompartida: null,
        fixadaMotiu: null,
        moguda: false,
        canviAula: false,
        recuperada: false
      },

      // 18:00 - 19:00: Hueco libre / disponible

      // 19:00 - 20:00 (Bases de Dades - Franja 1 de 2 consecutivas)
      {
        idSessio: 'S-Q40003-09',
        data: data,
        dia: 'L',
        hIni: '19:00',
        hFi: '20:00',
        duradaMin: 60,
        aula: 'Q4/0003',
        assignatura: { codi: '240031', nom: 'Bases de Dades' },
        grup: { idGrup: '240031·TE/450', grup: 'TE/450', tipus: 'TE' },
        alumnes: 50,
        profes: ['D107 - Dra. Elena Grau'],
        cohorts: ['GEI:2n'],
        idCompartida: null,
        fixadaMotiu: null,
        moguda: false,
        canviAula: false,
        recuperada: false
      },
      // 20:00 - 21:00 (Bases de Dades - Franja 2 de 2 consecutivas -> Fusión visual de 19:00 a 21:00)
      {
        idSessio: 'S-Q40003-10',
        data: data,
        dia: 'L',
        hIni: '20:00',
        hFi: '21:00',
        duradaMin: 60,
        aula: 'Q4/0003',
        assignatura: { codi: '240031', nom: 'Bases de Dades' },
        grup: { idGrup: '240031·TE/450', grup: 'TE/450', tipus: 'TE' },
        alumnes: 50,
        profes: ['D107 - Dra. Elena Grau'],
        cohorts: ['GEI:2n'],
        idCompartida: null,
        fixadaMotiu: null,
        moguda: false,
        canviAula: false,
        recuperada: false
      }
    ],
    truncat: false
  };
}

/**
 * Genera un conjunto de sesiones en formato exacto de contracte-fase2.md
 * Garantiza la presencia de franjas consecutivas con el mismo id/código para probar la fusión visual.
 */
export function generateMockParrillaResponse(aula, data = '2026-11-07', versionId = 1) {
  // Horario de prueba explícito para Q4/0003
  if (aula === 'Q4/0003' || aula?.replace(/[\s\-_]/g, '').toUpperCase().includes('Q4/0003')) {
    return getQ40003CustomSchedule(data, versionId);
  }

  const seed = hashString(`${aula}-${data}`);
  const items = [];

  // Patrones predefinidos de ocupación para variar entre salas
  // Cada patrón define asignaciones para las franjas horarias:
  // Mañana: 08:30, 09:30, 10:30, 11:30, 12:30, 13:30
  // Tarde:  15:00, 16:00, 17:00, 18:00, 19:00, 20:00
  const subIdx1 = seed % SAMPLE_SUBJECTS.length;
  const subIdx2 = (seed + 3) % SAMPLE_SUBJECTS.length;
  const subIdx3 = (seed + 7) % SAMPLE_SUBJECTS.length;
  const subIdx4 = (seed + 5) % SAMPLE_SUBJECTS.length;

  const s1 = SAMPLE_SUBJECTS[subIdx1];
  const s2 = SAMPLE_SUBJECTS[subIdx2];
  const s3 = SAMPLE_SUBJECTS[subIdx3];
  const s4 = SAMPLE_SUBJECTS[subIdx4];

  const groupNum1 = 10 + (seed % 40);
  const groupNum2 = 10 + ((seed + 20) % 40);
  const groupNum3 = 10 + ((seed + 50) % 40);

  // 1. MAÑANA: 08:30 a 10:30 (FUSIÓN: 2 franjas consecutivas con la misma asignatura)
  items.push({
    idSessio: `S${seed + 101}`,
    data: data,
    dia: 'L',
    hIni: '08:30',
    hFi: '09:30',
    duradaMin: 60,
    aula: aula,
    assignatura: { codi: s1.codi, nom: s1.nom },
    grup: { idGrup: `${s1.codi}·${s1.tipus}/${groupNum1}`, grup: `${s1.tipus}/${groupNum1}`, tipus: s1.tipus },
    alumnes: 45 + (seed % 35),
    profes: [s1.profe],
    cohorts: [s1.cohort],
    idCompartida: null,
    fixadaMotiu: null,
    moguda: false,
    canviAula: false,
    recuperada: false
  });

  items.push({
    idSessio: `S${seed + 102}`,
    data: data,
    dia: 'L',
    hIni: '09:30',
    hFi: '10:30',
    duradaMin: 60,
    aula: aula,
    assignatura: { codi: s1.codi, nom: s1.nom },
    grup: { idGrup: `${s1.codi}·${s1.tipus}/${groupNum1}`, grup: `${s1.tipus}/${groupNum1}`, tipus: s1.tipus },
    alumnes: 45 + (seed % 35),
    profes: [s1.profe],
    cohorts: [s1.cohort],
    idCompartida: null,
    fixadaMotiu: null,
    moguda: false,
    canviAula: false,
    recuperada: false
  });

  // 10:30 a 11:30 -> Hueco libre / disponible

  // 2. MAÑANA: 11:30 a 13:30 (FUSIÓN: 2 franjas consecutivas con la asignatura s2)
  items.push({
    idSessio: `S${seed + 103}`,
    data: data,
    dia: 'L',
    hIni: '11:30',
    hFi: '12:30',
    duradaMin: 60,
    aula: aula,
    assignatura: { codi: s2.codi, nom: s2.nom },
    grup: { idGrup: `${s2.codi}·${s2.tipus}/${groupNum2}`, grup: `${s2.tipus}/${groupNum2}`, tipus: s2.tipus },
    alumnes: 55 + (seed % 25),
    profes: [s2.profe],
    cohorts: [s2.cohort],
    idCompartida: null,
    fixadaMotiu: null,
    moguda: false,
    canviAula: false,
    recuperada: false
  });

  items.push({
    idSessio: `S${seed + 104}`,
    data: data,
    dia: 'L',
    hIni: '12:30',
    hFi: '13:30',
    duradaMin: 60,
    aula: aula,
    assignatura: { codi: s2.codi, nom: s2.nom },
    grup: { idGrup: `${s2.codi}·${s2.tipus}/${groupNum2}`, grup: `${s2.tipus}/${groupNum2}`, tipus: s2.tipus },
    alumnes: 55 + (seed % 25),
    profes: [s2.profe],
    cohorts: [s2.cohort],
    idCompartida: null,
    fixadaMotiu: null,
    moguda: false,
    canviAula: false,
    recuperada: false
  });

  // 13:30 a 14:30 -> Sesión simple de 1 hora si el seed es par, o libre si es impar
  if (seed % 2 === 0) {
    items.push({
      idSessio: `S${seed + 105}`,
      data: data,
      dia: 'L',
      hIni: '13:30',
      hFi: '14:30',
      duradaMin: 60,
      aula: aula,
      assignatura: { codi: s3.codi, nom: s3.nom },
      grup: { idGrup: `${s3.codi}·SEM/1`, grup: 'SEM/1', tipus: 'SEM' },
      alumnes: 25,
      profes: [s3.profe],
      cohorts: [s3.cohort],
      idCompartida: null,
      fixadaMotiu: null,
      moguda: false,
      canviAula: false,
      recuperada: false
    });
  }

  // 14:30 a 15:00 -> FRANJA GRIS (PAUSA / ALMUERZO) - No tiene docencia

  // 3. TARDE: 15:00 a 16:00 -> Sesión individual de 1 hora
  items.push({
    idSessio: `S${seed + 201}`,
    data: data,
    dia: 'L',
    hIni: '15:00',
    hFi: '16:00',
    duradaMin: 60,
    aula: aula,
    assignatura: { codi: s3.codi, nom: s3.nom },
    grup: { idGrup: `${s3.codi}·${s3.tipus}/${groupNum3}`, grup: `${s3.tipus}/${groupNum3}`, tipus: s3.tipus },
    alumnes: 40,
    profes: [s3.profe],
    cohorts: [s3.cohort],
    idCompartida: null,
    fixadaMotiu: null,
    moguda: false,
    canviAula: false,
    recuperada: false
  });

  // 4. TARDE: 16:00 a 18:00 (FUSIÓN: 2 franjas consecutivas con la asignatura s4)
  items.push({
    idSessio: `S${seed + 202}`,
    data: data,
    dia: 'L',
    hIni: '16:00',
    hFi: '17:00',
    duradaMin: 60,
    aula: aula,
    assignatura: { codi: s4.codi, nom: s4.nom },
    grup: { idGrup: `${s4.codi}·${s4.tipus}/90`, grup: `${s4.tipus}/90`, tipus: s4.tipus },
    alumnes: 60,
    profes: [s4.profe],
    cohorts: [s4.cohort],
    idCompartida: null,
    fixadaMotiu: null,
    moguda: false,
    canviAula: false,
    recuperada: false
  });

  items.push({
    idSessio: `S${seed + 203}`,
    data: data,
    dia: 'L',
    hIni: '17:00',
    hFi: '18:00',
    duradaMin: 60,
    aula: aula,
    assignatura: { codi: s4.codi, nom: s4.nom },
    grup: { idGrup: `${s4.codi}·${s4.tipus}/90`, grup: `${s4.tipus}/90`, tipus: s4.tipus },
    alumnes: 60,
    profes: [s4.profe],
    cohorts: [s4.cohort],
    idCompartida: null,
    fixadaMotiu: null,
    moguda: false,
    canviAula: false,
    recuperada: false
  });

  // 18:00 a 19:00 -> Libre

  // 19:00 a 21:00 (FUSIÓN: 2 franjas consecutivas)
  if (seed % 3 !== 0) {
    items.push({
      idSessio: `S${seed + 204}`,
      data: data,
      dia: 'L',
      hIni: '19:00',
      hFi: '20:00',
      duradaMin: 60,
      aula: aula,
      assignatura: { codi: s1.codi, nom: s1.nom },
      grup: { idGrup: `${s1.codi}·TE/99`, grup: 'TE/99', tipus: 'TE' },
      alumnes: 38,
      profes: [s1.profe],
      cohorts: [s1.cohort],
      idCompartida: null,
      fixadaMotiu: null,
      moguda: false,
      canviAula: false,
      recuperada: false
    });

    items.push({
      idSessio: `S${seed + 205}`,
      data: data,
      dia: 'L',
      hIni: '20:00',
      hFi: '21:00',
      duradaMin: 60,
      aula: aula,
      assignatura: { codi: s1.codi, nom: s1.nom },
      grup: { idGrup: `${s1.codi}·TE/99`, grup: 'TE/99', tipus: 'TE' },
      alumnes: 38,
      profes: [s1.profe],
      cohorts: [s1.cohort],
      idCompartida: null,
      fixadaMotiu: null,
      moguda: false,
      canviAula: false,
      recuperada: false
    });
  }

  return {
    idVersio: versionId,
    setmana: '2026-W45',
    dies: [
      { dia: 'L', data: data }
    ],
    filtre: { aula: aula },
    calendari: [],
    items: items,
    truncat: false
  };
}

/**
 * Consulta la parrilla de sesiones para un aula.
 * Intenta conectar con el endpoint del backend /versions/:id/parrilla o /api/versions/:id/parrilla.
 * Si no está disponible o falla, proporciona el mock con estructura idéntica garantizada.
 */
export async function getRoomSchedule(aula, data = '2026-11-07', versionId = 1) {
  const endpoint = `/api/versions/${versionId}/parrilla?aula=${encodeURIComponent(aula)}&data=${encodeURIComponent(data)}`;

  try {
    const res = await fetch(endpoint, {
      headers: { 'Accept': 'application/json' },
      signal: AbortSignal.timeout(2500)
    });

    if (res.ok) {
      const json = await res.json();
      if (json && Array.isArray(json.items)) {
        return { data: json, source: 'backend' };
      }
    }
  } catch (_) {
    // Si la API aún no está levantada o da timeout/network error, recurre al mock
  }

  // Fallback con contrato real garantizado
  const mockData = generateMockParrillaResponse(aula, data, versionId);
  return { data: mockData, source: 'mock-contract' };
}

