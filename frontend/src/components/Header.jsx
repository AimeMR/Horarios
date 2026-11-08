import React from 'react';
import { useLanguage } from '../context/LanguageContext';
import { FlagEs, FlagCa, FlagEn } from './FlagIcons';

export default function Header({ isSidebarOpen, onToggleSidebar, currentFloor }) {
  const { lang, setLang, t } = useLanguage();

  return (
    <header className="app-header">
      <div className="header-left">
        <button
          type="button"
          className="icon-button"
          onClick={onToggleSidebar}
          aria-label={isSidebarOpen ? t('app.hideSidebar') : t('app.showSidebar')}
          title={t('app.toggleSidebar')}
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
          <span className="brand-title">{t('app.brandTitle')}</span>
          <span className="brand-divider">/</span>
          <span className="brand-subtitle">{t('app.floorLabel')} {currentFloor}</span>
        </div>
      </div>

      {/* Selector de idiomas con las 3 banderas: Castellano, Català e Inglés */}
      <div className="header-right">
        <div className="language-selector-toolbar" role="group" aria-label="Selector de idioma">
          <button
            type="button"
            className={`lang-switch-btn ${lang === 'es' ? 'is-active' : ''}`}
            onClick={() => setLang('es')}
            title="Castellano"
            aria-label="Cambiar a Castellano"
          >
            <FlagEs />
            <span className="lang-label-text">ES</span>
          </button>

          <button
            type="button"
            className={`lang-switch-btn ${lang === 'ca' ? 'is-active' : ''}`}
            onClick={() => setLang('ca')}
            title="Català"
            aria-label="Canviar a Català"
          >
            <FlagCa />
            <span className="lang-label-text">CA</span>
          </button>

          <button
            type="button"
            className={`lang-switch-btn ${lang === 'en' ? 'is-active' : ''}`}
            onClick={() => setLang('en')}
            title="English"
            aria-label="Switch to English"
          >
            <FlagEn />
            <span className="lang-label-text">EN</span>
          </button>
        </div>
      </div>
    </header>
  );
}

