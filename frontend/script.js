/**
 * VISOR DE PLANOS - INTERACTIVIDAD DEL ESQUELETO VISUAL
 * 
 * Funcionalidades:
 * 1. Sistema de Zoom y Pan exclusivamente en el mapa (Rueda, botones +, -, reset, arrastre y doble clic).
 * 2. Filtros de barra lateral como desplegables colapsables (accordions) con sincronización en tiempo real.
 * 3. Selección y feedback interactivo de aulas (<rect> y <g class="room">).
 * 4. Navegación fluida entre los 3 pisos.
 */

document.addEventListener('DOMContentLoaded', () => {
  // ==========================================================================
  // ESTADO GENERAL
  // ==========================================================================
  let currentFloor = 1;
  const TOTAL_FLOORS = 3;
  let selectedRoom = null;

  // Estado del Zoom y Pan (exclusivo para el mapa)
  let zoom = 1.0;
  let panX = 0;
  let panY = 0;
  const MIN_ZOOM = 0.5;
  const MAX_ZOOM = 4.0;
  const ZOOM_STEP = 0.25;

  const floorDescriptions = {
    1: 'Piso 1 — Bloques Q1-Q6, Ala Central (QC) & Ala Sur (QP)',
    2: 'Piso 2 — Laboratorios, Biblioteca & Aulas 201-203',
    3: 'Piso 3 — Área Docente, Despachos & Terraza'
  };

  // Cache para los SVGs cargados
  const svgCache = {};

  // ==========================================================================
  // ELEMENTOS DEL DOM
  // ==========================================================================
  const workspaceLayout = document.querySelector('.workspace-layout');
  const toggleSidebarBtn = document.getElementById('toggle-sidebar-btn');
  const closeSidebarBtn = document.getElementById('close-sidebar-btn');

  // Pisos
  const prevFloorBtn = document.getElementById('prev-floor-btn');
  const nextFloorBtn = document.getElementById('next-floor-btn');
  const floorPills = document.querySelectorAll('.floor-pill');
  const currentFloorTitle = document.getElementById('current-floor-title');
  const headerFloorLabel = document.getElementById('header-floor-label');

  // Mapa y Zoom
  const mapContainer = document.getElementById('map-container');
  const mapCanvasViewport = document.getElementById('map-canvas-viewport');
  const zoomInBtn = document.getElementById('zoom-in-btn');
  const zoomOutBtn = document.getElementById('zoom-out-btn');
  const zoomResetBtn = document.getElementById('zoom-reset-btn');
  const zoomFitBtn = document.getElementById('zoom-fit-btn');
  const zoomPercentage = document.getElementById('zoom-percentage');

  // Filtros de barra lateral (Desplegables)
  const filterForm = document.getElementById('filter-form');
  const filterDateInput = document.getElementById('filter-date');
  const filterDatePreset = document.getElementById('filter-date-preset');
  const filterClassSelect = document.getElementById('filter-class');
  const filterGroupSelect = document.getElementById('filter-group');
  const filterCourseSelect = document.getElementById('filter-course');
  const resetBtn = document.getElementById('reset-filters-btn');

  // Badges resumen de los desplegables
  const badgeDate = document.getElementById('badge-date');
  const badgeClass = document.getElementById('badge-class');
  const badgeGroup = document.getElementById('badge-group');
  const badgeCourse = document.getElementById('badge-course');

  // ==========================================================================
  // 1. SISTEMA DE ZOOM Y PAN (EXCLUSIVO DEL MAPA)
  // ==========================================================================
  function applyTransform(animate = true) {
    if (!mapCanvasViewport) return;
    mapCanvasViewport.style.transition = animate 
      ? 'transform 0.16s cubic-bezier(0.16, 1, 0.3, 1)' 
      : 'none';
    mapCanvasViewport.style.transform = `translate(${panX}px, ${panY}px) scale(${zoom})`;

    if (zoomPercentage) {
      zoomPercentage.textContent = `${Math.round(zoom * 100)}%`;
    }

    if (mapContainer) {
      if (zoom > 1.05) {
        mapContainer.classList.add('is-zoomed');
      } else {
        mapContainer.classList.remove('is-zoomed');
      }
    }
  }

  function setZoom(newZoom, focalX = 0, focalY = 0) {
    const clampedZoom = Math.min(Math.max(newZoom, MIN_ZOOM), MAX_ZOOM);
    if (clampedZoom === zoom) return;

    // Zoom focalizado en la posición del ratón
    if (focalX !== 0 || focalY !== 0) {
      const scaleChange = clampedZoom / zoom;
      panX = focalX - (focalX - panX) * scaleChange;
      panY = focalY - (focalY - panY) * scaleChange;
    }

    zoom = clampedZoom;
    applyTransform(true);
  }

  function zoomIn() {
    setZoom(zoom + ZOOM_STEP);
  }

  function zoomOut() {
    setZoom(zoom - ZOOM_STEP);
  }

  function resetZoom() {
    zoom = 1.0;
    panX = 0;
    panY = 0;
    applyTransform(true);
  }

  zoomInBtn?.addEventListener('click', zoomIn);
  zoomOutBtn?.addEventListener('click', zoomOut);
  zoomResetBtn?.addEventListener('click', resetZoom);
  zoomFitBtn?.addEventListener('click', resetZoom);

  // Zoom con la rueda del ratón (INTERCEPTADO SOLO EN EL MAPA)
  mapContainer?.addEventListener('wheel', (e) => {
    // Evita el scroll global de la página web
    e.preventDefault();

    const rect = mapContainer.getBoundingClientRect();
    const mouseX = e.clientX - rect.left - rect.width / 2;
    const mouseY = e.clientY - rect.top - rect.height / 2;

    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
    setZoom(zoom * zoomFactor, mouseX, mouseY);
  }, { passive: false });

  // Arrastre y desplazamiento (Pan) al hacer clic y mover
  let isDragging = false;
  let hasMoved = false;
  let startClientX = 0;
  let startClientY = 0;
  let initialPanX = 0;
  let initialPanY = 0;

  mapContainer?.addEventListener('mousedown', (e) => {
    if (e.button !== 0) return; // Solo clic izquierdo
    // Si hace clic en la barra flotante de zoom o banner, no inicia arrastre
    if (e.target.closest('.map-zoom-toolbar') || e.target.closest('.selected-room-banner')) {
      return;
    }

    isDragging = true;
    hasMoved = false;
    startClientX = e.clientX;
    startClientY = e.clientY;
    initialPanX = panX;
    initialPanY = panY;
    mapCanvasViewport.style.transition = 'none';
  });

  window.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    const deltaX = e.clientX - startClientX;
    const deltaY = e.clientY - startClientY;

    if (Math.abs(deltaX) > 4 || Math.abs(deltaY) > 4) {
      hasMoved = true;
      mapContainer?.classList.add('is-panning');
    }

    panX = initialPanX + deltaX;
    panY = initialPanY + deltaY;
    applyTransform(false);
  });

  window.addEventListener('mouseup', () => {
    if (isDragging) {
      isDragging = false;
      mapContainer?.classList.remove('is-panning');
      mapCanvasViewport.style.transition = '';
    }
  });

  // Doble clic sobre el plano para hacer zoom rápido hacia esa zona
  mapContainer?.addEventListener('dblclick', (e) => {
    if (e.target.closest('.map-zoom-toolbar') || e.target.closest('.selected-room-banner')) return;
    const rect = mapContainer.getBoundingClientRect();
    const mouseX = e.clientX - rect.left - rect.width / 2;
    const mouseY = e.clientY - rect.top - rect.height / 2;
    setZoom(zoom < 2.0 ? zoom * 1.6 : 1.0, mouseX, mouseY);
  });

  // ==========================================================================
  // 2. CONTROL DE LA BARRA LATERAL Y DESPLEGABLES
  // ==========================================================================
  function toggleSidebar() {
    workspaceLayout.classList.toggle('sidebar-collapsed');
  }

  function closeSidebar() {
    workspaceLayout.classList.add('sidebar-collapsed');
  }

  toggleSidebarBtn?.addEventListener('click', toggleSidebar);
  closeSidebarBtn?.addEventListener('click', closeSidebar);

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
      e.preventDefault();
      toggleSidebar();
    } else if (e.key === 'Escape' && !workspaceLayout.classList.contains('sidebar-collapsed')) {
      closeSidebar();
    }
  });

  // Sincronización de los desplegables de filtros con sus etiquetas resumen (Badges)
  function updateFilterBadges() {
    // 1. Fecha
    if (filterDatePreset && filterDateInput && badgeDate) {
      if (filterDatePreset.value === 'today') {
        badgeDate.textContent = 'Hoy';
        badgeDate.classList.remove('is-active');
      } else if (filterDatePreset.value === 'tomorrow') {
        badgeDate.textContent = 'Mañana';
        badgeDate.classList.add('is-active');
      } else if (filterDatePreset.value === 'monday') {
        badgeDate.textContent = 'Lunes';
        badgeDate.classList.add('is-active');
      } else {
        const parts = filterDateInput.value.split('-');
        badgeDate.textContent = parts.length === 3 ? `${parts[2]}/${parts[1]}` : 'Fecha';
        badgeDate.classList.add('is-active');
      }
    }

    // 2. Clase
    if (filterClassSelect && badgeClass) {
      if (filterClassSelect.value) {
        badgeClass.textContent = filterClassSelect.value;
        badgeClass.classList.add('is-active');
      } else {
        badgeClass.textContent = 'Todas';
        badgeClass.classList.remove('is-active');
      }
    }

    // 3. Grupo
    if (filterGroupSelect && badgeGroup) {
      if (filterGroupSelect.value) {
        const txt = filterGroupSelect.options[filterGroupSelect.selectedIndex].text.split(' ')[0];
        badgeGroup.textContent = txt;
        badgeGroup.classList.add('is-active');
      } else {
        badgeGroup.textContent = 'Todos';
        badgeGroup.classList.remove('is-active');
      }
    }

    // 4. Curso
    if (filterCourseSelect && badgeCourse) {
      if (filterCourseSelect.value) {
        const txt = filterCourseSelect.options[filterCourseSelect.selectedIndex].text;
        badgeCourse.textContent = txt.split(' ')[0];
        badgeCourse.classList.add('is-active');
      } else {
        badgeCourse.textContent = 'Todos';
        badgeCourse.classList.remove('is-active');
      }
    }
  }

  // Preselección rápida de fechas
  filterDatePreset?.addEventListener('change', (e) => {
    const val = e.target.value;
    const today = new Date('2026-11-07T12:00:00'); // Fecha base de trabajo

    if (val === 'today') {
      filterDateInput.value = '2026-11-07';
    } else if (val === 'tomorrow') {
      const tomorrow = new Date(today);
      tomorrow.setDate(today.getDate() + 1);
      filterDateInput.value = tomorrow.toISOString().split('T')[0];
    } else if (val === 'monday') {
      const monday = new Date(today);
      monday.setDate(today.getDate() + 2); // 9 de Noviembre
      filterDateInput.value = monday.toISOString().split('T')[0];
    }
    updateFilterBadges();
  });

  filterDateInput?.addEventListener('change', () => {
    if (filterDatePreset) filterDatePreset.value = 'custom';
    updateFilterBadges();
  });

  filterGroupSelect?.addEventListener('change', updateFilterBadges);
  filterCourseSelect?.addEventListener('change', updateFilterBadges);

  // ==========================================================================
  // 3. SELECCIÓN INTERACTIVA DE AULAS Y RECTÁNGULOS
  // ==========================================================================
  function showSelectedRoomBanner(roomId) {
    let banner = document.getElementById('selected-room-banner');
    if (!roomId) {
      if (banner) banner.remove();
      return;
    }

    if (!banner) {
      banner = document.createElement('div');
      banner.id = 'selected-room-banner';
      banner.className = 'selected-room-banner';
      mapContainer.appendChild(banner);
    }

    banner.innerHTML = `
      <span class="banner-dot"></span>
      <span>Espacio seleccionado: <strong class="banner-code">${roomId}</strong></span>
    `;
  }

  function selectRoom(roomId, triggerSource = 'map') {
    selectedRoom = roomId;

    const svg = mapCanvasViewport?.querySelector('svg');
    if (svg) {
      const allRooms = svg.querySelectorAll('.room, [data-room]');
      allRooms.forEach(r => r.classList.remove('is-selected'));

      if (roomId) {
        const target = svg.querySelector(`.room[data-room="${roomId}"], [data-room="${roomId}"]`);
        if (target) {
          target.classList.add('is-selected');
        }
      }
    }

    if (filterClassSelect && triggerSource !== 'select') {
      filterClassSelect.value = roomId || '';
    }

    updateFilterBadges();
    showSelectedRoomBanner(roomId);
  }

  filterClassSelect?.addEventListener('change', (e) => {
    selectRoom(e.target.value, 'select');
  });

  function bindSvgRoomInteractions(svgElement) {
    if (!svgElement) return;

    const rooms = svgElement.querySelectorAll('.room, [data-room]');

    rooms.forEach(room => {
      const roomId = room.getAttribute('data-room') || room.id;
      if (!roomId) return;

      room.style.cursor = 'pointer';

      room.addEventListener('click', (e) => {
        // Si el usuario estaba arrastrando/paneando el plano, no cuenta como selección
        if (hasMoved) return;
        e.stopPropagation();
        selectRoom(roomId, 'map');
      });

      room.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          selectRoom(roomId, 'map');
        }
      });
    });

    // Clic en fondo neutro para desmarcar
    svgElement.addEventListener('click', (e) => {
      if (hasMoved) return;
      if (!e.target.closest('.room') && !e.target.closest('[data-room]')) {
        selectRoom(null, 'map');
      }
    });

    if (selectedRoom) {
      selectRoom(selectedRoom, 'map');
    }
  }

  // ==========================================================================
  // 4. CARGA DINÁMICA DEL MAPA SVG
  // ==========================================================================
  async function loadFloorSvg(floor) {
    const url = `maps/piso-${floor}.svg`;

    try {
      let svgText = svgCache[floor];
      if (!svgText) {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        svgText = await res.text();
        svgCache[floor] = svgText;
      }

      if (mapCanvasViewport) {
        mapCanvasViewport.innerHTML = svgText;
        const injectedSvg = mapCanvasViewport.querySelector('svg');
        if (injectedSvg) {
          injectedSvg.classList.add('map-svg-render');
          bindSvgRoomInteractions(injectedSvg);
        }
      }
    } catch (err) {
      console.warn('Fallback a object/embed para el mapa SVG:', err);
      if (mapCanvasViewport) {
        mapCanvasViewport.innerHTML = `
          <object id="active-floor-object" type="image/svg+xml" data="${url}" class="map-svg-render">
            <img src="${url}" alt="Plano Piso ${floor}" class="map-svg-render" />
          </object>
        `;

        const obj = document.getElementById('active-floor-object');
        obj?.addEventListener('load', () => {
          try {
            const doc = obj.contentDocument;
            if (doc) {
              const innerSvg = doc.querySelector('svg');
              bindSvgRoomInteractions(innerSvg);
            }
          } catch (e) {
            console.warn('No se pudo acceder a contentDocument:', e);
          }
        });
      }
    }

    if (selectedRoom) {
      showSelectedRoomBanner(selectedRoom);
    }
  }

  window.addEventListener('message', (event) => {
    if (event.data && (event.data.type === 'ROOM_SELECTED' || event.data.type === 'FLOOR_ROOM_CLICK')) {
      if (event.data.roomId) {
        selectRoom(event.data.roomId, 'map');
      }
    }
  });

  // ==========================================================================
  // 5. NAVEGACIÓN ENTRE PISOS
  // ==========================================================================
  function updateFloorUI(floor) {
    currentFloor = floor;

    prevFloorBtn.disabled = currentFloor <= 1;
    nextFloorBtn.disabled = currentFloor >= TOTAL_FLOORS;

    floorPills.forEach((pill) => {
      const pillFloor = parseInt(pill.getAttribute('data-floor'), 10);
      if (pillFloor === currentFloor) {
        pill.classList.add('active');
        pill.setAttribute('aria-current', 'page');
      } else {
        pill.classList.remove('active');
        pill.removeAttribute('aria-current');
      }
    });

    if (currentFloorTitle) {
      currentFloorTitle.textContent = floorDescriptions[currentFloor] || `Piso ${currentFloor}`;
    }
    if (headerFloorLabel) {
      headerFloorLabel.textContent = `Planta ${currentFloor}`;
    }

    // Restablecer zoom al cambiar de piso para visualización completa
    resetZoom();

    // Cargar mapa SVG correspondiente
    loadFloorSvg(currentFloor);
  }

  prevFloorBtn?.addEventListener('click', () => {
    if (currentFloor > 1) updateFloorUI(currentFloor - 1);
  });

  nextFloorBtn?.addEventListener('click', () => {
    if (currentFloor < TOTAL_FLOORS) updateFloorUI(currentFloor + 1);
  });

  floorPills.forEach((pill) => {
    pill.addEventListener('click', () => {
      const selected = parseInt(pill.getAttribute('data-floor'), 10);
      if (selected && selected !== currentFloor) {
        updateFloorUI(selected);
      }
    });
  });

  // Atajos de teclado para pisos
  document.addEventListener('keydown', (e) => {
    const isTyping = ['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName);
    if (!isTyping) {
      if (e.key === 'ArrowLeft' && currentFloor > 1) {
        updateFloorUI(currentFloor - 1);
      } else if (e.key === 'ArrowRight' && currentFloor < TOTAL_FLOORS) {
        updateFloorUI(currentFloor + 1);
      }
    }
  });

  // Reset de filtros
  resetBtn?.addEventListener('click', () => {
    filterForm.reset();
    selectRoom(null, 'select');
    updateFilterBadges();
  });

  // Inicialización
  updateFilterBadges();
  updateFloorUI(1);
});
