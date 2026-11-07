import React from 'react';

export default function Header({ isSidebarOpen, onToggleSidebar, currentFloor }) {
  return (
    <header className="app-header">
      <div className="header-left">
        <button
          type="button"
          className="icon-button"
          onClick={onToggleSidebar}
          aria-label={isSidebarOpen ? 'Ocultar barra lateral' : 'Mostrar barra lateral'}
          title="Alternar filtros (Ctrl+B)"
        >
          <svg
            className="icon"
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
          </svg>
        </button>

        <div className="brand">
          <span className="brand-title">Edificio Central</span>
          <span className="brand-divider">/</span>
          <span className="brand-subtitle">Planta {currentFloor}</span>
        </div>
      </div>

      <div className="header-right">
        <div className="status-indicator">
          <span className="status-dot"></span>
          <span className="status-text">Visualizador React</span>
        </div>
      </div>
    </header>
  );
}

