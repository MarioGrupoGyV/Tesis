# Estado Sprint 5 — Seguimiento y reportes

Fecha de revisión: 4 de octubre de 2026, America/Lima. Alcance exclusivo S5.

## Alcance y conservación

S5 añade Alertas, actividades de seguimiento, resumen operativo y exportación CSV
con API/PostgreSQL reales para el estudio SYNTHETIC registrado. REAL continúa
bloqueado. No hay comunicaciones, eficacia escolar, evaluación de la hipótesis ni S6.
El estudio activo no se regeneró ni reentrenó. Las comparaciones necesarias para el
recorrido nuevo se ejecutaron únicamente en fixtures y almacenamiento aislados.

SHA inicial y HEAD final: `e9349f26b3f0b301cd4d5f50bbec0a7532110e85`.
El checkout inicial estaba limpio. No se hizo commit, push o despliegue externo.
Se conservan cuentas/credenciales Windows, secretos, volúmenes, puertos, respaldos,
versiones/locks y evidencias S0–S4. La lista completa de archivos de esta iteración
está en el [inventario completo](../../tests/evidence/s5-changed-files.json).

La [ADR 008](../adr/008-seguimiento-reportes-s5.md) se registró antes del código.
El [manual S5](../manuals/Manual_Seguimiento_Reportes_S5.md) explica las acciones
y límites. La [matriz](Matriz_verificacion_S5.md) vincula roles, pantallas y pruebas.

## Implementación

- ORM explícito, repositorios, servicios, esquemas y rutas separados para seguimiento
  y reportes. El núcleo matemático `backend/app/ml`, pipelines y artefactos previos
  permanece intacto; solo cambia la orquestación transaccional de inferencia.
- `followup-policy-v1`: MEDIUM/HIGH actuales requieren seguimiento, LOW conserva
  el caso para revisión humana o registra NO_ALERT. Faltantes/abstención no se vuelven
  LOW. La fuente no retrocede; una nueva revisión queda pendiente de evaluación.
- Migración manual `0004_followup`, posterior a 0003. Nueva tabla mínima
  `followup_decisions`: una decisión inmutable por predicción, origen/matrícula/
  modelo/lote/estudio coherentes, vínculo al caso cuando corresponde. Total: 15 tablas.
  `interventions` añade `creation_key` y `creation_payload_sha256`, digest del payload
  original por actor. No se ejecutó Esquema.sql sobre la base existente.
- Locks comunes: periodo compartido, modelo compartido, matrículas por UUID y
  recurso de seguimiento. Unicidad DB, versiones estrictas y triggers respaldan
  concurrencia, periodo bloqueado, terminales, procedencia y no borrado.
- Predicciones, seguimiento y auditoría se confirman juntos o se revierten juntos.
  Repeticiones no duplican decisiones/casos/auditoría ni reabren casos cerrados.
  La inferencia histórica solo sincroniza predicciones que siguen siendo actuales;
  informa `ignored_stale` sin retroceder fuente ni versión.
- Alertas: OPEN→IN_REVIEW/RESOLVED/DISMISSED; IN_REVIEW→RESOLVED/DISMISSED.
  Cierre humano con motivo y hora del servidor. Actividades PLANNED→DONE/CANCELLED;
  DONE exige fecha efectiva explícita con zona y no futura. No copia programación
  ni completa/cancela actividades al cerrar el caso.
- Resumen y CSV comparten una lectura consistente y la consulta actual de estudiantes:
  una matrícula por fila, agregación antes de joins, filtros/alcance del servidor.
  Total=evaluados+sin evaluar+insuficientes; evaluados=LOW+MEDIUM+HIGH.
  Porcentajes con denominador cero son null con explicación.
- CSV de 19 columnas: conjunto completo filtrado, UTF-8 BOM, CRLF/quoting, nombre
  fijo `seguimiento-escolar-reporte.csv`, attachment/no-store. Elimina controles y
  neutraliza prefijos de fórmula en la proyección; no cambia DB. Excluye narrativas,
  etiquetas y privados ML. Audita la solicitud sin filas y sin afirmar apertura.
- Interfaz conectada: Alertas/lista/caso, formularios de actividades y cierre,
  Reportes/CSV, Inicio compacto y seguimiento del estudiante/timeline. Conflicto 409
  conserva borrador y exige revisión explícita; creación incierta conserva clave y
  payload originales. Permisos, cancelación/descarte por sesión y reloj API se conservan.

## Contrato y permisos

OpenAPI **0.5.0**, **27 operaciones en 26 paths**, tipos frontend regenerados.
Se añadieron exclusivamente estas ocho operaciones bajo `/api/v1`:

