import React from 'react';

export default function Floor1Svg({ selectedRoom, onSelectRoom }) {
  const renderRoom = (id, name, x, y, width, height, isSmall = false) => {
    const isSelected = selectedRoom === name;
    const centerX = x + width / 2;
    const centerY = y + height / 2;

    return (
      <g
        key={id}
        className={`room ${isSelected ? 'is-selected' : ''}`}
        id={`room-${id}`}
        data-room={name}
        tabIndex={0}
        role="button"
        aria-label={`Aula ${name}`}
        onClick={(e) => onSelectRoom(name, e)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
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
          .room-label { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 25px; font-weight: 700; fill: #111827; text-anchor: middle; dominant-baseline: central; letter-spacing: 0.5px; pointer-events: none; user-select: none; }
          .room-label-sm { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 21px; font-weight: 700; fill: #111827; text-anchor: middle; dominant-baseline: central; letter-spacing: 0.3px; pointer-events: none; user-select: none; }
          .room { cursor: pointer; outline: none; }
          .room .room-rect { cursor: pointer; transition: fill 0.15s ease, stroke 0.15s ease; }
          .room:hover .room-rect { fill: #E0F2FE !important; stroke: #0284C7 !important; stroke-width: 6 !important; }
          .room:hover text { fill: #0284C7 !important; }
          .room.is-selected .room-rect { fill: #BAE6FD !important; stroke: #0369A1 !important; stroke-width: 7 !important; }
          .room.is-selected text { fill: #0369A1 !important; font-weight: 800 !important; }
        `}</style>
      </defs>

      {/* Fondo */}
      <rect width="3500" height="2500" className="bg" />

      {/* Columna / Pasillo vertical conector oeste */}
      <rect x="1180" y="100" width="270" height="1650" className="wall" />

      {/* BLOQUE Q4 */}
      <g id="block-q4">
        {renderRoom('q4-1003', 'Q4/1003', 1450, 100, 230, 210)}
        {renderRoom('q4-1005', 'Q4/1005', 1680, 100, 230, 210)}
        {renderRoom('q4-1009', 'Q4/1009', 1910, 100, 230, 210)}
        {renderRoom('q4-1013', 'Q4/1013', 2140, 100, 230, 210)}
        <rect x="1450" y="310" width="920" height="70" className="wall" />
      </g>

      {/* BLOQUE Q3 */}
      <g id="block-q3">
        {renderRoom('q3-1003', 'Q3/1003', 1450, 490, 280, 210)}
        {renderRoom('q3-1007', 'Q3/1007', 1730, 490, 360, 210)}
        {renderRoom('q3-1011', 'Q3/1011', 2090, 490, 280, 210)}
        <rect x="1450" y="700" width="920" height="70" className="wall" />
      </g>

      {/* BLOQUE Q6 */}
      <g id="block-q6">
        {renderRoom('q6-1006', 'Q6/1006', 2370, 710, 440, 210)}
        {renderRoom('q6-1011', 'Q6/1011', 2810, 710, 210, 210)}
        {renderRoom('q6-1012', 'Q6/1012', 3020, 710, 210, 210)}
        <rect x="2370" y="920" width="860" height="70" className="wall" />
      </g>

      {/* BLOQUE Q2 */}
      <g id="block-q2">
        {renderRoom('q2-1003', 'Q2/1003', 1450, 940, 230, 210)}
        {renderRoom('q2-1005', 'Q2/1005', 1680, 940, 230, 210)}
        {renderRoom('q2-1009', 'Q2/1009', 1910, 940, 230, 210)}
        {renderRoom('q2-1013', 'Q2/1013', 2140, 940, 230, 210)}
        <rect x="1450" y="1150" width="920" height="70" className="wall" />
      </g>

      {/* BLOQUE Q5 */}
      <g id="block-q5">
        {renderRoom('q5-1005', 'Q5/1005', 2370, 1150, 172, 210, true)}
        {renderRoom('q5-1006', 'Q5/1006', 2542, 1150, 172, 210, true)}
        {renderRoom('q5-1009', 'Q5/1009', 2714, 1150, 172, 210, true)}
        {renderRoom('q5-1010', 'Q5/1010', 2886, 1150, 172, 210, true)}
        {renderRoom('q5-1011', 'Q5/1011', 3058, 1150, 172, 210, true)}
        <rect x="2370" y="1360" width="860" height="70" className="wall" />
      </g>

      {/* BLOQUE Q1 */}
      <g id="block-q1">
        {renderRoom('q1-1003', 'Q1/1003', 1450, 1380, 280, 210)}
        {renderRoom('q1-1005', 'Q1/1005', 1730, 1380, 360, 210)}
        {renderRoom('q1-1007', 'Q1/1007', 2090, 1380, 280, 210)}
        <rect x="1450" y="1590" width="920" height="70" className="wall" />
      </g>

      {/* ALA SUR / QC */}
      <g id="block-qc">
        <rect x="150" y="1750" width="3200" height="600" className="wall" />
        {renderRoom('qc-1086', 'QC/1086', 150, 1750, 350, 210)}
        {renderRoom('qc-1088', 'QC/1088', 150, 2140, 350, 210)}
        {renderRoom('qc-1031', 'QC/1031', 1850, 1750, 350, 210)}
        {renderRoom('qc-1033', 'QC/1033', 1850, 2140, 350, 210)}
        {renderRoom('qc-1041', 'QC/1041', 2200, 2140, 350, 210)}
      </g>
    </svg>
  );
}
