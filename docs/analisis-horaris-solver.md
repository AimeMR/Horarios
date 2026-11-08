# Análisis de `horaris_solver`: por qué acaba en INFEASIBLE

Análisis estático (sin ejecutar el solver) del pipeline greedy + CP-SAT.

## 🔴 Causa principal: un límite que debía ser una penalización acaba prohibiendo soluciones

Ficheros: `horaris_solver/solver/phase1_time.py` (líneas 174-177) y `horaris_solver/solver/local_cpsat_repair.py` (líneas 165-167).

```python
# |start - partida| / 30 as integer steps
delta = model.NewIntVar(0, 24 * 2, ...)  # dominio 0..48
model.AddAbsEquality(delta, start_vars[...] - template.start_min)  # en MINUTOS
```

- El comentario habla de pasos de 30 minutos, pero el código nunca divide entre 30. `start_vars` está en minutos, así que `|start − partida|` tiene que ser ≤ 48 minutos.
- Como los horarios van en una rejilla de 30 minutos, cada actividad solo puede quedarse en su hora original o moverse ±30 minutos. Lo que debía ser un coste blando se ha convertido en una restricción dura.
- Si la hora original cae fuera de su turno (por ejemplo, una clase de mañana empezando a las 15:00) o no encaja en la rejilla, esa actividad no tiene ningún valor posible. El modelo es INFEASIBLE antes incluso de buscar.
- Se aplica también con `stop_after_first_feasible=True`, porque la restricción se añade igualmente aunque el `Minimize` no se use.
- La reparación local con CP-SAT tiene el mismo fallo. Por eso falla con las mismas actividades que el greedy no consiguió colocar.

**Arreglo:** usar `delta` con dominio `0..24*60` (o el rango real de los turnos), o modelar los pasos con `AddDivisionEquality(steps, delta, 30)` y penalizar `steps`.

## 🟠 Por qué siempre "prueba las mismas soluciones"

1. **Todo es determinista y nada cambia entre reintentos.** `s1_batches.py` (líneas 524-537) relanza el mismo pipeline sobre subconjuntos de los mismos datos. El greedy es determinista, y el modelo CP-SAT lleva el mismo límite erróneo, así que el resultado se repite: `GREEDY_PARTIAL` y luego `INFEASIBLE`.
2. **El hint del greedy no es compatible con el modelo CP-SAT.** El greedy (`greedy_phase1.py`) no respeta:
   - el límite de ±48 minutos (pondera la distancia con la hora original, pero no la limita);
   - los `dies_sense_classe` ni las aturades (no llama a `day_forbidden_for_activity` ni a `aturada_windows_for_day`);
   - los R7 fijados (los mueve libremente), mientras que CP-SAT los convierte en constantes.

   Por tanto el warm-start no es válido, CP-SAT lo descarta y vuelve a explorar desde cero.
3. **`stop_after_first_solution` en la reparación**, con un único worker (`num_search_workers = 1`) y siempre el mismo vecindario, siempre explora el mismo espacio.

## 🟠 Errores de lógica en el greedy (pueden dar soluciones con choques)

- **`_sync_shared` no comprueba choques** (`greedy_phase1.py`, líneas 248-273). Mueve las actividades con el mismo `id_compartida` a la franja de la raíz sin mirar sus profesores ni sus cohortes. `_clashes_placed` solo comprueba la actividad raíz.
- **El rollback de `try_displace` es incompleto** (`greedy_phase1.py`, líneas 362-366). `unplace(activity.id)` no deshace los compañeros compartidos que `place()` había movido. Se quedan en la franja del intento fallido y el estado se corrompe.
- **La reparación local ignora el calendario.** No aplica aturades ni días prohibidos, así que aunque funcionara podría devolver algo que el verificador rechaza.

## 🟡 Incoherencias menores

- **`_allowed_days`** (`phase1_time.py`, líneas 63-65): si quedan menos de 2 días legales, vuelve a permitir los 5. Se pueden aceptar días prohibidos y luego fallar en el verificador.
- **Choques entre R7 fijados:** las actividades R7 fijadas son constantes, pero nunca se comprueba si dos de ellas ya chocan en la propuesta original. Si chocan, el resultado es INFEASIBLE inmediato y sin un mensaje que lo explique.
- **Grupos compartidos sin franjas en común** (`phase1_time.py`, líneas 157-158): se saltan en silencio y pueden acabar en horas distintas, mientras que la reparación (que no tiene ese filtro) sí los obliga a coincidir.
- **Presupuesto de tiempo** (`pipeline.py`, línea 130): `phase1_budget = max(30, budget // 2)` puede superar el presupuesto total si `budget` es menor de 60.

## Prioridad recomendada

1. Corregir el dominio de `delta` en `phase1_time.py` y `local_cpsat_repair.py`. Es casi seguro que esto, por sí solo, resuelve el INFEASIBLE.
2. Hacer que el greedy respete el calendario y los R7 fijados, para que su resultado sirva como hint válido.
3. Corregir `_sync_shared` y el rollback de `try_displace`.
4. Añadir una semilla aleatoria (`random_seed`) o vecindarios distintos en los reintentos, para que no repitan exactamente el mismo intento.
