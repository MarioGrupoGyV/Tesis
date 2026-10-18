# ADR 012: procesamiento REAL local de una cohorte (Bloque 3A, solo diseño)

Estado: **aceptada con ajustes** (auditoría del 2026-10-17); implementación por etapas: 3B-1 (esquema y componentes puros, sin cambiar el comportamiento) y 3B-2 (activación). Fecha: 2026-10-17. Rama `mejoras-tesis`.
Relacionados: [ADR 011](011-fase-mejoras-tesis.md), [Mapa de impacto](../planning/Mapa_Impacto_REAL.md),
[Indicadores de la tesis](../manuals/Indicadores_Tesis.md).

Este documento no afirma eficacia escolar, validación académica ni exactitud del modelo. Contiene solo códigos y agregados;
ningún nombre de alumno, directivo ni dato identificable del Excel.

## 1. Contexto

La dirección del colegio autorizó el uso de los registros de una cohorte (60 estudiantes de 3.º de secundaria, secciones A y B,
bimestres B1 y B2 de 2026) y el usuario quiere correr dentro del propio sistema, con esos datos, el flujo completo: evaluación,
alertas, intervenciones, reportes, indicadores y entrenamiento/comparación de modelos (RF, SVM, XGBoost).

Hoy REAL está bloqueado por diseño (`INSTITUTIONAL_PROCESSING_NOT_READY`) y **toda la cadena** evaluación → seguimiento → modelos
está atada a `SyntheticStudyRecord`/`study_id` y a `data_origin='SYNTHETIC'` (ver el mapa de impacto: decenas de puntos entre SQL,
servicios, ML, API y frontend). El estudio sintético aporta, además del contexto, las etiquetas de referencia (carga privada
`labels.outcomes`) y el protocolo de validación (cortes de desarrollo/externos con estudiantes de reserva distintos).

Decisión del usuario sobre autorización: no se guarda el documento, el nombre de quien autoriza ni la fecha del permiso.

## 2. Decisiones ya tomadas (se respetan)

- **D1** El modelo predice con datos disponibles **al corte** (mitad del bimestre); el objetivo es el riesgo de referencia al **cierre**.
  Nunca se entrena con datos de cierre para predecir el cierre.
- **D2** El **backend** calcula el riesgo de referencia con la regla RIESGO_V1, independiente del modelo.
- **D3** Con REAL, análisis, indicadores, CSV y evidencias usan códigos anónimos. Los nombres solo pueden vivir en la ficha
  (`students.full_name`, base local) y nunca en exportaciones, indicadores, logs, evidencias ni repositorio.
- **D4** El «protocolo REAL» **no guarda** consentimientos, documentos, nombres de autorizadores ni fechas de permiso. Es un interruptor
  técnico con parámetros y un booleano `authorization_confirmed_by_admin` que solo un ADMIN activa, con auditoría
  (actor + instante UTC) sin datos personales. Sin él, REAL sigue bloqueado.
- **D5** Solo local; REAL y SYNTHETIC no se mezclan en ningún cálculo, modelo, índice ni reporte.
- **D6** Gráficos en SVG propio, sin librerías (Bloque 6).

## 2b. Decisiones del usuario (2026-10-17)

Vigentes tras la auditoría de este ADR (sustituyen a cualquier lista anterior):

1. **Alertas e intervenciones del Excel:** fueron generadas por script; **no son acciones reales**. No se importan como historial ni se muestran como reales.
2. **El sistema no ha estado en uso.** B2 «con sistema» es una **simulación retrospectiva**: las alertas las genera el sistema al corte, rotuladas como tales
   (relojes `as_of_at`/`detected_at`). El NIA y la intervención oportuna **reales** quedan para registros reales o un piloto futuro.
3. **Plazos de la tesis:** alerta **antes del cierre** del bimestre; intervención **≤ 14 días**; ambos parámetros viven en el protocolo.
4. **Variables y calendario:** la participación queda fuera de las características (**4 variables** al corte); corte = disponibilidad de la última fuente
   (**horizonte de 17 días**); **un solo periodo 2026** para B1 y B2.
5. **Nombres** solo en la ficha del alumno, desde un archivo local; análisis, indicadores, CSV y evidencias usan **solo códigos**.
6. **PRV 120/126 y reportes 113/120 del Excel:** procedencia **por confirmar**; **no** se crean `reception_log` ni `report_log` por ahora.

Principios que se mantienen del encargo del Bloque 3B-1: la arquitectura (a) aprobada (generalizar el registro de estudio con un parámetro de origen, sin renombrar
`synthetic_studies` en 3B); los dos relojes de la evaluación retrospectiva (el instante de registro sigue siendo el real); toda operación REAL sigue devolviendo
`INSTITUTIONAL_PROCESSING_NOT_READY` hasta 3B-2; y el protocolo REAL es un interruptor técnico sin consentimientos, documento, autorizador ni fecha de permiso (D4).

