# Mapa de impacto: procesamiento REAL (Bloque 3A, solo diseño)

Fecha: 2026-10-17. Rama `mejoras-tesis`, HEAD `c44e0cc`. No se modificó código, migraciones, contrato ni pruebas.
Complementa el [ADR 012](../adr/012-procesamiento-real.md). Líneas verificadas contra el árbol actual (338 pruebas
pasan; las migraciones 0001–0006 son las únicas existentes).

Clasificación: **P** = se generaliza con un parámetro de origen; **N** = requiere código/SQL nuevo; **D** = se deja como está.
Esfuerzo: **S** (≤ unas líneas, una prueba), **M** (función o consulta nueva, varias pruebas), **L** (subsistema).

## 1. Esquema SQL (triggers, funciones, CHECK, FK)

| Archivo:línea | Qué ata a SYNTHETIC | Clase | Esf. |
|---|---|---|---|
| `0003_synthetic_study.py:12-18` (`processing_origin`) | Solo admite `REAL`/`SYNTHETIC` en 9 tablas; ya permite REAL. | D | — |
| `0003_synthetic_study.py:23` (`students_eligibility_check`) | REAL elegible exige `consent_documented AND assent_documented`. D4 prohíbe guardar consentimientos: hay que sustituir la regla por una basada en el protocolo confirmado. | N | M |
| `0003_synthetic_study.py:26-44` (`synthetic_studies`) | `data_origin CHECK ='SYNTHETIC'`, `generator_version CHECK ='synthetic-generator-v1'`, `period_id UNIQUE`, `storage_key` de carga privada con CSV+dataset+etiquetas. Es el ancla de toda la cadena. | P | M |
| `0003_synthetic_study.py:46-48` (`import_batches_/model_versions_synthetic_provenance`) | `(data_origin='SYNTHETIC')=(study_id IS NOT NULL)`: hoy un lote/modelo REAL **no puede** tener `study_id`. | P | S |
| `0003_synthetic_study.py:49` (`import_registered_csv_fk`) | El lote debe tener el mismo hash que el CSV registrado del estudio. Sirve tal cual para REAL si el estudio registra el hash del CSV canónico. | D | — |
| `0003_synthetic_study.py:50-53` (`synthetic_only_active_model`) | Modelo activo exige `SYNTHETIC`, `scope='SYNTHETIC_STUDY'`, `approval_kind='TECHNICAL_SIMULATION'`. | N | M |
| `0006_manual_evaluable.sql:20-38` (`check_prediction_study`) | Solo valida procedencia `IF NEW.data_origin='SYNTHETIC'`; una predicción REAL hoy no comprueba estudio=modelo. Debe aplicar a REAL (con el mismo estudio por periodo). | N | M |
| `0006_manual_evaluable.sql:40-76` (`check_followup_provenance`) | Rechaza todo lo que no sea `SYNTHETIC` (`'Institutional followup is blocked'`). Debe permitir REAL solo con protocolo confirmado que cubra el periodo. | N | M |
| `0006_manual_evaluable.sql:3-18` (`deny_manual_prediction`) | Mediciones MANUAL solo se evalúan en SYNTHETIC. REAL manual queda bloqueado (no es objetivo de este plan). | D | — |
| `0004_followup.py:14,22` (`followup_decisions`) | `data_origin CHECK ='SYNTHETIC'` y FK a `synthetic_studies(id,data_origin)`. | P | S |
| `0004_followup.py:65-120` (`check_followup_change`) | Reglas de versión/inmutabilidad; llama a `check_followup_provenance`. Generic. | D | — |
| `0004_followup.py:122-135` (`check_followup_decision`) | Compara estudio de la predicción con el de la decisión; generic. | D | — |
| `0001_demo_schema.sql:132` y `0005_manual_academic.sql:22-23` (`snapshot_participation_scale`) | Participación 1–3 para CSV (1–5 solo MANUAL). La tesis usa 1–5. | P | S |
| `0005_manual_academic.sql:24-31` (`snapshot_channel_provenance`) | CSV exige `target_date`, `purpose='PARTIAL'`, lote y hash: encaja con los cortes a mitad de bimestre. | D | — |
| `0005_manual_academic.sql:37` (`check_snapshot_period`) | Ventana ≤ disponibilidad ≤ corte < objetivo ≤ fin de periodo; sirve para un periodo 2026 que contenga ambos bimestres. | D | — |
| (no existe) | No hay tabla para riesgo de referencia, protocolo REAL, bitácora de recepción ni historial importado. | N | L |

