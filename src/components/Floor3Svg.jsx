import React from 'react';

export default function Floor3Svg({ selectedRoom, onSelectRoom, matchingRooms = [] }) {
  const matchingSet = React.useMemo(() => new Set(matchingRooms || []), [matchingRooms]);

  const renderRoom = (id, name, x, y, width, height, isSmall = false) => {
    const isSelected = selectedRoom === name;
    const isMatch = matchingSet.has(name);
    const centerX = x + width / 2;
    const centerY = y + height / 2;

    return (
      <g
        key={id}
        className={`room ${isSelected ? 'is-selected' : ''} ${isMatch ? 'is-filter-match' : ''}`}
        id={`room-${id}`}
        data-room={name}
        tabIndex={0}
        role="button"
        aria-label={`Aula ${name}`}
        onClick={(e) => {
          e.stopPropagation();
          onSelectRoom(name, e);
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            e.stopPropagation();
            onSelectRoom(name, e);
          }
        }}
      >
        <title>{`Aula ${name}`}</title>
        <rect x={x} y={y} width={width} height={height} className="wall room-rect" />
        <text
          x={centerX}
          y={centerY}
          className={isSmall ? 'room-label-sm' : 'room-label'}
        >
          {name}
        </text>
      </g>
    );
  };

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 3500 2500"
      width="3500"
      height="2500"
      className="floor-svg-canvas"
    >
      <defs>
        <style>{`
          .bg { fill: #FFFFFF; }
          .wall { fill: #FFFFFF; stroke: #111827; stroke-width: 4.5; stroke-linejoin: miter; stroke-linecap: square; }
          .grey-wing { fill: #CBD5E1; stroke: #111827; stroke-width: 4.5; stroke-linejoin: miter; stroke-linecap: square; }
          .room-label { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 24px; font-weight: 700; fill: #111827; text-anchor: middle; dominant-baseline: central; letter-spacing: 0.5px; pointer-events: none; user-select: none; }
          .room-label-sm { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 19px; font-weight: 700; fill: #111827; text-anchor: middle; dominant-baseline: central; letter-spacing: 0.3px; pointer-events: none; user-select: none; }
          .room { cursor: pointer; outline: none; }
          .room .room-rect { cursor: pointer; transition: fill 0.15s ease, stroke 0.15s ease; }
          .room:hover .room-rect { fill: #E0F2FE !important; stroke: #0284C7 !important; stroke-width: 6 !important; }
          .room:hover text { fill: #0284C7 !important; }
          .room.is-selected .room-rect { fill: #BAE6FD !important; stroke: #0369A1 !important; stroke-width: 7 !important; }
          .room.is-selected text { fill: #0369A1 !important; font-weight: 800 !important; }
          .room.is-filter-match .room-rect { fill: #2563EB !important; stroke: #1D4ED8 !important; stroke-width: 6 !important; filter: drop-shadow(0 0 10px rgba(37, 99, 235, 0.45)); }
          .room.is-filter-match text { fill: #FFFFFF !important; font-weight: 800 !important; }
          .room.is-filter-match:hover .room-rect { fill: #1D4ED8 !important; stroke: #1E40AF !important; stroke-width: 7 !important; }
          .room.is-filter-match.is-selected .room-rect { fill: #1E40AF !important; stroke: #172554 !important; stroke-width: 8 !important; }
        `}</style>
      </defs>

      {/* Fondo */}
      <rect width="3500" height="2500" className="bg" />

      {/* ==================== BLOQUES GRISES (ALA OESTE Y ALAS PRINCIPALES) ==================== */}
      {/* Columna / Pasillo vertical conector */}
      <rect x="1200" y="120" width="280" height="1540" className="grey-wing" />

      {/* Ala 4 (Superior) */}
      <rect x="1480" y="120" width="940" height="260" className="grey-wing" />

      {/* Ala 3 */}
      <rect x="1480" y="470" width="940" height="260" className="grey-wing" />

      {/* Ala Este Superior */}
      <rect x="2420" y="730" width="960" height="260" className="grey-wing" />

      {/* Ala 2 */}
      <rect x="1480" y="920" width="940" height="260" className="grey-wing" />

      {/* Ala Este Inferior */}
      <rect x="2420" y="1180" width="960" height="260" className="grey-wing" />

      {/* Ala 1 */}
      <rect x="1480" y="1370" width="940" height="260" className="grey-wing" />

      {/* ==================== ALA SUR / PASILLO PRINCIPAL QC ==================== */}
      <g id="block-qc">
        {/* Contenedor exterior del corredor QC */}
        <rect x="150" y="1660" width="3230" height="600" className="wall" />

        {/* QC/3088 (Extremo Oeste - Sala de altura completa) */}
        {renderRoom('qc-3088', 'QC/3088', 150, 1660, 350, 600)}

        {/* QC/3078 (Pared Sur Oeste) */}
        {renderRoom('qc-3078', 'QC/3078', 670, 2060, 200, 200)}

        {/* QC/3042 (Pared Norte Centro-Oeste) */}
        {renderRoom('qc-3042', 'QC/3042', 1160, 1660, 200, 200)}

        {/* QC/3010 (Pared Norte en el nexo vertical) */}
        {renderRoom('qc-3010', 'QC/3010', 1480, 1660, 200, 200)}

        {/* QC/3012 (Pared Sur opuesta a QC/3010) */}
        {renderRoom('qc-3012', 'QC/3012', 1480, 2060, 200, 200)}

        {/* QC/3047 (Pared Norte Centro-Este) */}
        {renderRoom('qc-3047', 'QC/3047', 2220, 1660, 200, 200)}

        {/* QC/3049 (Pared Sur Centro-Este) */}
        {renderRoom('qc-3049', 'QC/3049', 2320, 2060, 200, 200)}
      </g>
    </svg>
  );
}

