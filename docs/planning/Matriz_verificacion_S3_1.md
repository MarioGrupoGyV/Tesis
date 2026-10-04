# Matriz de verificación S3.1

Alcance: **Estudio con datos sintéticos**, origen SYNTHETIC; REAL permanece bloqueado.
Contrato 0.4.0, prefijo `/api/v1`, 19 operaciones implementadas. Esta matriz separa
pruebas aisladas de la aplicación activa. No acredita resultados escolares, eficacia
institucional, aprobación académica ni implementación de S4–S6.

SHA inicial/final: `412c370519900351f37bf2d444df9c943e58288d`; cambios locales sin
commit. Los cierres y evidencias anteriores se conservan; los informes nuevos usan
el prefijo `s3-1`.

## Comprobaciones aisladas y documentales

Suite final consultada: **217 pruebas, cero fallos, errores y omisiones**, en
Linux/Python 3.12.12 y PostgreSQL 17.6 aislado, código de salida 0. Pytest informó
119,09 segundos y 40 advertencias; el JUnit registra 119,04 segundos. Las operaciones
de aplicación usan riesgo_app; el propietario prepara/migra y comprueba restricciones.
Evidencia: [JUnit backend](../../tests/evidence/s3-1-backend.xml) y
[entorno backend](../../tests/evidence/s3-1-backend-environment.json).

Los nombres siguientes corresponden a pruebas efectivamente presentes en esa suite.
Las pruebas de ML solo usan fixtures y almacenamiento temporal del entorno aislado.

