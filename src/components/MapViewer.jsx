import React, { useState, useRef, useEffect, useCallback } from 'react';
import Floor0Svg from './Floor0Svg';
import Floor1Svg from './Floor1Svg';
import Floor2Svg from './Floor2Svg';
import Floor3Svg from './Floor3Svg';
import RoomSchedulePopup from './RoomSchedulePopup';

export default function MapViewer({
  currentFloor,
  selectedRoom,
  onSelectRoom,
  filters,
  appliedFilters,
  matchingRooms = []
}) {
  const [zoom, setZoom] = useState(1.0);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);

  const containerRef = useRef(null);
  const isDraggingRef = useRef(false);
  const dragStartRef = useRef({ x: 0, y: 0, panX: 0, panY: 0 });
  const hasMovedRef = useRef(false);
  const pendingRoomTargetRef = useRef(null);

  const MIN_ZOOM = 0.4;
  const MAX_ZOOM = 5.0;
  const ZOOM_STEP = 0.25;

  // Reset zoom & pan al cambiar de piso
  useEffect(() => {
    setZoom(1.0);
    setPan({ x: 0, y: 0 });
  }, [currentFloor]);

  // ==========================================================================
  // 1. ZOOM CON LA RUEDA DEL RATÓN (EXCLUSIVO DEL MAPA)
  // ==========================================================================
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleWheel = (e) => {
      // Si el pop-up de horarios está abierto o el ratón está sobre el modal, NO aplicar zoom al mapa
      if (
        selectedRoom ||
        e.target.closest('.schedule-modal-backdrop') ||
        e.target.closest('.schedule-modal-dialog') ||
        e.target.closest('.no-pan')
      ) {
        return;
      }

      // Bloquea completamente el scroll de la página web
      e.preventDefault();

      const rect = container.getBoundingClientRect();
      const mouseX = e.clientX - rect.left - rect.width / 2;
      const mouseY = e.clientY - rect.top - rect.height / 2;

      const factor = e.deltaY < 0 ? 1.15 : 0.87;

      setZoom((prevZoom) => {
        const nextZoom = Math.min(Math.max(prevZoom * factor, MIN_ZOOM), MAX_ZOOM);
        const ratio = nextZoom / prevZoom;

        // Ajusta el pan focalizado en la posición del ratón
        setPan((prevPan) => ({
          x: mouseX - (mouseX - prevPan.x) * ratio,
          y: mouseY - (mouseY - prevPan.y) * ratio,
        }));

        return nextZoom;
      });
    };

    container.addEventListener('wheel', handleWheel, { passive: false });
    return () => container.removeEventListener('wheel', handleWheel);
  }, [selectedRoom]);

  // ==========================================================================
  // 2. ARRASTRE Y DESPLAZAMIENTO (PAN & DRAG) CON CLIC ROBUSTO
  // ==========================================================================
  const handlePointerDown = (e) => {
    if (e.button !== 0) return; // Solo clic primario
    if (e.target.closest('.no-pan') || e.target.closest('.room-schedule-popup')) return;

    // Detectar si el usuario presionó sobre un aula
    const roomEl = e.target.closest('.room') || e.target.closest('[data-room]');
    pendingRoomTargetRef.current = roomEl?.getAttribute('data-room') || null;

    isDraggingRef.current = true;
    hasMovedRef.current = false;
    dragStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      panX: pan.x,
      panY: pan.y,
    };
  };

  const handlePointerMove = (e) => {
    if (!isDraggingRef.current) return;

    const dx = e.clientX - dragStartRef.current.x;
    const dy = e.clientY - dragStartRef.current.y;

    // Solo si el ratón se desplaza más de 5px se considera arrastre
    if (!hasMovedRef.current && (Math.abs(dx) > 5 || Math.abs(dy) > 5)) {
      hasMovedRef.current = true;
      pendingRoomTargetRef.current = null; // Si arrastró, se anula la selección
      setIsPanning(true);
      try {
        if (!e.currentTarget.hasPointerCapture(e.pointerId)) {
          e.currentTarget.setPointerCapture(e.pointerId);
        }
      } catch (_) { }
    }

    if (hasMovedRef.current) {
      setPan({
        x: dragStartRef.current.panX + dx,
        y: dragStartRef.current.panY + dy,
      });
    }
  };

  const handlePointerUp = (e) => {
    if (!isDraggingRef.current) return;
    const wasDragging = hasMovedRef.current;
    const clickedRoom = pendingRoomTargetRef.current;

    isDraggingRef.current = false;
    hasMovedRef.current = false;
    setIsPanning(false);
    pendingRoomTargetRef.current = null;

    try {
      if (e.currentTarget.hasPointerCapture(e.pointerId)) {
        e.currentTarget.releasePointerCapture(e.pointerId);
      }
    } catch (_) { }

    // Si fue un clic simple sin arrastrar sobre un aula, abrir de inmediato
    if (!wasDragging && clickedRoom) {
      onSelectRoom(clickedRoom);
    }
  };

  // Doble clic para zoom rápido en un punto
  const handleDoubleClick = (e) => {
    if (e.target.closest('.no-pan') || e.target.closest('.room-schedule-popup')) return;

    const rect = containerRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left - rect.width / 2;
    const mouseY = e.clientY - rect.top - rect.height / 2;

    setZoom((prevZoom) => {
      const targetZoom = prevZoom < 2.0 ? prevZoom * 1.6 : 1.0;
      const ratio = targetZoom / prevZoom;

      setPan((prevPan) => ({
        x: mouseX - (mouseX - prevPan.x) * ratio,
        y: mouseY - (mouseY - prevPan.y) * ratio,
      }));

      return targetZoom;
    });
  };

  // Clic en un aula (discriminando si el usuario estaba arrastrando)
  const handleRoomSelect = useCallback((roomId, e) => {
    if (e) e.stopPropagation();
    if (!hasMovedRef.current) {
      onSelectRoom(roomId);
    }
  }, [onSelectRoom]);

  // Clic en fondo neutro del mapa para deseleccionar aula
  const handleBackgroundClick = (e) => {
    if (hasMovedRef.current) return;
    if (
      e.target.closest('.room') ||
      e.target.closest('[data-room]') ||
      e.target.closest('.no-pan') ||
      e.target.closest('.room-schedule-popup')
    ) {
      return;
    }
    onSelectRoom(null);
  };

  // ==========================================================================
  // 3. CONTROLES DE ZOOM MANUALES
  // ==========================================================================
  const handleZoomIn = () => {
    setZoom((prev) => Math.min(prev + ZOOM_STEP, MAX_ZOOM));
  };

  const handleZoomOut = () => {
    setZoom((prev) => Math.max(prev - ZOOM_STEP, MIN_ZOOM));
  };

  const handleResetZoom = () => {
    setZoom(1.0);
    setPan({ x: 0, y: 0 });
  };

  return (
    <section className="map-viewport-section">
      <div
        ref={containerRef}
        id="map-container"
        className={`map-frame ${isPanning ? 'is-panning' : ''} ${zoom > 1.05 ? 'is-zoomed' : ''}`}
        tabIndex={0}
        aria-label="Lienzo interactivo del plano"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        onDoubleClick={handleDoubleClick}
        onClick={handleBackgroundClick}
        onDragStart={(e) => e.preventDefault()}
      >
        {/* Lienzo del plano con Transformación de Zoom y Pan */}
        <div
          className="map-canvas-viewport"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transition: isDraggingRef.current ? 'none' : 'transform 0.16s cubic-bezier(0.16, 1, 0.3, 1)',
          }}
        >
          {currentFloor === 0 && (
            <Floor0Svg
              selectedRoom={selectedRoom}
              onSelectRoom={handleRoomSelect}
              matchingRooms={matchingRooms}
            />
          )}
          {currentFloor === 1 && (
            <Floor1Svg
              selectedRoom={selectedRoom}
              onSelectRoom={handleRoomSelect}
              matchingRooms={matchingRooms}
            />
          )}
          {currentFloor === 2 && (
            <Floor2Svg
              selectedRoom={selectedRoom}
              onSelectRoom={handleRoomSelect}
              matchingRooms={matchingRooms}
            />
          )}
          {currentFloor === 3 && (
            <Floor3Svg
              selectedRoom={selectedRoom}
              onSelectRoom={handleRoomSelect}
              matchingRooms={matchingRooms}
            />
          )}
        </div>

        {/* Barra Flotante de Controles de Zoom */}
        <div className="map-zoom-toolbar no-pan" role="toolbar" aria-label="Controles de zoom">
          <button
            type="button"
            className="zoom-btn"
            onClick={handleZoomIn}
            title="Acercar mapa (+)"
            aria-label="Acercar mapa"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
          </button>

          <button
            type="button"
            className="zoom-btn zoom-level-btn"
            onClick={handleResetZoom}
            title="Restablecer zoom al 100%"
            aria-label="Restablecer zoom"
          >
            <span>{Math.round(zoom * 100)}%</span>
          </button>

          <button
            type="button"
            className="zoom-btn"
            onClick={handleZoomOut}
            title="Alejar mapa (-)"
            aria-label="Alejar mapa"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round">
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
          </button>

          <button
            type="button"
            className="zoom-btn"
            onClick={handleResetZoom}
            title="Ajustar y centrar plano"
            aria-label="Ajustar plano"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path>
            </svg>
          </button>
        </div>

        {/* Indicador de arrastre */}
        <div className="map-pan-hint">
          <span>Rueda para zoom • Arrastra para moverte por el plano</span>
        </div>

        {/* Pop-up modal de horarios semanales (centrado en pantalla, estilo tabla Excel) */}
        {selectedRoom && (
          <RoomSchedulePopup
            room={selectedRoom}
            onClose={() => onSelectRoom(null)}
            appliedFilters={appliedFilters}
          />
        )}
      </div>
    </section>
  );
}

