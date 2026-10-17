# Indicadores de la tesis (Anexo 1)

Los indicadores salen de los datos del sistema, por periodo y por sección, con un corte `as_of`
explícito (reproducible). **Solo periodos SYNTHETIC:** son una simulación, no resultados del colegio
ni medida de eficacia escolar. Los periodos REAL siguen respondiendo
`INSTITUTIONAL_PROCESSING_NOT_READY` (el riesgo de referencia sobre datos reales corresponde al
Bloque 4; no se calcula aquí).

- Pantalla: **Indicadores** (ADMIN, DIRECTOR, RESEARCHER; TUTOR solo sus secciones).
- API: `GET /indicators/contexts`, `GET /indicators`, `GET /indicators/students`,
  `GET /indicators/export.csv` (`period_id`, `section_id` y `as_of` opcionales; `close_at` opcional).
- CSV por estudiante con código anónimo; **nunca nombres**; celdas neutralizadas contra fórmulas.

## Unidad de análisis y reglas generales

- **Estudiante elegible** = matrícula del periodo con estudiante activo y `eligible_for_processing`.
  Inelegibles/inactivos quedan fuera de todos los denominadores y se cuentan en *Excluidos*.
- **Último corte**: por estudiante, el corte con mayor `cutoff_at`/revisión que ya existía en `as_of`.
  Varios cortes del mismo estudiante no se cuentan como personas distintas.
- **Evaluación vigente**: predicción registrada para ese último corte.
- **Sin riesgo inventado**: sin riesgo de referencia almacenado el estudiante no entra al
  denominador de PDER ni a las métricas; el indicador es `null` con motivo y se informa el número de excluidos.
- Constante `OPPORTUNE_WINDOW_DAYS = 14` («dos semanas» de la tesis) en `backend/app/services/indicators.py`.
- Porcentajes sin denominador: `null` + `reason`. Nunca 0 % por defecto.

## Dónde vive hoy el riesgo de referencia

El sistema **no guarda** un riesgo de referencia en las tablas. Solo existe en la carga privada del estudio
sintético (`labels.outcomes`: resultado futuro con el criterio `synthetic-future-v1`), vinculada a cada corte
CSV importado mediante los `bindings` del estudio. Por tanto:

- Cortes CSV de un estudio sintético importado → tienen referencia.
- Mediciones MANUAL → no tienen referencia (excluidas con `NO_REFERENCE_FOR_LATEST_SNAPSHOT`).
- Periodo sin estudio o sin importación → PDER y métricas `null` con `REFERENCE_NOT_AVAILABLE`.

## Definiciones

| Indicador | Fórmula | Numerador | Denominador | Fuente |
|---|---|---|---|---|
| **PRV** | válidos procesados ÷ recibidos × 100 | filas válidas de lotes `COMMITTED` cuyo estudiante es elegible | suma de `total_rows` de los lotes recibidos hasta `as_of` | `import_batches`, `academic_snapshots` |
| **CRA** | cubiertos ÷ elegibles × 100 | elegibles con predicción vigente y, si el riesgo es MEDIUM/HIGH, alerta registrada (el reporte existe para toda matrícula autorizada) | estudiantes elegibles | predicciones, alertas |
| **PDER** | detectados ÷ con referencia MEDIUM/HIGH × 100 | elegibles con referencia MEDIUM/HIGH y alerta abierta **antes del cierre** | elegibles con referencia MEDIUM/HIGH | referencia del estudio; `alerts.opened_at` |
| **NIA** | intervenciones realizadas por estudiante | `DONE` con fecha efectiva ≤ `as_of` | elegibles (y, aparte, solo alertados) | `interventions` |
| **Intervención oportuna** | oportunas ÷ con alerta × 100 | con ≥ 1 intervención realizada entre 0 y 14 días calendario (Lima) tras la alerta | elegibles con alerta | alertas, intervenciones |
| **Métricas del modelo** | matriz de confusión, precisión, sensibilidad, F1, exactitud, macro | pares (referencia, predicho) | elegibles evaluados con referencia | reutiliza `app.ml.evaluate.metrics` |
| **Rendimiento** | n, media, DE, mediana, mín., máx. | promedio y asistencia del último corte | elegibles con dato | `academic_snapshots` |

