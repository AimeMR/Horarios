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

function sessionCoversSlot(session, slot) {
  if (!session || !session.hIni || !session.hFi) return false;
  return session.hIni < slot.end && session.hFi > slot.start;
}

// Procesa una lista de franjas para un día calculando fusiones consecutivas (rowSpan)
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

  // Agrupación consecutiva: si comparten el mismo subjectId, se fusionan como en Excel
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

  const getCellTypeClass = (tipus) => {
    switch (tipus) {
      case 'TE':
        return 'cell-type-te';
      case 'PLAB':
        return 'cell-type-plab';
      case 'SEM':
        return 'cell-type-sem';
      default:
        return 'cell-type-default';
    }
  };

  return (
    <div
      className="schedule-modal-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`Horario semanal del aula ${room}`}
    >
      {/* Cajón central tipo Excel */}
      <div
        className="schedule-modal-dialog"
        onClick={(e) => e.stopPropagation()}
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

        {/* Cajón contenedor de la tabla Excel */}
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
                      if (cell.isCovered) return null; // Omitir celda cubierta por rowSpan superior

                      if (!cell.session) {
                        return (
                          <td key={day.key} className="excel-cell excel-cell-empty">
                            <span className="empty-text">—</span>
                          </td>
                        );
                      }

                      const s = cell.session;
                      const isMerged = cell.rowSpan > 1;

                      return (
                        <td
                          key={day.key}
                          rowSpan={cell.rowSpan}
                          className={`excel-cell excel-cell-occupied ${getCellTypeClass(s.grup?.tipus)} ${
                            isMerged ? 'is-merged-slot' : ''
                          }`}
                        >
                          <div className="cell-content">
                            <div className="cell-subject-name">{s.assignatura?.nom}</div>
                            <div className="cell-subline">
                              <span className="cell-group-badge">{s.grup?.grup}</span>
                              <span className="cell-subject-code">Cód. {s.assignatura?.codi}</span>
                            </div>
                            {s.profes && s.profes[0] && (
                              <div className="cell-prof">{s.profes[0]}</div>
                            )}
                            {isMerged && (
                              <div className="cell-merged-indicator">
                                {cell.rowSpan} horas combinadas
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

                      return (
                        <td
                          key={day.key}
                          rowSpan={cell.rowSpan}
                          className={`excel-cell excel-cell-occupied ${getCellTypeClass(s.grup?.tipus)} ${
                            isMerged ? 'is-merged-slot' : ''
                          }`}
                        >
                          <div className="cell-content">
                            <div className="cell-subject-name">{s.assignatura?.nom}</div>
                            <div className="cell-subline">
                              <span className="cell-group-badge">{s.grup?.grup}</span>
                              <span className="cell-subject-code">Cód. {s.assignatura?.codi}</span>
                            </div>
                            {s.profes && s.profes[0] && (
                              <div className="cell-prof">{s.profes[0]}</div>
                            )}
                            {isMerged && (
                              <div className="cell-merged-indicator">
                                {cell.rowSpan} horas combinadas
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
