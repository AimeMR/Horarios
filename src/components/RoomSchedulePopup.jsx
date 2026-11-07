import React, { useState, useEffect, useMemo } from 'react';
import { getRoomSchedule } from '../services/scheduleService';

// Franjas horarias base de 1 hora
const MORNING_SLOTS = [
  { start: '08:30', end: '09:30' },
  { start: '09:30', end: '10:30' },
  { start: '10:30', end: '11:30' },
  { start: '11:30', end: '12:30' },
  { start: '12:30', end: '13:30' },
  { start: '13:30', end: '14:30' },
];

const AFTERNOON_SLOTS = [
  { start: '15:00', end: '16:00' },
  { start: '16:00', end: '17:00' },
  { start: '17:00', end: '18:00' },
  { start: '18:00', end: '19:00' },
  { start: '19:00', end: '20:00' },
  { start: '20:00', end: '21:00' },
];

// Comprueba si una sesión del contrato cubre una franja de 1 hora
function sessionCoversSlot(session, slot) {
  if (!session || !session.hIni || !session.hFi) return false;
  return session.hIni < slot.end && session.hFi > slot.start;
}

// Algoritmo de agrupación: fusiona franjas consecutivas con la misma asignatura (mismo codi)
function groupConsecutiveSlots(slotDefinitions, sessionItems) {
  // 1. Asigna a cada franja su sesión correspondiente si existe
  const mappedSlots = slotDefinitions.map((slot) => {
    const matchingSession = sessionItems.find((s) => sessionCoversSlot(s, slot));
    return {
      ...slot,
      session: matchingSession || null,
      subjectId: matchingSession?.assignatura?.codi || null,
    };
  });

  // 2. Agrupa franjas consecutivas que compartan el mismo subjectId
  const blocks = [];
  let currentBlock = null;

  for (let i = 0; i < mappedSlots.length; i++) {
    const slot = mappedSlots[i];
    const isOccupied = Boolean(slot.session);
    const subjectId = slot.subjectId;

    if (!currentBlock) {
      currentBlock = {
        start: slot.start,
        end: slot.end,
        slotsCount: 1,
        isOccupied,
        subjectId,
        session: slot.session,
        slots: [slot],
      };
    } else {
      const isConsecutiveSameSubject =
        currentBlock.isOccupied &&
        isOccupied &&
        currentBlock.subjectId === subjectId;

      if (isConsecutiveSameSubject) {
        currentBlock.end = slot.end;
        currentBlock.slotsCount += 1;
        currentBlock.slots.push(slot);
      } else {
        blocks.push(currentBlock);
        currentBlock = {
          start: slot.start,
          end: slot.end,
          slotsCount: 1,
          isOccupied,
          subjectId,
          session: slot.session,
          slots: [slot],
        };
      }
    }
  }

  if (currentBlock) {
    blocks.push(currentBlock);
  }

  return blocks;
}