| Criterio | Estado | Prueba o evidencia | Alcance y límite |
|---|---|---|---|
| ADR previa y separación científica | COMPROBADO documental | [ADR 006](../adr/006-estudio-sintetico-s3-1.md); [manual del estudio](../manuals/Manual_Estudio_Sintetico.md) | Separa software, comparación condicionada por el generador y evaluación real pendiente. No afirma aprobación del asesor/colegio. |
| Migración en base limpia | COMPROBADO aislado | `infra/run_backend_tests.py` ejecuta upgrade head antes de pytest; `test_migration_has_design_tables_and_s31_provenance_registry` | 14 tablas, registro privado y constraints revisados; no se ejecuta SQL de referencia sobre la base activa. |
| Migración desde S3 y conservación de historia | COMPROBADO aislado | `test_s3_1_migration.py::test_upgrade_from_s3_preserves_accounts_audit_and_historical_origins` | Base separada en 0002→0003; conserva huellas de cuentas/auditoría y valores DEMO/REAL históricos. REAL no puede activarse; no reetiqueta registros. |
| Origen y relaciones coherentes | COMPROBADO aislado | `test_database_origin_links_and_exact_registered_hash`; `test_prediction_database_rejects_other_synthetic_study`; `test_origin_scope_pairings_rejected` | Rechaza lote/hash incompatible, vínculos entre orígenes/estudios y combinaciones contradictorias de contratos internos. |
| Configuración/generador reproducibles | COMPROBADO aislado | `test_generator_deterministic_uuid_dates_bytes_and_private_outcomes`; `test_protocol_invalid_not_silently_repaired`; `test_v2_dataset_hash_survives_private_sorted_json_round_trip` | Mismos bytes/UUID/fechas/hashes con versión/configuración/semilla; 60 estudiantes ficticios y 360 cortes por defecto. No cambia fixtures para obtener precisión. |
| Preparación y CSV de procedencia verificada | COMPROBADO aislado | `test_preparation_is_explicit_idempotent_and_does_not_import`; `test_exact_csv_provenance_rejects_modification_and_wrong_context`; `test_unimported_study_cannot_compare_or_register` | Preparar no crea registros académicos. Solo el archivo exacto registrado entra al importador; rechazo de modificaciones, contexto REAL y origen declarado por cliente. |
| Preview, commit, vínculos y rollback | COMPROBADO aislado | `test_preview_commit_bindings_repetition_and_no_false_consent`; `test_synthetic_commit_rollback_includes_bindings_and_audit`; `test_registered_database_evidence_is_immutable` | Vista previa sin alumnos/matrículas/cortes; commit y enlaces a resultados privados atómicos. Consentimiento/asentimiento false no se presentan como autorizaciones reales. |
| Futuro, corte y disponibilidad temporal | COMPROBADO aislado | `test_synthetic_temporal_provenance_rejections`; `test_cv_and_external_are_distinct_no_groups_overlap_or_fit_leakage` | Rechaza disponibilidad posterior al corte, etiquetas ausentes/incompatibles y grupos solapados. Todas las etiquetas usadas en fit preceden a ajuste/reserva. |
| Grupos, pipelines y selección | COMPROBADO aislado | `test_imputation_train_development_only_and_no_refit_on_external`; `test_reserved_outcomes_do_not_choose_algorithm_or_fit` | Cuatro algoritmos comparten CV por estudiante; reserva sin fit/imputación/escala/selección. Regla de selección previa, sin tuning ni precisión mínima. |
| Diagnósticos CLI autenticados | COMPROBADO aislado | Dos casos de `test_authenticated_cli_ml_diagnostics_are_explicit_and_sanitized` | ADMIN y contraseña fixture comprobados efectivamente con riesgo_app; soporte insuficiente conserva su código y mensajes privados quedan sanitizados. Salida 2, sin datos/modelos/auditoría parciales ni regeneración. |
| Artefactos privados, compatibilidad y abstención | COMPROBADO aislado | `test_synthetic_signed_artifact_round_trip_and_abstention` para cuatro algoritmos; `test_v2_artifacts_rejected_before_deserialization`; `test_private_artifact_volume_supported_in_deployed_image_layout`; `test_private_artifacts_reject_entire_repository_not_only_backend`; regresión `test_artifact_rejection_before_deserialization` | Firma/hash/esquema/versión antes de deserializar; rutas/symlinks/corrupción rechazados; XGBoost conserva UBJSON. Comprueba la ubicación privada con layout de imagen desplegada y rechaza todo el checkout. Faltantes provocan abstención, probabilidades null. |
| Registro, activación y lectura real de API | COMPROBADO aislado | `test_full_registered_comparison_activation_and_api_inference`; `test_database_activation_rejects_real_and_incomplete_synthetic_manifest` | Servicios y PostgreSQL efectivos, registro/activación explícitos y auditados, lectura de modelos/estudiantes/detalle/historial. Aprobación técnica habilita únicamente simulación. CLI en activo se verifica aparte. |
| Permisos, CSRF y estado general | COMPROBADO aislado | `test_roles_csrf_and_general_processing_status`; `test_processing_status_tutor_without_synthetic_section`; `test_synthetic_and_real_catalogs_do_not_mix_sections_in_same_year` | ADMIN para escrituras; tutor por sección, sin mezclar catálogos del mismo año. RESEARCHER sin casos/modelos. El estado deriva de requisitos efectivos, no de health. |
| Privacidad de proyecciones y 503 | COMPROBADO aislado | Cuatro pruebas de `test_s3_1_public_projection.py`; `test_private_registered_payload_corruption_is_rejected` | Generación pública y comparación agregada sin códigos/grupos/etiquetas; evidencia privada conservada. `X-Role` no escala permisos; 503 sanitizada no revela SQL/secretos. |
| Idempotencia y concurrencia | COMPROBADO aislado | `test_concurrent_confirmations_reuse_one_synthetic_import`; `test_comparison_during_initial_commit_observes_no_partial_academic_evidence`; `test_full_registered_comparison_activation_and_api_inference`; regresión `test_concurrent_prediction_reuses_unique_result` | Un commit por archivo/periodo y ninguna comparación de filas parciales. Repetición SYNTHETIC no duplica predicciones; concurrencia del núcleo de persistencia también se conserva con fixtures inactivos S3. |
| Contrato, tipos, SQL y locks | COMPROBADO documental | [s3-1-contracts.json](../../tests/evidence/s3-1-contracts.json): 199 comprobaciones, 14 tablas, 19 rutas, 94 campos tipados | Checker estático; no sustituye permisos/migración/runtime. Regeneración de tipos y build frontend comprobados por el coordinador con `npm run generate:api --workspace frontend` y `npm run build --workspace frontend`. |
| Aviso servidor y regresión de navegador aislado | COMPROBADO aislado | [Playwright aislado](../../tests/evidence/s3-1-isolated-playwright.json): cinco pruebas passed; [entorno](../../tests/evidence/s3-1-browser-environment.json); capturas `s3-1-isolated-{rol}-*` | Aviso sintético, cuatro roles, contexto aislado vacío, teclado, restauración/logout/revocación y ausencia de tokens en storage. Tamaños 1440×900, 768×1024 y 390×844. No completa pantallas S4. |

Pruebas citadas de S3.1: [integración](../../backend/tests/test_s3_1_integration.py),
[migración](../../backend/tests/test_s3_1_migration.py), [ML](../../backend/tests/test_s3_1_ml.py)
y [privacidad](../../backend/tests/test_s3_1_public_projection.py).

## Aplicación activa y cierre integrado

Estos criterios están **COMPROBADOS** con las evidencias de la aplicación activa.
El recorrido usa API/PostgreSQL reales y comandos ADMIN explícitos; sus resultados
se verifican separadamente de la suite aislada.

