import React from 'react';

export default function FloorSelector({ currentFloor, onSelectFloor, totalFloors = 3 }) {
  const floorDescriptions = {
    1: 'Piso 1 — Bloques Q1-Q6, Ala Central (QC) & Ala Sur (QP)',
    2: 'Piso 2 — Laboratorios, Biblioteca & Aulas 201-203',
    3: 'Piso 3 — Área Docente, Despachos & Terraza'
  };

  return (
    <section className="floor-navigation-bar" aria-label="Navegación entre pisos">
      <div className="floor-selector-card">
        {/* Flecha Anterior */}
        <button
          type="button"
          className="nav-arrow-btn"
          onClick={() => onSelectFloor(currentFloor - 1)}
          disabled={currentFloor <= 1}
          aria-label="Ir al piso anterior"
          title="Piso anterior"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6"></polyline>
          </svg>
        </button>

        {/* Botones de los 3 pisos */}
        <div className="floor-indicators">
          {[1, 2, 3].map((num) => (
            <button
              key={num}
              type="button"
              className={`floor-pill ${currentFloor === num ? 'active' : ''}`}
              onClick={() => onSelectFloor(num)}
              aria-label={`Piso ${num}`}
            >
              <span className="pill-number">{num}</span>
              <span className="pill-text">Piso {num}</span>
            </button>
          ))}
        </div>

        {/* Flecha Siguiente */}
        <button
          type="button"
          className="nav-arrow-btn"
          onClick={() => onSelectFloor(currentFloor + 1)}
          disabled={currentFloor >= totalFloors}
          aria-label="Ir al piso siguiente"
          title="Piso siguiente"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="9 18 15 12 9 6"></polyline>
          </svg>
        </button>
      </div>

      <div className="floor-meta-badge">
        <span className="meta-dot"></span>
        <span>{floorDescriptions[currentFloor] || `Piso ${currentFloor}`}</span>
      </div>
    </section>
  );
}

