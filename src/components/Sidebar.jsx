import React, { useState } from 'react';
import { useFilterCategories } from '../services/useFilterCategories';

export default function Sidebar({
  isOpen,
  onClose,
  filters,
  onFilterChange,
  onResetFilters
}) {
  const [openSections, setOpenSections] = useState({
    date: true,
    degree: true,
    course: true,
    subject: true,
    group: true
  });

  // Consumo dinámico de categorías preparadas para endpoint backend
  const { categories, isLoading, isFallback } = useFilterCategories();
  const { degrees, subjects, groups } = categories;

  const toggleSection = (section) => {
    setOpenSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  // Cursos actualizados: 1º, 2º, 3º, 4º y 5º Curso
  const courses = [
    { id: '1', name: '1º Curso', short: '1º' },
    { id: '2', name: '2º Curso', short: '2º' },
    { id: '3', name: '3º Curso', short: '3º' },
    { id: '4', name: '4º Curso', short: '4º' },
    { id: '5', name: '5º Curso', short: '5º' }
  ];

  const formatDateBadge = (dateStr) => {
    if (!dateStr) return 'Fecha';
    const parts = dateStr.split('-');
    return parts.length === 3 ? `${parts[2]}/${parts[1]}` : dateStr;
  };

  const getDegreeBadge = () => {
    const found = degrees.find(d => d.id === filters.degree);
    return found ? found.short : 'Todos';
  };

  const getCourseBadge = () => {
    const found = courses.find(c => c.id === filters.course);
    return found ? found.short : 'Todos';
  };

  const getSubjectBadge = () => {
    const found = subjects.find(s => s.id === filters.subject);
    if (!found) return 'Todas';
    return found.name.length > 12 ? `${found.name.substring(0, 10)}...` : found.name;
  };

  const getGroupBadge = () => {
    const found = groups.find(g => g.id === filters.group);
    return found ? found.short : 'Todos';
  };

  // Filtrado de asignaturas según grado o curso si están definidos
  const filteredSubjects = subjects.filter(s => {
    if (filters.degree && s.gradoId && s.gradoId !== filters.degree) return false;
    if (filters.course && s.curso && s.curso !== filters.course) return false;
    return true;
  });

  const availableSubjects = filteredSubjects.length > 0 ? filteredSubjects : subjects;

  return (
    <aside className={`sidebar ${!isOpen ? 'collapsed' : ''}`} aria-label="Filtros de búsqueda">
      <div className="sidebar-header">
        <div className="sidebar-title-group">
          <svg className="icon-subtle" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
          </svg>
          <h2 className="sidebar-title">Filtros</h2>
        </div>
        <button
          type="button"
          className="close-sidebar-btn"
          onClick={onClose}
          aria-label="Ocultar filtros"
          title="Ocultar barra lateral"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <form className="filter-form" onSubmit={(e) => e.preventDefault()}>
        {/* 1. FECHA (DÍA CONCRETO) */}
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
              <span className="summary-title">Fecha (día concreto)</span>
            </div>
            <div className="summary-right">
              <span className="summary-badge is-active">{formatDateBadge(filters.date)}</span>
              <svg className="chevron-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </div>
          </button>

          {openSections.date && (
            <div className="filter-dropdown-content">
              <div className="filter-subgroup">
                <label className="filter-sublabel" htmlFor="date-input">Seleccionar día</label>
                <input
                  type="date"
                  id="date-input"
                  className="form-control"
                  value={filters.date}
                  onChange={(e) => onFilterChange('date', e.target.value)}
                />
              </div>
              <span className="filter-hint">Consulta la ocupación y horarios para este día</span>
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
              <span className="summary-title">Grado</span>
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
                  <option value="">Todos los grados</option>
                  {degrees.map(d => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </select>
              </div>
              <span className="filter-hint">Titulación académica obtenida del sistema</span>
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
              <span className="summary-title">Curso</span>
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
                  <option value="">Todos los cursos</option>
                  {courses.map(c => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
              <span className="filter-hint">Año o nivel lectivo (1º a 5º)</span>
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
              <span className="summary-title">Asignatura</span>
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
                  <option value="">Todas las asignaturas</option>
                  {availableSubjects.map(s => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
              <span className="filter-hint">Materia correspondiente según titulación</span>
            </div>
          )}
        </div>

        {/* 5. GRUPO (DESDE ENDPOINT) */}
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
              <span className="summary-title">Grupo</span>
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
              <div className="select-wrapper">
                <select
                  className="form-control"
                  value={filters.group}
                  onChange={(e) => onFilterChange('group', e.target.value)}
                  disabled={isLoading}
                >
                  <option value="">Todos los grupos</option>
                  {groups.map(g => (
                    <option key={g.id} value={g.id}>{g.name}</option>
                  ))}
                </select>
              </div>
              <span className="filter-hint">Turno de mañana o tarde</span>
            </div>
          )}
        </div>

        {/* Botones de Acción */}
        <div className="filter-actions">
          <button type="button" className="button button-secondary" onClick={onResetFilters}>
            Limpiar filtros
          </button>
          <button type="submit" className="button button-primary">
            Filtrar aulas
          </button>
        </div>
      </form>

      <div className="sidebar-footer">
        <p className="footer-note">
          Categorías conectadas al endpoint <code>/api/filters</code> {isFallback && '(modo base)'}.
        </p>
      </div>
    </aside>
  );
}
