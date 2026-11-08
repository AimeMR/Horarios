import React from 'react';
import { useLanguage } from '../context/LanguageContext';

export default function FloorSelector({
  currentFloor,
  onSelectFloor,
  floorMatchCounts = {},
  hasActiveFilters = false
}) {
  const { t } = useLanguage();

  return (
    <section className="floor-navigation-bar" aria-label={t('floorSelector.floorPill', currentFloor)}>
      <div className="floor-selector-card">
        {/* Flecha Anterior (deshabilitada en la planta 0) */}
        <button
          type="button"
          className="nav-arrow-btn"
          onClick={() => onSelectFloor(currentFloor - 1)}
          disabled={currentFloor <= 0}
          aria-label={t('floorSelector.previousFloor')}
          title={t('floorSelector.previousFloor')}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6"></polyline>
          </svg>
        </button>

        {/* Botones de las 4 plantas: 0, 1, 2 y 3 con alerta de aulas coincidentes */}
        <div className="floor-indicators">
          {[0, 1, 2, 3].map((num) => {
            const count = floorMatchCounts[num] || 0;
            const isOtherFloor = num !== currentFloor;
            const showAlert = hasActiveFilters && count > 0;

            return (
              <div key={num} className="floor-indicator-item">
                <button
                  type="button"
                  className={`floor-pill ${currentFloor === num ? 'active' : ''}`}
                  onClick={() => onSelectFloor(num)}
                  aria-label={t('floorSelector.floorPill', num)}
                >
                  <span className="pill-number">{num}</span>
                  <span className="pill-text">{t('floorSelector.floorPill', num)}</span>
                </button>

                {showAlert && (
                  <div
                    className={`floor-alert-badge ${isOtherFloor ? 'is-other-floor' : 'is-current-floor'}`}
                    title={t('floorSelector.alertTooltip', count, num)}
                  >
                    <span className="alert-icon">⚠️</span>
                    <span className="alert-count">{t('floorSelector.alertText', count)}</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Flecha Siguiente (deshabilitada en la planta 3) */}
        <button
          type="button"
          className="nav-arrow-btn"
          onClick={() => onSelectFloor(currentFloor + 1)}
          disabled={currentFloor >= 3}
          aria-label={t('floorSelector.nextFloor')}
          title={t('floorSelector.nextFloor')}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="9 18 15 12 9 6"></polyline>
          </svg>
        </button>
      </div>

      <div className="floor-meta-badge">
        <span className="meta-dot"></span>
        <span>{t(`floorSelector.floorDescriptions.${currentFloor}`)}</span>
      </div>
    </section>
  );
}
