# Especificación del Endpoint para Filtros

El front-end está preparado para recibir dinámicamente las categorías de **Grado**, **Asignatura** y **Grupo** a través de una llamada HTTP `GET`.

## Configuración del Endpoint

* **Ruta por defecto:** `/api/filters`
* **Variable de entorno opcional (`.env`):** `VITE_API_FILTERS_URL=https://tu-servidor.com/api/filters`
* **Método:** `GET`
* **Content-Type:** `application/json`

## Estructura del JSON esperado

El front-end admite tanto la nomenclatura en español como en inglés para mayor compatibilidad:

```json
{
  "grados": [
    {
      "id": "ing-informatica",
      "nombre": "Grado en Ingeniería Informática",
      "abreviatura": "Ing. Inf."
    },
    {
      "id": "ia",
      "nombre": "Grado en Inteligencia Artificial",
      "abreviatura": "IA"
    }
  ],
  "asignaturas": [
    {
      "id": "prog1",
      "nombre": "Programación I",
      "gradoId": "ing-informatica",
      "curso": "1"
    },
    {
      "id": "eda",
      "nombre": "Estructuras de Datos y Algoritmos",
      "gradoId": "ing-informatica",
      "curso": "2"
    }
  ],
  "grupos": [
    {
      "id": "g1-m",
      "nombre": "Grupo 1 (Mañana)",
      "abreviatura": "G1-M"
    },
    {
      "id": "g2-m",
      "nombre": "Grupo 2 (Mañana)",
      "abreviatura": "G2-M"
    }
  ]
}
```

### Campos soportados:

1. **`grados`** (o `degrees`):
   * `id` (o `codigo`): Identificador único (string).
   * `nombre` (o `name`, `titulo`): Nombre completo del grado.
   * `abreviatura` (o `short`, `siglas`): Texto para el badge (máx. 10 caracteres).

2. **`asignaturas`** (o `subjects`):
   * `id` (o `codigo`): Identificador único (string).
   * `nombre` (o `name`, `titulo`): Nombre de la asignatura.
   * `gradoId` *(opcional)*: ID del grado al que pertenece para filtrado contextual.
   * `curso` *(opcional)*: Nivel (`1`, `2`, `3`, `4`, `5`).

3. **`grupos`** (o `groups`):
   * `id` (o `codigo`): Identificador del grupo (string).
   * `nombre` (o `name`): Nombre descriptivo (ej: `Grupo 1 (Mañana)`).
   * `abreviatura` (o `short`, `siglas`): Texto para el badge (ej: `G1-M`).

## Comportamiento con Fallback

Si el endpoint devuelve error (404, 500 o sin conexión), la aplicación entra en modo de respaldo (*fallback*) utilizando los datos base predeterminados sin bloquear al usuario ni interrumpir la navegación.
