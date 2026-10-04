# Estado del Sprint 3.1 — Estudio con datos sintéticos

**COMPROBADO, 4 de octubre de 2026 (America/Lima).** Únicamente S3.1: adaptación
local ejecutada con API/PostgreSQL reales del proyecto y registros nuevos SYNTHETIC.
No se usaron registros de alumnos reales ni datos de la antigua DEMO. REAL permanece
bloqueado. S4–S6 pendientes. [ADR 006](../adr/006-estudio-sintetico-s3-1.md),
[manual reproducible](../manuals/Manual_Estudio_Sintetico.md) y
[matriz](Matriz_verificacion_S3_1.md) detallan decisiones y criterios.

SHA inicial y final de HEAD: `412c370519900351f37bf2d444df9c943e58288d`.
Checkout inicialmente limpio; cambios finales locales, **sin commit, push ni despliegue externo**.
La solicitud S3.1 sustituye la prohibición de generar registros ficticios para este
estudio concreto; no atribuye esta decisión a los cierres anteriores.

## Cambios implementados

- Migración manual `0003_synthetic_study`, posterior a 0002, 14 tablas. Nueve
  dominios aceptan SYNTHETIC; las restricciones incompatibles se sustituyen
  explícitamente, sin transformar historia ni permitir nuevos DEMO. REAL no puede
  activarse. Se conservan defaults academic-v1, claves compuestas, revisiones,
  unicidad, permisos y guards de evidencia/auditoría. Sin autogeneración ni SQL retroactivo.
- Registro privado mínimo synthetic_studies: configuración/manifiesto y hashes,
  CSV exacto/periodo, vínculos entre cortes importados y resultados futuros,
  comparación incorporada una vez. Payload y etiquetas fuera del checkout.
  Lote/modelo/periodo y predicción conservan origen y estudio con FK/guards.
- Generador `synthetic-generator-v1` con protocolo `synthetic-study-v1`:
  trayectorias, heterogeneidad y ruido; cinco variables base, escalas explícitas de
  simulación, UTC/días Lima, resultados futuros separados. UUID5/fechas/bytes
  reproducibles; timestamps de incorporación operativa separados. Dataset/manifiesto
  v2 SYNTHETIC_STUDY mantiene v1 histórico. Hash v2 canónico tras round-trip JSON.
- Importación mediante preview/GET lote/commit existentes, verificación de archivo
  exacto registrado, origen asignado en servidor, expected_preview_version, CSRF,
  atomicidad/idempotencia/locks. Preview no crea filas académicas. Consentimiento y
  asentimiento quedan false, sin fingir aprobación institucional. Contextos/secciones
  REAL y SYNTHETIC del mismo año se separan en las consultas.
- Comparación Dummy/Random Forest/SVM/XGBoost CPU con pipelines, grupos, misma CV y
  reserva posterior independiente; sin tuning/calibración. Selección fijada en
  desarrollo, antes de reserva. Solo ese algoritmo puede registrarse/activarse.
  Archivos privados firmados, hashes/versiones/esquemas/procedencia antes de carga;
  XGBoost conserva UBJSON nativo. Registro/activación ADMIN explícitos, auditados y
  atómicos; sin entrenamiento HTTP ni carga/activación al arrancar.
- Inferencia existente integrada con SYNTHETIC, último corte/revisión por as_of,
  unicidad snapshot/model, auditoría, reutilización y abstención. Probabilidades
  null, probabilities_calibrated=false. Lecturas muestran Datos insuficientes cuando
  incumplen la política del modelo; sin predicción válida no aparece riesgo LOW.
- Única operación nueva: **GET /api/v1/processing/status**, autenticada, permisos
  efectivos y motivos por operación, sin registros privados. RESEARCHER conserva
  restricciones. Contrato **0.4.0**, 19 operaciones, tipos frontend regenerados y
  SQL de referencia/validadores actualizados. Cambio incompatible: origen público
  REAL/SYNTHETIC y nuevos contratos internos v2.
- Acceso/inicio muestra el aviso del servidor: «Estudio con datos sintéticos. No
  corresponde a estudiantes reales». Sin selector institucional ni pantallas S4.
  Comandos y runners PowerShell usan prefijos S3.1 para preservar evidencias previas.

Áreas modificadas: backend/app/api, core/study_storage, models, schemas,
repositories, services, ml y synthetic_cli; migración 0003; regresión backend;
frontend/App, API/tipos; Compose y herramientas infra; AGENTS/README/backend/infra,
plan/criterios/Inicio/conciliación, ADR 006, manual y cierres nuevos. Listado exacto:
[s3-1-changed-files.json](../../tests/evidence/s3-1-changed-files.json).
Las migraciones 0001/0002, cierres, ADR previas, evidencias históricas y locks no cambiaron.

