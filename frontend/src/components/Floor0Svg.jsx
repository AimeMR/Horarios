import React from 'react';

export default function Floor0Svg({ selectedRoom, onSelectRoom, matchingRooms = [] }) {
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
          .room-label { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 23px; font-weight: 700; fill: #111827; text-anchor: middle; dominant-baseline: central; letter-spacing: 0.5px; pointer-events: none; user-select: none; }
          .room-label-sm { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 16.5px; font-weight: 700; fill: #111827; text-anchor: middle; dominant-baseline: central; letter-spacing: 0.3px; pointer-events: none; user-select: none; }
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

      {/* ==================== COLUMNA / PASILLO VERTICAL OESTE ==================== */}
      <rect x="1150" y="100" width="280" height="1590" className="wall" />

      {/* ==================== BLOQUE Q4 ==================== */}
      <g id="block-q4">
        {renderRoom('q4-0003', 'Q4/0003', 1430, 100, 320, 200)}
        {renderRoom('q4-0007', 'Q4/0007', 1750, 100, 325, 200)}
        {renderRoom('q4-0011', 'Q4/0011', 2075, 100, 325, 200)}
        {/* Pasillo inferior Q4 */}
        <rect x="1430" y="300" width="970" height="60" className="wall" />
      </g>

      {/* ==================== BLOQUE Q3 ==================== */}
      <g id="block-q3">
        {renderRoom('q3-0003', 'Q3/0003', 1430, 480, 270, 200)}
        {renderRoom('q3-0007', 'Q3/0007', 1700, 480, 420, 200)}
        {renderRoom('q3-0011', 'Q3/0011', 2120, 480, 280, 200)}
        {/* Pasillo inferior Q3 */}
        <rect x="1430" y="680" width="970" height="60" className="wall" />
      </g>

      {/* ==================== BLOQUE Q6 (ESTE SUPERIOR) ==================== */}
      <g id="block-q6">
        {/* Distribuidor / espacio abierto izquierdo */}
        <rect x="2400" y="680" width="240" height="240" className="wall" />
        {/* Sala Q6/0005 */}
        {renderRoom('q6-0005', 'Q6/0005', 2640, 680, 740, 240)}
      </g>

      {/* ==================== BLOQUE Q2 ==================== */}
      <g id="block-q2">
        {renderRoom('q2-0003', 'Q2/0003', 1430, 920, 200, 200)}
        {renderRoom('q2-0007', 'Q2/0007', 1630, 920, 150, 200, true)}
        {renderRoom('q2-0011', 'Q2/0011', 1780, 920, 150, 200, true)}
        {renderRoom('q2-0013', 'Q2/0013', 1930, 920, 150, 200, true)}
        {renderRoom('q2-0017', 'Q2/0017', 2080, 920, 150, 200, true)}
        {renderRoom('q2-0019', 'Q2/0019', 2230, 920, 170, 200, true)}
        {/* Pasillo inferior Q2 */}
        <rect x="1430" y="1120" width="970" height="60" className="wall" />
      </g>

      {/* ==================== BLOQUE Q5 (ESTE INFERIOR) ==================== */}
      <g id="block-q5">
        {/* Distribuidor izquierdo abierto */}
        <rect x="2400" y="1120" width="240" height="240" className="wall" />
        {/* Sala Q5/0003 */}
        {renderRoom('q5-0003', 'Q5/0003', 2640, 1120, 370, 180)}
        {/* Pasillo inferior bajo Q5/0003 */}
        <rect x="2640" y="1300" width="370" height="60" className="wall" />
        {/* Sala Q5/0004 */}
        {renderRoom('q5-0004', 'Q5/0004', 3010, 1120, 370, 240)}
      </g>

      {/* ==================== BLOQUE Q1 ==================== */}
      <g id="block-q1">
        {renderRoom('q1-0003', 'Q1/0003', 1430, 1360, 290, 200)}
        {renderRoom('q1-0005', 'Q1/0005', 1720, 1360, 280, 200)}
        {/* Distribuidor abierto entre 2000 y 2110 */}
        {renderRoom('q1-0019', 'Q1/0019', 2110, 1360, 290, 200)}
        {/* Pasillo inferior Q1 */}
        <rect x="1430" y="1560" width="970" height="60" className="wall" />
      </g>

      {/* ==================== ALA SUR / PASILLO PRINCIPAL QC ==================== */}
      <g id="block-qc">
        {/* Contenedor exterior del corredor principal QC */}
        <rect x="100" y="1690" width="3280" height="600" className="wall" />

        {/* Fila Norte de Salas QC */}
        {renderRoom('qc-0011', 'QC/0011', 1430, 1690, 230, 180)}
        {renderRoom('qc-0019', 'QC/0019', 1710, 1690, 160, 180)}
        {renderRoom('qc-0067', 'QC/0067', 1920, 1690, 160, 180)}
        {renderRoom('qc-0075', 'QC/0075', 2080, 1690, 150, 180)}
        {renderRoom('qc-0081', 'QC/0081', 2230, 1690, 100, 180, true)}
        {renderRoom('qc-0085', 'QC/0085', 2330, 1690, 150, 180)}
        {renderRoom('qc-0089', 'QC/0089', 2480, 1690, 150, 180)}
        {renderRoom('qc-0091', 'QC/0091', 2630, 1690, 100, 180, true)}
        {renderRoom('qc-0107', 'QC/0107', 2780, 1690, 160, 180)}
        {renderRoom('qc-0109', 'QC/0109', 2940, 1690, 150, 180)}
        {renderRoom('qc-0113', 'QC/0113', 3240, 1690, 140, 600, true)}

        {/* Fila Sur de Salas QC */}
        {renderRoom('qc-0069', 'QC/0069', 1920, 2110, 160, 180)}
        {renderRoom('qc-0073', 'QC/0073', 2080, 2110, 100, 180, true)}
        {renderRoom('qc-0077', 'QC/0077', 2180, 2110, 100, 180, true)}
        {renderRoom('qc-0079', 'QC/0079', 2280, 2110, 160, 180)}
        {renderRoom('qc-0083', 'QC/0083', 2440, 2110, 160, 180)}
        {renderRoom('qc-0087', 'QC/0087', 2600, 2110, 160, 180)}
        {renderRoom('qc-0111', 'QC/0111', 3010, 2110, 210, 180)}
      </g>
    </svg>
  );
}
