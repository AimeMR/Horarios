/**
 * SERVICIO DE COMUNICACIÓN CON IA LOCAL
 * Soporta llamadas a servidores de IA locales (Ollama, LM Studio, LocalAI, vLLM, etc.)
 * utilizando una API Key de autorización y formato compatible con OpenAI (/v1/chat/completions)
 * o nativo de Ollama (/api/chat).
 */

const STORAGE_KEY_API_KEY = 'local_ai_api_key';
const STORAGE_KEY_URL = 'local_ai_url';
const STORAGE_KEY_MODEL = 'local_ai_model';

export const DEFAULT_AI_CONFIG = {
  apiKey: (typeof import.meta !== 'undefined' && (import.meta.env?.VITE_LOCAL_AI_KEY || import.meta.env?.VITE_AI_API_KEY)) || '',
  url: (typeof import.meta !== 'undefined' && (import.meta.env?.VITE_LOCAL_AI_URL || import.meta.env?.VITE_AI_URL)) || 'http://localhost:11434/v1/chat/completions',
  model: (typeof import.meta !== 'undefined' && (import.meta.env?.VITE_LOCAL_AI_MODEL || import.meta.env?.VITE_AI_MODEL)) || 'llama3',
};

/**
 * Obtiene la configuración de la IA local desde localStorage o variables de entorno.
 */
export function getAiConfig() {
  try {
    const apiKey = localStorage.getItem(STORAGE_KEY_API_KEY) ?? DEFAULT_AI_CONFIG.apiKey;
    const url = localStorage.getItem(STORAGE_KEY_URL) ?? DEFAULT_AI_CONFIG.url;
    const model = localStorage.getItem(STORAGE_KEY_MODEL) ?? DEFAULT_AI_CONFIG.model;
    return { apiKey, url, model };
  } catch (_) {
    return { ...DEFAULT_AI_CONFIG };
  }
}

/**
 * Guarda la configuración de la IA local en localStorage.
 */
export function saveAiConfig({ apiKey, url, model }) {
  try {
    if (apiKey !== undefined) localStorage.setItem(STORAGE_KEY_API_KEY, apiKey);
    if (url !== undefined) localStorage.setItem(STORAGE_KEY_URL, url);
    if (model !== undefined) localStorage.setItem(STORAGE_KEY_MODEL, model);
  } catch (err) {
    console.warn('No se pudo guardar la configuración de IA en localStorage:', err);
  }
  return getAiConfig();
}

/**
 * Construye el prompt del sistema contextualizando al modelo en el edificio y los horarios universitarios.
 */
function buildSystemPrompt(lang = 'es') {
  const langGuides = {
    es: 'Responde siempre en ESPAÑOL de manera clara, concisa, profesional y estructurada.',
    ca: 'Respon sempre en CATALÀ de manera clara, concisa, professional i estructurada.',
    en: 'Always reply in ENGLISH in a clear, concise, professional and structured manner.'
  };

  return `Eres el asistente virtual inteligente de la Facultad (Edificio Central).
${langGuides[lang] || langGuides.es}

CONTEXTO DEL EDIFICIO Y MAPA:
- Consta de 4 plantas: Planta 0, Planta 1, Planta 2 y Planta 3.
  * Planta 0: Bloques Q1 a Q6, Ala Central (QC) y Ala Sur (QP).
  * Planta 1: Bloques Q1 a Q6 y Ala Central (QC).
  * Planta 2: Bloques Q5 y Q6 y Ala Central (QC).
  * Planta 3: Ala Central Superior (QC).
- Franjas horarias lectivas (Lunes a Viernes):
  * Turno de Mañana: 08:30 a 14:30 (intervalos de 1 hora).
  * Franja de Pausa / Almuerzo: 14:30 a 15:00.
  * Turno de Tarde: 15:00 a 21:00 (intervalos de 1 hora).
- Aula piloto de prueba: Q4/0003 (situada en el Bloque Q4, Planta 0), con sesiones semanales de asignaturas como Cálculo I, Física I, Programación I y Álgebra Lineal.
- Grados universitarios: Grado en Ingeniería Informática, Grado en Inteligencia Artificial, Grado en Ciberseguridad, Grado en Ciencia e Ingeniería de Datos, Grado en Ingeniería del Software.

Sé educado, breve, resolutivo y proporciona información precisa cuando te pregunten sobre ubicaciones, plantas o franjas horarias.`;
}