| Criterio | Estado | Comando/evidencia | Resultado observado |
|---|---|---|---|
| Recorrido local completo | COMPROBADO activo | `py -3.12 infra/review_study.py --admin-credential ADMIN --tutor-id <tutor_id>`; [48 peticiones sanitizadas](../../tests/evidence/s3-1-active-endpoints.json) | Generar→preview→GET lote→commit→comparar→registrar→activar→inferir→consultar/listar/historial. 60 estudiantes ficticios, 360 cortes, un modelo SVM de simulación; 55 predicciones y cinco abstenciones. Repetición: cero nuevas, 55 reutilizadas. |
| Comparación sintética y selección previa | COMPROBADO activo | [Comparación agregada](../../tests/evidence/s3-1-comparison.json); comandos `compare/register/activate` del recorrido | Cuatro algoritmos, desarrollo por grupos y reserva externa separados; SVM seleccionado por la regla de desarrollo y activado explícitamente. Métricas dependen del generador; probabilidades no calibradas null. |
| Cuatro cuentas y acceso por sección en activo | COMPROBADO activo | [Reporte de endpoints](../../tests/evidence/s3-1-active-endpoints.json) | ADMIN, TUTOR, DIRECTOR y RESEARCHER; sección propia/ajena, CSRF, roles y cookie revocada. RESEARCHER sin casos/modelos ni escalada por X-Role. Cuatro cuentas y hashes de contraseña conservados, credenciales privadas. |
| Persistencia y preservación histórica | COMPROBADO activo | `$env:PERSISTENCE_REPORT_PREFIX = 's3-1'`; `py -3.12 infra/check_access_persistence.py`; [persistencia](../../tests/evidence/s3-1-persistence.json) y [cierre integrado](../../tests/evidence/s3-1-review.json) | Recreación sin borrar volúmenes: 14 tablas y archivos privados exactamente iguales inmediatamente después. Estudio/artefactos, cuentas y auditoría conservados; login/logout/revocación posteriores sin cambios académicos. Entorno histórico detenido y hashes del respaldo intactos. |
| Aviso y regresión visual de aplicación activa | COMPROBADO activo | `$env:REVIEW_REPORT_PREFIX = 's3-1-active'`; `py -3.12 infra/review_browser.py`; [Playwright activo](../../tests/evidence/s3-1-active-playwright.json) y capturas | Cinco pruebas passed, cuatro roles y tres tamaños. Aviso obtenido del servidor, contexto SYNTHETIC por rol, teclado, sesión y revocación. Inspección visual real del coordinador: ADMIN 1440×900, TUTOR 390×844 e investigador 768×1024. Sin credenciales; solo acceso/inicio actual, sin pantallas S4. |
| Validador final integrado | COMPROBADO | `infra/check_study.py`; [s3-1-review.json](../../tests/evidence/s3-1-review.json) | 19 rutas, 48 respuestas activas y 16 muestras positivas válidas contra el contrato. Suite 217 y navegador activo/aislado cinco casos cada uno; pip check aprobado, CLI REAL bloqueada, locks/versiones/históricos conservados, volúmenes/cuentas/backup comprobados. |

Capturas inspeccionadas: [ADMIN escritorio](../../tests/evidence/s3-1-active-admin-1440x900.png),
[TUTOR móvil](../../tests/evidence/s3-1-active-tutor-390x844.png) e
[investigador tablet](../../tests/evidence/s3-1-active-researcher-768x1024.png).
La revisión automatizada también cubre los demás roles/tamaños; no constituye
una auditoría completa de accesibilidad ni evidencia de pantallas pendientes.

## Fallos conservados y límites

Las ejecuciones previas permanecen como evidencia: `s3-1-backend-first.xml` registra
204 pruebas y tres fallos; `s3-1-backend-second.xml`, 210 y un fallo;
`s3-1-backend-lock-probe.xml`, 213 y un fallo. La suite final citada arriba registra
217 y cero fallos. El [primer recorrido activo](../../tests/evidence/s3-1-active-first-endpoints.json)
falló durante generación con `PRIVATE_STORAGE_REQUIRED`: el cálculo de raíz del
checkout no contemplaba el layout de la imagen API. Se corrigió sin escrituras
académicas parciales y se añadieron las dos pruebas de ubicación/rechazo del checkout;
la suite y el recorrido finales quedaron aprobados. [Estado S3.1](Estado_Sprint_3_1.md)
registra causas, correcciones y comandos. Estos informes previos no se borran ni se
presentan como comprobaciones aprobadas. Las 40 advertencias de la suite final se
conservan como diagnóstico, sin actualizar dependencias para ocultarlas.

**PENDIENTE académico:** revisión con asesor de objetivos/hipótesis, unidad de
análisis, origen/generador, instrumentos, análisis, discusión y generalización.
No se edita el documento académico oficial ni se afirma autorización del colegio.
**NO EJECUTADO / fuera de alcance:** uso de datos reales, entrenamiento/activación
REAL, evaluación institucional, calibración y S4–S6. La CV de grupos y la reserva
temporal sintética son evidencias diferentes, ambas dependientes del generador.

El checklist de base vacía no se ejecuta sobre la aplicación con cuentas/estudio.
No commit, push, despliegue externo ni eliminación de volúmenes.
