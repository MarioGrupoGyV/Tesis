# Indicadores de la tesis (Anexo 1)

Los indicadores salen de los datos del sistema, por periodo y por sección, con un corte `as_of`
explícito (reproducible). **Solo periodos SYNTHETIC:** son una simulación, no resultados del colegio
ni medida de eficacia escolar. Los periodos REAL siguen respondiendo
`INSTITUTIONAL_PROCESSING_NOT_READY` (el riesgo de referencia sobre datos reales corresponde al
Bloque 4; no se calcula aquí).

- Pantalla: **Indicadores** (ADMIN, DIRECTOR, RESEARCHER; TUTOR solo sus secciones).
- API: `GET /indicators/contexts`, `GET /indicators`, `GET /indicators/students`, `GET /indicators/interventions.csv`,
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
| **Intervención oportuna · por estudiante** | oportunas ÷ con alerta × 100 | con ≥ 1 intervención realizada entre 0 y 14 días calendario (Lima) tras la alerta | elegibles con alerta | alertas, intervenciones |
| **Intervención oportuna · por intervención** | oportunas ÷ realizadas ligadas a alerta × 100 | intervenciones `DONE` con `performed_at` entre 0 y 14 días calendario (Lima) tras la apertura de la alerta de su caso | intervenciones `DONE` de estudiantes elegibles con `alert_id` ligado (las `DONE` sin alerta se cuentan aparte como `without_alert`) | alertas, intervenciones |
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

### Intervención oportuna: por estudiante o por intervención

Ambas versiones usan la misma regla temporal (`OPPORTUNE_WINDOW_DAYS = 14`, día 14 sí, día 15 no, medido en fechas
calendario de America/Lima desde la apertura de la alerta) y cuentan solo intervenciones **realizadas**. Cambia la
unidad de análisis:

| Versión | Unidad | Cuándo usarla |
|---|---|---|
| **Por intervención** (`opportune_by_intervention`) | cada intervención realizada ligada a una alerta | Comparable con la **Tabla 6** de la tesis («% de intervención oportuna» junto al número de intervenciones, p. ej. 21 de 26 = 80,77 %). También el Excel real marca «oportuna sí/no» por intervención. |
| **Por estudiante** (`opportune`) | cada estudiante con alerta: sí/no según su primera intervención | Insumo de la condición **dicotómica por estudiante** de la metodología (prueba de **McNemar**, antes/después). |

Una proporción sobre intervenciones **no** es una proporción sobre estudiantes: un estudiante con dos intervenciones pesa
dos veces en la primera y una sola vez en la segunda. No mezclar ambas en un mismo cuadro sin indicarlo. Reglas de la
versión por intervención: las `DONE` sin alerta ligada no entran al denominador (`without_alert`); planificadas y
canceladas no cuentan; las de estudiantes inelegibles quedan fuera; sin denominador el valor es `null` con motivo
`NO_INTERVENTIONS_LINKED_TO_ALERT`, nunca 0 %. Una intervención anterior a la apertura de la alerta (días negativos)
está en el denominador pero no es oportuna.

Exportaciones: `GET /indicators/export.csv` (una fila por estudiante, versión por estudiante) y
`GET /indicators/interventions.csv` (una fila por intervención realizada: periodo, código anónimo, sección, fecha de
alerta, fecha de intervención, días, oportuna SI/NO; las sin alerta ligada llevan `alerta_vinculada = NO` y `oportuna`
vacío). Ambas con solo códigos, fórmulas neutralizadas y registro de auditoría.

Ejemplo (prueba `test_b2b_opportune_by_intervention.py`): el alumno *a* tiene dos realizadas (día 14 y día 15), *b* una
(día 1), *c* ninguna, *d* una sin alerta, *e* solo una planificada y una cancelada, *f* es inelegible. Por intervención:
**2 / 3 = 66,67 %** (a-día 14 y b sí; a-día 15 no) y `without_alert = 1`. Por estudiante: alertados *a, b, c, e* →
**2 / 4 = 50 %**.

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

## Datos reales locales (Bloque 3B-2)

Con un protocolo REAL confirmado, *Indicadores* admite periodos REAL y el filtro `bimestre` (`B1`, `B2`, …; el corte elegido es el
de ese bimestre). Rótulo obligatorio: «Datos reales locales — análisis exploratorio, no demuestra eficacia escolar».

- **Riesgo de referencia:** `risk_references` (RIESGO_V1 con insumos de cierre), no etiquetas del generador sintético.
- **PDER:** la detección se mide con `detected_at` (fecha simulada de la evaluación retrospectiva) frente al cierre del bimestre; la
  ventana `detection_days` del protocolo reduce el margen aceptado. Las alertas generadas ahora sobre cortes pasados se cuentan y se
  rotulan como «simulación retrospectiva».
- **NIA e intervención oportuna:** solo con intervenciones reales (flujo existente). Sin ellas son `null` con motivo `NO_REAL_INTERVENTIONS`;
  nunca se rellenan con ceros. Con ellas, el plazo se mide desde el instante real de la alerta (`opened_at`) y la ventana es
  `intervention_days` del protocolo.
- **Métricas del modelo:** evaluación retrospectiva con un modelo ajustado con los mismos estudiantes; son descriptivas, no una validación.
- **CSV:** solo códigos anónimos; columnas adicionales `fecha_deteccion_utc` y `simulacion_retrospectiva`.
- Los indicadores REAL no están disponibles para el rol Investigador.

## PDER, CRA y métricas por corte (Bloque 3B-3)