| Método y ruta | Permiso |
| --- | --- |
| POST /alerts/sync | ADMIN + CSRF |
| GET /alerts | ADMIN/TUTOR/DIRECTOR |
| GET /alerts/{id} | ADMIN/TUTOR/DIRECTOR, recurso autorizado |
| PATCH /alerts/{id} | ADMIN/TUTOR + CSRF, versión estricta |
| POST /interventions | ADMIN/TUTOR + CSRF, versión de caso + clave original |
| PATCH /interventions/{id} | ADMIN/TUTOR + CSRF, versión estricta |
| GET /reports/summary | ADMIN/TUTOR/DIRECTOR, alcance servidor |
| GET /reports/export.csv | ADMIN/TUTOR/DIRECTOR, mismo alcance/filtros |

TUTOR consulta/modifica/exporta únicamente sus secciones. DIRECTOR solo consulta.
RESEARCHER conserva Inicio limitado/estado general y sesión; no casos/modelos/CSV.
UUID ajeno e inexistente comparten 404 seguro. Todas las escrituras comprueban el
periodo; las lecturas autorizadas siguen disponibles al bloquearlo.
`PredictionRunResult.followup` y las cinco disponibilidades nuevas por rol de
`ProcessingStatus` son tipadas. Se mantienen 401/403/404/409/422/503 sanitizados y
request_id; CSV fallido usa JSON Error y no descarga aparente. Health conserva Health.

## Comprobaciones y evidencias

**COMPROBADO**: backend, navegador aislado/activo, contrato/tipos/build, migración,
persistencia y checker S5. Los resultados y sus límites se detallan abajo.

| Comprobación | Resultado efectivo | Evidencia |
| --- | --- | --- |
| Suite backend completa | 269 aprobadas, 0 fallos/errores/omisiones; 248 warnings previos; 371.39 s terminal (371.204 s JUnit) | [JUnit](../../tests/evidence/s5-backend-final.xml), [entorno](../../tests/evidence/s5-backend-final-environment.json) |
| Runtime y DB aislada | Linux/Python 3.12.12, PostgreSQL 17.6, DB `riesgo_escolar_test_b8da4342296d`; aplicación riesgo_app | Entorno backend; asserts de rol en pruebas |
| Migración limpia/desde S4 | Head limpio y 0003→0004; 14 tablas previas conservadas, grants/guards/15 tablas | test_s5_migration y suite completa |
| Upgrade activo antes de seguimiento | 15 tablas; 60/360/55, 4 cuentas y archivos idénticos; cero casos/actividades | [upgrade activo](../../tests/evidence/s5-upgrade-active.json) |
| Navegador aislado | 1 importación + 5 casos S5 aprobados; DB `riesgo_escolar_test_browser_f1042afbf1b0` | [importación](../../tests/evidence/s5-complete-final-import-playwright.json), [Playwright](../../tests/evidence/s5-complete-final-playwright.json), [entorno](../../tests/evidence/s5-complete-final-environment.json) |
| Primera inferencia por UI aislada | 60 seleccionadas, 55 creadas, 0 reutilizadas, 5 abstenciones; seguimiento 51 casos/4 NO_ALERT/5 sin evaluación | Respuesta real PredictionRunResult y capturas first-ui-inference-followup-created |
| Navegador activo | 4 roles aprobados; 1 omisión intencional del test de fallos solo aislado | [Playwright](../../tests/evidence/s5-active-final-playwright.json), [entorno](../../tests/evidence/s5-active-final-environment.json) |
| Sincronización/repetición activa | Primera acción explícita: 51 casos/4 NO_ALERT/5 faltantes; repetición e inferencia: 0 nuevas predicciones, 55 reutilizadas y 55 decisiones reutilizadas | [respuestas activas](../../tests/evidence/s5-active-final-response-samples.json) |
| CSV descargado por navegador | ADMIN60/TUTOR30/DIRECTOR60 filas; 19 columnas, BOM y conjunto completo, tutor sin sección ajena | Metadatos `s5-active-final-*-csv.json` y equivalentes aislados |
| Contrato documental | OpenAPI0.5.0: 27 operaciones/26 paths; 15 tablas, 74 sentencias, 119 tipos mapeados, 292 checks y 66 respuestas reales validadas | [contratos](../../tests/evidence/s5-contracts.json), [fuentes de respuestas](../../tests/evidence/s5-response-sources.json) |
| Revisión de fuentes | Git diff --check, AST Python y enlaces locales aprobados | [fuentes](../../tests/evidence/s5-source-checks.json) |
| Tipos/build/pip | Regeneración, typecheck, build Windows y Docker aprobados; 87 módulos; No broken requirements found | [build](../../tests/evidence/s5-build.json) |
| Checker S5 poblado | 269 pruebas, 66 respuestas, 27 operaciones reales; locks/ML/migraciones/históricos intactos, respaldo verificado y contenedores sanos | [cierre automatizado](../../tests/evidence/s5-review.json) |
| Persistencia | 15 tablas, cuentas/auditoría/archivos idénticos antes/inmediatamente después de recrear sin borrar volúmenes; 4 roles login/logout/revocación | [persistencia](../../tests/evidence/s5-persistence.json) |
| Visual | 30 PNG iniciales y 27 finales inspeccionados por agente UI; root revisó además tres finales en tres tamaños; corrección de tablas confirmada | [inventario inicial](../../tests/evidence/s5-ui-first-visual-review.json), [inventario final](../../tests/evidence/s5-ui-final-visual-review.json) |

