import React, { useState, useEffect, useMemo } from 'react';
import { getRoomSchedule } from '../services/scheduleService';

const DAYS = [
  { key: 'L', label: 'Lunes' },
  { key: 'M', label: 'Martes' },
  { key: 'X', label: 'Miércoles' },
  { key: 'J', label: 'Jueves' },
  { key: 'V', label: 'Viernes' }
];

const MORNING_SLOTS = [
  { start: '08:30', end: '09:30', label: '08:30 – 09:30' },
  { start: '09:30', end: '10:30', label: '09:30 – 10:30' },
  { start: '10:30', end: '11:30', label: '10:30 – 11:30' },
  { start: '11:30', end: '12:30', label: '11:30 – 12:30' },
  { start: '12:30', end: '13:30', label: '12:30 – 13:30' },
  { start: '13:30', end: '14:30', label: '13:30 – 14:30' },
];

const AFTERNOON_SLOTS = [
  { start: '15:00', end: '16:00', label: '15:00 – 16:00' },
  { start: '16:00', end: '17:00', label: '16:00 – 17:00' },
  { start: '17:00', end: '18:00', label: '17:00 – 18:00' },
  { start: '18:00', end: '19:00', label: '18:00 – 19:00' },
  { start: '19:00', end: '20:00', label: '19:00 – 20:00' },
  { start: '20:00', end: '21:00', label: '20:00 – 21:00' },
];

// Paleta de 16 colores vivos, atractivos y contrastados
const SUBJECT_THEMES = [
  { bg: '#eff6ff', border: '#2563eb', text: '#1e3a8a', badgeBg: '#dbeafe', badgeText: '#1e40af' }, // Azul Cobalto
  { bg: '#ecfdf5', border: '#059669', text: '#064e3b', badgeBg: '#d1fae5', badgeText: '#065f46' }, // Verde Esmeralda
  { bg: '#fffbeb', border: '#d97706', text: '#78350f', badgeBg: '#fef3c7', badgeText: '#92400e' }, // Ámbar Dorado
  { bg: '#faf5ff', border: '#9333ea', text: '#581c87', badgeBg: '#f3e8ff', badgeText: '#6b21a8' }, // Púrpura Intenso
  { bg: '#ecfeff', border: '#0891b2', text: '#164e63', badgeBg: '#cffafe', badgeText: '#155e75' }, // Cian / Azul Petróleo
  { bg: '#fff7ed', border: '#ea580c', text: '#7c2d12', badgeBg: '#ffedd5', badgeText: '#9a3412' }, // Naranja / Coral
  { bg: '#fff1f2', border: '#e11d48', text: '#881337', badgeBg: '#ffe4e6', badgeText: '#9f1239' }, // Rosa Frambuesa
  { bg: '#f7fee7', border: '#65a30d', text: '#365314', badgeBg: '#ecfccb', badgeText: '#3f6212' }, // Verde Lima
  { bg: '#eef2ff', border: '#4f46e5', text: '#312e81', badgeBg: '#e0e7ff', badgeText: '#3730a3' }, // Añil / Índigo
  { bg: '#fdf4ff', border: '#c026d3', text: '#701a75', badgeBg: '#fae8ff', badgeText: '#86198f' }, // Fucsia Magenta
  { bg: '#f0f9ff', border: '#0284c7', text: '#0c4a6e', badgeBg: '#e0f2fe', badgeText: '#0369a1' }, // Celeste Cielo
  { bg: '#f5f3ff', border: '#7c3aed', text: '#4c1d95', badgeBg: '#ede9fe', badgeText: '#5b21b6' }, // Violeta
  { bg: '#fefce8', border: '#ca8a04', text: '#713f12', badgeBg: '#fef08a', badgeText: '#854d0e' }, // Ocre Mostaza
  { bg: '#f0fdf4', border: '#16a34a', text: '#14532d', badgeBg: '#dcfce7', badgeText: '#15803d' }, // Verde Bosque
  { bg: '#f0fdfa', border: '#0d9488', text: '#134e4a', badgeBg: '#ccfbf1', badgeText: '#115e59' }, // Turquesa
  { bg: '#fff1f1', border: '#be123c', text: '#881337', badgeBg: '#ffe4e6', badgeText: '#9f1239' }, // Carmesí
];

function sessionCoversSlot(session, slot) {
  if (!session || !session.hIni || !session.hFi) return false;
  return session.hIni < slot.end && session.hFi > slot.start;
}

