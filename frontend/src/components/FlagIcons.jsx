import React from 'react';

/**
 * Bandera de España (Castellano)
 */
export function FlagEs({ width = 20, height = 15, className = '' }) {
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 20 15"
      className={`flag-icon flag-es ${className}`}
      aria-hidden="true"
    >
      <clipPath id="es-clip">
        <rect width="20" height="15" rx="2" />
      </clipPath>
      <g clipPath="url(#es-clip)">
        <rect width="20" height="15" fill="#c60b1e" />
        <rect y="3.75" width="20" height="7.5" fill="#ffc400" />
      </g>
    </svg>
  );
}

/**
 * Bandera de Catalunya - Senyera (Català)
 * 4 barras rojas sobre fondo amarillo
 */
export function FlagCa({ width = 20, height = 15, className = '' }) {
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 20 15"
      className={`flag-icon flag-ca ${className}`}
      aria-hidden="true"
    >
      <clipPath id="ca-clip">
        <rect width="20" height="15" rx="2" />
      </clipPath>
      <g clipPath="url(#ca-clip)">
        {/* Fondo amarillo */}
        <rect width="20" height="15" fill="#FCD116" />
        {/* 4 barras rojas (9 franjas en total) */}
        <rect y="1.67" width="20" height="1.67" fill="#DA121A" />
        <rect y="5.00" width="20" height="1.67" fill="#DA121A" />
        <rect y="8.33" width="20" height="1.67" fill="#DA121A" />
        <rect y="11.67" width="20" height="1.67" fill="#DA121A" />
      </g>
    </svg>
  );
}

/**
 * Bandera del Reino Unido (English)
 */
export function FlagEn({ width = 20, height = 15, className = '' }) {
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 60 30"
      className={`flag-icon flag-en ${className}`}
      aria-hidden="true"
    >
      <clipPath id="en-clip">
        <rect width="60" height="30" rx="4" />
      </clipPath>
      <g clipPath="url(#en-clip)">
        <rect width="60" height="30" fill="#012169" />
        {/* Diagonales blancas */}
        <path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" strokeWidth="6" />
        {/* Diagonales rojas */}
        <path d="M0,0 L60,30 M60,0 L0,30" stroke="#C8102E" strokeWidth="4" />
        {/* Cruz blanca */}
        <path d="M30,0 V30 M0,15 H60" stroke="#fff" strokeWidth="10" />
        {/* Cruz roja */}
        <path d="M30,0 V30 M0,15 H60" stroke="#C8102E" strokeWidth="6" />
      </g>
    </svg>
  );
}