## 2. ORM y repositorios

| Archivo:línea | Qué ata a SYNTHETIC | Clase | Esf. |
|---|---|---|---|
| `models/synthetic.py:10` (`SyntheticStudyRecord`, tabla `synthetic_studies`) | Nombre y semántica sintéticos; ~12 consultas SQL usan el nombre literal. Se conserva el nombre en 3B; renombrar es cosmético y posterior. | P | S |
| `models/followup.py:52`, `models/ml.py:15`, `models/s2.py:42` | `study_id` FK; ya genéricos. | D | — |
| `repositories/followup.py:7-12` (`REGISTERED_SECTION`) | `ctx.data_origin='SYNTHETIC'` y secciones del manifiesto del estudio. Parametrizar origen; para REAL el manifiesto del estudio debe traer el contexto de secciones. | P | M |
| `repositories/followup.py:24,29,52,91,118` | Filtros `data_origin='SYNTHETIC'` en recurso, matrículas, filas actuales, listado y detalle de casos. | P | S |
| `repositories/followup.py:46-49` (`current_rows`) | `COALESCE(ib.study_id, estudio del periodo con data_origin='SYNTHETIC')`. | P | S |
| `repositories/followup.py:71-80` y `repositories/students.py:37-44` (CASE de `INSUFFICIENT_DATA`) | La fracción de faltantes se calcula sobre **cinco** columnas fijas; con un conjunto de variables distinto (sin participación) la proyección no coincidiría con lo que decide el modelo. | N | M |
| `repositories/students.py:17-20` (`current_model`) | `e.data_origin<>'SYNTHETIC' OR m.study_id=...`: para REAL no exige estudio. Generalizar a «modelo del estudio del periodo» para ambos orígenes. | P | S |
| `repositories/reports.py:17` | `e.data_origin='SYNTHETIC'`. | P | S |
| `repositories/indicators.py:27,42,67` | Mismo filtro en filas por estudiante, lotes e intervenciones. | P | S |
| `repositories/s1.py:49-59` (`sections_for_period`) | SYNTHETIC se ata al manifiesto del estudio; REAL usa `grade_sections.data_origin`. Ya soporta ambos. | D | — |
| `repositories/ml.py:9-10,18,32` | Ya filtran `('REAL','SYNTHETIC')`. | D | — |

## 3. Servicios

