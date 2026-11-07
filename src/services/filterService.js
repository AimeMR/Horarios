/**
 * SERVICIO DE CATEGORÍAS Y FILTROS ACADÉMICOS
 * 
 * Este servicio está preparado para consumir el endpoint del backend cuando esté listo.
 * Mientras tanto, si el endpoint devuelve 404 o no responde, utiliza datos estructurados
 * de respaldo (fallback) sin romper la interfaz de usuario.
 */

export const FILTERS_API_ENDPOINT = import.meta.env.VITE_API_FILTERS_URL || '/api/filters';

/**
 * Estructura de datos por defecto (Mock Fallback)
 * Cumple con el formato JSON esperado del backend.
 */
export const DEFAULT_FILTER_DATA = {
  grados: [
    { id: 'ing-informatica', nombre: 'Grado en Ingeniería Informática', abreviatura: 'Ing. Inf.' },
    { id: 'ia', nombre: 'Grado en Inteligencia Artificial', abreviatura: 'IA' },
    { id: 'ciberseguridad', nombre: 'Grado en Ciberseguridad', abreviatura: 'Ciber' },
    { id: 'ciencia-datos', nombre: 'Grado en Ciencia e Ingeniería de Datos', abreviatura: 'Datos' },
    { id: 'ing-software', nombre: 'Grado en Ingeniería del Software', abreviatura: 'Software' }
  ],
  asignaturas: [
    { id: 'prog1', nombre: 'Programación I', gradoId: 'ing-informatica', curso: '1' },
    { id: 'eda', nombre: 'Estructuras de Datos y Algoritmos', gradoId: 'ing-informatica', curso: '2' },
    { id: 'algebra', nombre: 'Álgebra Lineal', gradoId: 'ing-informatica', curso: '1' },
    { id: 'calculo', nombre: 'Cálculo', gradoId: 'ing-informatica', curso: '1' },
    { id: 'so', nombre: 'Sistemas Operativos', gradoId: 'ing-informatica', curso: '2' },
    { id: 'redes', nombre: 'Redes de Computadores', gradoId: 'ing-informatica', curso: '3' },
    { id: 'bd', nombre: 'Bases de Datos', gradoId: 'ing-informatica', curso: '2' },
    { id: 'ia', nombre: 'Inteligencia Artificial', gradoId: 'ia', curso: '3' },
    { id: 'ac', nombre: 'Arquitectura de Computadores', gradoId: 'ing-informatica', curso: '2' },
    { id: 'is', nombre: 'Ingeniería del Software', gradoId: 'ing-software', curso: '3' },
    { id: 'seguridad', nombre: 'Seguridad en Sistemas', gradoId: 'ciberseguridad', curso: '4' },
    { id: 'tfg', nombre: 'Trabajo Fin de Grado', gradoId: 'ing-informatica', curso: '5' }
  ],
  grupos: [
    { id: 'g1-m', nombre: 'Grupo 1 (Mañana)', abreviatura: 'G1-M' },
    { id: 'g2-m', nombre: 'Grupo 2 (Mañana)', abreviatura: 'G2-M' },
    { id: 'g3-t', nombre: 'Grupo 3 (Tarde)', abreviatura: 'G3-T' },
    { id: 'g4-t', nombre: 'Grupo 4 (Tarde)', abreviatura: 'G4-T' },
    { id: 'ga', nombre: 'Grupo A', abreviatura: 'GA' },
    { id: 'gb', nombre: 'Grupo B', abreviatura: 'GB' }
  ]
};

/**
 * Normaliza cualquier variante de nombres de campo (inglés/español) que pueda devolver el backend.
 */
export function normalizeFilterCategories(rawJson) {
  if (!rawJson || typeof rawJson !== 'object') {
    return normalizeFilterCategories(DEFAULT_FILTER_DATA);
  }

  // 1. Grados (grados o degrees)
  const rawDegrees = rawJson.grados || rawJson.degrees || DEFAULT_FILTER_DATA.grados;
  const degrees = Array.isArray(rawDegrees)
    ? rawDegrees.map(item => ({
        id: String(item.id || item.codigo || item.code || ''),
        name: String(item.nombre || item.name || item.titulo || ''),
        short: String(item.abreviatura || item.short || item.siglas || item.nombre || item.name || '').substring(0, 10)
      }))
    : [];

  // 2. Asignaturas (asignaturas o subjects)
  const rawSubjects = rawJson.asignaturas || rawJson.subjects || DEFAULT_FILTER_DATA.asignaturas;
  const subjects = Array.isArray(rawSubjects)
    ? rawSubjects.map(item => ({
        id: String(item.id || item.codigo || item.code || ''),
        name: String(item.nombre || item.name || item.titulo || ''),
        gradoId: item.gradoId || item.degreeId || null,
        curso: String(item.curso || item.course || '')
      }))
    : [];

  // 3. Grupos (grupos o groups)
  const rawGroups = rawJson.grupos || rawJson.groups || DEFAULT_FILTER_DATA.grupos;
  const groups = Array.isArray(rawGroups)
    ? rawGroups.map(item => ({
        id: String(item.id || item.codigo || item.code || ''),
        name: String(item.nombre || item.name || ''),
        short: String(item.abreviatura || item.short || item.siglas || item.nombre || item.name || '').substring(0, 8)
      }))
    : [];

  return { degrees, subjects, groups };
}

/**
 * Petición asíncrona al endpoint con manejo de errores y fallback transparente.
 */
export async function fetchFilterCategories(customUrl = null) {
  const url = customUrl || FILTERS_API_ENDPOINT;

  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      }
    });

    if (!response.ok) {
      throw new Error(`Endpoint HTTP status: ${response.status}`);
    }

    const data = await response.json();
    return {
      data: normalizeFilterCategories(data),
      isFallback: false,
      error: null
    };
  } catch (error) {
    // Si el endpoint aún no está listo o da error de red/404, usamos los datos de respaldo
    console.info(`[FilterService] Endpoint "${url}" no disponible (${error.message}). Utilizando estructura de datos base.`);
    return {
      data: normalizeFilterCategories(DEFAULT_FILTER_DATA),
      isFallback: true,
      error: error.message
    };
  }
}