## 3. Lo que contiene el Excel (hojas y agregados, sin datos personales)

Libro con 13 hojas: `Resumen`, `Parametros`, `Pareados`, `Bimestres`, `Predicciones`, `Alertas`, `Intervenciones`, `Calificaciones`,
`Incidencias`, `Procesamiento`, `Reportes`, `Fuentes`, `Estudiantes`. Varias hojas traen una columna de nombre del estudiante:
**el conversor debe descartarla** salvo para el archivo opcional código→nombre.

| Dato | Hallazgo (agregado) |
|---|---|
| Cohorte | 60 estudiantes, 3.º, secciones A (30) y B (30); 120 registros estudiante-bimestre |
| Calendario 2026 | B1: inicio 03-09, cierre 05-08; B2: inicio 05-18, cierre 07-17; 45 días lectivos por bimestre |
| Corte intermedio | B1: 04-17 (disponible 04-20/04-21); B2: 06-26 (disponible 06-29/06-30); 30 de 45 días programados al corte |
| Datos al corte | notas parciales por curso (720 = 6 cursos × 120; evaluadas 04-03…04-10 / 06-12…06-19, disponibles ≤ 04-14 / 06-23), asistencia y actividades acumuladas al corte (120), incidencias con fecha (B1: 35 de 53 hasta el corte; B2: 42 de 59) |
| **No hay participación al corte** | `participacion_1_5` es un único valor por bimestre (de cierre) |
| Datos de cierre | promedio final (6 cursos, igual peso), asistencia final (45 días), entrega final, participación, incidencias del bimestre |
| Referencia RIESGO_V1 | B1: Bajo 15, Medio 21, Alto 24; B2: Bajo 25, Medio 11, Alto 24 (total 40/32/48). Transiciones B1→B2: B→B 15, M→M 8, M→A 3, M→B 10, A→A 21, A→M 3 |
| Predicciones de la base | `CLASIFICADOR_V1`, 120 filas, coincidencia con la referencia 96/120; **se calculan en la fecha de cierre** (corte de datos = 05-08/07-17) y las alertas se emiten tras la disponibilidad del cierre (05-11…07-28) |
| Alertas / intervenciones | 79 alertas (B1 43, B2 36); 79 intervenciones: 65 ejecutadas, 10 pendientes, 4 canceladas; `dias_desde_alerta` hasta 11 |
| Procesamiento | 126 recepciones: 120 válidas, 6 rechazadas (clave duplicada, código fuera de la cohorte, asistidos > programados, nota fuera de 0–20, entregadas > programadas, bimestre ausente) |
| Reportes | 120 esperados, 113 generados, 7 «fallo de generación» |
| Parámetros de oportunidad de la base | detección ≤ 3 días desde disponibilidad del corte; intervención ≤ 5 días desde la alerta |

Contradicciones a resolver con el usuario (sección 13): el Excel mide la detección **después** del cierre y con 3/5 días; las decisiones de
los Bloques 1–2 son «alerta antes del cierre» y 14 días; y la participación no existe al corte.

## 4. Regla RIESGO_V1 exacta

Fuente: hoja `Parametros` (criterios y parámetros). Cinco componentes de 0 a 2 puntos; total 0–10.

| Componente | 2 puntos | 1 punto | 0 puntos |
|---|---|---|---|
| Promedio de notas (0–20, dos decimales) | < 11 | 11 a < 14 | ≥ 14 |
| Asistencia = asistidos ÷ programados | < 80 % | 80 % a < 90 % | ≥ 90 % |
| Actividades = entregadas ÷ programadas | < 60 % | 60 % a < 80 % | ≥ 80 % |
| Participación (1–5) | 1–2 | 3 | 4–5 |
| Incidencias del bimestre | ≥ 3 | 1–2 | 0 |

**Nivel:** Bajo 0–1 · **Medio 2–4** (frontera Medio/Bajo = 2 puntos) · **Alto ≥ 5**.

Convenciones de implementación (para evitar errores de frontera): porcentajes con aritmética entera
(`100·asistidos < 80·programados`); promedio = media de las seis notas de curso con `Decimal`, redondeo a 2 decimales
(mitad hacia arriba) y regla aplicada al valor redondeado; participación entera; incidencias = conteo.