Precisiones:

- **PRV**: `ineligible_omitted` cuenta filas válidas de estudiantes inelegibles (procesadas pero omitidas del
  procesamiento predictivo); `valid_not_committed` cuenta válidas de lotes sin confirmar; `rejected`, las inválidas.
  Las mediciones manuales no pertenecen a lotes y se informan aparte. Con filtro de sección o rol TUTOR el PRV es
  `null` (`PERIOD_LEVEL_ONLY`) porque los lotes son del periodo completo.
- **PDER**: «cierre» = inicio del día siguiente al fin del periodo en America/Lima, o `close_at` si se indica
  (p. ej. fin de un bimestre). Registro por estudiante `alert_before_close` sí/no. Una alerta activa, resuelta o
  descartada cuenta si se abrió antes del cierre. En periodos pasados con alertas creadas hoy, PDER es 0 % por
  construcción (las alertas se abren después del cierre): es una limitación del demo, no un error.
- **NIA**: solo `DONE`; una actividad planificada o cancelada no cuenta. Se informa total, media y mediana sobre
  elegibles y sobre alertados.
- **Oportuna**: la alerta de referencia es la primera alerta de la matrícula. Días = diferencia de fechas
  calendario en Lima; 14 días exactos es oportuno, 15 no. Se muestra también la mediana de días alerta→primera
  intervención realizada. Alerta sin intervención o solo planificada: no oportuna.
- **Métricas**: la fila es el riesgo de referencia, la columna el predicho; «sin dato» = no estimable por falta de soporte.
  Sin calibración ni evaluación prospectiva institucional.
- **as_of**: filtra cortes, predicciones, alertas e intervenciones por su fecha de registro. El estado
  (p. ej. `DONE`) es el actual, no el histórico: reproducibilidad completa requeriría un historial de estados.

## Ejemplo numérico (prueba `test_b2_indicators.py`)

Diez alumnos manuales con alerta abierta en T0 (hace 40 días, 10:00 Lima), todos en una sección con `E0`
elegibles previos:

| Alumno | Evaluado | Realizadas (días tras la alerta) | Resultado |
|---|---|---|---|
| s1 | ALTO | 3 | oportuna |
| s2 | ALTO | 14 | oportuna (límite exacto) |
| s3 | ALTO | 15 | **no** oportuna |
| s4 | ALTO | — | alerta sin intervención |
| s5 | ALTO | solo planificada | NIA 0, no oportuna |
| s6 | ALTO | 2 y 20 | NIA 2, oportuna |
| s7 | BAJO | — | sin alerta, cubierto por CRA |
| s8 | sin evaluar | — | no cubierto |
| s9 | MEDIO | 0 | oportuna |
| s10 | ALTO | 4 | inelegible: fuera de todo |

Con `E = E0 + 9` elegibles: **CRA = 8 / E**; **NIA total = 6** (media 6/E; entre los 7 alertados: media 6/7 y
mediana 1); **oportuna = 4 / 7 = 57,14 %** (mediana alerta→primera 3 días entre 5 con intervención). Otra prueba
construye la matriz de confusión de 12 estudiantes del estudio con predicciones forzadas y la compara con la
calculada a mano a partir de los resultados regenerados del generador.

## Limitaciones

- Simulación: los valores dependen del generador sintético y del modelo técnico; no miden eficacia escolar.
- No hay riesgo de referencia para periodos sin estudio sintético ni para mediciones manuales.
- Acceso de RESEARCHER: ve los indicadores y el CSV por código anónimo por autorización expresa de este bloque;
  no accede a casos ni reportes operativos.
- No se modifican el modelo, la política de seguimiento ni la elegibilidad.