## Recorrido efectivo y preservación

Entorno local riesgo-escolar, DB riesgo_escolar, API/CLI con **riesgo_app**;
propietario solo para migrar. Puertos 15173/18000/55432 y volúmenes db_data,
import_data y ml_data conservados. La aplicación antes tenía cuatro cuentas y cero
registros escolares/modelos/predicciones. No se recrearon cuentas ni se restablecieron
contraseñas; se usaron sus credenciales privadas Windows en memoria/stdin.

El recorrido realizó generar → preview → detalle de lote → commit → comparar →
registrar → activar explícitamente → predictions/run → lista/detalle/historial.
[48 peticiones/respuestas sanitizadas](../../tests/evidence/s3-1-active-endpoints.json)
contra API/DB, junto con comandos autenticados para operaciones internas:

| Resultado activo | Cantidad/estado |
|---|---|
| Estudio / periodo / secciones SYNTHETIC | 1 / 1 / 2 |
| Estudiantes ficticios independientes / matrículas | 60 / 60 |
| Observaciones importadas / lote | 360 / 1 |
| Modelos comparados en almacenamiento privado | 4 |
| Modelo registrado/activo | 1, SVM; APPROVED/TECHNICAL_SIMULATION únicamente |
| Cortes seleccionados para inferencia | 60 |
| Predicciones nuevas | 55 |
| Abstenciones | 5; sin filas de riesgo inventadas |
| Segunda ejecución, mismo as_of | 0 nuevas; 55 reutilizadas; mismas abstenciones |
| Alertas / intervenciones | 0 / 0 |
| Cuentas locales | 4, hashes de contraseña sin cambios |

ADMIN consultó modelos/estudiantes/historial; TUTOR solo su sección (30 casos),
DIRECTOR las dos (60); RESEARCHER sin casos/modelos. Predicción ajena e inexistente
ambas 404 para TUTOR. ADMIN sin CSRF fue rechazado; otros roles no ejecutan inferencia.
Logout y cookie revocada comprobados en los cuatro roles. El checker final verifica también
las 28 sesiones y 59 eventos de auditoría anteriores contra sus huellas iniciales,
sin publicar esas huellas. No se registraron secretos
ni etiquetas reservadas en la evidencia pública; códigos de estudiantes sanitizados.

[Persistencia](../../tests/evidence/s3-1-persistence.json): down/up **sin -v**,
instantáneas de las 14 tablas, cuentas, hashes, sesiones, auditoría, CSV y artefactos
exactamente iguales antes/después de recrear. Los accesos posteriores solo añadieron
su sesión/auditoría esperadas. Entorno histórico DEMO detenido y hashes de sus
respaldos intactos, comprobados por el validador final. No se ejecutó checker de base vacía.

## Comparación experimental sintética

Protocolo/semilla prefijados: 1729, 60 estudiantes ficticios, seis cortes por persona.
48 estudiantes de desarrollo y 12 de reserva. **143 observaciones de desarrollo**,
**33 de reserva externa**, cinco folds efectivos por grupos; soporte LOW/MEDIUM/HIGH
13/64/66 y 2/14/17, respectivamente. La unidad independiente es el estudiante.

Ajuste simulado: 2025-05-01T22:00:00Z (17:00 Lima); etiquetas de train disponibles
antes del ajuste y cortes externos de julio/agosto/septiembre. El comando de ajuste
real ocurrió en octubre de 2026; este calendario simulado no acredita prospección
real. Exclusiones: 144 cortes tardíos de desarrollo fuera de fit; 36 cortes tempranos
de reserva fuera de evaluación externa; 1 observación de desarrollo y 3 externas no
elegibles. No se aumentó población ni se regeneró para conseguir métricas.

Selección por macro-F1 agregado de predicciones CV de desarrollo, luego balanced
accuracy, luego orden fijo DUMMY/RANDOM_FOREST/SVM/XGBOOST. La variación de folds se
reporta aparte. SVM se seleccionó con esa regla; **XGBoost obtuvo mayor macro-F1 en
reserva y no sustituyó la selección**. No es un concurso para aprobar uso escolar.