**Evidencia:** se recalculó la regla sobre los 120 registros usando las notas por curso, asistencia, actividades, participación e
incidencias de la propia base: **120/120 coinciden** con `riesgo_referencia` y con `puntos_riesgo`, tanto con el promedio redondeado
como sin redondear (ninguna frontera cambia). En 2 registros el `promedio_0_20` almacenado difiere en ≤ 0,01 de la media recalculada de
los seis cursos (no altera ningún nivel). El conteo de incidencias de la hoja `Incidencias` coincide con `numero_incidencias` en los 120.
No quedan ambigüedades de la regla; las preguntas son de proceso (sección 13).

## 5. Alternativas de arquitectura para el contexto REAL

| Criterio | (a) Generalizar el registro de estudio y añadir un cargador institucional | (b) Tabla paralela `institutional_studies` | (c) Reducir a «protocolo + cortes + referencias» sin objeto estudio |
|---|---|---|---|
| Idea | `synthetic_studies` pasa a ser el registro de estudio de cualquier origen (columnas `kind`, `protocol_id`); la carga privada de REAL contiene CSV canónico y manifiesto; las etiquetas salen de `risk_references` | Duplicar tabla, servicios de comparación/registro/activación y guards | Quitar `study_id` de modelos, decisiones y lotes y atarlos al periodo/protocolo |
| Reutiliza entrenamiento, comparación, registro, activación, predicción, seguimiento, indicadores | **Alta**: mismo servicio con parámetro de origen | Baja: copia | Media: reescribe las FK de procedencia |
| Archivos de aplicación tocados (3B+5) | ~35 + ~20 | ~60 | ~50 (cambia modelo de datos y migra evidencia) |
| Riesgo de regresión en las 338 pruebas | **Bajo-medio**: las migraciones solo **amplían** CHECK; los literales `'SYNTHETIC'` pasan a parámetro con valor por defecto; el camino sintético conserva sus pruebas | Bajo (no toca lo existente) pero deja dos caminos divergentes | Alto: cambia FK y triggers que protegen S3–S6 |
| No mezcla REAL/SYNTHETIC | FK compuesta `(study_id, data_origin)` ya existente + `kind`↔origen CHECK + trigger `check_prediction_study` extendido + pruebas cruzadas | Aislamiento físico, pero el modelo y la decisión necesitan dos FK opcionales con CHECK «exactamente una» | Depende solo de CHECK por periodo |
| Costo de mantenimiento | Un solo camino | Dos caminos | Un camino nuevo sin historia |

### Recomendación: **(a), por etapas y sin renombrar la tabla en 3B**

1. **Mantener el nombre físico** `synthetic_studies` y la clase ORM en 3B (el renombrado a `studies` es cosmético y queda posterior); evita tocar
   ~12 consultas SQL con el nombre literal y reduce el riesgo de regresión.
2. Migración 0007 **aditiva**: ampliar CHECK (`data_origin IN ('SYNTHETIC','REAL')`, `generator_version`), añadir `kind` y `protocol_id`,
   cambiar las provenance CHECK de `import_batches`/`model_versions` a `study_id IS NOT NULL` para orígenes procesados, y reemplazar
   `synthetic_only_active_model` por una regla por alcance (`SYNTHETIC_STUDY`+`TECHNICAL_SIMULATION` o `INSTITUTIONAL_STUDY`+`LOCAL_EXPLORATORY`).
3. Introducir un único punto `study_for_period(period)` y un `require_real_protocol(db, period)` que reemplazan las ramas
   `if period.data_origin!='SYNTHETIC': raise ...`.
4. Un periodo REAL = **un periodo 2026** que contiene B1 y B2 (cortes 04-21 y 06-30), un estudio REAL y un modelo activo por origen
   (ya es el comportamiento: la activación desactiva el modelo activo del mismo origen).

Por qué un periodo y no dos: `synthetic_studies.period_id` es único y la activación mantiene **un** modelo activo por origen
(`services/synthetic_study.py:289-313`); dos periodos obligarían a dos estudios y a reactivar uno desactivando el otro. El estudio sintético
ya usa varios cortes dentro del mismo periodo.

## 6. Modelo de datos propuesto

### 6.1 Protocolo REAL (`processing_protocols`) — D4

Tabla con una fila por cohorte/periodo REAL. **Sin** campos de consentimiento, documento, autorizador ni fecha de permiso.

