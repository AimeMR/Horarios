/**
 * DICCIONARIO DE TRADUCCIÓN MULTI-IDIOMA
 * Idiomas soportados: Castellano ('es'), Català ('ca'), English ('en')
 */

export const TRANSLATIONS = {
  es: {
    app: {
      brandTitle: 'Edificio Central',
      floorLabel: 'Planta',
      toggleSidebar: 'Alternar filtros (Ctrl+B)',
      hideSidebar: 'Ocultar barra lateral',
      showSidebar: 'Mostrar barra lateral'
    },
    sidebar: {
      title: 'Filtros',
      weekSection: 'Semana lectiva',
      selectWeekInCalendar: 'Indicar semana en calendario',
      clearWeek: 'Quitar semana',
      allWeeks: 'Todas',
      weekFromTo: (w, r, m, f) => `Semana ${w} (${r}): del lunes ${m} al viernes ${f}`,
      allWeeksDesc: 'Horarios aplicables a todo el semestre',
      weekHint: 'Selecciona la semana en el calendario para ver el horario completo de Lunes a Viernes',
      degreeSection: 'Grado',
      allDegrees: 'Todos los grados',
      allDegreesBadge: 'Todos',
      degreeHint: 'Titulación académica obtenida del sistema',
      courseSection: 'Curso',
      allCourses: 'Todos los cursos',
      allCoursesBadge: 'Todos',
      courseHint: 'Año o nivel lectivo (1º a 5º)',
      subjectSection: 'Asignatura',
      allSubjects: 'Todas las asignaturas',
      allSubjectsBadge: 'Todas',
      subjectHint: 'Materia correspondiente según titulación',
      groupSection: 'Grupo',
      allGroupsBadge: 'Todos',
      groupNumberLabel: 'Número identificador',
      groupPlaceholder: 'Ej: 450',
      groupHint: 'Introduce el número del grupo (ej. 450)',
      clearFilters: 'Limpiar filtros',
      applyFilters: 'Aplicar filtros',
      footerEndpoint: 'Categorías conectadas al endpoint /api/filters (modo base).'
    },
    floorSelector: {
      previousFloor: 'Planta anterior',
      nextFloor: 'Planta siguiente',
      floorPill: (num) => `Planta ${num}`,
      floorDescriptions: {
        0: 'Planta 0 — Bloques Q1-Q6, Ala Central (QC) & Ala Sur (QP)',
        1: 'Planta 1 — Bloques Q1-Q6 y Ala Central (QC)',
        2: 'Planta 2 — Bloques Q5-Q6 y Ala Central (QC)',
        3: 'Planta 3 — Ala Central Superior (QC)'
      },
      alertText: (count) => `${count} ${count === 1 ? 'aula' : 'aulas'}`,
      alertTooltip: (count, num) => `${count} ${count === 1 ? 'aula que cumple' : 'aulas que cumplen'} el filtro en Planta ${num}`
    },
    map: {
      panHint: 'Rueda para zoom • Arrastra para moverte por el plano',
      zoomIn: 'Acercar mapa (+)',
      zoomOut: 'Alejar mapa (-)',
      resetZoom: 'Restablecer zoom al 100%',
      fitPlan: 'Ajustar y centrar plano',
      roomAria: (name) => `Aula ${name}`
    },
    schedule: {
      roomBadge: (room) => `Aula ${room}`,
      title: 'Horario Semanal',
      subtitle: (week, range) => week ? `Semana ${week} (${range}) • Lunes a Viernes` : 'Lunes a Viernes • 08:30 a 21:00',
      activeFilter: 'Filtro activo (franjas coincidentes destacadas)',
      close: 'Cerrar horario (Esc)',
      loading: (room) => `Cargando horario semanal del aula ${room}...`,
      timeColumn: 'Hora',
      pauseTime: '14:30 – 15:00',
      pauseText: 'PAUSA / ALMUERZO',
      codePrefix: 'Cód.',
      combinedHours: (h) => `${h}h combinadas`,
      days: {
        L: 'Lunes',
        M: 'Martes',
        X: 'Miércoles',
        J: 'Jueves',
        V: 'Viernes'
      }
    },
    degrees: {
      'ing-informatica': { name: 'Grado en Ingeniería Informática', short: 'Ing. Inf.' },
      'ia': { name: 'Grado en Inteligencia Artificial', short: 'IA' },
      'ciberseguridad': { name: 'Grado en Ciberseguridad', short: 'Ciber' },
      'ciencia-datos': { name: 'Grado en Ciencia e Ingeniería de Datos', short: 'Datos' },
      'ing-software': { name: 'Grado en Ingeniería del Software', short: 'Software' }
    },
    courses: {
      '1': { name: '1º Curso', short: '1º' },
      '2': { name: '2º Curso', short: '2º' },
      '3': { name: '3º Curso', short: '3º' },
      '4': { name: '4º Curso', short: '4º' },
      '5': { name: '5º Curso', short: '5º' }
    },
    subjects: {
      '240011': 'Física I',
      '240012': 'Cálculo I',
      '240013': 'Programación I',
      '240021': 'Álgebra Lineal',
      '240022': 'Estructuras de Datos',
      '240023': 'Sistemas Operativos',
      '240031': 'Bases de Datos',
      '240032': 'Redes de Computadores',
      '240041': 'Ingeniería del Software',
      '240051': 'Inteligencia Artificial',
      '240052': 'Aprendizaje Automático',
      '240061': 'Ciberseguridad Avanzada'
    }
  },

  ca: {
    app: {
      brandTitle: 'Edifici Central',
      floorLabel: 'Planta',
      toggleSidebar: 'Alternar filtres (Ctrl+B)',
      hideSidebar: 'Amagar barra lateral',
      showSidebar: 'Mostrar barra lateral'
    },
    sidebar: {
      title: 'Filtres',
      weekSection: 'Setmana lectiva',
      selectWeekInCalendar: 'Indicar setmana al calendari',
      clearWeek: 'Treure setmana',
      allWeeks: 'Totes',
      weekFromTo: (w, r, m, f) => `Setmana ${w} (${r}): de dilluns ${m} a divendres ${f}`,
      allWeeksDesc: 'Horaris aplicables a tot el semestre',
      weekHint: 'Selecciona la setmana al calendari per veure l\'horari complet de Dilluns a Divendres',
      degreeSection: 'Grau',
      allDegrees: 'Tots els graus',
      allDegreesBadge: 'Tots',
      degreeHint: 'Titulació acadèmica obtinguda del sistema',
      courseSection: 'Curs',
      allCourses: 'Tots els cursos',
      allCoursesBadge: 'Tots',
      courseHint: 'Any o nivell lectiu (1r a 5è)',
      subjectSection: 'Assignatura',
      allSubjects: 'Totes les assignatures',
      allSubjectsBadge: 'Totes',
      subjectHint: 'Matèria corresponent segons titulació',
      groupSection: 'Grup',
      allGroupsBadge: 'Tots',
      groupNumberLabel: 'Número identificador',
      groupPlaceholder: 'Ex: 450',
      groupHint: 'Introdueix el número del grup (ex. 450)',
      clearFilters: 'Netejar filtres',
      applyFilters: 'Aplicar filtres',
      footerEndpoint: 'Categories connectades a l\'endpoint /api/filters (mode base).'
    },
    floorSelector: {
      previousFloor: 'Planta anterior',
      nextFloor: 'Planta següent',
      floorPill: (num) => `Planta ${num}`,
      floorDescriptions: {
        0: 'Planta 0 — Blocs Q1-Q6, Ala Central (QC) & Ala Sud (QP)',
        1: 'Planta 1 — Blocs Q1-Q6 i Ala Central (QC)',
        2: 'Planta 2 — Blocs Q5-Q6 i Ala Central (QC)',
        3: 'Planta 3 — Ala Central Superior (QC)'
      },
      alertText: (count) => `${count} ${count === 1 ? 'aula' : 'aules'}`,
      alertTooltip: (count, num) => `${count} ${count === 1 ? 'aula que compleix' : 'aules que compleixen'} el filtre a Planta ${num}`
    },
    map: {
      panHint: 'Roda per a zoom • Arrossega per moure\'t pel plànol',
      zoomIn: 'Apropar mapa (+)',
      zoomOut: 'Allunyar mapa (-)',
      resetZoom: 'Restablir zoom al 100%',
      fitPlan: 'Ajustar i centrar plànol',
      roomAria: (name) => `Aula ${name}`
    },
    schedule: {
      roomBadge: (room) => `Aula ${room}`,
      title: 'Horari Setmanal',
      subtitle: (week, range) => week ? `Setmana ${week} (${range}) • Dilluns a Divendres` : 'Dilluns a Divendres • 08:30 a 21:00',
      activeFilter: 'Filtre actiu (franges coincidents destacades)',
      close: 'Tancar horari (Esc)',
      loading: (room) => `Carregant horari setmanal de l'aula ${room}...`,
      timeColumn: 'Hora',
      pauseTime: '14:30 – 15:00',
      pauseText: 'PAUSA / DINAR',
      codePrefix: 'Codi',
      combinedHours: (h) => `${h}h combinades`,
      days: {
        L: 'Dilluns',
        M: 'Dimarts',
        X: 'Dimecres',
        J: 'Dijous',
        V: 'Divendres'
      }
    },
    degrees: {
      'ing-informatica': { name: 'Grau en Enginyeria Informàtica', short: 'Eng. Inf.' },
      'ia': { name: 'Grau en Intel·ligència Artificial', short: 'IA' },
      'ciberseguridad': { name: 'Grau en Ciberseguretat', short: 'Ciber' },
      'ciencia-datos': { name: 'Grau en Ciència i Enginyeria de Dades', short: 'Dades' },
      'ing-software': { name: 'Grau en Enginyeria del Software', short: 'Software' }
    },
    courses: {
      '1': { name: '1r Curs', short: '1r' },
      '2': { name: '2n Curs', short: '2n' },
      '3': { name: '3r Curs', short: '3r' },
      '4': { name: '4t Curs', short: '4t' },
      '5': { name: '5è Curs', short: '5è' }
    },
    subjects: {
      '240011': 'Física I',
      '240012': 'Càlcul I',
      '240013': 'Programació I',
      '240021': 'Àlgebra Lineal',
      '240022': 'Estructures de Dades',
      '240023': 'Sistemes Operatius',
      '240031': 'Bases de Dades',
      '240032': 'Xarxes de Computadors',
      '240041': 'Enginyeria del Software',
      '240051': 'Intel·ligència Artificial',
      '240052': 'Aprenentatge Automàtic',
      '240061': 'Ciberseguretat Avançada'
    }
  },

  en: {
    app: {
      brandTitle: 'Central Building',
      floorLabel: 'Floor',
      toggleSidebar: 'Toggle filters (Ctrl+B)',
      hideSidebar: 'Hide sidebar',
      showSidebar: 'Show sidebar'
    },
    sidebar: {
      title: 'Filters',
      weekSection: 'Teaching week',
      selectWeekInCalendar: 'Select week in calendar',
      clearWeek: 'Clear week',
      allWeeks: 'All',
      weekFromTo: (w, r, m, f) => `Week ${w} (${r}): from Monday ${m} to Friday ${f}`,
      allWeeksDesc: 'Schedules applicable to the entire semester',
      weekHint: 'Select the week in the calendar to view the full Monday to Friday schedule',
      degreeSection: 'Degree',
      allDegrees: 'All degrees',
      allDegreesBadge: 'All',
      degreeHint: 'Academic degree retrieved from system',
      courseSection: 'Year',
      allCourses: 'All years',
      allCoursesBadge: 'All',
      courseHint: 'Academic year or level (1st to 5th)',
      subjectSection: 'Subject',
      allSubjects: 'All subjects',
      allSubjectsBadge: 'All',
      subjectHint: 'Course corresponding to degree',
      groupSection: 'Group',
      allGroupsBadge: 'All',
      groupNumberLabel: 'Identifier number',
      groupPlaceholder: 'e.g. 450',
      groupHint: 'Enter the group number (e.g. 450)',
      clearFilters: 'Clear filters',
      applyFilters: 'Apply filters',
      footerEndpoint: 'Categories connected to /api/filters endpoint (fallback mode).'
    },
    floorSelector: {
      previousFloor: 'Previous floor',
      nextFloor: 'Next floor',
      floorPill: (num) => `Floor ${num}`,
      floorDescriptions: {
        0: 'Floor 0 — Blocks Q1-Q6, Central Wing (QC) & South Wing (QP)',
        1: 'Floor 1 — Blocks Q1-Q6 and Central Wing (QC)',
        2: 'Floor 2 — Blocks Q5-Q6 and Central Wing (QC)',
        3: 'Floor 3 — Upper Central Wing (QC)'
      },
      alertText: (count) => `${count} ${count === 1 ? 'room' : 'rooms'}`,
      alertTooltip: (count, num) => `${count} matching ${count === 1 ? 'room' : 'rooms'} on Floor ${num}`
    },
    map: {
      panHint: 'Scroll to zoom • Drag to pan across floor plan',
      zoomIn: 'Zoom in (+)',
      zoomOut: 'Zoom out (-)',
      resetZoom: 'Reset zoom to 100%',
      fitPlan: 'Fit and center floor plan',
      roomAria: (name) => `Room ${name}`
    },
    schedule: {
      roomBadge: (room) => `Room ${room}`,
      title: 'Weekly Schedule',
      subtitle: (week, range) => week ? `Week ${week} (${range}) • Monday to Friday` : 'Monday to Friday • 08:30 to 21:00',
      activeFilter: 'Active filter (matching slots highlighted)',
      close: 'Close schedule (Esc)',
      loading: (room) => `Loading weekly schedule for room ${room}...`,
      timeColumn: 'Time',
      pauseTime: '14:30 – 15:00',
      pauseText: 'LUNCH BREAK',
      codePrefix: 'Code',
      combinedHours: (h) => `${h}h combined`,
      days: {
        L: 'Monday',
        M: 'Tuesday',
        X: 'Wednesday',
        J: 'Thursday',
        V: 'Friday'
      }
    },
    degrees: {
      'ing-informatica': { name: 'Bachelor in Computer Engineering', short: 'Comp. Eng.' },
      'ia': { name: 'Bachelor in Artificial Intelligence', short: 'AI' },
      'ciberseguridad': { name: 'Bachelor in Cybersecurity', short: 'Cyber' },
      'ciencia-datos': { name: 'Bachelor in Data Science and Engineering', short: 'Data' },
      'ing-software': { name: 'Bachelor in Software Engineering', short: 'Software' }
    },
    courses: {
      '1': { name: '1st Year', short: '1st' },
      '2': { name: '2nd Year', short: '2nd' },
      '3': { name: '3rd Year', short: '3rd' },
      '4': { name: '4th Year', short: '4th' },
      '5': { name: '5th Year', short: '5th' }
    },
    subjects: {
      '240011': 'Physics I',
      '240012': 'Calculus I',
      '240013': 'Programming I',
      '240021': 'Linear Algebra',
      '240022': 'Data Structures',
      '240023': 'Operating Systems',
      '240031': 'Databases',
      '240032': 'Computer Networks',
      '240041': 'Software Engineering',
      '240051': 'Artificial Intelligence',
      '240052': 'Machine Learning',
      '240061': 'Advanced Cybersecurity'
    }
  }
};

/**
 * Obtiene el nombre traducido de una asignatura según su código o nombre original.
 */
export function getTranslatedSubjectName(codi, fallbackName, lang = 'es') {
  const dict = TRANSLATIONS[lang]?.subjects || TRANSLATIONS.es.subjects;
  if (codi && dict[codi]) {
    return dict[codi];
  }
  return fallbackName || '';
}

/**
 * Obtiene el nombre y abreviatura de un grado según idioma.
 */
export function getTranslatedDegree(id, fallbackName, lang = 'es') {
  const dict = TRANSLATIONS[lang]?.degrees || TRANSLATIONS.es.degrees;
  if (id && dict[id]) {
    return dict[id];
  }
  return { name: fallbackName || '', short: fallbackName?.substring(0, 8) || '' };
}