function buildDaySlotCells(slotDefinitions, daySessions) {
  const cells = slotDefinitions.map((slot) => {
    const session = daySessions.find((s) => sessionCoversSlot(s, slot)) || null;
    return {
      slot,
      session,
      subjectId: session?.assignatura?.codi || null,
      rowSpan: 1,
      isCovered: false,
    };
  });

  // Agrupación consecutiva tipo Excel
  for (let i = 0; i < cells.length; i++) {
    if (cells[i].isCovered) continue;
    if (!cells[i].session) continue;

    let span = 1;
    for (let j = i + 1; j < cells.length; j++) {
      if (cells[j].session && cells[j].subjectId === cells[i].subjectId) {
        span++;
        cells[j].isCovered = true;
      } else {
        break;
      }
    }
    cells[i].rowSpan = span;
  }

  return cells;
}

export default function RoomSchedulePopup({ room, onClose }) {
  const [scheduleData, setScheduleData] = useState(null);

  useEffect(() => {
    let isMounted = true;
    getRoomSchedule(room).then((result) => {
      if (isMounted) {
        setScheduleData(result.data);
      }
    });

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      isMounted = false;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [room, onClose]);

  // Asignación dinámica, única y determinista de colores por asignatura para este horario
  const subjectThemeMap = useMemo(() => {
    if (!scheduleData?.items) return {};

    // 1. Extraer identificadores únicos de las asignaturas presentes en este horario
    const uniqueSubjectIds = [];
    scheduleData.items.forEach((item) => {
      const key = item.assignatura?.codi || item.assignatura?.nom;
      if (key && !uniqueSubjectIds.includes(key)) {
        uniqueSubjectIds.push(key);
      }
    });

    // Ordenar canónicamente para que no dependa del orden de los registros
    uniqueSubjectIds.sort();

    // 2. Semilla determinista basada en el aula para que sea reproducible al abrir y cerrar
    let seed = 0;
    const roomStr = room || 'default-room';
    for (let i = 0; i < roomStr.length; i++) {
      seed = (seed << 5) - seed + roomStr.charCodeAt(i);
      seed |= 0;
    }
    seed = Math.abs(seed);

    // 3. Barajar pseudo-aleatoriamente la paleta según la semilla
    const paletteIndices = Array.from({ length: SUBJECT_THEMES.length }, (_, i) => i);
    let currentSeed = seed;
    const nextRand = () => {
      currentSeed = (currentSeed * 9301 + 49297) % 233280;
      return currentSeed / 233280;
    };

    for (let i = paletteIndices.length - 1; i > 0; i--) {
      const j = Math.floor(nextRand() * (i + 1));
      [paletteIndices[i], paletteIndices[j]] = [paletteIndices[j], paletteIndices[i]];
    }

    // 4. Asignar a cada asignatura del horario un color distinto del resto
    const mapping = {};
    uniqueSubjectIds.forEach((key, index) => {
      const themeIndex = paletteIndices[index % paletteIndices.length];
      mapping[key] = SUBJECT_THEMES[themeIndex];
    });

    return mapping;
  }, [scheduleData, room]);

  // Construcción de la matriz semanal (Lunes a Viernes)
  const weeklyGrid = useMemo(() => {
    if (!scheduleData?.items) return null;

    const grid = {};
    DAYS.forEach((day) => {
      const daySessions = scheduleData.items.filter((item) => item.dia === day.key);
      const morningCells = buildDaySlotCells(MORNING_SLOTS, daySessions);
      const afternoonCells = buildDaySlotCells(AFTERNOON_SLOTS, daySessions);
      grid[day.key] = {
        morning: morningCells,
        afternoon: afternoonCells,
      };
    });

    return grid;
  }, [scheduleData]);

  return (
    <div
      className="schedule-modal-backdrop"
      onClick={onClose}
      onWheel={(e) => {
        // Bloquea completamente la propagación del zoom al mapa de detrás
        e.stopPropagation();
      }}
      role="dialog"
      aria-modal="true"
      aria-label={`Horario semanal del aula ${room}`}
    >
      {/* Cajón central tipo Excel */}
      <div
        className="schedule-modal-dialog"
        onClick={(e) => e.stopPropagation()}
        onWheel={(e) => {
          e.stopPropagation();
        }}
      >
        {/* Cabecera del pop-up con botón de cierre X */}
        <div className="schedule-modal-header">
          <div className="modal-header-titles">
            <div className="modal-header-badge">Aula {room}</div>
            <h2 className="modal-title">Horario Semanal</h2>
            <span className="modal-subtitle">Lunes a Viernes • 08:30 a 21:00</span>
          </div>

          <button
            type="button"
            className="modal-close-x-btn"
            onClick={onClose}
            aria-label="Cerrar horario"
            title="Cerrar (Esc)"
          >
            ✕
          </button>
        </div>

        {/* Cajón contenedor responsivo de la tabla */}
        <div className="excel-table-scrollbox">
          {!weeklyGrid ? (
            <div className="modal-loading-box">
              <div className="excel-spinner"></div>
              <span>Cargando horario semanal del aula {room}...</span>
            </div>
          ) : (
            <table className="excel-schedule-table">
              <thead>
                <tr>
                  <th className="excel-th excel-th-time">Hora</th>
                  {DAYS.map((day) => (
                    <th key={day.key} className="excel-th excel-th-day">
                      {day.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {/* 1. TURNO MAÑANA: 08:30 A 14:30 */}
                {MORNING_SLOTS.map((slot, slotIdx) => (
                  <tr key={`morning-${slotIdx}`}>
                    <td className="excel-time-cell">{slot.label}</td>
                    {DAYS.map((day) => {
                      const cell = weeklyGrid[day.key].morning[slotIdx];
                      if (cell.isCovered) return null;

                      if (!cell.session) {
                        return (
                          <td key={day.key} className="excel-cell excel-cell-empty">
                            <span className="empty-text">—</span>
                          </td>
                        );
                      }

                      const s = cell.session;
                      const isMerged = cell.rowSpan > 1;
                      const subjectKey = s.assignatura?.codi || s.assignatura?.nom;
                      const theme = subjectThemeMap[subjectKey] || SUBJECT_THEMES[0];

                      return (
                        <td
                          key={day.key}
                          rowSpan={cell.rowSpan}
                          className={`excel-cell excel-cell-occupied ${isMerged ? 'is-merged-slot' : ''}`}
                          style={{
                            backgroundColor: theme.bg,
                            borderLeft: `4px solid ${theme.border}`,
                          }}
                        >
                          <div className="cell-content">
                            <div className="cell-subject-name" style={{ color: theme.text }}>
                              {s.assignatura?.nom}
                            </div>
                            <div className="cell-subline">
                              <span
                                className="cell-group-badge"
                                style={{ backgroundColor: theme.badgeBg, color: theme.badgeText }}
                              >
                                {s.grup?.grup}
                              </span>
                              <span className="cell-subject-code">Cód. {s.assignatura?.codi}</span>
                            </div>
                            {s.profes && s.profes[0] && (
                              <div className="cell-prof">{s.profes[0]}</div>
                            )}
                            {isMerged && (
                              <div
                                className="cell-merged-indicator"
                                style={{ backgroundColor: theme.badgeBg, color: theme.badgeText }}
                              >
                                {cell.rowSpan}h combinadas
                              </div>
                            )}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}

                {/* 2. FRANJA GRIS: 14:30 A 15:00 (PAUSA / ALMUERZO) */}
                <tr className="excel-pause-row">
                  <td className="excel-time-cell excel-pause-time">14:30 – 15:00</td>
                  <td colSpan="5" className="excel-pause-cell">
                    PAUSA / ALMUERZO
                  </td>
                </tr>

                {/* 3. TURNO TARDE: 15:00 A 21:00 */}
                {AFTERNOON_SLOTS.map((slot, slotIdx) => (
                  <tr key={`afternoon-${slotIdx}`}>
                    <td className="excel-time-cell">{slot.label}</td>
                    {DAYS.map((day) => {
                      const cell = weeklyGrid[day.key].afternoon[slotIdx];
                      if (cell.isCovered) return null;

                      if (!cell.session) {
                        return (
                          <td key={day.key} className="excel-cell excel-cell-empty">
                            <span className="empty-text">—</span>
                          </td>
                        );
                      }

                      const s = cell.session;
                      const isMerged = cell.rowSpan > 1;
                      const subjectKey = s.assignatura?.codi || s.assignatura?.nom;
                      const theme = subjectThemeMap[subjectKey] || SUBJECT_THEMES[0];

                      return (
                        <td
                          key={day.key}
                          rowSpan={cell.rowSpan}
                          className={`excel-cell excel-cell-occupied ${isMerged ? 'is-merged-slot' : ''}`}
                          style={{
                            backgroundColor: theme.bg,
                            borderLeft: `4px solid ${theme.border}`,
                          }}
                        >
                          <div className="cell-content">
                            <div className="cell-subject-name" style={{ color: theme.text }}>
                              {s.assignatura?.nom}
                            </div>
                            <div className="cell-subline">
                              <span
                                className="cell-group-badge"
                                style={{ backgroundColor: theme.badgeBg, color: theme.badgeText }}
                              >
                                {s.grup?.grup}
                              </span>
                              <span className="cell-subject-code">Cód. {s.assignatura?.codi}</span>
                            </div>
                            {s.profes && s.profes[0] && (
                              <div className="cell-prof">{s.profes[0]}</div>
                            )}
                            {isMerged && (
                              <div
                                className="cell-merged-indicator"
                                style={{ backgroundColor: theme.badgeBg, color: theme.badgeText }}
                              >
                                {cell.rowSpan}h combinadas
                              </div>
                            )}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
