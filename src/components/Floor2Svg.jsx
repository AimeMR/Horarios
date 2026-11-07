import React from 'react';

export default function Floor2Svg({ selectedRoom, onSelectRoom }) {
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
        `}</style>
      </defs>

      {/* Fondo */}
      <rect width="3500" height="2500" className="bg" />

      {/* Bloques Grises (Alas Técnicas / Reservadas) */}
      <rect x="1200" y="120" width="280" height="1540" className="grey-wing" />
      <rect x="1480" y="120" width="940" height="260" className="grey-wing" />
      <rect x="1480" y="470" width="940" height="260" className="grey-wing" />
      <rect x="1480" y="920" width="940" height="260" className="grey-wing" />
      <rect x="1480" y="1370" width="940" height="260" className="grey-wing" />

      {/* BLOQUE Q6 */}
      <g id="block-q6">
        {renderRoom('q6-2004', 'Q6/2004', 2420, 730, 240, 210)}
        {renderRoom('q6-2005', 'Q6/2005', 2660, 730, 240, 210)}
        {renderRoom('q6-2007', 'Q6/2007', 2900, 730, 150, 210, true)}
        {renderRoom('q6-2008', 'Q6/2008', 3050, 730, 160, 210, true)}
        {renderRoom('q6-2009', 'Q6/2009', 3210, 730, 170, 210, true)}
        <rect x="2420" y="940" width="960" height="70" className="wall" />
      </g>

      {/* BLOQUE Q5 */}
      <g id="block-q5">
        {renderRoom('q5-2003', 'Q5/2003', 2420, 1180, 240, 210)}
        {renderRoom('q5-2006', 'Q5/2006', 2660, 1180, 170, 210, true)}
        {renderRoom('q5-2007', 'Q5/2007', 2830, 1180, 180, 210, true)}
        {renderRoom('q5-2008', 'Q5/2008', 3010, 1180, 170, 210, true)}
        {renderRoom('q5-2009', 'Q5/2009', 3180, 1180, 200, 210, true)}
        <rect x="2420" y="1390" width="960" height="70" className="wall" />
      </g>

      {/* ALA SUR / QC */}
      <g id="block-qc">
        <rect x="150" y="1660" width="3230" height="600" className="wall" />
        {renderRoom('qc-2090', 'QC/2090', 150, 1660, 350, 600)}
        {renderRoom('qc-2080', 'QC/2080', 500, 1660, 350, 200)}
        {renderRoom('qc-2082', 'QC/2082', 500, 2060, 350, 200)}
        {renderRoom('qc-2004', 'QC/2004', 1400, 2060, 350, 200)}
        {renderRoom('qc-2011', 'QC/2011', 1930, 2060, 180, 200, true)}
        {renderRoom('qc-2015', 'QC/2015', 2110, 2060, 180, 200, true)}
        {renderRoom('qc-2101', 'QC/2101', 2490, 1660, 180, 200, true)}
        {renderRoom('qc-2099', 'QC/2099', 2490, 2060, 180, 200, true)}
        {renderRoom('qc-2149', 'QC/2149', 2800, 1660, 280, 200)}
        {renderRoom('qc-2161', 'QC/2161', 3080, 1660, 150, 200, true)}
        {renderRoom('qc-2165', 'QC/2165', 3230, 1660, 150, 200, true)}
        {renderRoom('qc-2147', 'QC/2147', 2800, 2060, 290, 200)}
        {renderRoom('qc-2159', 'QC/2159', 3090, 2060, 290, 200)}
      </g>
    </svg>
  );
}