| Columna | Contenido |
|---|---|
| `id`, `period_id` (UNIQUE, FK a `academic_periods(id, data_origin='REAL')`) | cohorte/periodo |
| `school_label`, `cohort_label` | texto libre (colegio, «3.º secundaria 2026») |
| `grade_scale_min/max` | 0 y 20 |
| `participation_min/max` | 1 y 5 (`participation_labels` opcional) |
| `bimesters` (jsonb) | por bimestre: código, inicio, fecha de corte de datos, instante de disponibilidad, cierre, instante de disponibilidad del cierre, días programados |
| `source_label` | p. ej. «base de seguimiento académico (Excel)» |
| `quality_rules`, `eligibility_rules` (jsonb) | rangos, claves únicas, `inference_max_missing_fraction`, `required_features` |
| `risk_rule` (jsonb) | `RIESGO_V1` con sus umbrales (los de la hoja `Parametros`) |
| `opportune_windows` (jsonb) | plazos de detección e intervención (ver pregunta 2) |
| `authorization_confirmed_by_admin` (bool, por defecto `false`), `confirmed_by`, `confirmed_at` | CHECK: verdadero ⇔ actor e instante presentes |

Reglas: un trigger prohíbe editar parámetros una vez confirmado (cambios = otro protocolo); confirmar y revocar generan eventos de auditoría
`PROTOCOL_AUTHORIZATION_CONFIRMED`/`_REVOKED` con `actor_id` y `recorded_at` y solo `protocol_id`/`period_id` en el payload. `require_real_protocol`
devuelve el protocolo solo si está confirmado y cubre el periodo; en cualquier otro caso mantiene `INSTITUTIONAL_PROCESSING_NOT_READY`.
**Elegibilidad:** `students_eligibility_check` (`0003:23`) exige consentimientos para REAL. Se sustituye por un trigger que permite
`eligible_for_processing` en REAL solo si existe un protocolo confirmado y la matrícula pertenece a su periodo; `consent_documented`/`assent_documented`
siguen en `false` (no se fabrican).

### 6.2 Estudio institucional

`synthetic_studies` con `kind='INSTITUTIONAL_STUDY'`, `protocol_id` obligatorio, `csv_sha256` del CSV canónico de cortes y carga privada con
CSV, instantánea del protocolo y manifiesto del dataset. **No** guarda etiquetas en la carga privada: se leen de `risk_references` al construir el
dataset. `bindings` = lista de `snapshot_id` del periodo. `compare`/`register`/`activate` reutilizan el servicio con parámetro de alcance.

### 6.3 Dónde vive el riesgo de referencia: `risk_references`

Hoy solo existe en la carga privada del estudio sintético (`labels.outcomes`, enlazado por `bindings`; ver `services/indicators.py:80-100`).
Propuesta de tabla inmutable, común y consultable por los indicadores:

```
risk_references(
  id uuid PK,
  enrollment_id uuid NOT NULL, period_id uuid NOT NULL, data_origin text NOT NULL,
  snapshot_id uuid NOT NULL,                 -- corte (mitad de bimestre) cuyo objetivo es este cierre
  bimester text NOT NULL,                    -- código del protocolo (B1, B2)
  rule_version text NOT NULL,                -- 'RIESGO_V1'
  closing_date date NOT NULL, closing_available_at timestamptz NOT NULL,   -- >= target_date del corte
  average_grade numeric(5,2), days_scheduled int, days_attended int,
  activities_scheduled int, activities_delivered int,
  participation_level smallint CHECK (BETWEEN 1 AND 5), behavior_incidents int,   -- insumos de cierre
  points_grade/points_attendance/points_activities/points_participation/points_conduct smallint CHECK (BETWEEN 0 AND 2),
  total_points smallint CHECK (BETWEEN 0 AND 10), risk_level text CHECK (LOW|MEDIUM|HIGH),
  revision int NOT NULL, supersedes_id uuid, computed_by uuid NOT NULL, computed_at timestamptz NOT NULL,
  UNIQUE(snapshot_id, rule_version, revision),
  FK (snapshot_id, enrollment_id, data_origin) → academic_snapshots(id, enrollment_id, data_origin)
)
```

- CHECK de coherencia: el nivel se deduce del total (≥5 Alto; 2–4 Medio; ≤1 Bajo) y cada componente se deduce de su insumo (una `CASE` por componente);
  el trigger `deny_evidence_mutation` (ya existente) impide UPDATE/DELETE; una corrección crea otra `revision` que reemplaza a la anterior.
- **Independencia del modelo:** la calcula `app/services/risk_reference.py` (función pura con `Decimal` y enteros) al cargar los insumos de cierre; nunca
  recibe predicciones ni usa el modelo.
- **Sin fuga:** `closing_date >= snapshot.target_date`, `closing_available_at >= closing_date`, y los insumos de cierre **no** forman parte del conjunto de
  características del modelo (se almacenan en esta tabla, no en `academic_snapshots`).
