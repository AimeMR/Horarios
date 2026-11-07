import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import FloorSelector from './components/FloorSelector';
import MapViewer from './components/MapViewer';

export default function App() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [currentFloor, setCurrentFloor] = useState(0); // 0, 1, 2 y 3
  const [selectedRoom, setSelectedRoom] = useState(null);

  // Filtros: fecha (dia concreto), grado, curso, asignatura y grupo
  const [filters, setFilters] = useState({
    date: '2026-11-07',
    degree: '',
    course: '',
    subject: '',
    group: ''
  });

  const handleFilterChange = (field, value) => {
    setFilters((prev) => ({ ...prev, [field]: value }));
  };

  const handleSelectRoomFromMap = (roomId) => {
    setSelectedRoom(roomId);
  };

  const handleResetFilters = () => {
    setFilters({
      date: '2026-11-07',
      degree: '',
      course: '',
      subject: '',
      group: ''
    });
    setSelectedRoom(null);
  };

  // Atajos de teclado: Ctrl+B para barra lateral, flechas para cambiar entre plantas 0, 1 y 2
  useEffect(() => {
    const handleKeyDown = (e) => {
      const isInput = ['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement?.tagName);

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
        e.preventDefault();
        setIsSidebarOpen((prev) => !prev);
      } else if (e.key === 'Escape') {
        if (selectedRoom) {
          setSelectedRoom(null);
        } else if (isSidebarOpen) {
          setIsSidebarOpen(false);
        }
      } else if (!isInput) {
        if (e.key === 'ArrowLeft' && currentFloor > 0) {
          setCurrentFloor((f) => f - 1);
        } else if (e.key === 'ArrowRight' && currentFloor < 3) {
          setCurrentFloor((f) => f + 1);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isSidebarOpen, currentFloor, selectedRoom]);

  return (
    <div className="app-container">
      {/* HEADER FIJO EN SU POSICIÓN */}
      <Header
        isSidebarOpen={isSidebarOpen}
        onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
        currentFloor={currentFloor}
      />

      {/* ESPACIO DE TRABAJO */}
      <div className={`workspace-layout ${!isSidebarOpen ? 'sidebar-collapsed' : ''}`}>
        {/* BARRA LATERAL CON LOS FILTROS: Fecha, Grado, Curso, Asignatura y Grupo */}
        <Sidebar
          isOpen={isSidebarOpen}
          onClose={() => setIsSidebarOpen(false)}
          filters={filters}
          onFilterChange={handleFilterChange}
          onResetFilters={handleResetFilters}
        />

        {/* CONTENIDO PRINCIPAL: SELECTOR DE PLANTAS (0, 1, 2, 3) Y VISOR DE MAPA */}
        <main className="main-content">
          <FloorSelector
            currentFloor={currentFloor}
            onSelectFloor={setCurrentFloor}
          />

          <MapViewer
            currentFloor={currentFloor}
            selectedRoom={selectedRoom}
            onSelectRoom={handleSelectRoomFromMap}
            filters={filters}
          />
        </main>
      </div>
    </div>
  );
}