| Algoritmo | Macro-F1 desarrollo | Balanced desarrollo | Macro-F1 reserva | Balanced reserva | SD macro-F1 entre folds |
|---|---:|---:|---:|---:|---:|
| DUMMY | 0.275051 | 0.320076 | 0.226667 | 0.333333 | 0.008012 |
| RANDOM_FOREST | 0.545283 | 0.533763 | 0.401235 | 0.418768 | 0.104423 |
| SVM | 0.610365 | 0.594831 | 0.402975 | 0.414566 | 0.136903 |
| XGBOOST | 0.535784 | 0.528397 | 0.548387 | 0.577031 | 0.117298 |

Matrices de confusión: filas reales simuladas y columnas predichas, orden
LOW/MEDIUM/HIGH; development = CV agrupada, external = reserva posterior.

| Algoritmo | Evaluación | Matriz (filas) |
|---|---|---|
| DUMMY | development | `[0, 3, 10]; [0, 12, 52]; [0, 15, 51]` |
| DUMMY | external | `[0, 0, 2]; [0, 0, 14]; [0, 0, 17]` |
| RANDOM_FOREST | development | `[2, 10, 1]; [2, 49, 13]; [0, 21, 45]` |
| RANDOM_FOREST | external | `[0, 2, 0]; [1, 11, 2]; [0, 9, 8]` |
| SVM | development | `[4, 8, 1]; [3, 47, 14]; [1, 16, 49]` |
| SVM | external | `[0, 2, 0]; [1, 10, 3]; [0, 8, 9]` |
| XGBOOST | development | `[2, 10, 1]; [4, 47, 13]; [0, 20, 46]` |
| XGBOOST | external | `[1, 1, 0]; [1, 9, 4]; [1, 6, 10]` |

| Algoritmo | Evaluación | Clase | Soporte | Precision | Recall | F1 |
|---|---|---|---:|---:|---:|---:|
| DUMMY | development | LOW | 13 | null | 0.000000 | 0.000000 |
| DUMMY | development | MEDIUM | 64 | 0.400000 | 0.187500 | 0.255319 |
| DUMMY | development | HIGH | 66 | 0.451327 | 0.772727 | 0.569832 |
| DUMMY | external | LOW | 2 | null | 0.000000 | 0.000000 |
| DUMMY | external | MEDIUM | 14 | null | 0.000000 | 0.000000 |
| DUMMY | external | HIGH | 17 | 0.515152 | 1.000000 | 0.680000 |
| RANDOM_FOREST | development | LOW | 13 | 0.500000 | 0.153846 | 0.235294 |
| RANDOM_FOREST | development | MEDIUM | 64 | 0.612500 | 0.765625 | 0.680556 |
| RANDOM_FOREST | development | HIGH | 66 | 0.762712 | 0.681818 | 0.720000 |
| RANDOM_FOREST | external | LOW | 2 | 0.000000 | 0.000000 | 0.000000 |
| RANDOM_FOREST | external | MEDIUM | 14 | 0.500000 | 0.785714 | 0.611111 |
| RANDOM_FOREST | external | HIGH | 17 | 0.800000 | 0.470588 | 0.592593 |
| SVM | development | LOW | 13 | 0.500000 | 0.307692 | 0.380952 |
| SVM | development | MEDIUM | 64 | 0.661972 | 0.734375 | 0.696296 |
| SVM | development | HIGH | 66 | 0.765625 | 0.742424 | 0.753846 |
| SVM | external | LOW | 2 | 0.000000 | 0.000000 | 0.000000 |
| SVM | external | MEDIUM | 14 | 0.500000 | 0.714286 | 0.588235 |
| SVM | external | HIGH | 17 | 0.750000 | 0.529412 | 0.620690 |
| XGBOOST | development | LOW | 13 | 0.333333 | 0.153846 | 0.210526 |
| XGBOOST | development | MEDIUM | 64 | 0.610390 | 0.734375 | 0.666667 |
| XGBOOST | development | HIGH | 66 | 0.766667 | 0.696970 | 0.730159 |
| XGBOOST | external | LOW | 2 | 0.333333 | 0.500000 | 0.400000 |
| XGBOOST | external | MEDIUM | 14 | 0.562500 | 0.642857 | 0.600000 |
| XGBOOST | external | HIGH | 17 | 0.714286 | 0.588235 | 0.645161 |

Valores completos sin redondear, accuracy, métricas macro, variación y motivos
no estimables: [comparación agregada](../../tests/evidence/s3-1-comparison.json).
Precision null cuando no hay soporte predicho, métricas macro correspondientes null
con motivo; F1=0 con soporte observado y ninguna clasificación correcta es estimable.
AUC null; sin probabilidades calibradas. LOW tiene solo dos observaciones externas;
los cortes repetidos no aumentan estudiantes independientes. No se implementaron
intervalos de confianza o generalización estadística a población real.

