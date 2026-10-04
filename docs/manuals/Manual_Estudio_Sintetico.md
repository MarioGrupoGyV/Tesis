# Manual — Estudio con datos sintéticos S3.1

SYNTHETIC identifica registros y resultados completamente generados. No son alumnos
observados ni datos reales anonimizados. La comparación depende del mecanismo de
generación; no acredita eficacia escolar, impacto, validación prospectiva o hipótesis
de tesis. REAL continúa bloqueado. ADR 006 sustituye para este alcance la prohibición
anterior; cierres S2.1/S2.2/S3 y migraciones 0001/0002 conservan sus hechos.

## Preparación Windows

Docker Desktop conserva Linux/Python 3.12.12 internamente. No WSL/Bash/Make para el
operador. Versiones y locks vigentes intactos, CPU/un hilo y cuatro algoritmos.
La instalación actual conserva las cuatro cuentas S2.2 y sus entradas privadas
Windows; no ejecutar bootstrap ni review_accounts para recrearlas.

```powershell
py -3.12 infra/manage.py up
py -3.12 infra/study.py status --admin-credential ADMIN
py -3.12 infra/ml.py compatibility
py -3.12 infra/ml.py train  # Salida 2: REAL permanece bloqueado
```

`up` construye y aplica Alembic hasta 0003 mediante propietario temporal; API/CLI
utilizan riesgo_app. Conserva puertos 15173/18000/55432, secretos y tres volúmenes.
Nunca borrar volúmenes ni aplicar Esquema.sql sobre la base existente.

## Protocolo reproducible

Configuración versionada: backend/app/ml/synthetic-study-v1.json. Su versión y la
del código synthetic-generator-v1, semilla y parámetros determinan UUID5, CSV,
etiquetas, particiones y hashes. El tamaño por defecto es 60 estudiantes ficticios,
360 observaciones (seis cortes); no son 360 personas independientes.
Dataset v2 usa JSON canónico con claves ordenadas y listas en su orden original;
su hash permanece igual después de guardar y recuperar el payload privado.
Dataset v1 conserva su serialización histórica.

| Parámetro | Supuesto de simulación |
|---|---|
| Calendario | 2025-01-01–2025-12-31, America/Lima; instantes almacenados UTC |
| Cortes de desarrollo | 31 enero, 28 febrero y 31 marzo |
| Ajuste simulado | 1 mayo 2025; todas las etiquetas de desarrollo disponibles antes |
| Cortes externos | 31 julio, 31 agosto, 30 septiembre; estudiantes distintos |
| Ventana / horizonte / disponibilidad de etiqueta | 30 días / 14 días / un día después del resultado futuro |
| Reserva prefijada | 20% por estudiante (12), desarrollo 48; asignación determinista antes de medir |
| Promedio | 0–20, dos decimales |
| Asistencia / actividades | 0–100, dos decimales |
| Participación | Categorías 1/2/3 (supuestos; sin escala institucional) |
| Incidencias | Conteo 0–12 |
| Edad / grado | Metadatos CSV, excluidos de X |
| Calidad para análisis | Máximo 40% de faltantes en cinco variables, regla propia de investigación sintética |
| Inferencia | Máximo 40% de faltantes y promedio requerido, política operativa distinta configurada explícitamente |

Las dos políticas de faltantes tienen igual valor por configuración; ninguna se
deduce de la otra. La elegibilidad de simulación no finge consentimiento/asentimiento:
ambos campos quedan false. Los ejemplos sin datos conservan null y abstención.
El CSV guarda missing_fraction sobre sus seis mediciones; ML vuelve a calcularlo
solo sobre las cinco variables seleccionadas.

Criterio hipotético synthetic-future-v1, sobre resultados **futuros**:

1. HIGH si promedio futuro <10, asistencia futura <65 o incidencias futuras >=6.
2. En ausencia de HIGH, MEDIUM si promedio futuro <14, asistencia futura <85 o incidencias >=3.
3. LOW en los demás casos. HIGH tiene precedencia.

No se etiqueta únicamente la nota actual. El generador usa heterogeneidad latente
(logro uniforme 8–19, compromiso 55–99, conducta 0.05–3.5), deriva normal (SD 0.5),
cambio longitudinal y perturbaciones nuevas en observaciones/resultados futuros.
Ruido de notas actual/futuro SD 1.1/2.0; asistencia SD 4/7; actividades SD 7/9;
incidencias Poisson con límite 12. Estos parámetros fijos pertenecen a la versión
del código. No entran al estimador latentes, ruido, códigos, UUID, fechas, tutor,
etiquetas ni resultados posteriores. Faltantes aleatorios 4%; cada estudiante 17
tiene su último corte totalmente faltante, sin depender del riesgo futuro.