- Los indicadores leen esta tabla para REAL (`reference_map`). Para SYNTHETIC se conserva la lectura de la carga privada; unificar es opcional y posterior.
- Migración necesaria: 0007 (esta tabla, `processing_protocols`, ampliaciones de CHECK, trigger de elegibilidad, extensión de `check_prediction_study` y
  `check_followup_provenance`, índice de un modelo activo por origen).

### 6.4 Bitácora de recepción y de reportes (diferida)

La base trae 126 recepciones (120 válidas, 6 rechazadas) y 120 fichas esperadas con 113 generadas; ese PRV (120/126) y el CRA (113/120) tendrían que salir de una bitácora de
recepción y otra de reportes. **Decisión 6 (2026-10-17): su procedencia está por confirmar y no se crean `reception_log` ni `report_log` por ahora.** Mientras tanto el
PRV del sistema solo cuenta los lotes que el propio sistema recibe (`import_batches`), con las limitaciones ya documentadas en el manual de indicadores. Si se confirma la
procedencia, las tablas serían solo de lectura tras la carga y con solo códigos. Tampoco se importa historial de alertas ni de intervenciones (decisiones 1 y 2).

## 7. Corte y cierre por bimestre

**Observación (al corte).** Una fila del CSV canónico = un estudiante en un bimestre, con las variables disponibles al corte:

| Variable | Fuente al corte | Disponibilidad |
|---|---|---|
| `average_grade` | media de las 6 notas **parciales** disponibles | ≤ 04-14 (B1) / 06-23 (B2) |
| `attendance_pct` | asistidos al corte ÷ 30 programados | 04-20 / 06-29 |
| `activities_pct` | entregadas al corte ÷ programadas al corte | 04-21 / 06-30 |
| `behavior_incidents` | incidencias con fecha ≤ corte | misma fecha del incidente (confirmar) |
| `participation_level` | **no existe al corte** | — (ver sección 8) |

**Mapeo de fechas al esquema del sistema.** El sistema exige `available_at ≤ cutoff_at` y `ventana ≤ disponibilidad ≤ corte < objetivo ≤ fin de periodo`.
En el Excel el «corte de datos» (04-17) es anterior a la disponibilidad (04-20/04-21). Por tanto: `window_start` = inicio del bimestre; `cutoff_at` =
`available_at` = instante de disponibilidad de la última fuente (04-21 y 06-30); `target_date` = cierre del bimestre (05-08 y 07-17). El **horizonte
queda en 17 días en ambos bimestres** (constante, compatible con `validate_observation`, `features/__init__.py:141`); `horizon_days` del
protocolo sustituye al 14 del estudio sintético.

**Cierre (objetivo).** El cierre no es un corte: son los insumos de cierre almacenados en `risk_references` (sección 6.3) y la referencia RIESGO_V1 resultante. Se
vincula al corte de su bimestre. Nunca entra al conjunto de características.

**Dos mediciones por estudiante.** B1 y B2 son dos cortes (`revision=1` cada uno) del mismo estudiante y periodo, con dos referencias. Los pares
(B1, B2) por estudiante sirven para la prueba dicotómica por estudiante (McNemar) y para el análisis pretest/postest; los indicadores aceptan un filtro
`bimester` (ventana del protocolo) además de periodo y sección.

**Fugas evitadas:** (1) etiqueta y características provienen de tablas distintas; (2) `closing_date ≥ target_date`; (3) no se usan variables de B1-cierre como
características de B2 en esta versión (aunque estuvieran disponibles antes del corte de B2, se excluyen para simplificar y evitar dependencia entre B1 y B2);
(4) la validación agrupa por estudiante.

## 8. Escala de participación y rangos de variables

- Hoy la participación 1–3 aparece fija en `csv_validation.py:118`, en `0001_demo_schema.sql:132` y `0005_manual_academic.sql:22-23`, y la etiqueta del formulario depende
  de `data_origin==='SYNTHETIC'` (`Measurements.tsx:43`). Con REAL el rango sale del protocolo (1–5): `csv_validation` recibe la escala del periodo y el CHECK pasa a 1–5.
- El rechazo `MEASUREMENT_OUT_OF_MODEL_SCALE` (Bloque 1) **ya usa la escala del modelo** (`services/ml.py:214-227`, `config.scales` y `participation_values`); no cambia.
- **Participación no está disponible al corte.** Tres caminos: (i) excluirla de las características (modelo de 4 variables) — **recomendado**; (ii) dejarla vacía: hoy falla
  (`TRAIN_FEATURE_WITHOUT_SUPPORT`, `train/__init__.py:103`) y la proyección SQL de `INSUFFICIENT_DATA` cuenta cinco columnas fijas (`repositories/students.py:37-44`);
  (iii) usar el valor de cierre: **prohibido por D1** (fuga). El camino (i) requiere un conjunto de variables configurable: `FeatureConfig` con `base_features`
  (por defecto las cinco, `features/__init__.py:14,54-55`), `factory` sin columna categórica cuando no hay participación (`train/__init__.py:38-57`) y la proyección SQL derivada
  del manifiesto del modelo. La participación de cierre sigue siendo insumo de RIESGO_V1.