/**
 * Envía el mensaje del usuario a la IA local mediante su API Key y endpoint configurado.
 *
 * @param {string} prompt - Mensaje actual del usuario.
 * @param {Array} conversationHistory - Historial de mensajes anteriores [{ sender: 'user'|'assistant', text: string }].
 * @param {Object} options - { lang: 'es'|'ca'|'en', config: { apiKey, url, model } }
 * @returns {Promise<{ success: boolean, text?: string, error?: string, isConnectionError?: boolean }>}
 */
export async function sendMessageToLocalAI(prompt, conversationHistory = [], options = {}) {
  const { lang = 'es', config: customConfig = null } = options;
  const config = customConfig || getAiConfig();
  const { apiKey, url, model } = config;

  // Normalizamos el historial previo (máximo las últimas 6 intervenciones para no saturar tokens de contexto local)
  const historySlice = (conversationHistory || [])
    .filter(m => m.text && !m.isLoading && !m.isError)
    .slice(-6)
    .map(m => ({
      role: m.sender === 'user' ? 'user' : 'assistant',
      content: m.text
    }));

  const messages = [
    { role: 'system', content: buildSystemPrompt(lang) },
    ...historySlice,
    { role: 'user', content: prompt }
  ];

  // Configuración de cabeceras de autorización HTTP con la API Key
  const headers = {
    'Content-Type': 'application/json'
  };

  const cleanKey = (apiKey || '').trim();
  if (cleanKey) {
    headers['Authorization'] = `Bearer ${cleanKey}`;
    headers['api-key'] = cleanKey;
    headers['X-API-Key'] = cleanKey;
  }

  // Preparación del cuerpo según el endpoint local
  let requestBody;
  const isOllamaChat = url.includes('/api/chat');
  const isOllamaGenerate = url.includes('/api/generate');

  if (isOllamaChat) {
    requestBody = {
      model: model || 'llama3',
      messages,
      stream: false
    };
  } else if (isOllamaGenerate) {
    requestBody = {
      model: model || 'llama3',
      prompt: `${buildSystemPrompt(lang)}\n\nUsuario: ${prompt}\nAsistente:`,
      stream: false
    };
  } else {
    // Formato estándar OpenAI /v1/chat/completions (compatible con LM Studio, LocalAI, vLLM, Ollama v1)
    requestBody = {
      model: model || 'llama3',
      messages,
      temperature: 0.7,
      max_tokens: 800
    };
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 35000); // 35s timeout para LLMs locales

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(requestBody),
      signal: controller.signal
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      let errorDetails = '';
      try {
        const errorJson = await response.json();
        errorDetails = errorJson.error?.message || errorJson.error || JSON.stringify(errorJson);
      } catch (_) {
        errorDetails = await response.text();
      }

      return {
        success: false,
        status: response.status,
        error: errorDetails || `Error HTTP ${response.status}: ${response.statusText}`,
        url,
        hasApiKey: Boolean(cleanKey)
      };
    }

    const data = await response.json();
    let reply = '';

    if (data.choices && data.choices[0]) {
      reply = data.choices[0].message?.content || data.choices[0].text || '';
    } else if (data.message && data.message.content) {
      reply = data.message.content;
    } else if (data.response) {
      reply = data.response;
    } else if (typeof data === 'string') {
      reply = data;
    } else {
      reply = JSON.stringify(data);
    }

    return {
      success: true,
      text: (reply || '').trim(),
      model: data.model || model,
      url
    };
  } catch (error) {
    clearTimeout(timeoutId);

    const isAbort = error.name === 'AbortError';
    const errorMsg = isAbort
      ? 'La petición a la IA local superó el tiempo de espera (35s).'
      : error.message || 'Error desconocido de red al contactar con la IA local.';

    return {
      success: false,
      isConnectionError: true,
      error: errorMsg,
      url,
      hasApiKey: Boolean(cleanKey)
    };
  }
}

