import React from 'react';

export default function Floor2Svg({ selectedRoom, onSelectRoom }) {
  const rooms = [
    { id: '201', name: 'Aula 201', x: 60, y: 60, width: 180, height: 190, desc: 'Capacidad: 32' },
    { id: '202', name: 'Aula 202', x: 250, y: 60, width: 180, height: 190, desc: 'Capacidad: 35' },
    { id: '203', name: 'Aula 203', x: 570, y: 60, width: 150, height: 190, desc: 'Capacidad: 30' },
    { id: 'lab-info', name: 'Lab. Informática', x: 60, y: 350, width: 230, height: 190, desc: '28 Equipos' },
    { id: 'biblioteca', name: 'Biblioteca', x: 300, y: 350, width: 330, height: 190, desc: 'Zona Silencio' },
    { id: 'lab-ciencias', name: 'Lab. Ciencias', x: 640, y: 350, width: 200, height: 190, desc: 'Capacidad: 25' }
  ];

  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 600" width="100%" height="100%" className="floor-svg-canvas">
      <defs>
        <pattern id="grid2" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#f1f5f9" strokeWidth="1"/>
        </pattern>
        <style>{`
          .room { cursor: pointer; outline: none; }
          .room .room-rect { cursor: pointer; transition: fill 0.15s ease, stroke 0.15s ease; }
          .room:hover .room-rect { fill: #E0F2FE !important; stroke: #0284C7 !important; stroke-width: 3 !important; }
          .room:hover text { fill: #0284C7 !important; }
          .room.is-selected .room-rect { fill: #BAE6FD !important; stroke: #0369A1 !important; stroke-width: 4 !important; }
          .room.is-selected text { fill: #0369A1 !important; font-weight: 700 !important; }
        `}</style>
      </defs>

      <rect width="900" height="600" fill="#ffffff" />
      <rect width="900" height="600" fill="url(#grid2)" />
      <rect x="50" y="50" width="800" height="500" rx="8" fill="#f8fafc" stroke="#334155" strokeWidth="3"/>

      {/* Pasillo */}
      <rect x="50" y="260" width="800" height="80" fill="#ffffff" stroke="#cbd5e1" strokeWidth="1.5" strokeDasharray="4 4"/>
      <text x="450" y="306" fontFamily="system-ui, sans-serif" fontSize="12" fill="#94a3b8" fontWeight="600" textAnchor="middle" letterSpacing="3">
        PASILLO CENTRAL (PLANTA 2)
      </text>

      {/* Escaleras */}
      <rect x="440" y="60" width="120" height="190" fill="#e2e8f0" stroke="#475569" strokeWidth="2" rx="4"/>
      <text x="500" y="140" fontFamily="system-ui, sans-serif" fontSize="13" fontWeight="700" fill="#334155" textAnchor="middle">Escaleras</text>

      {/* Aseos */}
      <rect x="730" y="60" width="110" height="190" fill="#f8fafc" stroke="#475569" strokeWidth="2" rx="4"/>
      <text x="785" y="145" fontFamily="system-ui, sans-serif" fontSize="14" fontWeight="700" fill="#475569" textAnchor="middle">Aseos</text>

      {/* Aulas */}
      {rooms.map((room) => {
        const isSelected = selectedRoom === room.name;
        return (
          <g
            key={room.id}
            className={`room ${isSelected ? 'is-selected' : ''}`}
            data-room={room.name}
            tabIndex={0}
            role="button"
            onClick={(e) => onSelectRoom(room.name, e)}
          >
            <title>{room.name}</title>
            <rect x={room.x} y={room.y} width={room.width} height={room.height} fill="#ffffff" stroke="#475569" strokeWidth="2" rx="4" className="room-rect" />
            <text x={room.x + room.width / 2} y={room.y + room.height / 2 - 10} fontFamily="system-ui, sans-serif" fontSize="16" fontWeight="700" fill="#1e293b" textAnchor="middle">
              {room.name}
            </text>
            <text x={room.x + room.width / 2} y={room.y + room.height / 2 + 15} fontFamily="system-ui, sans-serif" fontSize="12" fill="#64748b" textAnchor="middle">
              {room.desc}
            </text>
          </g>
        );
      })}

      <g transform="translate(70, 70)">
        <rect width="64" height="26" rx="4" fill="#0284c7" fillOpacity="0.12" stroke="#0284c7" strokeWidth="1"/>
        <text x="32" y="18" fontFamily="system-ui, sans-serif" fontSize="12" fontWeight="700" fill="#0284c7" textAnchor="middle">PISO 2</text>
      </g>
    </svg>
  );
}

