# Carpeta de Mapas SVG (Floorplans)

Esta carpeta contiene los planos de los pisos en formato SVG.

## Nomenclatura de archivos esperada

La aplicación busca y carga los siguientes archivos por defecto:
- `piso-1.svg` — Plano correspondiente al **Piso 1** (o Planta Baja).
- `piso-2.svg` — Plano correspondiente al **Piso 2** (o Planta 1).
- `piso-3.svg` — Plano correspondiente al **Piso 3** (o Planta 2).

## Recomendaciones para tus mapas SVG

1. **Atributo `viewBox`**: Asegúrate de que tus SVGs tengan el atributo `viewBox="0 0 900 600"` (o la proporción de tu edificio) y `width="100%" height="100%"`.
2. **Identificadores para aulas y espacios**:
   Si quieres que luego al filtrar en React se iluminen o seleccionen automáticamente, asigna a cada aula o espacio un `id` o `data-room`:
   ```xml
   <g class="room" id="room-101" data-room="Aula 101">
      <rect ... />
      <text>Aula 101</text>
   </g>
   ```
3. **Escalabilidad**: Al ser archivos vectoriales SVG puros, se verán nítidos en cualquier resolución o pantalla retina.

