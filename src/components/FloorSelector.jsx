import React from 'react';

export default function FloorSelector({ currentFloor, onSelectFloor }) {
  const floorDescriptions = {
    0: 'Planta 0 — Bloques Q1-Q6, Ala Central (QC) & Ala Sur (QP)',
    1: 'Planta 1 — Bloques Q1-Q6 y Ala Central (QC)',
    2: 'Planta 2 — Bloques Q5-Q6 y Ala Central (QC)'
  };

  return (
    <section className="floor-navigation-bar" aria-label="Navegación entre plantas">
      <div className="floor-selector-card">
        {/* Flecha Anterior (deshabilitada en la planta 0) */}
        <button
          type="button"
          className="nav-arrow-btn"
          onClick={() => onSelectFloor(currentFloor - 1)}
          disabled={currentFloor <= 0}
          aria-label="Ir a la planta anterior"
          title="Planta anterior"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6"></polyline>
          </svg>
        </button>

        {/* Botones de las 3 plantas: 0, 1 y 2 */}
        <div className="floor-indicators">
          {[0, 1, 2].map((num) => (
            <button
              key={num}
              type="button"
              className={`floor-pill ${currentFloor === num ? 'active' : ''}`}
              onClick={() => onSelectFloor(num)}
              aria-label={`Planta ${num}`}
            >
              <span className="pill-number">{num}</span>
              <span className="pill-text">Planta {num}</span>
            </button>
          ))}
        </div>

        {/* Flecha Siguiente (deshabilitada en la planta 2) */}
        <button
          type="button"
          className="nav-arrow-btn"
          onClick={() => onSelectFloor(currentFloor + 1)}
          disabled={currentFloor >= 2}
          aria-label="Ir a la planta siguiente"
          title="Planta siguiente"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="9 18 15 12 9 6"></polyline>
          </svg>
        </button>
      </div>

      <div className="floor-meta-badge">
        <span className="meta-dot"></span>
        <span>{floorDescriptions[currentFloor] || `Planta ${currentFloor}`}</span>
      </div>
    </section>
  );
}
