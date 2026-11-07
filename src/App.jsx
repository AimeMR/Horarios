import React, { useState, useEffect, useMemo } from 'react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import FloorSelector from './components/FloorSelector';
import MapViewer from './components/MapViewer';
import { evaluateAllFloorsFilters } from './services/scheduleFilterService';

export default function App() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [currentFloor, setCurrentFloor] = useState(0); // 0, 1, 2 y 3
  const [selectedRoom, setSelectedRoom] = useState(null);

  // Filtros de trabajo del formulario en la barra lateral
  const [filters, setFilters] = useState({
    date: '',
    degree: '',
    course: '',
    subject: '',
    group: ''
  });

  // Filtros aplicados efectivamente tras pulsar "Aplicar filtros"
  const [appliedFilters, setAppliedFilters] = useState(null);

  const handleFilterChange = (field, value) => {
    setFilters((prev) => ({ ...prev, [field]: value }));
  };

  const handleApplyFilters = () => {
    setAppliedFilters({ ...filters });
  };

  const handleSelectRoomFromMap = (roomId) => {
    setSelectedRoom(roomId);
  };

  const handleResetFilters = () => {
    const emptyFilters = {
      date: '',
      degree: '',
      course: '',
      subject: '',
      group: ''
    };
    setFilters(emptyFilters);
    setAppliedFilters(null);
    setSelectedRoom(null);
  };

  // Evaluación de aulas coincidentes en todos los pisos con los filtros aplicados
  const filterEvaluation = useMemo(() => {
    return evaluateAllFloorsFilters(appliedFilters);
  }, [appliedFilters]);

  const currentFloorMatchingRooms = filterEvaluation.matchingRoomsByFloor[currentFloor] || [];

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
          onApplyFilters={handleApplyFilters}
        />

        {/* CONTENIDO PRINCIPAL: SELECTOR DE PLANTAS (0, 1, 2, 3) Y VISOR DE MAPA */}
        <main className="main-content">
          <FloorSelector
            currentFloor={currentFloor}
            onSelectFloor={setCurrentFloor}
            floorMatchCounts={filterEvaluation.countsByFloor}
            hasActiveFilters={filterEvaluation.hasActiveFilters}
          />

          <MapViewer
            currentFloor={currentFloor}
            selectedRoom={selectedRoom}
            onSelectRoom={handleSelectRoomFromMap}
            filters={filters}
            appliedFilters={appliedFilters}
            matchingRooms={currentFloorMatchingRooms}
          />
        </main>
      </div>
    </div>
  );
}
