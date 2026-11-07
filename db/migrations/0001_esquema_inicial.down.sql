-- =====================================================================================================
-- 0001_esquema_inicial (down) · Deshace 0001_esquema_inicial.up.sql
--
-- Borra las 26 tablas en orden inverso de dependencia (hijas antes que padres), para que no falle ninguna FK
-- con foreign_keys activado. Los índices se borran con sus tablas. Sin BEGIN/COMMIT: la transacción la abre
-- el runner. Se pierden todos los datos.
-- =====================================================================================================

DROP TABLE relaxacio_sessio;
DROP TABLE relaxacio;
DROP TABLE registre_canvi;
DROP TABLE assignacio;
DROP TABLE versio_horari;
DROP TABLE canvi_alumnes;
DROP TABLE cancellacio;
DROP TABLE tancament_aula;
DROP TABLE calendari;
DROP TABLE sessio;
DROP TABLE activitat;
DROP TABLE indisponibilitat_profe;
DROP TABLE escenari;
DROP TABLE docencia;
DROP TABLE profe;
DROP TABLE grup;
DROP TABLE assignatura_pla;
DROP TABLE assignatura_cohort;
DROP TABLE assignatura;
DROP TABLE cohort;
DROP TABLE pla_titulacio;
DROP TABLE pla_estudis;
DROP TABLE titulacio;
DROP TABLE aula;
DROP TABLE departament;
DROP TABLE facultat;
