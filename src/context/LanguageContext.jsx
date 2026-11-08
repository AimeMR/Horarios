import React, { createContext, useContext, useState, useEffect } from 'react';
import { TRANSLATIONS, getTranslatedSubjectName, getTranslatedDegree } from '../i18n/translations';

const LanguageContext = createContext(null);

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(() => {
    try {
      const saved = localStorage.getItem('horarios_lang');
      if (saved && ['es', 'ca', 'en'].includes(saved)) {
        return saved;
      }
    } catch (_) {}
    return 'es'; // Idioma por defecto
  });

  const setLang = (newLang) => {
    if (!['es', 'ca', 'en'].includes(newLang)) return;
    setLangState(newLang);
    try {
      localStorage.setItem('horarios_lang', newLang);
    } catch (_) {}
  };

  /**
   * Obtiene la traducción dada una clave con notación de punto (ej. 'sidebar.title')
   */
  const t = (keyPath, ...args) => {
    const keys = keyPath.split('.');
    let current = TRANSLATIONS[lang] || TRANSLATIONS.es;

    for (const k of keys) {
      if (current && typeof current === 'object' && k in current) {
        current = current[k];
      } else {
        // Fallback a castellano si falta la clave
        let fallback = TRANSLATIONS.es;
        for (const fk of keys) {
          if (fallback && typeof fallback === 'object' && fk in fallback) {
            fallback = fallback[fk];
          } else {
            return keyPath;
          }
        }
        current = fallback;
        break;
      }
    }

    if (typeof current === 'function') {
      return current(...args);
    }

    return current !== undefined ? current : keyPath;
  };

  const translateSubject = (codi, fallbackName) => {
    return getTranslatedSubjectName(codi, fallbackName, lang);
  };

  const translateDegree = (id, fallbackName) => {
    return getTranslatedDegree(id, fallbackName, lang);
  };

  return (
    <LanguageContext.Provider
      value={{
        lang,
        setLang,
        t,
        translateSubject,
        translateDegree
      }}
    >
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage debe ser utilizado dentro de un LanguageProvider');
  }
  return context;
}

