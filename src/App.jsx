import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import FloorSelector from './components/FloorSelector';
import MapViewer from './components/MapViewer';

export default function App() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [currentFloor, setCurrentFloor] = useState(1);
  const [selectedRoom, setSelectedRoom] = useState(null);

  const [filters, setFilters] = useState({
    datePreset: 'today',
    date: '2026-11-07',
    class: '',
    group: '',
    course: ''
  });

  // Manejo de cambio en los filtros
  const handleFilterChange = (field, value) => {
    setFilters((prev) => ({ ...prev, [field]: value }));

    // Si se cambia la clase desde la barra lateral, sincroniza el plano
    if (field === 'class') {
      setSelectedRoom(value || null);
    }
  };

  // Manejo de selección de aula desde el mapa
  const handleSelectRoomFromMap = (roomId) => {
    setSelectedRoom(roomId);
    setFilters((prev) => ({ ...prev, class: roomId || '' }));
  };

  // Reset completo de filtros
  const handleResetFilters = () => {
    setFilters({
      datePreset: 'today',
      date: '2026-11-07',
      class: '',
      group: '',
      course: ''
    });
    setSelectedRoom(null);
  };

  // Atajos de teclado globales
  useEffect(() => {
    const handleKeyDown = (e) => {
      const isInput = ['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement?.tagName);

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
        e.preventDefault();
        setIsSidebarOpen((prev) => !prev);
      } else if (e.key === 'Escape' && isSidebarOpen) {
        setIsSidebarOpen(false);
      } else if (!isInput) {
        if (e.key === 'ArrowLeft' && currentFloor > 1) {
          setCurrentFloor((f) => f - 1);
        } else if (e.key === 'ArrowRight' && currentFloor < 3) {
          setCurrentFloor((f) => f + 1);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isSidebarOpen, currentFloor]);

  return (
    <div className="app-container">
      {/* 1. HEADER FIJO EN SU POSICIÓN */}
      <Header
        isSidebarOpen={isSidebarOpen}
        onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
        currentFloor={currentFloor}
      />

      {/* 2. ESPACIO DE TRABAJO */}
      <div className={`workspace-layout ${!isSidebarOpen ? 'sidebar-collapsed' : ''}`}>
        {/* BARRA LATERAL CON DESPLEGABLES */}
        <Sidebar
          isOpen={isSidebarOpen}
          onClose={() => setIsSidebarOpen(false)}
          filters={filters}
          onFilterChange={handleFilterChange}
          onResetFilters={handleResetFilters}
        />

        {/* CONTENIDO PRINCIPAL: SELECTOR DE PISOS Y VISOR CON ZOOM & PAN */}
        <main className="main-content">
          <FloorSelector
            currentFloor={currentFloor}
            onSelectFloor={setCurrentFloor}
            totalFloors={3}
          />

          <MapViewer
            currentFloor={currentFloor}
            selectedRoom={selectedRoom}
            onSelectRoom={handleSelectRoomFromMap}
          />
        </main>
      </div>
    </div>
  );
}