- **PDER:** para cada alumno y cada corte, *detectado* significa que **la predicción de ese corte** fue media o alta y se emitió antes del cierre
  del bimestre menos `detection_days` (instante `COALESCE(as_of_at, predicted_at)`). PDER = detectados ÷ alumnos con referencia media o alta
  en ese bimestre. La alerta única de la matrícula no se hereda de un bimestre a otro: un alumno con alerta en B1 y predicción baja en B2 no
  cuenta como detectado en B2, y uno bajo en B1 y alto en B2 no cuenta en B1.
- **CRA:** *cubierto* = predicción baja, o media/alta que el seguimiento reflejó en una alerta con **decisión propia** (`CREATED` o `UPDATED`
  en `followup_decisions`). Una alerta heredada de un corte anterior no cubre. No requiere migración.
- **NIA e intervención oportuna:** siguen anclados a la alerta real (`opened_at`); no cambian.
- **Métricas del modelo (REAL):** cifra principal = validación cruzada (fuera de muestra) del informe de comparación del modelo activo, con
  media, DE de F1 macro y número de repeticiones; solo a nivel de periodo. Si el modelo activo no trae informe: `null` con motivo
  `NO_OUT_OF_SAMPLE_REPORT`. El cálculo en memoria (`in_sample_metrics`) se conserva solo como dato interno rotulado «en memoria, no valida el
  modelo». Los CSV traen `metric_basis` (`OUT_OF_FOLD` o `IN_SAMPLE`). SYNTHETIC conserva sus métricas, con base `IN_SAMPLE`.

## Detección validada (fuera de muestra) y por qué el PDER del sistema es 100 % (Bloque 5.1)

**Qué cambia en la lectura.** En la corrida real el PDER del sistema sale 100 % y el CRA 100 %. No es un resultado de desempeño: el modelo activo se
ajustó con los mismos 60 estudiantes que luego evalúa (**en muestra**), así que reconoce a todos los que ya vio. Esas cifras se conservan porque describen
que el sistema funciona, pero **la medida de calidad predictiva es la detección validada**.

**Definición.** *Detección validada* = de las observaciones cuyo riesgo de referencia es **Medio o Alto**, la proporción que el modelo predijo **Medio o Alto**
cuando ese estudiante estaba en el pliegue de validación de la validación cruzada agrupada por estudiante (el modelo no lo había visto: ninguna fila de
entrenamiento entra en el cálculo, y los dos bimestres de un mismo estudiante siempre quedan juntos en entrenamiento o en validación). En cada repetición cada
observación se valida una vez; se informa la **media y la desviación entre las 20 repeticiones** (la desviación no es un intervalo de confianza), por bimestre
(B1, B2) y en total, para cada modelo y para el modelo activo.

**Desglose** (misma validación): Medio detectado como Medio/Alto; Alto detectado como Medio/Alto; **Alto confundido como Bajo** (el caso perdido más grave); y
la **falsa alarma**, Bajo de referencia que el modelo marcó Medio/Alto. La falsa alarma no es un adorno: un modelo que marcara a todos como Alto detectaría el
100 % (el modelo Dummy lo hace), así que la detección sola no distingue un buen modelo de uno que alarma a todos. Los conteos sumados de las repeticiones
coinciden con la matriz de confusión agregada del informe (control interno: si no coinciden, la comparación se detiene).

**CRA validado.** El CRA mide que el sistema no pierde casos de su propia salida (toda predicción Media o Alta genera alerta con el flujo de seguimiento; Baja no la
necesita), por lo que fuera de muestra también es 100 % por definición del flujo. **Es un control de funcionamiento; no se presenta como resultado de desempeño.**
La medida de calidad predictiva es la detección.

**Dónde se ve.**
- *Indicadores* (periodos REAL): tarjeta «PDER del sistema · en muestra · dato de funcionamiento», nota en CRA, y el panel **Detección validada (fuera de
  muestra)** con media ± desviación, repeticiones, conteos sumados, desglose y aviso de n pequeño. Respeta el filtro de bimestre (sin filtro = total). Solo a
  nivel de periodo (por sección: `PERIOD_LEVEL_ONLY`). Si el modelo activo no trae el dato (informes anteriores a este bloque): `null` con motivo `NO_OUT_OF_SAMPLE_REPORT`.
- API: `total.validated_detection` en `GET /indicators` (porcentajes; `metric_basis = OUT_OF_FOLD`), contrato 0.13.0.
- CSV por estudiante: columnas nuevas `deteccion_validada_pct`, `deteccion_validada_sd_pct`, `deteccion_validada_repeticiones` y
  `deteccion_validada_metric_basis` (`OUT_OF_FOLD`); es la cifra del periodo repetida en cada fila, vacía si no hay informe. El CSV por intervención no cambia.
- Informe de comparación (`algorithms.<modelo>.detection`) y resumen agregado de la corrida real (sin códigos de alumno).

**Límites.** n = 60 estudiantes (120 observaciones no independientes); la selección del algoritmo y su evaluación usan los mismos datos, así que la cifra puede ser
optimista; no hay validación externa ni prospectiva; la desviación entre repeticiones no es un intervalo de confianza. Es análisis exploratorio local.
Un 100 % ± 0 en un bimestre (en la corrida real, B2 con los cuatro modelos) significa que ninguna de las 20 repeticiones dejó escapar un caso de ese bimestre; no es un error,
pero se lee con cautela: RIESGO_V1 se calcula con los insumos de cierre del mismo bimestre (nota, asistencia, actividades, participación, incidencias), cercanos a las
variables del corte, así que parte de la separación puede ser estructural y no prueba capacidad predictiva a futuro.
