import React, { useState } from 'react';

export default function Sidebar({
  isOpen,
  onClose,
  filters,
  onFilterChange,
  onResetFilters
}) {
  const [openSections, setOpenSections] = useState({
    date: true,
    class: true,
    group: true,
    course: true
  });

  const toggleSection = (section) => {
    setOpenSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const handleDatePresetChange = (preset) => {
    const today = new Date('2026-11-07T12:00:00');
    let dateStr = '2026-11-07';

    if (preset === 'tomorrow') {
      const tomorrow = new Date(today);
      tomorrow.setDate(today.getDate() + 1);
      dateStr = tomorrow.toISOString().split('T')[0];
    } else if (preset === 'monday') {
      const monday = new Date(today);
      monday.setDate(today.getDate() + 2);
      dateStr = monday.toISOString().split('T')[0];
    }

    onFilterChange('datePreset', preset);
    if (preset !== 'custom') {
      onFilterChange('date', dateStr);
    }
  };

  const getDateBadgeText = () => {
    if (filters.datePreset === 'today') return 'Hoy';
    if (filters.datePreset === 'tomorrow') return 'Mañana';
    if (filters.datePreset === 'monday') return 'Lunes';
    if (filters.date) {
      const parts = filters.date.split('-');
      return parts.length === 3 ? `${parts[2]}/${parts[1]}` : 'Fecha';
    }
    return 'Hoy';
  };

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
        {/* 1. SELECCIONAR FECHA (DESPLEGABLE) */}
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
              <span className="summary-title">Fecha</span>
            </div>
            <div className="summary-right">
              <span className="summary-badge is-active">{getDateBadgeText()}</span>
              <svg className="chevron-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </div>
          </button>

          {openSections.date && (
            <div className="filter-dropdown-content">
              <div className="filter-subgroup">
                <label className="filter-sublabel" htmlFor="date-preset-select">Preselección rápida</label>
                <div className="select-wrapper">
                  <select
                    id="date-preset-select"
                    className="form-control"
                    value={filters.datePreset}
                    onChange={(e) => handleDatePresetChange(e.target.value)}
                  >
                    <option value="today">Hoy (07/11/2026)</option>
                    <option value="tomorrow">Mañana (08/11/2026)</option>
                    <option value="monday">Próximo Lunes (09/11/2026)</option>
                    <option value="custom">Fecha personalizada...</option>
                  </select>
                </div>
              </div>
              <div className="filter-subgroup">
                <label className="filter-sublabel" htmlFor="date-input">Calendario</label>
                <input
                  type="date"
                  id="date-input"
                  className="form-control"
                  value={filters.date}
                  onChange={(e) => {
                    onFilterChange('datePreset', 'custom');
                    onFilterChange('date', e.target.value);
                  }}
                />
              </div>
              <span className="filter-hint">Elige un día para ver la asignación de espacios</span>
            </div>
          )}
        </div>

        {/* 2. ELEGIR CLASE (DESPLEGABLE) */}
        <div className={`filter-dropdown ${openSections.class ? 'is-open' : ''}`}>
          <button
            type="button"
            className="filter-dropdown-summary"
            onClick={() => toggleSection('class')}
            aria-expanded={openSections.class}
          >
            <div className="summary-label-group">
              <svg className="summary-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <line x1="9" y1="3" x2="9" y2="21"></line>
              </svg>
              <span className="summary-title">Clase / Espacio</span>
            </div>
            <div className="summary-right">
              <span className={`summary-badge ${filters.class ? 'is-active' : ''}`}>
                {filters.class || 'Todas'}
              </span>
              <svg className="chevron-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </div>
          </button>

          {openSections.class && (
            <div className="filter-dropdown-content">
              <div className="select-wrapper">
                <select
                  className="form-control"
                  value={filters.class}
                  onChange={(e) => onFilterChange('class', e.target.value)}
                >
                  <option value="">Todas las clases</option>
                  <optgroup label="Bloque Q4">
                    <option value="Q4/0003">Q4/0003</option>
                    <option value="Q4/0007">Q4/0007</option>
                    <option value="Q4/0011">Q4/0011</option>
                  </optgroup>
                  <optgroup label="Bloque Q3">
                    <option value="Q3/0003">Q3/0003</option>
                    <option value="Q3/0007">Q3/0007</option>
                    <option value="Q3/0011">Q3/0011</option>
                  </optgroup>
                  <optgroup label="Bloque Q2">
                    <option value="Q2/0003">Q2/0003</option>
                    <option value="Q2/0007">Q2/0007</option>
                    <option value="Q2/0011">Q2/0011</option>
                    <option value="Q2/0013">Q2/0013</option>
                    <option value="Q2/0017">Q2/0017</option>
                    <option value="Q2/0019">Q2/0019</option>
                  </optgroup>
                  <optgroup label="Bloque Q1">
                    <option value="Q1/0003">Q1/0003</option>
                    <option value="Q1/0007">Q1/0007</option>
                    <option value="Q1/0013">Q1/0013</option>
                    <option value="Q1/0019">Q1/0019</option>
                  </optgroup>
                  <optgroup label="Bloque Q5 / Q6">
                    <option value="Q6/0006">Q6/0006</option>
                    <option value="Q5/0003">Q5/0003</option>
                    <option value="Q5/0004">Q5/0004</option>
                  </optgroup>
                  <optgroup label="Ala Central (QC)">
                    <option value="QC/0067">QC/0067</option>
                    <option value="QC/0069">QC/0069</option>
                    <option value="QC/0073">QC/0073</option>
                    <option value="QC/0075">QC/0075</option>
                    <option value="QC/0077">QC/0077</option>
                    <option value="QC/0079">QC/0079</option>
                    <option value="QC/0081">QC/0081</option>
                    <option value="QC/0083">QC/0083</option>
                    <option value="QC/0085">QC/0085</option>
                    <option value="QC/0087">QC/0087</option>
                    <option value="QC/0089">QC/0089</option>
                    <option value="QC/0091">QC/0091</option>
                    <option value="QC/0107">QC/0107</option>
                    <option value="QC/0109">QC/0109</option>
                    <option value="QC/0111">QC/0111</option>
                    <option value="QC/0113">QC/0113</option>
                  </optgroup>
                  <optgroup label="Ala Sur (QP)">
                    <option value="QP/0002">QP/0002</option>
                    <option value="QP/0003">QP/0003</option>
                    <option value="QP/0005">QP/0005</option>
                    <option value="QP/0006">QP/0006</option>
                    <option value="QP/0007">QP/0007</option>
                    <option value="QP/0008">QP/0008</option>
                    <option value="QP/0009">QP/0009</option>
                    <option value="QP/0012">QP/0012</option>
                  </optgroup>
                </select>
              </div>
              <span className="filter-hint">Haz clic en un aula del plano o elígela aquí</span>
            </div>
          )}
        </div>

        {/* 3. ELEGIR GRUPO (DESPLEGABLE) */}
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
                {filters.group ? filters.group.replace('grupo-', 'G-').toUpperCase() : 'Todos'}
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
                >
                  <option value="">Todos los grupos</option>
                  <option value="grupo-a">Grupo A (Mañana)</option>
                  <option value="grupo-b">Grupo B (Mañana)</option>
                  <option value="grupo-c">Grupo C (Tarde)</option>
                  <option value="grupo-d">Grupo D (Tarde)</option>
                </select>
              </div>
              <span className="filter-hint">Turno de mañana o tarde</span>
            </div>
          )}
        </div>

        {/* 4. ELEGIR CURSO (DESPLEGABLE) */}
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
                {filters.course ? `${filters.course}º` : 'Todos'}
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
                  <option value="1">1º Curso</option>
                  <option value="2">2º Curso</option>
                  <option value="3">3º Curso</option>
                  <option value="4">4º Curso</option>
                  <option value="master">Máster / Postgrado</option>
                </select>
              </div>
              <span className="filter-hint">Nivel académico asociado</span>
            </div>
          )}
        </div>

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
          Visualización y filtros reactivos en <code>React 18</code>.
        </p>
      </div>
    </aside>
  );
}

