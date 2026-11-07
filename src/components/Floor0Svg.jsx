import React from 'react';

export default function Floor0Svg({ selectedRoom, onSelectRoom }) {
  const renderRoom = (id, name, x, y, width, height, isVertical = false) => {
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
          className={isVertical ? 'room-label-vert' : 'room-label'}
          transform={isVertical ? `rotate(-90 ${centerX} ${centerY})` : undefined}
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
          .corridor-bound { fill: none; stroke: #111827; stroke-width: 4.5; stroke-linejoin: miter; stroke-linecap: square; }
          .room-label { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 24px; font-weight: 700; fill: #111827; text-anchor: middle; dominant-baseline: central; letter-spacing: 0.5px; pointer-events: none; user-select: none; }
          .room-label-vert { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 21px; font-weight: 700; fill: #111827; text-anchor: middle; dominant-baseline: central; letter-spacing: 0.5px; pointer-events: none; user-select: none; }
          .corridor-label { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 20px; font-weight: 600; fill: #6B7280; text-anchor: middle; dominant-baseline: central; letter-spacing: 4px; pointer-events: none; user-select: none; }
          .entry-text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 24px; font-weight: 700; fill: #111827; letter-spacing: 2px; pointer-events: none; user-select: none; }
          .arrow { stroke: #111827; stroke-width: 4; stroke-linecap: round; stroke-linejoin: round; fill: none; }
          .room { cursor: pointer; outline: none; }
          .room .room-rect { cursor: pointer; transition: fill 0.15s ease, stroke 0.15s ease; }
          .room:hover .room-rect { fill: #E0F2FE !important; stroke: #0284C7 !important; stroke-width: 6 !important; }
          .room:hover text { fill: #0284C7 !important; }
          .room.is-selected .room-rect { fill: #BAE6FD !important; stroke: #0369A1 !important; stroke-width: 7 !important; }
          .room.is-selected text { fill: #0369A1 !important; font-weight: 800 !important; }
        `}</style>
      </defs>

      <rect width="3500" height="2500" className="bg" />

      {/* Acceso y Pasillo Oeste */}
      <g id="access-entry">
        <line x1="720" y1="1100" x2="720" y2="1175" className="arrow" />
        <path d="M 710 1160 L 720 1175 L 730 1160" className="arrow" />
        <text x="695" y="1145" className="entry-text" textAnchor="end">ENTRY</text>
      </g>

      <path d="M 280 1200 L 700 1200" className="corridor-bound" />
      <path d="M 740 1200 L 820 1200" className="corridor-bound" />
      <path d="M 280 1200 L 280 1460 L 1420 1460" className="corridor-bound" />
      <path d="M 820 1200 L 820 280 L 940 280" className="corridor-bound" />
      <path d="M 820 1200 L 1480 1200" className="corridor-bound" />

      {/* BLOQUE OESTE (Q4) */}
      <g id="block-q4">
        {renderRoom('q4-0003', 'Q4/0003', 940, 280, 160, 150)}
        {renderRoom('q4-0007', 'Q4/0007', 1100, 280, 170, 150)}
        {renderRoom('q4-0011', 'Q4/0011', 1270, 280, 170, 150)}
      </g>

      {/* BLOQUE OESTE (Q3) */}
      <g id="block-q3">
        {renderRoom('q3-0003', 'Q3/0003', 940, 510, 160, 150)}
        {renderRoom('q3-0007', 'Q3/0007', 1100, 510, 170, 150)}
        {renderRoom('q3-0011', 'Q3/0011', 1270, 510, 170, 150)}
      </g>

      {/* BLOQUE OESTE (Q2) */}
      <g id="block-q2">
        {renderRoom('q2-0003', 'Q2/0003', 940, 730, 150, 150)}
        {renderRoom('q2-0007', 'Q2/0007', 1090, 730, 70, 150, true)}
        {renderRoom('q2-0011', 'Q2/0011', 1160, 730, 70, 150, true)}
        {renderRoom('q2-0013', 'Q2/0013', 1230, 730, 70, 150, true)}
        {renderRoom('q2-0017', 'Q2/0017', 1300, 730, 70, 150, true)}
        {renderRoom('q2-0019', 'Q2/0019', 1370, 730, 70, 150, true)}
      </g>

      {/* BLOQUE OESTE (Q1) */}
      <g id="block-q1">
        {renderRoom('q1-0003', 'Q1/0003', 940, 940, 150, 140)}
        {renderRoom('q1-0007', 'Q1/0007', 1090, 940, 140, 140)}
        {renderRoom('q1-0013', 'Q1/0013', 1230, 940, 75, 140, true)}
        {renderRoom('q1-0019', 'Q1/0019', 1305, 940, 135, 140)}
      </g>

      {/* BLOQUE CENTRAL SUPERIOR (Q6) */}
      <g id="block-q6">
        <rect x="1480" y="580" width="120" height="150" className="wall" />
        <text x="1540" y="655" className="corridor-label">CORRIDOR</text>
        {renderRoom('q6-0006', 'Q6/0006', 1600, 580, 260, 150)}
      </g>

      {/* BLOQUE CENTRAL SUPERIOR (Q5) */}
      <g id="block-q5">
        {renderRoom('q5-0003', 'Q5/0003', 1480, 780, 220, 100)}
        <rect x="1480" y="880" width="220" height="70" className="wall" />
        <text x="1590" y="915" className="corridor-label">CORRIDOR</text>
        {renderRoom('q5-0004', 'Q5/0004', 1700, 780, 160, 170)}
      </g>

      {/* ALA CENTRAL (QC) - TOP */}
      <g id="block-qc-top">
        {renderRoom('qc-0067', 'QC/0067', 1510, 1200, 240, 120)}
        {renderRoom('qc-0075', 'QC/0075', 1750, 1200, 170, 120)}
        {renderRoom('qc-0081', 'QC/0081', 1920, 1200, 80, 120, true)}
        {renderRoom('qc-0085', 'QC/0085', 2000, 1200, 150, 120)}
        {renderRoom('qc-0089', 'QC/0089', 2150, 1200, 150, 120)}
        {renderRoom('qc-0091', 'QC/0091', 2300, 1200, 80, 120, true)}
        {renderRoom('qc-0107', 'QC/0107', 2380, 1200, 200, 120)}
        {renderRoom('qc-0109', 'QC/0109', 2580, 1200, 80, 120, true)}
        {renderRoom('qc-0113', 'QC/0113', 2660, 1200, 160, 260, true)}
      </g>

      {/* ALA CENTRAL (QC) - BOTTOM */}
      <g id="block-qc-bottom">
        {renderRoom('qc-0069', 'QC/0069', 1580, 1340, 170, 120)}
        {renderRoom('qc-0073', 'QC/0073', 1750, 1340, 65, 120, true)}
        {renderRoom('qc-0077', 'QC/0077', 1815, 1340, 65, 120, true)}
        {renderRoom('qc-0079', 'QC/0079', 1880, 1340, 170, 120)}
        {renderRoom('qc-0083', 'QC/0083', 2050, 1340, 140, 120)}
        {renderRoom('qc-0087', 'QC/0087', 2190, 1340, 220, 120)}
        {renderRoom('qc-0111', 'QC/0111', 2540, 1340, 120, 120)}
      </g>

      {/* ALA SUR (QP) */}
      <g id="south-corridor">
        <path d="M 1480 1560 L 2430 1560" className="corridor-bound" />
        <text x="1955" y="1625" className="corridor-label">CORRIDOR</text>
      </g>

      <g id="block-qp-nexus">
        {renderRoom('qp-0002', 'QP/0002', 1390, 1560, 90, 130, true)}
      </g>

      <g id="block-qp-row">
        {renderRoom('qp-0003', 'QP/0003', 1390, 1690, 220, 240)}
        {renderRoom('qp-0005', 'QP/0005', 1610, 1690, 170, 240)}
        {renderRoom('qp-0006', 'QP/0006', 1780, 1690, 130, 240)}
        {renderRoom('qp-0007', 'QP/0007', 1910, 1690, 70, 240, true)}
        {renderRoom('qp-0008', 'QP/0008', 1980, 1690, 200, 240)}
        {renderRoom('qp-0009', 'QP/0009', 2180, 1690, 250, 240)}
        {renderRoom('qp-0012', 'QP/0012', 2430, 1560, 390, 370)}
      </g>
    </svg>
  );
}