export default function RoomSchedulePopup({ room, date = '2026-11-07', onClose }) {
  const [scheduleData, setScheduleData] = useState(null);
  const [dataSource, setDataSource] = useState('loading');
  const [activeTab, setActiveTab] = useState('visual'); // 'visual' | 'json'
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let isMounted = true;
    setScheduleData(null);
    setDataSource('loading');

    getRoomSchedule(room, date).then((result) => {
      if (isMounted) {
        setScheduleData(result.data);
        setDataSource(result.source);
      }
    });

    return () => {
      isMounted = false;
    };
  }, [room, date]);

  // Agrupación visual de mañana y tarde con fusión consecutiva
  const morningBlocks = useMemo(() => {
    if (!scheduleData?.items) return [];
    return groupConsecutiveSlots(MORNING_SLOTS, scheduleData.items);
  }, [scheduleData]);

  const afternoonBlocks = useMemo(() => {
    if (!scheduleData?.items) return [];
    return groupConsecutiveSlots(AFTERNOON_SLOTS, scheduleData.items);
  }, [scheduleData]);

  // Resumen de ocupación
  const stats = useMemo(() => {
    if (!scheduleData?.items) return { occupiedHours: 0, totalHours: 12, freeHours: 12 };
    let occupied = 0;
    morningBlocks.forEach((b) => {
      if (b.isOccupied) occupied += b.slotsCount;
    });
    afternoonBlocks.forEach((b) => {
      if (b.isOccupied) occupied += b.slotsCount;
    });
    return {
      occupiedHours: occupied,
      totalHours: 12,
      freeHours: 12 - occupied,
    };
  }, [morningBlocks, afternoonBlocks, scheduleData]);

  const handleCopyJson = () => {
    if (!scheduleData) return;
    navigator.clipboard.writeText(JSON.stringify(scheduleData, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getTipusBadgeClass = (tipus) => {
    switch (tipus) {
      case 'TE':
        return 'badge-te';
      case 'PLAB':
        return 'badge-plab';
      case 'SEM':
        return 'badge-sem';
      default:
        return 'badge-default';
    }
  };

  return (
    <aside
      className="room-schedule-popup no-pan"
      aria-label={`Horario de la sala ${room}`}
    >
      {/* Cabecera del Pop-up */}
      <div className="popup-header">
        <div className="popup-title-area">
          <div className="popup-badge-row">
            <span className="popup-room-badge">Aula {room}</span>
            <span className="popup-date-badge">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                <line x1="16" y1="2" x2="16" y2="6"></line>
                <line x1="8" y1="2" x2="8" y2="6"></line>
                <line x1="3" y1="10" x2="21" y2="10"></line>
              </svg>
              {date}
            </span>
            {dataSource === 'mock-contract' && (
              <span className="popup-source-pill" title="Estructura garantizada según contracte-fase2.md">
                JSON Contract
              </span>
            )}
          </div>
          <h3 className="popup-title">Ocupación y Parrilla Horaria</h3>
        </div>

        <button
          type="button"
          className="popup-close-btn"
          onClick={onClose}
          aria-label="Cerrar ventana de horarios"
          title="Cerrar (Esc)"
        >
          ✕
        </button>
      </div>

      {/* Pestañas de Vista: Gráfico vs JSON backend */}
      <div className="popup-tabs-bar">
        <div className="popup-tabs">
          <button
            type="button"
            className={`popup-tab-btn ${activeTab === 'visual' ? 'active' : ''}`}
            onClick={() => setActiveTab('visual')}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="7" height="7"></rect>
              <rect x="14" y="3" width="7" height="7"></rect>
              <rect x="14" y="14" width="7" height="7"></rect>
              <rect x="3" y="14" width="7" height="7"></rect>
            </svg>
            Parrilla Visual
          </button>
          <button
            type="button"
            className={`popup-tab-btn ${activeTab === 'json' ? 'active' : ''}`}
            onClick={() => setActiveTab('json')}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="16 18 22 12 16 6"></polyline>
              <polyline points="8 6 2 12 8 18"></polyline>
            </svg>
            JSON Contrato (Fase 2)
          </button>
        </div>

        {activeTab === 'visual' && (
          <div className="popup-stats-summary">
            <span className="stat-pill stat-occupied">
              {stats.occupiedHours}h ocupadas
            </span>
            <span className="stat-pill stat-free">
              {stats.freeHours}h libres
            </span>
          </div>
        )}
      </div>

      {/* CUERPO DEL POP-UP */}
      <div className="popup-body">
        {dataSource === 'loading' ? (
          <div className="popup-loading">
            <div className="loading-spinner"></div>
            <span>Cargando datos de parrilla para el aula {room}...</span>
          </div>
        ) : activeTab === 'visual' ? (
          <div className="schedule-timeline">
            {/* SECCIÓN MAÑANA (08:30 a 14:30) */}
            <div className="timeline-section">
              <div className="section-divider">
                <span className="section-title">Turno Mañana (08:30 – 14:30)</span>
                <span className="section-span">6 franjas de 1h</span>
              </div>

              <div className="slots-list">
                {morningBlocks.map((block, idx) => (
                  <SlotCard key={`morning-${idx}`} block={block} getTipusBadgeClass={getTipusBadgeClass} />
                ))}
              </div>
            </div>

            {/* FRANJA GRIS: 14:30 A 15:00 (PAUSA / ALMUERZO) */}
            <div className="pause-break-slot" role="region" aria-label="Franja de pausa del mediodía">
              <div className="pause-icon-container">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 8h1a4 4 0 0 1 0 8h-1"></path>
                  <path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z"></path>
                  <line x1="6" y1="1" x2="6" y2="4"></line>
                  <line x1="10" y1="1" x2="10" y2="4"></line>
                  <line x1="14" y1="1" x2="14" y2="4"></line>
                </svg>
              </div>
              <div className="pause-info">
                <div className="pause-time">14:30 – 15:00</div>
                <div className="pause-text">Franja de Pausa / Almuerzo e Intercambio de Turnos</div>
              </div>
              <span className="pause-badge">Sin actividad</span>
            </div>

            {/* SECCIÓN TARDE (15:00 a 21:00) */}
            <div className="timeline-section">
              <div className="section-divider">
                <span className="section-title">Turno Tarde (15:00 – 21:00)</span>
                <span className="section-span">6 franjas de 1h</span>
              </div>

              <div className="slots-list">
                {afternoonBlocks.map((block, idx) => (
                  <SlotCard key={`afternoon-${idx}`} block={block} getTipusBadgeClass={getTipusBadgeClass} />
                ))}
              </div>
            </div>
          </div>
        ) : (
          /* PESTAÑA: JSON EXACTO DEL CONTRATO */
          <div className="json-contract-view">
            <div className="json-toolbar">
              <span className="json-meta-info">
                Endpoint: <code>GET /versions/1/parrilla?aula={room}</code>
              </span>
              <button
                type="button"
                className="button-sm copy-json-btn"
                onClick={handleCopyJson}
              >
                {copied ? '✓ ¡Copiado!' : 'Copiar JSON'}
              </button>
            </div>
            <pre className="json-code-box">
              <code>{JSON.stringify(scheduleData, null, 2)}</code>
            </pre>
          </div>
        )}
      </div>
    </aside>
  );
}

// Subcomponente de tarjeta de franja / bloque unificado
function SlotCard({ block, getTipusBadgeClass }) {
  const { start, end, slotsCount, isOccupied, session } = block;
  const isMerged = slotsCount > 1;

  if (!isOccupied) {
    return (
      <div className="slot-card is-free">
        <div className="slot-time-col">
          <span className="slot-start">{start}</span>
          <span className="slot-time-sep">↓</span>
          <span className="slot-end">{end}</span>
          <span className="slot-dur-badge">1h</span>
        </div>
        <div className="slot-content is-empty">
          <div className="empty-indicator">
            <span className="empty-dot"></span>
            <span className="empty-label">Espacio disponible</span>
          </div>
          <span className="empty-subtext">Sin docencia asignada en esta franja</span>
        </div>
      </div>
    );
  }

  const { assignatura, grup, profes, cohorts, alumnes } = session;

  return (
    <div className={`slot-card is-occupied ${isMerged ? 'is-merged-block' : ''}`}>
      {/* Columna Horaria con indicador de fusión */}
      <div className="slot-time-col">
        <span className="slot-start">{start}</span>
        <span className="slot-time-sep">↓</span>
        <span className="slot-end">{end}</span>
        <span className="slot-dur-badge">
          {slotsCount}h {isMerged ? 'juntas' : ''}
        </span>
      </div>

      {/* Contenido de la Asignatura */}
      <div className="slot-content">
        <div className="slot-card-header">
          <div className="slot-subject-title">
            <span className="subject-name">{assignatura?.nom || 'Sin nombre'}</span>
            <span className="subject-code">Cód. {assignatura?.codi}</span>
          </div>
          {isMerged && (
            <span className="merged-tag" title="Franjas consecutivas unificadas visualmente">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polyline points="7 13 12 18 17 13"></polyline>
                <polyline points="7 6 12 11 17 6"></polyline>
              </svg>
              {slotsCount}h consecutivas
            </span>
          )}
        </div>

        <div className="slot-card-meta">
          {/* Grupo y Tipo */}
          <span className={`meta-pill ${getTipusBadgeClass(grup?.tipus)}`}>
            {grup?.grup || 'Grup'} ({grup?.tipus || 'TE'})
          </span>

          {/* Titulación / Cohorte */}
          {cohorts && cohorts.length > 0 && (
            <span className="meta-pill badge-cohort">
              {cohorts.join(', ')}
            </span>
          )}

          {/* Alumnos */}
          {alumnes !== undefined && (
            <span className="meta-pill badge-neutral">
              👤 {alumnes} alumnos
            </span>
          )}
        </div>

        {/* Docente / Profesores */}
        {profes && profes.length > 0 && (
          <div className="slot-prof-row">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
              <circle cx="12" cy="7" r="4"></circle>
            </svg>
            <span className="prof-name">{profes.join(', ')}</span>
          </div>
        )}
      </div>
    </div>
  );
}