## 9. Entrenamiento y evaluación con 60 estudiantes

Situación: 60 estudiantes (120 observaciones no independientes: el mismo estudiante en B1 y B2). Soporte por clase y bimestre: B1 15/21/24, B2 25/11/24 (Bajo/Medio/Alto). La clase más
escasa es Medio en B2 (11 estudiantes). El protocolo sintético actual (`compare_study`, `train/__init__.py:126`) necesita cortes externos con estudiantes de reserva distintos y **no
aplica**: reservar a B2 como prueba externa filtraría información porque son las mismas personas.

**Esquema recomendado (1.ª versión):**

1. **Unidad:** estudiante. Todas las particiones usan `StratifiedGroupKFold` con grupo = estudiante (B1 y B2 del mismo estudiante siempre juntos), que el código ya hace en
   `partitions` (`evaluate/__init__.py:8-23`).
2. **Evaluación principal:** validación cruzada de 5 pliegues **repetida** (p. ej. 20 repeticiones con semillas derivadas de la semilla del estudio) sobre las 120 observaciones agrupadas por
   estudiante (n efectivo = 60). Se reporta media y desviación entre repeticiones y la matriz de confusión agregada. Es lo que cambia en `train`: un `compare_institutional`
   que reutiliza `_compare`/`metrics` y añade el bucle de repeticiones y el cálculo de agregados (M).
3. **Sensibilidad:** *leave-one-student-out* (60 iteraciones) para comprobar la estabilidad; no sustituye al esquema principal.
4. **Análisis por bimestre** (opcional): el mismo esquema por separado con 60 observaciones.
5. **Selección:** se reportan los cuatro algoritmos (RF, SVM, XGBoost y `DUMMY` como línea base); la regla actual «mayor F1 macro, luego exactitud balanceada, luego orden fijo» se aplica
   sobre la media de las repeticiones. Sin ajuste de hiperparámetros (se conservan los de `factory`).
6. **Clases con pocos casos:** `partitions` exige que cada pliegue contenga las tres clases en entrenamiento y validación y reduce el número de pliegues si no es posible; con 11 estudiantes
   de Medio el máximo razonable es 5 pliegues. Las métricas por clase sin soporte salen `null` con motivo (`metrics`, `evaluate/__init__.py:27-50`).
7. **Modelo registrado:** ajuste final con todas las observaciones (como `_compare`), `approval_kind='LOCAL_EXPLORATORY'`, hash del dataset, semilla, parámetros, particiones y soporte por clase
   guardados en el manifiesto.

**Métricas que reporta el sistema:** matriz de confusión agregada, precisión/sensibilidad/F1 por clase, F1 macro, exactitud balanceada y exactitud, con media ± desviación entre repeticiones.

**Advertencias obligatorias en pantalla y manifiesto:** n = 60 estudiantes (120 observaciones no independientes); sin validación externa ni prospectiva; la selección y la evaluación usan los mismos datos
(optimismo posible); clases pequeñas (Medio B2 = 11); probabilidades no calibradas; los resultados son exploratorios, no demuestran eficacia escolar ni validan la tesis. La validación cruzada anidada es
opcional (mejora el sesgo de selección; esfuerzo M).

## 10. Conversor del Excel (Bloque 4)

Programa local `infra/convert_real_excel.py`: lee el Excel desde **fuera del repositorio** (ruta por argumento), escribe en un directorio **fuera del repositorio** (rechaza destinos dentro del árbol de Git),
no envía nada por red y descarta toda columna de nombre.

**Salidas (todas con códigos, ninguna con nombres):**

1. `cortes.csv` — CSV canónico del sistema (contrato vigente en `csv_validation.py:16-17`): `student_code, grade, section, cutoff_at, target_date, available_at, window_start, average_grade,
   attendance_pct, activities_pct, participation_level (vacío), behavior_incidents, age_years (vacío)`. 120 filas. Escalas: notas 0–20 con ≤ 2 decimales, porcentajes 0–100 con ≤ 2 decimales
   (calculados con enteros y redondeados mitad hacia arriba), fechas RFC 3339 en America/Lima, grado 3, secciones A y B.