Hash CSV: `79fedc114a952631977bbd46cabe5c5a76faeef7e7293e709d5a1a11c9b31374` (48010 bytes).
Hash dataset v2: `7137144ef824de51c2176656fe8032c9dcb8ffc9ddfb8c368743558f9af81d61`.
Configuración/generador quedan en Git; payload/manifiestos completos/particiones,
etiquetas/resultados futuros, datasets y cuatro artefactos en volúmenes privados
fuera del checkout (15 archivos ML y CSV del lote, sin publicación web).

## Comprobaciones y comandos PowerShell ejecutados

| Comprobación | Resultado | Evidencia |
|---|---|---|
| Suite backend completa Linux/Python 3.12.12, PostgreSQL 17.6 aislado | **217 aprobadas, 0 fallos/errores/omisiones; 119.09 s** | s3-1-backend.xml y s3-1-backend-environment.json; base final riesgo_escolar_test_d6709ec88f4e |
| Migración limpia y S3→S3.1 | COMPROBADO | Upgrade head y test_s3_1_migration, incluye historia DEMO/REAL inmutable |
| ML cuatro algoritmos, grupos/tiempo/round-trip/corrupción/layouts | COMPROBADO aislado | test_s3_1_ml, S3 preservado y fixtures temporales |
| Integridad, roles, CSRF, rollback, confirmación/inferencia concurrentes | COMPROBADO aislado | test_s3_1_integration y regresiones S1/S2/S3 |
| CLI autenticada: soporte insuficiente y errores privados | COMPROBADO aislado | Dos casos de test_authenticated_cli_ml_diagnostics_are_explicit_and_sanitized; salida 2, diagnóstico concreto/sanitizado, sin cambios en datos/modelos/auditoría |
| pip check en tester y API final | COMPROBADO | No broken requirements found; s3-1-review.json |
| Contrato/SQL/tipos | COMPROBADO | 199 comprobaciones, 14 tablas, 19 rutas, 94 campos; s3-1-contracts.json |
| Generación de tipos + typecheck/build frontend host e imagen web | COMPROBADO | npm generate:api y tsc --noEmit/vite build; 18 módulos |
| Navegador aislado y activo | **5 + 5 aprobadas** | s3-1-isolated-playwright.json / s3-1-active-playwright.json |
| Inspección visual real | COMPROBADO | ADMIN 1440×900, TUTOR 390×844, RESEARCHER 768×1024; aviso, contexto/alcance, sin credenciales visibles |
| Persistencia recreando contenedores | COMPROBADO | s3-1-persistence.json |
| Cierre integrado | COMPROBADO | s3-1-review.json: 48 respuestas y 16 muestras validadas; rutas, historia, cuentas, locks, CLI REAL bloqueada |
| git diff --check | COMPROBADO | Sin errores de whitespace; avisos LF/CRLF de Windows no modifican historia |

```powershell
$env:TEST_REPORT_NAME = 's3-1-backend'
docker compose -f infra/compose.test.yaml build tester
docker compose build api web
docker compose -f infra/compose.test.yaml run --rm tester
.\.venv-s0\Scripts\python.exe infra/sync_study_contract.py
npm run generate:api --workspace frontend
npm run build --workspace frontend
.\.venv-s0\Scripts\python.exe infra/check_s0.py
py -3.12 infra/manage.py migrate
docker compose -f compose.yaml -f infra/compose.migrate.yaml run --rm --no-deps api python -m alembic -c /app/alembic.ini current
docker compose up -d --wait
$tutorId = 'df354a4d-d596-45ec-b9c7-55ba58608085'
py -3.12 infra/review_study.py --admin-credential ADMIN --tutor-id $tutorId
$env:BROWSER_REPORT_PREFIX = 's3-1'
py -3.12 infra/test_browser.py
$env:REVIEW_REPORT_PREFIX = 's3-1-active'
py -3.12 infra/review_browser.py
$env:PERSISTENCE_REPORT_PREFIX = 's3-1'
py -3.12 infra/check_access_persistence.py
.\.venv-s0\Scripts\python.exe infra/check_study.py
py -3.12 infra/study.py status --admin-credential ADMIN
git diff --check
```

