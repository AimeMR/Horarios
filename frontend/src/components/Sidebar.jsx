import React, { useState } from 'react';
import { useFilterCategories } from '../services/useFilterCategories';
import { getWeekInfo } from '../services/scheduleFilterService';
import { useLanguage } from '../context/LanguageContext';

export default function Sidebar({
  isOpen,
  onClose,
  filters,
  onFilterChange,
  onResetFilters,
  onApplyFilters
}) {
  const { lang, t, translateSubject, translateDegree } = useLanguage();

  const [openSections, setOpenSections] = useState({
    date: true,
    degree: true,
    course: true,
    subject: true,
    group: true
  });

  // Consumo dinámico de categorías preparadas para endpoint backend
  const { categories, isLoading, isFallback } = useFilterCategories();
  const { degrees, subjects } = categories;

  const toggleSection = (section) => {
    setOpenSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  // Cursos traducidos
  const courses = [
    { id: '1', name: t('courses.1.name'), short: t('courses.1.short') },
    { id: '2', name: t('courses.2.name'), short: t('courses.2.short') },
    { id: '3', name: t('courses.3.name'), short: t('courses.3.short') },
    { id: '4', name: t('courses.4.name'), short: t('courses.4.short') },
    { id: '5', name: t('courses.5.name'), short: t('courses.5.short') }
  ];

  const getWeekBadge = () => {
    if (!filters.week) return t('sidebar.allWeeks');
    const info = getWeekInfo(filters.week);
    if (!info) return filters.week;
    const prefix = lang === 'en' ? 'Wk.' : 'Sem.';
    return `${prefix} ${info.week} (${info.rangeLabel})`;
  };

  const getDegreeBadge = () => {
    const found = degrees.find(d => d.id === filters.degree);
    return found ? translateDegree(found.id, found.name).short : t('sidebar.allDegreesBadge');
  };

  const getCourseBadge = () => {
    const found = courses.find(c => c.id === filters.course);
    return found ? found.short : t('sidebar.allCoursesBadge');
  };

  const getSubjectBadge = () => {
    const found = subjects.find(s => s.id === filters.subject);
    if (!found) return t('sidebar.allSubjectsBadge');
    const sName = translateSubject(found.id, found.name);
    return sName.length > 12 ? `${sName.substring(0, 10)}...` : sName;
  };

  const getGroupBadge = () => {
    return filters.group ? `G. ${filters.group}` : t('sidebar.allGroupsBadge');
  };

  // Filtrado de asignaturas según grado o curso si están definidos
  const filteredSubjects = subjects.filter(s => {
    if (filters.degree && s.gradoId && s.gradoId !== filters.degree) return false;
    if (filters.course && s.curso && s.curso !== filters.course) return false;
    return true;
  });

  const availableSubjects = filteredSubjects.length > 0 ? filteredSubjects : subjects;

  const currentWeekInfo = getWeekInfo(filters.week);

  return (
    <aside className={`sidebar ${!isOpen ? 'collapsed' : ''}`} aria-label={t('sidebar.title')}>
      <div className="sidebar-header">
        <div className="sidebar-title-group">
          <svg className="icon-subtle" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
          </svg>
          <h2 className="sidebar-title">{t('sidebar.title')}</h2>
        </div>
        <button
          type="button"
          className="close-sidebar-btn"
          onClick={onClose}
          aria-label={t('app.hideSidebar')}
          title={t('app.hideSidebar')}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <form className="filter-form" onSubmit={(e) => { e.preventDefault(); if (onApplyFilters) onApplyFilters(); }}>
        {/* 1. SEMANA LECTIVA COMPLETA (LUNES A VIERNES) */}
        <div className={`filter-dropdown ${openSections.date ? 'is-open' : ''}`}>
          <button
            type="button"
            className="filter-dropdown-summary"
            onClick={() => toggleSection('date')}
            aria-expanded={openSections.date}
          >
            <div className="summary-label-group">
              <svg className="summary-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                <line x1="16" y1="2" x2="16" y2="6"></line>
                <line x1="8" y1="2" x2="8" y2="6"></line>
                <line x1="3" y1="10" x2="21" y2="10"></line>
              </svg>
              <span className="summary-title">{t('sidebar.weekSection')}</span>
            </div>
            <div className="summary-right">
              <span className={`summary-badge ${filters.week ? 'is-active' : ''}`}>{getWeekBadge()}</span>
              <svg className="chevron-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </div>
          </button>

          {openSections.date && (
            <div className="filter-dropdown-content">
              {/* Único sistema: indicar semana en calendario */}
              <div className="filter-subgroup">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <label className="filter-sublabel" htmlFor="week-calendar-input" style={{ marginBottom: 0 }}>
                    {t('sidebar.selectWeekInCalendar')}
                  </label>
                  {filters.week && (
                    <button
                      type="button"
                      style={{ background: 'none', border: 'none', color: '#0284c7', fontSize: '0.75rem', cursor: 'pointer', padding: 0 }}
                      onClick={() => onFilterChange('week', '')}
                    >
                      {t('sidebar.clearWeek')}
                    </button>
                  )}
                </div>
                <input
                  type="week"
                  id="week-calendar-input"
                  className="form-control"
                  value={filters.week || ''}
                  onChange={(e) => onFilterChange('week', e.target.value)}
                />
              </div>

              {currentWeekInfo && (
                <div className="week-highlight-dates" style={{ marginTop: '2px', color: '#0369a1', fontWeight: 600, fontSize: '0.75rem' }}>
                  {t('sidebar.weekFromTo',
                    currentWeekInfo.week,
                    currentWeekInfo.rangeLabel,
                    currentWeekInfo.monday.split('-').reverse().join('/'),
                    currentWeekInfo.friday.split('-').reverse().join('/')
                  )}
                </div>
              )}

              <span className="filter-hint">
                {t('sidebar.weekHint')}
              </span>
            </div>
          )}
        </div>

        {/* 2. GRADO (DESDE ENDPOINT) */}
        <div className={`filter-dropdown ${openSections.degree ? 'is-open' : ''}`}>
          <button
            type="button"
            className="filter-dropdown-summary"
            onClick={() => toggleSection('degree')}
            aria-expanded={openSections.degree}
          >
            <div className="summary-label-group">
              <svg className="summary-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"></path>
              </svg>
              <span className="summary-title">{t('sidebar.degreeSection')}</span>
            </div>
            <div className="summary-right">
              <span className={`summary-badge ${filters.degree ? 'is-active' : ''}`}>
                {getDegreeBadge()}
              </span>
              <svg className="chevron-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </div>
          </button>

          {openSections.degree && (
            <div className="filter-dropdown-content">
              <div className="select-wrapper">
                <select
                  className="form-control"
                  value={filters.degree}
                  onChange={(e) => onFilterChange('degree', e.target.value)}
                  disabled={isLoading}
                >
                  <option value="">{t('sidebar.allDegrees')}</option>
                  {degrees.map(d => {
                    const translated = translateDegree(d.id, d.name);
                    return (
                      <option key={d.id} value={d.id}>{translated.name}</option>
                    );
                  })}
                </select>
              </div>
              <span className="filter-hint">{t('sidebar.degreeHint')}</span>
            </div>
          )}
        </div>

        {/* 3. CURSO (1º A 5º) */}
        <div className={`filter-dropdown ${openSections.course ? 'is-open' : ''}`}>
          <button
            type="button"
            className="filter-dropdown-summary"
            onClick={() => toggleSection('course')}
            aria-expanded={openSections.course}
          >
            <div className="summary-label-group">
              <svg className="summary-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M22 10v6M2 10l10-5 10 5-10 5z"></path>
                <path d="M6 12v5c3 3 9 3 12 0v-5"></path>
              </svg>
              <span className="summary-title">{t('sidebar.courseSection')}</span>
            </div>
            <div className="summary-right">
              <span className={`summary-badge ${filters.course ? 'is-active' : ''}`}>
                {getCourseBadge()}
              </span>
              <svg className="chevron-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </div>
          </button>

          {openSections.course && (
            <div className="filter-dropdown-content">
              <div className="select-wrapper">
                <select
                  className="form-control"
                  value={filters.course}
                  onChange={(e) => onFilterChange('course', e.target.value)}
                >
                  <option value="">{t('sidebar.allCourses')}</option>
                  {courses.map(c => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
              <span className="filter-hint">{t('sidebar.courseHint')}</span>
            </div>
          )}
        </div>

        {/* 4. ASIGNATURA (DESDE ENDPOINT) */}
        <div className={`filter-dropdown ${openSections.subject ? 'is-open' : ''}`}>
          <button
            type="button"
            className="filter-dropdown-summary"
            onClick={() => toggleSection('subject')}
            aria-expanded={openSections.subject}
          >
            <div className="summary-label-group">
              <svg className="summary-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
              </svg>
              <span className="summary-title">{t('sidebar.subjectSection')}</span>
            </div>
            <div className="summary-right">
              <span className={`summary-badge ${filters.subject ? 'is-active' : ''}`}>
                {getSubjectBadge()}
              </span>
              <svg className="chevron-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </div>
          </button>

          {openSections.subject && (
            <div className="filter-dropdown-content">
              <div className="select-wrapper">
                <select
                  className="form-control"
                  value={filters.subject}
                  onChange={(e) => onFilterChange('subject', e.target.value)}
                  disabled={isLoading}
                >
                  <option value="">{t('sidebar.allSubjects')}</option>
                  {availableSubjects.map(s => (
                    <option key={s.id} value={s.id}>{translateSubject(s.id, s.name)}</option>
                  ))}
                </select>
              </div>
              <span className="filter-hint">{t('sidebar.subjectHint')}</span>
            </div>
          )}
        </div>

        {/* 5. GRUPO (NUMÉRICO) */}
        <div className={`filter-dropdown ${openSections.group ? 'is-open' : ''}`}>
          <button
            type="button"
            className="filter-dropdown-summary"
            onClick={() => toggleSection('group')}
            aria-expanded={openSections.group}
          >
            <div className="summary-label-group">
              <svg className="summary-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                <circle cx="9" cy="7" r="4"></circle>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
              </svg>
              <span className="summary-title">{t('sidebar.groupSection')}</span>
            </div>
            <div className="summary-right">
              <span className={`summary-badge ${filters.group ? 'is-active' : ''}`}>
                {getGroupBadge()}
              </span>
              <svg className="chevron-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </div>
          </button>

          {openSections.group && (
            <div className="filter-dropdown-content">
              <div className="filter-subgroup">
                <label className="filter-sublabel" htmlFor="group-input">{t('sidebar.groupNumberLabel')}</label>
                <input
                  type="number"
                  id="group-input"
                  className="form-control"
                  placeholder={t('sidebar.groupPlaceholder')}
                  min="1"
                  value={filters.group || ''}
                  onChange={(e) => onFilterChange('group', e.target.value)}
                />
              </div>
              <span className="filter-hint">{t('sidebar.groupHint')}</span>
            </div>
          )}
        </div>

        {/* Botones de Acción */}
        <div className="filter-actions">
          <button type="button" className="button button-secondary" onClick={onResetFilters}>
            {t('sidebar.clearFilters')}
          </button>
          <button type="submit" className="button button-primary">
            {t('sidebar.applyFilters')}
          </button>
        </div>
      </form>

      <div className="sidebar-footer">
        <p className="footer-note">
          {t('sidebar.footerEndpoint')}
        </p>
      </div>
    </aside>
  );
}