| Archivo:línea | Qué ata a SYNTHETIC | Clase | Esf. |
|---|---|---|---|
| `services/processing_policy.py:13-22` (`require_ml_protocol`, `require_processing_protocol`) | Excepciones incondicionales `INSTITUTIONAL_PROCESSING_NOT_READY`. Se vuelven `require_real_protocol(db, period)` que devuelve el protocolo si está confirmado. | N | M |
| `services/processing_policy.py:24-27` (`synthetic_studies`) | Lista solo estudios (sintéticos). Los guards de API (`api/v1/ml.py:30-32`, `api/v1/followup.py:29-31`, `services/imports.py:94-96`) preguntan «¿hay algún estudio?» antes de parsear. | P | S |
| `services/processing_policy.py:56-62,78-92` (`processing_status`) | `scope='SYNTHETIC_STUDY'`, códigos `SYNTHETIC_*`, `institutional_ready=False` fijo, un solo conjunto de operaciones. | N | M |
| `services/synthetic_study.py` (24 referencias a `study_id`; `prepare` 87, `validate_registered` 54, `bind_imported` 137, `compare_registered` 225, `register_model` 254, `activate_model` 289) | Estudio sintético completo: genera, valida carga privada (`labels_sha256`), vincula, compara con reserva externa, registra con `data_origin='SYNTHETIC'`, `approval_kind='TECHNICAL_SIMULATION'`; **activación desactiva todo modelo activo del origen** (`advisory_lock('active-model:SYNTHETIC')`, línea 289-313). | P/N | L |
| `services/synthetic_study.py:74-85` (`verified_csv`) y `services/imports.py:99-104` (`registered_source`) | REAL llama a `require_processing_protocol()` y devuelve `None`. REAL necesita verificar el hash del CSV canónico contra el estudio registrado. | N | M |
| `services/imports.py:173` | `eligible_for_processing=batch.data_origin=='SYNTHETIC'`: REAL queda no elegible. | P | S |
| `services/imports.py:205-231` (`commit`) | `bind_imported` solo en SYNTHETIC; REAL debe vincular snapshots y cargar `risk_references`. | N | M |
| `services/manual.py:119,157` | Elegibilidad por origen (`period.data_origin=='SYNTHETIC'`). | P | S |
| `services/ml.py:64,110` | REAL elegible exige `consent_documented AND assent_documented`. | N | S |
| `services/ml.py:66,71,142-171` (`load_active_model`) | `SyntheticStudyRecord` por periodo; exige `scope=='SYNTHETIC_STUDY'` y `approval_kind=='TECHNICAL_SIMULATION'`. | P | M |
| `services/ml.py:179,236` (`run_period`, `evaluate_student`) | `if period.data_origin!='SYNTHETIC': require_ml_protocol()`. | P | S |
| `services/ml.py:214-227` (`out_of_model_scale`) | **Ya toma la escala del modelo** (`config.scales`, `participation_values`). No cambia. | D | — |
| `services/followup.py:40-68` (`context_period`) | REAL → `require_processing_protocol()`; exige `SyntheticStudyRecord`. | P | M |
| `services/followup.py:85-91,115,133,158,296` | Modelo activo por `study_id`, `data_origin='SYNTHETIC'` en alertas, decisiones, actividades. | P | M |
| `services/indicators.py:54,68-69,82-83,225` | REAL bloqueado; contextos y referencia solo del estudio sintético (`labels.outcomes` vía `bindings`); `data_origin='SYNTHETIC'` literal en la respuesta. | P/N | M |
| `services/indicators.py:262,271,301,308` y `services/reports.py:80,89` | `'SYNTHETIC','SYNTHETIC_STUDY'` fijos en CSV y auditoría. | P | S |
| `services/csv_validation.py:16,118` | Participación `(1,3)` fija y `grade` 1–5; requiere parametrizar por protocolo. | P | S |
| `services/catalogs.py:28`, `services/imports.py:27` | Ya admiten REAL. | D | — |

## 4. ML (`backend/app/ml`)

| Archivo:línea | Qué ata a SYNTHETIC | Clase | Esf. |
|---|---|---|---|
| `features/__init__.py:14,54-55` (`BASE_FEATURES`, `features`) | Las cinco variables base son fijas; no se puede excluir participación. | N | M |
| `features/__init__.py:106,127-133` (`Dataset.scope`) | Existe el alcance `INSTITUTIONAL` (datos REAL, `ml-dataset-v1`), sin uso. | P | S |
| `features/__init__.py:141` (`validate_observation`) | Horizonte exacto = `config.horizon_days` (ya parametrizable: 17 días con el calendario real, ver ADR). | D | — |
| `manifest.py:44-45,70-79` | `scope` solo `ISOLATED_TEST`/`SYNTHETIC_STUDY`; metadatos sintéticos obligatorios según alcance. | N | M |
| `artifacts.py:78-82,147-154` | Verifica alcance/origen y procedencia sintética del artefacto. | N | M |
| `predict/__init__.py:34-36` | SYNTHETIC exige `scope='SYNTHETIC_STUDY'` y `ml-artifact-v2`; REAL exige `ISOLATED_TEST`. | N | S |
| `train/__init__.py:38-57` (`factory`) | Participación categórica one-hot con `participation_values` del modelo (**ya parametrizable**), pero la columna `participation_level` está fija en el `ColumnTransformer`. | N | S |
| `train/__init__.py:66-70` (`compare`) | Todo alcance ≠ `ISOLATED_TEST` llama a `require_ml_protocol()`. | P | S |
| `train/__init__.py:73-117` (`_compare`) | Validación cruzada agrupada por estudiante, genérica; un solo plan de particiones; `TRAIN_FEATURE_WITHOUT_SUPPORT` si una variable está vacía en un pliegue. | D (base) / N (repetición) | M |
| `train/__init__.py:126-243` (`compare_study`) | Protocolo sintético con cortes de desarrollo/externos y estudiantes de reserva distintos; no aplica a 60 estudiantes con B1/B2 de las mismas personas. | N | L |
| `evaluate/__init__.py:8-23,27-50` (`partitions`, `metrics`) | Genéricos; `metrics` devuelve `None` + motivo si falta soporte. Se reutilizan. | D | — |
| `ml/cli.py:15`, `synthetic_cli.py` | CLI solo del estudio sintético; `ml/cli.py` bloquea todo salvo aislado. | N | M |