## Comandos explícitos ADMIN

Credencial `SeguimientoEscolar/S2.2/ADMIN` leída en memoria; contraseña nunca en args,
archivos, capturas o documentación. La CLI verifica hash y ADMIN activo en servidor.
El tutor siguiente es la cuenta local existente; se asigna únicamente la primera
sección sintética. Otra queda fuera de su alcance para verificar permisos.

```powershell
$tutorId = 'df354a4d-d596-45ec-b9c7-55ba58608085'
py -3.12 infra/study.py generate --admin-credential ADMIN --seed 1729 --tutor-id $tutorId
# Usar study_id y period_id devueltos; no rutas privadas
$studyId = '<study_id>'
$periodId = '<period_id>'
py -3.12 infra/study.py import --admin-credential ADMIN --study-id $studyId
py -3.12 infra/study.py compare --admin-credential ADMIN --study-id $studyId
py -3.12 infra/study.py register --admin-credential ADMIN --study-id $studyId
$modelId = '<model_id>'
py -3.12 infra/study.py activate --admin-credential ADMIN --model-id $modelId
py -3.12 infra/study.py run --admin-credential ADMIN --period-id $periodId
py -3.12 infra/study.py status --admin-credential ADMIN
```

`generate --students <n>` o `--config <JSON>` permite otra configuración validada,
con nuevo identificador/hash/contexto. No aumenta población ni repite semillas para
lograr exactitud. Repetir configuración/semilla reutiliza preparación. La primera
versión acepta exclusivamente su CSV exacto, sin correcciones manuales de ese archivo.
El motor de revisiones S2 se conserva/probara aisladamente; permitir generaciones de
corrección registradas requiere diseñar esa procedencia en otra iteración.

`import` ejecuta preview → GET lote → commit con expected_preview_version, sesión y
CSRF. El CSV viaja desde el volumen privado a memoria del launcher; no se escribe en
el checkout. Una vista previa no crea alumnos/matrículas/cortes. Registro/hash/contexto
se verifican en el servidor; un checkbox, flag de origen o archivo modificado no los
sustituye. Se mantienen 5 MiB/10000 filas, parser, precisión, fechas, stale 409,
transacción, locks, idempotencia y auditoría. Un fallo revierte también bindings.

`compare` solo tras importar, reutiliza evidencia existente sin volver a entrenar.
`register` exige el algoritmo seleccionado en desarrollo antes de evaluar la reserva;
`--algorithm` solo puede confirmar ese mismo algoritmo. No se permite cambiar la
selección después de ver resultados externos. `activate` es siempre otro
comando explícito, atómico/auditado. APPROVED/TECHNICAL_SIMULATION significa compatible
para simulación, nunca aprobado para decisiones sobre estudiantes reales.

El limitador de login permanece 10 intentos/IP por 300 segundos. Si se alcanza,
esperar la ventana; no cambiar límites para la revisión. Los comandos internos de
comparación/registro/activación no crean sesiones HTTP ni tareas de arranque.
Una evaluación sin suficientes clases/grupos devuelve salida 2 y diagnóstico
INSUFFICIENT_CLASS_GROUP_SUPPORT (u otro INSUFFICIENT_* pertinente), sin regenerar
ni aumentar la población automáticamente. Configuración inválida devuelve
SYNTHETIC_CONFIG_INVALID; los mensajes no imprimen valores privados o trazas.

## Evaluación y archivos privados

CV de desarrollo por estudiante, estratificada cuando hay soporte, entre dos y cinco
folds efectivos; nunca división por filas. Imputación/codificación y escala SVM se
ajustan dentro de train/fold. Misma partición para Dummy/RF/SVM/XGBoost, parámetros
S3 fijados, sin tuning/calibración. Todas las etiquetas usadas en fit deben estar
disponibles antes del ajuste y los cortes externos. Se guardan exclusiones temporales
y por calidad. Si faltan grupos/clases, diagnóstico explícito; no regenerar ni fingir métricas.

Selección **antes de evaluar reserva**: mayor macro-F1 de desarrollo, luego balanced
accuracy, luego orden fijo DUMMY/RANDOM_FOREST/SVM/XGBOOST. Reserva excluida de fit,
transformaciones y selección. Se informa matriz LOW/MEDIUM/HIGH, soporte, métricas
por clase/macro, accuracy/balanced y variación de folds. Null con motivo si no estimable;
AUC null, probabilidades null y probabilities_calibrated=false.