2. `cierres.csv` — insumos de cierre por estudiante-bimestre (seis notas de curso o su media, días programados/asistidos, actividades programadas/entregadas, participación, incidencias, fechas de cierre y disponibilidad). El
   backend calcula RIESGO_V1; el conversor **no** envía el nivel (solo lo usa para una verificación local: 120/120 debe coincidir).
3. **Sin** bitácoras de recepción ni de reportes y **sin** historial de alertas ni de intervenciones (decisiones 1 y 6).
4. Opcional: `identidades.local.csv` (código → nombre) para cargar `full_name` en la ficha mediante una orden de ADMIN. Nunca entra al repositorio ni a evidencias.

**Validación y rechazo** (replica las 6 causas de la hoja `Procesamiento`): clave estudiante-bimestre duplicada; código fuera de la cohorte; asistidos > programados; nota fuera de la escala; entregadas >
programadas; bimestre ausente. Además: fechas dentro del calendario del protocolo, disponibilidad ≤ corte, `target_date` = cierre, y rechazo de cualquier campo que parezca un nombre. Las filas rechazadas **no** van al CSV de
cortes; el conversor solo informa en su resumen local el número de rechazos por causa (sin guardarlos en el sistema).

**Alertas e intervenciones del Excel: no se importan** (decisiones 1 y 2). Fueron generadas por script, de modo que no representan acciones reales: no se cargan
como historial ni se muestran como reales. Además las 79 alertas del Excel se calcularon con los datos del cierre y se emitieron después de él (05-11…07-28), y bajo D1 el
sistema genera las suyas al corte (≈ 04-21). El sistema **produce** predicciones y alertas propias mediante una evaluación **retrospectiva** (B2 «con sistema» es una simulación): cada
evaluación se ejecuta con `as_of` simulado y deja constancia de ambos relojes en `predictions.as_of_at` y `alerts.detected_at`, y esas alertas se rotulan como generadas por el sistema.
La detección oportuna se mide como alerta **antes del cierre** del bimestre. El NIA y la intervención oportuna **reales** no existen todavía: dependen de intervenciones registradas por
personas, ya sea con registros reales o en un piloto futuro (sección 13, pregunta 1).

## 11. Plan por bloques

| Bloque | Alcance | Archivos (aprox.) | Depende de |
|---|---|---|---|
| **3B** Protocolo y generalización | Migración 0007; `processing_protocols`; `risk_references`; función `risk_reference`; `require_real_protocol`; parámetro de origen en servicios/repositorios/SQL; elegibilidad por protocolo; pruebas de no mezcla | ~35 de aplicación + ~12 pruebas | — |
| **4** Conversor y carga | `convert_real_excel.py`; contrato del CSV canónico; CLI de registro de protocolo/estudio/cierres; ruta de importación REAL con hash del CSV | ~15 | contrato CSV (congelar antes), 3B para la carga |
| **5** Entrenamiento, evaluación e indicadores REAL | conjunto de variables configurable; `compare_institutional`; registro/activación REAL; evaluación retrospectiva al corte con `as_of_at`/`detected_at`; indicadores por origen y bimestre; etiquetas de UI | ~20 | 3B, 4 |
| **6** SVG | Gráficos propios en la página Indicadores | ~3 | API de indicadores estable |
| **7** Demo y E2E | datos de demo y prueba E2E | ~5 | 5 |

**Paralelismo:** el conversor (Bloque 4) puede desarrollarse en paralelo con 3B una vez congelado el contrato del CSV (no toca la aplicación); el Bloque 6 puede correr en paralelo con el 5. **No**
se paralelizan las migraciones (un solo responsable) ni 5 con 3B/4.

**Camino mínimo para la sustentación:** 3B núcleo (protocolo, generalización del estudio, `risk_references`, compuertas) → conversor + carga de cortes y cierres → comparación/registro/activación REAL y
evaluación al corte → indicadores desde `risk_references`. **Recortable:** (la bitácora de recepción y de reportes ya está diferida por la decisión 6), validación anidada, leave-one-out, gráficos SVG, flujo vivo de alertas con REAL, carga de nombres, respaldo REAL.

### Estado de implementación 3B-2 (2026-10-17)

Hecho: migración `0008_real_chain` (estudios institucionales sobre `synthetic_studies` con `kind`/`protocol_id`, un modelo activo por origen
con alcance, triggers de procedencia y elegibilidad por protocolo); punto único `study_for_period`/`require_real_protocol`; variables base
configurables (4 en REAL, sin participación); `compare_institutional` (CV agrupada repetida); evaluación retrospectiva con
`as_of_at`/`detected_at`; indicadores por origen y bimestre; página *Protocolo REAL*. Desviaciones: el estudio institucional, su
comparación y la activación se operan por CLI (`infra/study.py`), no por API; la alerta de B1 se actualiza en B2 (una alerta activa por
matrícula), de modo que el PDER de B2 hereda la detección de B1. La carga de nombres y el conversor del Excel siguen en el Bloque 4.