## 5. API, contrato e infraestructura

| Archivo:línea | Qué ata a SYNTHETIC | Clase | Esf. |
|---|---|---|---|
| `api/v1/ml.py:30-32`, `api/v1/followup.py:29-31` | Guard previo «sin estudios → bloqueado». | P | S |
| `schemas/processing.py:29,31-32` | `scope: Literal['SYNTHETIC_STUDY']`, `institutional_ready: Literal[False]`, `synthetic_ready`. | N | M |
| `schemas/indicators.py:114`, `schemas/s5.py:168` | `data_origin: Literal['SYNTHETIC']`. | P | S |
| `docs/planning/Contrato_API.yaml`, `frontend/src/lib/api.generated.d.ts` | Reflejan los literales anteriores y las operaciones nuevas. | N | S |
| `infra/study.py`, `infra/check_s4.py`, `infra/check_s5.py`, `infra/check_s6.py`, `infra/check_study.py` | Comprobaciones y CLI del estudio sintético; no se tocan (históricas). | D | — |
| `infra/backup_restore.py:69,250-251,272` | Manifiesto de respaldo con `origin='SYNTHETIC'` y alcance privado `SYNTHETIC_STUDY`: un respaldo con datos REAL se rechazaría. Requiere decidir si el respaldo cubre REAL (DPAPI ya aplica). | N | M |

## 6. Frontend

| Archivo:línea | Qué ata a SYNTHETIC | Clase | Esf. |
|---|---|---|---|
| `app/App.tsx:72` | Periodo inicial: el primero SYNTHETIC. | P | S |
| `features/alerts/AlertsPage.tsx:18`, `AlertDetailPage.tsx:28-29` | «Seguimiento institucional bloqueado» si no es SYNTHETIC. | P | S |
| `features/reports/ReportsPage.tsx:16` | «Reporte institucional bloqueado». | P | S |
| `features/home/HomePage.tsx:12-15` | Resumen solo SYNTHETIC. | P | S |
| `features/imports/ImportsPage.tsx:114` | Importación bloqueada si no es SYNTHETIC; pide CSV registrado del generador. | P/N | M |
| `features/models/EvaluationPanel.tsx:29,41`, `ModelDetailPage.tsx:28-32` | Evaluación y avisos de «simulación» solo SYNTHETIC. | P | S |
| `features/students/EvaluateStudent.tsx:18`, `Measurements.tsx:43`, `ManualForms.tsx:49` | Botón/etiqueta «1–3 en la simulación». Debe leer la escala del protocolo/modelo. | P | S |
| `features/indicators/IndicatorsPage.tsx` | Chips «Simulación» y aviso fijo; con REAL deben decir «datos reales locales, exploratorio». | P | S |
| `lib/format.ts:17-23` | Textos `SYNTHETIC_*`. | P | S |

## 7. Garantías de no mezcla (qué ya existe y qué falta)

- Existe: FK compuesta `(study_id, data_origin)` en `import_batches` y `model_versions`; FK de `followup_decisions` al estudio
  con origen; `Dataset`/`ArtifactManifest` validan `scope` ↔ `data_origin`; `persist_evaluated` exige snapshot y modelo del mismo origen
  (`services/ml.py:66`).
- Falta: `check_prediction_study` para REAL; un índice único «un modelo activo por (origen, estudio)» en lugar del bloqueo global por
  origen; pruebas cruzadas REAL↔SYNTHETIC en trigger, API e indicadores.

## 8. Lectura de conjunto

- La mayoría de los puntos son **P** (cambiar un literal `'SYNTHETIC'` por el origen del periodo) y de esfuerzo **S**; el costo real está en los **N**: el protocolo y sus compuertas,
  la tabla de referencia de riesgo, los dos triggers de procedencia, el conjunto de variables configurable y la comparación institucional.
- Las pruebas existentes cubren el camino sintético; los cambios P deben conservar el valor por defecto actual para que sigan pasando sin modificar sus datos.
- Estimación para el Bloque 3B: ~35 archivos de aplicación y ~12 de pruebas; para el Bloque 5: ~20 más. Las cifras son orientativas.
- Bloque 4 (conversor del Excel): no altera ninguna fila del mapa; es un programa local nuevo (`infra/convert_real_excel.py`) que solo escribe archivos fuera del repositorio.