El calendario de 2025 es simulado. El entrenamiento operativo ocurre al ejecutar
el comando ahora: no prueba que se entrenó realmente en mayo ni que hubo evaluación
prospectiva escolar. CV de grupos y reserva posterior son evidencias distintas,
ambas condicionadas por el generador.

Volumen `/var/lib/riesgo/ml`: payload de estudio (CSV, configuración, resultados y
etiquetas), cuatro artefactos privados, datasets de desarrollo, manifiestos firmados,
particiones/predicciones de validación/reserva. `/var/lib/riesgo/imports` conserva el
CSV del lote. Solo identificadores internos, sin rutas arbitrarias o publicación web.
HMAC interna, hashes, clases, versiones exactas, esquema/criterio y procedencia se
comprueban antes de joblib. XGBoost conserva UBJSON nativo y preprocesamiento.
Un hash no vuelve confiable un archivo externo; no se admite upload/download de modelos.

Dataset/manifiesto v2 SYNTHETIC_STUDY/SYNTHETIC convive con v1 ISOLATED_TEST/REAL de
S3. Combinaciones contradictorias se rechazan. synthetic_studies conserva procedencia
inmutable y enlaces privados entre source_row_number/hash/código/corte/revisión,
snapshot generado, snapshot importado y su resultado futuro. FK de lote/hash/periodo,
modelo/estudio/origen y trigger de predicción evitan cruces. No nuevas tablas de etiquetas.

## API y consultas

Contrato 0.4.0, 19 operaciones efectivas; única ruta nueva GET /processing/status.
Autenticada y general por rol, incluye notice, synthetic_ready e institutional_ready=false.
Import/compare/register/activate/predict dependen de requisitos efectivos; disponibilidad
no se deduce de health. RESEARCHER conserva solo estado general/sesión, sin casos/modelos.
El aviso en inicio se obtiene del servidor; no hay selector de modo ni pantallas S4.

GET models/model sigue ADMIN; POST predictions/run ADMIN+CSRF con period_id/as_of.
REAL bloqueado antes de seleccionar información académica. SYNTHETIC exige registro,
modelo técnicamente aprobado/activo, esquema/criterio/hashes/procedencia compatibles.
Último corte/revisión cutoff/available/created <= as_of por matrícula; una corrección
no hereda evaluación. as_of también respeta incorporación operativa/modelo, no solo
fechas simuladas. No se usan etiquetas de reserva al inferir.

Abstención devuelve motivo sin insertar riesgo. Lecturas muestran INSUFFICIENT_DATA
cuando el corte incumple la política explícita del modelo activo; sin modelo/resultado
continúan pendientes, nunca LOW. Predicción única snapshot/model, auditoría atómica,
concurrencia/repetición reutiliza. No se crean alertas/intervenciones (S5).
GET predictions/{id}: tutor solo sección propia; ajena/inexistente ambas 404.
Estudiantes/lista/detalle/historial conservan alcance, filtros, orden/paginación S2.
503 sanitizado para indisponibilidad; integridad/conflictos son 409, ready conserva Health.

## Verificación y alcance académico pendiente

```powershell
$env:TEST_REPORT_NAME = 's3-1-backend'
docker compose -f infra/compose.test.yaml build tester
docker compose -f infra/compose.test.yaml run --rm tester
.\.venv-s0\Scripts\python.exe infra/sync_study_contract.py
npm run generate:api --workspace frontend
npm run build --workspace frontend
.\.venv-s0\Scripts\python.exe infra/check_s0.py
py -3.12 infra/review_study.py --admin-credential ADMIN --tutor-id $tutorId
$env:REVIEW_REPORT_PREFIX = 's3-1-active'
py -3.12 infra/review_browser.py
$env:PERSISTENCE_REPORT_PREFIX = 's3-1'
py -3.12 infra/check_access_persistence.py
$env:BROWSER_REPORT_PREFIX = 's3-1'
py -3.12 infra/test_browser.py
.\.venv-s0\Scripts\python.exe infra/check_study.py
git diff --check
```

No ejecutar check_runtime sobre la aplicación con cuentas/estudio. Resultados reales,
fallos/omisiones y métricas agregadas: Estado_Sprint_3_1.md y su matriz de evidencia.
Los runners vigentes usan prefijos S3.1 por defecto; los prefijos explícitos anteriores
solo identifican pruebas históricas y no deben reutilizarse para sobrescribirlas.
S4–S6, calibración y uso institucional pendientes. Revisar con el asesor objetivos e
hipótesis, unidad de análisis, origen/generador, instrumentos, análisis, discusión y
generalización. No se modifica el documento académico oficial ni se inventa aprobación.