### Estado de implementación 3B-3 (2026-10-18)

Corrige las desviaciones de 3B-2. **Alerta única por matrícula:** el índice `ux_active_alert_enrollment` se conserva (una alerta activa por
matrícula, que se actualiza al apuntar a la predicción más reciente), pero PDER y CRA dejaron de leerla. Para cada corte se usa **la predicción de
ese corte**: *detectado* = predicción media/alta cuyo instante (`COALESCE(as_of_at, predicted_at)`) es anterior al cierre menos `detection_days`;
PDER = detectados ÷ alumnos con referencia media/alta en ese bimestre. *Cubierto* (CRA) = predicción baja, o media/alta con decisión de
seguimiento propia `CREATED`/`UPDATED` (`followup_decisions` liga cada predicción con la alerta que la reflejó); una alerta heredada de un corte
anterior no cubre. No hizo falta migración. NIA e intervención oportuna siguen anclados a la alerta real (`opened_at`). **Métricas REAL:** la cifra
principal es la validación cruzada agrupada por estudiante del informe de comparación del modelo activo (media, DE, repeticiones,
`metric_basis=OUT_OF_FOLD`); el cálculo en memoria queda como `in_sample_metrics` rotulado «en memoria, no valida el modelo». Sin informe:
`null` con `NO_OUT_OF_SAMPLE_REPORT`. Revocar el protocolo ahora también retira la elegibilidad de los alumnos REAL del periodo.

## 12. Criterios de aceptación (medibles)

**3B:** (1) las 338 pruebas existentes siguen pasando y se añaden las nuevas; (2) 0007 se aplica en base limpia y sobre una base 0006 conservando los resúmenes de todas las tablas previas (como
`test_m1_migration`); (3) cualquier operación REAL sin protocolo confirmado devuelve `INSTITUTIONAL_PROCESSING_NOT_READY` (matriz de endpoints); (4) con protocolo confirmado solo se habilitan los
periodos que cubre; (5) pruebas de no mezcla: un modelo REAL no evalúa cortes SYNTHETIC ni al revés (trigger y API), y un indicador no toma datos del otro origen; (6) `risk_references` es inmutable y
RIESGO_V1 se prueba con casos de frontera de cada componente generados en la prueba (sin datos reales en el repositorio); (7) ningún texto de auditoría contiene datos personales.
**4:** el conversor reproduce 120 cortes, 120 referencias RIESGO_V1 idénticas a la base, el resumen local informa 6 filas rechazadas por causa (sin guardarlas en el sistema), y los CSV generados no contienen nombres (búsqueda automática sobre columnas y valores); salida
fuera del repositorio; hash determinista del CSV.
**5:** el esquema de validación se reproduce con la misma semilla (mismos hashes y métricas); los 4 algoritmos y la línea base se reportan con media ± desviación; las advertencias de n pequeño aparecen en pantalla y
manifiesto; la evaluación al corte crea predicciones solo con las 4 variables; indicadores REAL sin la etiqueta «Simulación» y con la de datos reales locales; E2E sobre una copia aislada.

## 13. Riesgos y preguntas abiertas para el usuario

Abiertas:

1. **Intervenciones ejecutadas.** No se importan (decisión 1). Se registran con el **flujo existente de intervenciones** (actividad de una alerta del sistema, con su fecha efectiva real) cuando haya
   un piloto o registros reales; hasta entonces NIA e intervención oportuna reales no se calculan para esta cohorte y la simulación retrospectiva los rotula como tales.
2. **Procedencia del PRV 120/126 y de los reportes 113/120 del Excel** (decisión 6): por confirmar con la fuente; no se crean `reception_log` ni `report_log` mientras tanto.

Resueltas el 2026-10-17 (sección 2b): plazos de oportunidad (decisión 3), participación fuera de las características (4), corte = disponibilidad de la última fuente con horizonte de 17 días (4),
un solo periodo 2026 (4), B2 «con sistema» como simulación retrospectiva (2) y nombres solo en la ficha desde archivo local (5).

Riesgos técnicos: regresión por el parámetro de origen en SQL (mitigación: migración aditiva y pruebas cruzadas); `check_followup_provenance` y `check_prediction_study` son críticas (mitigación: pruebas
de trigger con REAL y SYNTHETIC); n pequeño (mitigación: advertencias y reporte de dispersión); semántica de la evaluación retrospectiva (mitigación: `as_of_at`/`detected_at` documentados y probados en 3B-1).