Las pruebas nuevas cubren origen/alcance, sección fuera del registro, REAL, todas las
escrituras de periodo, vínculos incompatibles, idempotencia tras cierre/edición,
LOW, revisión pendiente, inferencia histórica/ignored_stale, tutor inexistente/
inactivo, versiones/transiciones, rollback de inferencia+seguimiento, concurrencia
sync/inferencia/ediciones y cierre de periodo mediante pg_blocking_pids/eventos.
Resumen/CSV comprueban unidad, filtros/denominadores, casos históricos, actividades
múltiples, quoting/Unicode/controles/fórmulas y conservación de texto DB. Timeline
comprueba eventos efectivos y apertura única. No sleeps como prueba de locks.

Las ramas **HTTP simuladas aisladas** fueron: preview409 heredado del recorrido S4,
CSV503, truncado del cuerpo de un POST201 real y entrega retenida de GET ADMIN real.
El reintento de creación devuelve200 real y el mismo ID/payload; el 409 de edición
es producido realmente por PostgreSQL. Estas simulaciones no son caídas DB reales.

## Conteos activos antes/después

| Entidad | Antes S5 | Tras revisión final | Tras recreación inmediata |
| --- | ---: | ---: | ---: |
| Cuentas | 4 | 4 | 4 |
| Estudiantes/matrículas | 60/60 | 60/60 | 60/60 |
| Cortes | 360 | 360 | 360 |
| Modelos/predicciones | 1/55 | 1/55 | 1/55 |
| Alertas | 0 | 51 (50 abiertas, 1 concluida) | 51 |
| Decisiones seguimiento | no existía la tabla | 55 (51 CREATED, 4 NO_ALERT) | 55 |
| Intervenciones | 0 | 2 (1 DONE, 1 CANCELLED, 0 PLANNED) | 2 |
| Auditoría | 169 | 297 | 297 |
| Sesiones | 53 | 61 | 61 |

Las cifras de auditoría/sesiones incluyen el primer intento activo fallido, que solo
agregó cinco eventos de autenticación y cuatro sesiones (169→174, 53→57). La revisión
final agregó seguimiento y sus acciones sin borrar ese intento. La comprobación de
acceso posterior a recrear agrega eventos/sesiones de autenticación; su conteo final
es **305 eventos de auditoría y 65 sesiones** en el [checker S5](../../tests/evidence/s5-review.json),
separado de la instantánea idéntica de persistencia.

Los 15 archivos ML privados, el CSV privado, registros/modelo/predicciones anteriores
y cuentas conservan fingerprints/hashes. El entorno DEMO histórico continúa detenido
y su respaldo mantiene hashes. Los casos/actividades son acciones simuladas de S5;
no resultados escolares. Se revisó un solo caso propio para las dos actividades y
el cierre; no se eliminaron las evidencias.


## Fallos intermedios conservados

La [bitácora](../../tests/evidence/s5-check-incidents.json) y los reportes originales
conservan fallos y correcciones; no se reemplazan por el resultado final:

1. Docker negó el acceso a su pipe en sandbox. La ejecución autorizada pasó sin
   cambios de datos. No hubo rechazo de revisión automática de aprobación.
2. Validación contractual inicial rechazó enum nullable sin null; se normalizó y se
   corrigieron defaults opcionales de entradas/PATCH. El generador acumulaba una
   cláusula descriptiva al repetirlo; quedó idempotente, comprobado por SHA256.
3. Build Windows inicial falló con EPERM/Vite/oxide dentro del sandbox. Con las mismas
   dependencias bloqueadas pasó la ejecución autorizada y el build Docker (87 módulos).
4. `s5-backend-first`: 253 aprobadas, 12 fallidas de 265, cero omitidas. Se corrigieron
   expectativa histórica403→404, SQLSTATE de vínculo inválido, fixtures CSV que
   alteraban el catálogo registrado y observación de locks con snapshot estadístico
   obsoleto. Para terminar esa ejecución fallida se liberaron cuatro transacciones
   exactamente identificadas de su base de prueba, nunca de la activa. Sus fallos
   no acreditan concurrencia: esa aceptación se repitió con observación DB correcta.