/**
 * Generador de respuesta simulada para pruebas rápidas sin necesidad de servidor local activo.
 */
export function generateSimulatedResponse(prompt, lang = 'es') {
  const p = (prompt || '').toLowerCase();

  const answers = {
    es: {
      q4: 'El aula **Q4/0003** se encuentra en la **Planta 0 (Bloque Q4)**. Cuenta con horarios lectivos en el turno de mañana (de 08:30 a 14:30) y de tarde (de 15:00 a 21:00) con clases de asignaturas como *Cálculo I*, *Física I* y *Programación I*. Puedes hacer clic en dicha aula en el plano interactivo para abrir su parrilla semanal completa estilo Excel.',
      floor0: 'La **Planta 0** es la planta principal de acceso. Contiene los Bloques **Q1, Q2, Q3, Q4, Q5 y Q6**, además del **Ala Central (QC)** y el **Ala Sur (QP)** con laboratorios y aules docents.',
      pause: 'La franja de **Pausa / Almuerzo** se realiza todos los días de **14:30 a 15:00**. Durante esta media hora no hay clases lectivas programadas para permitir el descanso y la comida de estudiantes y profesores.',
      default: (userText) => `He recibido tu consulta: *"Estas preguntando sobre ${userText.slice(0, 40)}..."*.\n\nComo asistente de la Facultad y de este visualizador, puedo ayudarte a localizar aulas, consultar franjas horarias y conocer la distribución de los bloques Q1 a Q6 en las 4 plantas.`
    },
    ca: {
      q4: 'L\'aula **Q4/0003** està situada a la **Planta 0 (Bloc Q4)**. Té horaris lectius en el torn de matí (de 08:30 a 14:30) i de tarda (de 15:00 a 21:00) amb classes d\'assignatures com *Càlcul I*, *Física I* i *Programació I*. Pots fer clic a l\'aula al mapa interactiu per obrir la graella setmanal estil Excel.',
      floor0: 'La **Planta 0** és la planta principal d\'accés. Conté els Blocs **Q1, Q2, Q3, Q4, Q5 i Q6**, a més de l\'**Ala Central (QC)** i l\'**Ala Sud (QP)** amb laboratoris i aules docents.',
      pause: 'La franja de **Pausa / Dinar** té lloc cada dia de **14:30 a 15:00**. Durant aquesta mitja hora no hi ha classes lectives programades.',
      default: (userText) => `He rebut la teva consulta: *"Estàs consultant sobre ${userText.slice(0, 40)}..."*.\n\nCom a assistent de la Facultat, et puc ajudar a trobar aules, comprovar horaris i revisar la distribució dels blocs Q1 a Q6 a les 4 plantes.`
    },
    en: {
      q4: 'Room **Q4/0003** is located on **Floor 0 (Block Q4)**. It has scheduled classes during morning sessions (08:30 to 14:30) and afternoon sessions (15:00 to 21:00) for courses such as *Calculus I*, *Physics I*, and *Programming I*. You can click on the classroom on the interactive map to view its full weekly Excel-style grid.',
      floor0: '**Floor 0** is the main ground entrance floor. It hosts Blocks **Q1 through Q6**, as well as the **Central Wing (QC)** and **South Wing (QP)** with teaching labs and lecture rooms.',
      pause: 'The **Lunch / Break** slot runs every day from **14:30 to 15:00**. No teaching sessions are scheduled during this half-hour window.',
      default: (userText) => `I received your message: *"Inquiring about ${userText.slice(0, 40)}..."*.\n\nAs your Faculty assistant, I can help you find classrooms, inspect timetable slots, and navigate the Q1-Q6 blocks across all 4 floors.`
    }
  };

  const dict = answers[lang] || answers.es;

  if (p.includes('q4') || p.includes('0003') || p.includes('aula')) {
    return dict.q4;
  }
  if (p.includes('planta 0') || p.includes('piso 0') || p.includes('floor 0') || p.includes('bloc') || p.includes('bloque')) {
    return dict.floor0;
  }
  if (p.includes('pausa') || p.includes('14:30') || p.includes('almuerzo') || p.includes('dinar') || p.includes('lunch') || p.includes('break')) {
    return dict.pause;
  }

  return dict.default(prompt);
}
