# Propuesta de mejora de `horaris_solver`

Complementa a [analisis-horaris-solver.md](analisis-horaris-solver.md). El plan está ordenado de menor a mayor esfuerzo, para que cada fase sea entregable por sí sola y se pueda parar en cuanto el solver dé soluciones válidas.

---

## Fase 0: preparar el diagnóstico (½ día)

Antes de cambiar nada, hay que poder medir el efecto de cada cambio.

1. **Crear un dataset pequeño de referencia.** Por ejemplo, S1 + `1r`, guardado en `tests/fixtures/` o generado desde la BD de SQLite. Así cada prueba tarda segundos.
2. **Comprobar los datos antes de llamar al solver.** Crear `solver/precheck.py`, que devuelva una lista de problemas con su motivo:
   - actividades sin ninguna franja posible (`slots_for_duration` vacío para su turno);
   - actividades cuya hora original está fuera de su turno;
   - pares de actividades R7 fijadas que ya chocan en la propuesta original;
   - grupos `id_compartida` con turnos incompatibles;
   - actividades sin días legales después de quitar `dies_sense_classe`.
3. **Mostrar el motivo del fallo.** Si el precheck encuentra un problema bloqueante, devolver `INFEASIBLE_DATA` con la lista en lugar de lanzar CP-SAT.
4. **Añadir tests de regresión.** Uno por cada error del análisis, que fallen antes del arreglo y pasen después (es el flujo TDD que pide el proyecto).

**Criterio de aceptación:** ante cualquier INFEASIBLE, el CLI dice qué actividades lo causan.

---

## Fase 1: arreglos urgentes sin cambiar el algoritmo (½–1 día)

### 1.1 Corregir el dominio de `delta` (bloqueante)

En `phase1_time.py` y `local_cpsat_repair.py`:

```python
MAX_SHIFT_MIN = 24 * 60
delta = model.NewIntVar(0, MAX_SHIFT_MIN, f"dstart_{aid}")
model.AddAbsEquality(delta, start_vars[aid] - template.start_min)
steps = model.NewIntVar(0, MAX_SHIFT_MIN // 30, f"steps_{aid}")
model.AddDivisionEquality(steps, delta, 30)
soft_terms.append(steps * WEIGHT_CANVI_HORA)  # ahora sí "por 30 minutos"
```

Test: una actividad cuya hora original está en otro turno tiene que poder colocarse.

### 1.2 Una sola fuente de verdad para las reglas

Crear `solver/feasibility.py` con dos funciones:

- `allowed_days(data, activity) -> list[int]`: aplica los R7 fijados y `dies_sense_classe`. Si no queda ningún día, lo registra como error del precheck en lugar de volver a permitir los 5.
- `allowed_starts(data, activity, day) -> list[int]`: aplica el turno y las aturades.

Las tres piezas (CP-SAT, greedy y reparación) deben usar **solo** estas funciones. Con eso desaparece la discrepancia entre el greedy y CP-SAT que invalida el hint.

### 1.3 Corregir el greedy

- `_clashes_placed` debe comprobar la actividad **y todos sus compañeros con el mismo `id_compartida`** (con la unión de sus profesores y cohortes).
- `_sync_shared` solo debe ejecutarse cuando ya se haya comprobado que el grupo entero cabe.
- `try_displace`: guardar el estado (`placed`, `activity_day`, `activity_start`) completo al empezar y restaurarlo entero si falla, en vez de deshacer a mano.
- No mover nunca las actividades R7 fijadas.

### 1.4 Validar el hint

Antes de pasar el resultado del greedy a CP-SAT como warm-start, comprobar que cumple todas las restricciones duras (con una función `validate_phase1(data, result)`). Si no las cumple, registrarlo y no usarlo como hint, o pasar `solver.parameters.repair_hint = True`.

### 1.5 Ajustes de parámetros

- `pipeline.py`: `phase1_budget = budget // 2`, `phase2_budget = budget - phase1_budget`, sin `max(30, …)`.
- Pasar `random_seed` configurable y dar una semilla distinta a cada reintento.
- En la reparación, quitar `stop_after_first_solution` y usar `num_search_workers = 8`.

**Criterio de aceptación:** S1 completo da una solución válida (`ok=True`) y el verificador oficial no encuentra choques.

---

## Fase 2: rehacer el modelo CP-SAT (recomendado, 1–2 días)

### Problema del modelo actual

Las restricciones se construyen por **pares**: dos booleanos (`same_day`, `lb`/`rb`) por cada par de actividades que interactúan. Eso da O(n²) variables. Con cientos o miles de actividades, el modelo se vuelve enorme y la propagación es débil, y por eso CP-SAT se queda en UNKNOWN o tarda muchísimo.