5. `s5-backend`: 268 aprobadas; `s5-backend-complete`: 269 aprobadas. Se añadió después
   una aserción histórica as_of/ignored_stale a la prueba de revisión existente y se
   repitió la suite completa con prefijo nuevo `s5-backend-final`.
6. `s5-first` pasó importación y cinco casos S5, pero preparó inferencia por API antes
   de UI. El recorrido final hizo la primera inferencia por botón real de interfaz.
7. `s5-complete` pasó importación y cuatro de cinco casos S5; TUTOR esperaba el mensaje
   de URL ajena mientras seguía pendiente su GET. El test ahora espera el 404 real
   antes del mensaje. Ese intento usó la imagen web anterior al último ajuste CSS;
   `s5-complete-final` usa la imagen final verificada y pasó los seis recorridos.
8. `s5-active-complete` no sincronizó: el test enfocó/activó por teclado antes de
   habilitarse la acción con ProcessingStatus. Diagnóstico de solo lectura confirmó
   permiso/modelo correctos; se añadió espera explícita de botón habilitado. TUTOR/
   DIRECTOR encontraron cero casos por esa ausencia de sincronización. RESEARCHER
   pasó. `s5-active-final` pasó los cuatro roles y conservó el intento anterior.
9. Capturas iniciales mostraban tablas comprimidas en tablet/móvil. Se reforzó su
   ancho, se muestran Estado/Cantidad primero y se añadió ayuda de desplazamiento.
   Las capturas finales se inspeccionan por separado y se conserva el inventario inicial.

Se conservan deprecaciones existentes de Starlette TestClient/httpx y SVC(probability);
no se actualizaron dependencias por conveniencia.

## Comandos PowerShell ejecutados

Desde la raíz, con versiones/locks existentes. Los prefijos de abajo son los del
cierre ya conservado: usa prefijos nuevos en futuras revisiones, sin sobrescribirlos.

```powershell
git status --short
git rev-parse HEAD
docker compose build api web
docker compose -f infra/compose.test.yaml build tester
$env:TEST_REPORT_NAME = 's5-backend-final'
docker compose -f infra/compose.test.yaml run --rm tester
.\.venv-s0\Scripts\python.exe infra/sync_followup_contract.py
npm run generate:api --workspace frontend
npm run typecheck --workspace frontend
npm run build --workspace frontend
.\.venv-s0\Scripts\python.exe infra/check_s0.py
$env:BROWSER_REPORT_PREFIX = 's5-complete-final'
py -3.12 -X utf8 infra/test_s5_browser.py
py -3.12 -X utf8 infra/manage.py migrate
docker compose up -d --wait api web
$env:REVIEW_REPORT_PREFIX = 's5-active-final'
py -3.12 -X utf8 infra/review_s5.py --study-id e3a2d28b-2f23-56ae-878c-1a8f4a257e7e --period-id c036cbcb-87db-5ed0-bcfa-bbd644928ccb
$env:PERSISTENCE_REPORT_PREFIX = 's5'
py -3.12 -X utf8 infra/check_access_persistence.py
docker compose exec -T api python -m pip check
.\.venv-s0\Scripts\python.exe infra/check_s5.py --backend-prefix s5-backend-final --isolated-prefix s5-complete-final --active-prefix s5-active-final
git diff --check
```

El operador usa PowerShell/Windows. Python 3.12.12/Linux para backend y PostgreSQL
17.6 se ejecutan en Docker; no se exige WSL, Bash o Make. El propietario se usa
solo para migraciones; la ejecución API/pruebas usa riesgo_app.

## Límites y pendientes

- S6 y su restauración final integrada no se ejecutaron. La recreación de contenedores
  sin borrar volúmenes prueba persistencia, no sustituye la restauración final S6.
- REAL, dataset autorizado, etiquetas/protocolo institucional y revisión académica
  siguen pendientes. Ninguna métrica operativa simulada acredita eficacia o hipótesis.
- No se hizo auditoría completa de accesibilidad/lectores de pantalla, hardware táctil,
  otros navegadores o carga de producción. Se verifican Chromium, teclado, foco,
  formularios y los tres tamaños solicitados. El caso móvil con historial extenso
  y formularios bloqueados conserva bastante longitud; los motivos están visibles.
- El 503 de exportación, preview409 y la pérdida de cuerpo se simularon solo para fallos UI. No
  se provocó una caída real de PostgreSQL activo ni se fabricaron éxitos positivos.
- HTTPS externo permanece fuera del entorno localhost; no despliegue externo.
- Los reportes son actuales; no hay selector histórico, eficacia de intervención,
  entrenamiento/activación HTTP ni gestión nueva de cuentas/asignaciones.