El orden de navegador aislado/activo puede variar; son entornos distintos. No ejecutar
revisiones repetidas por encima del limitador vigente (10 logins/IP/300 s); no se
redujeron ni deshabilitaron límites. Comandos individuales generar/importar/comparar/
registrar/activar/ejecutar y su preparación constan en el manual. El checker final
invocó readiness/compatibility/train institucional: salidas 0/0/**2 esperado**,
INSTITUTIONAL_PROCESSING_NOT_READY; no entrenamiento REAL ni bypass.
La revisión de Alembic devolvió `0003_synthetic_study (head)`. Tras la reconstrucción
final de la API, la consulta CLI con ADMIN existente confirmó synthetic_ready=true
e institutional_ready=false, sin escrituras ni secretos publicados.

Versiones sin cambios: Python 3.12.12, scikit-learn 1.9.1, xgboost-cpu 3.4.1,
NumPy 2.5.3, SciPy 1.18.1, pandas 3.0.6, joblib 1.6.0; PostgreSQL 17.6,
Node 24.14.1/npm 11.20.0. CPU, un hilo, sin GPU/servicios de pago.
No nueva dependencia; **diff de locks vacío**. Hashes requisitos/backend y npm en
s3-1-review.json. Cierres/ADR/migraciones y evidencias anteriores contrastados contra SHA inicial.

## Fallos encontrados, corregidos y omisiones

1. Primera suite: **201 aprobadas y 3 fallos** (204 casos, 129.35 s), conservada en
   s3-1-backend-first.xml. Dos harnesses nuevos: extra form field puede rechazarse
   como INVALID_MULTIPART antes de INVALID_FORM; mock rollback admitía cuatro args y
   necesitaba settings. Defecto real: comparison=None se guardaba como null JSON y
   el guard lo interpretaba como evidencia existente. JSONB(none_as_null=True) y
   CHECK SQL NULL/object corrigen el contrato de persistencia.
2. Segunda suite: **209 aprobadas y 1 fallo** (210 casos, 149.95 s),
   s3-1-backend-second.xml. El storage ordenaba claves JSON; el hash de Dataset
   dependía del orden de dicts al recuperarlo. Canonización v2 y test round-trip,
   conservando serialización v1; CSV/UUID/configuración no cambiaron.
3. Prueba exploratoria de locks: **212 aprobadas y 1 fallo** (213 casos, 211.55 s),
   s3-1-backend-lock-probe.xml. Premisa equivocada del test: periodo usa FOR SHARE,
   no exclusivo. No se demostró deadlock. Se armonizó orden de locks y la prueba
   comprueba rechazo antes de commit/sin parciales y éxito posterior, con eventos
   y observación PostgreSQL, sin esperas arbitrarias.
4. Primer recorrido activo falló durante generate, antes de importar:
   PRIVATE_STORAGE_REQUIRED por raíz protegida calculada como / en imagen API.
   s3-1-active-first-endpoints.json y s3-1-storage-diagnostic.json conservan evidencia.
   Contexto/filas académicas/modelos/ML privados permanecieron en cero y cuentas en
   cuatro. Guard corregido para /app en imagen y checkout completo en repositorio;
   dos pruebas de layouts. Suite final y recorrido activo posteriores aprobados.
5. Avisos finales: **40 warnings**, principalmente deprecaciones Starlette/TestClient
   y parámetro probability de SVC en scikit-learn. Se conserva probability=False;
   no se implementó calibración ni se actualizaron locks por conveniencia. Revisar
   compatibilidad en una futura actualización controlada.
6. La comprobación adicional de conservación de filas antiguas falló inicialmente
   por usar created_at para auditoría; su columna es recorded_at. Corregido el
   validador, se contrastan sesiones/auditoría anteriores sin modificar la base.

**Sin fallos técnicos abiertos de los recorridos comprobados.** Pendiente técnico:
procedencia registrada para correcciones sintéticas (esta versión acepta CSV exacto
sin ediciones manuales), futuras actualizaciones por deprecaciones, interfaz S4,
alertas/intervenciones/exportaciones S5 e integración/cierre S6.

**NO EJECUTADO / fuera de alcance:** datos reales, entrenamiento/activación/inferencia
REAL, estudio prospectivo escolar, hipótesis de tesis, calibración, tuning, SHAP,
S4–S6, despliegue externo/push/commit y restauración nueva del respaldo histórico.
El respaldo anterior se verificó por hashes; no se afirma una restauración adicional.
Pruebas de mutación/rollback/concurrencia se hicieron en DB aislada, sin corromper el
estudio activo para acreditarlas. Checker de base vacía omitido deliberadamente.

**PENDIENTE académico:** revisar con asesor objetivos/hipótesis referidos a alumnos
reales, unidad de análisis, origen/mecanismo generador, instrumentos, análisis,
discusión y límites de generalización. No se editó documento académico oficial ni
se inventó aprobación del colegio/asesor. La infraestructura y simulación local S3.1
están comprobadas; no existe modelo aprobado para uso escolar ni tesis validada.