### Modelo propuesto: tiempo absoluto e intervalos

1. **Una sola variable de tiempo por actividad:** `t = day * 1440 + start`, con el dominio `Domain.FromValues(...)` generado a partir de `allowed_days × allowed_starts`. Así el día, el turno, las aturades y los días prohibidos quedan dentro del dominio y no hacen falta restricciones reificadas.
2. **Un intervalo por actividad:** `iv = NewIntervalVar(t, dur, t + dur)`.
3. **Un `AddNoOverlap` por recurso y semana ISO**, en lugar de restricciones por pares:
   - un grupo por profesor y semana;
   - un grupo por cohorte y número de grupo y semana (siguiendo la regla de línea TE de `sessions_cohort_clash`);
   - un grupo por asignatura para el bloqueo PLAB↔TE/PAUL.

   Una actividad que aparece en varias semanas entra en el `NoOverlap` de cada una de ellas. Esto sustituye a `activities_share_iso_week`.
4. **Actividades compartidas:** un único `t` para todo el grupo `id_compartida`; se unen sus profesores y cohortes y el grupo ocupa un solo intervalo.
5. **Objetivo:**
   - cambio de día: `NewBoolVar` + `AddElement` o tabla precalculada del coste de cada valor de `t`. Lo más simple es precalcular `coste(t)` por actividad y usar `AddElement` sobre el índice del valor;
   - huecos (hores mortes): calcularlos solo para pares de la misma cohorte y día, o aproximarlos minimizando el número de franjas distintas que usa cada cohorte cada día (mucho más barato).

### Ventajas

- De O(n²) booleanos se pasa a O(n), con una propagación fuerte (`NoOverlap` usa edge-finding).
- Las reglas de calendario son restricciones duras sin coste, porque están en el dominio.
- El hint del greedy se traduce directamente a `t`.

**Criterio de aceptación:** el mismo resultado o mejor que en la Fase 1, en un tiempo como mínimo 5 veces menor sobre S1 completo.

---

## Fase 3: pipeline robusto (½–1 día)

Nuevo flujo de `_run_phase1`:

```
precheck ──► greedy (con feasibility.py) ──► validar ──► CP-SAT completo (hint, seed)
                                                           │
                                     ┌─── FEASIBLE ◄──────┤
                                     │                     └─ UNKNOWN / INFEASIBLE
                                     ▼                              │
                               LNS (mejora)               relajación escalonada
```

1. **Mejora con LNS (Large Neighbourhood Search).** Partir de una solución válida, liberar un subconjunto (una cohorte, un profesor, un día…), volver a resolverlo con CP-SAT y aceptarlo si mejora. Elegir el vecindario al azar con semilla en cada iteración. Esto sustituye a la "reparación local" actual y evita repetir siempre el mismo intento.
2. **Relajación escalonada en lugar de reintentar lo mismo.** Si CP-SAT no encuentra solución:
   1. permitir mover los R1;
   2. convertir los choques de cohorte en blandos con una penalización muy alta, y devolver una solución con la lista de choques restantes.

   Así siempre hay salida y un diagnóstico.
3. **Los lotes S1 (`s1_batches.py`)** solo tienen sentido si cada reintento cambia algo: otra semilla, otra relajación u otro vecindario. Si no cambia nada, hay que quitar el "ladder", porque solo repite el mismo cálculo.

---

## Fase 4: calidad (continuo)

- Ejecutar el verificador oficial dentro de los tests de integración sobre el dataset pequeño.
- Guardar métricas por ejecución (tiempo, estado, objetivo, actividades movidas) en el JSON enriquecido para comparar versiones.
- Dejar `node .agentic/scripts/verify.js` en verde: arreglar ruff, mypy y pytest, y aplicar `ruff format` a los 18 archivos pendientes. Los checks del backend también fallan porque falta `backend/package.json`: hay que restaurarlo o quitar esos pasos de `verify.config.json`.

---

## Resumen de prioridades

| # | Acción | Esfuerzo | Impacto |
|---|--------|----------|---------|
| 1 | Corregir el dominio de `delta` | 10 min | 🔴 Desbloquea el INFEASIBLE |
| 2 | Precheck con diagnóstico | 2–3 h | 🟠 Explica los fallos restantes |
| 3 | `feasibility.py` compartido + corregir el greedy | 3–4 h | 🟠 Hint válido, sin choques ocultos |
| 4 | Semillas y presupuestos | 30 min | 🟡 Reintentos que sí cambian algo |
| 5 | Modelo CP-SAT con intervalos y `NoOverlap` | 1–2 días | 🟠 Escala y rendimiento |
| 6 | LNS + relajación escalonada | 1 día | 🟡 Siempre devuelve algo útil |
