# Matriz de verificación S5 — Seguimiento y reportes

Estado de cierre: **COMPROBADO: backend final, navegador aislado, revisión activa, contrato/build, persistencia y checker agregado**. El estudio es SYNTHETIC. Los casos y actividades son simulaciones internas, no intervenciones escolares ni resultados académicos.

Fuentes: [ADR 008](../adr/008-seguimiento-reportes-s5.md), [contrato vigente](Contrato_API.yaml), [pruebas PostgreSQL S5](../../backend/tests/test_s5_followup.py), [migración desde S4](../../backend/tests/test_s5_migration.py) y [recorrido de navegador](../../tests/e2e/s5.spec.ts). Se conservan las pruebas y evidencias anteriores; S6 no forma parte del cierre.

## Roles, pantallas y operaciones

| Rol | Pantallas autorizadas S5 | Lecturas de seguimiento/reportes | Escrituras | Sincronización/inferencia | Alcance |
| --- | --- | --- | --- | --- | --- |
| ADMIN | Inicio, Alertas, detalle de caso, Reportes; recorridos previos de Estudiantes/Datos/Modelos | Sí | Estado de caso y planificación/registro de actividad | Sí, explícitas | Todo el estudio registrado |
| TUTOR | Inicio, Alertas, detalle de caso, Reportes y seguimiento dentro del estudiante | Sí | Solo sus casos y actividades | No | Secciones asignadas en el servidor |
| DIRECTOR | Inicio, Alertas, detalle de caso, Reportes y estudiante | Sí | No; sin formularios de mutación | No | Consulta del estudio registrado |
| RESEARCHER | Inicio limitado y sesión | No; API 403 y URL directa protegida | No | No | Sin casos, modelos o exportaciones |

El navegador no obtiene todos los casos para filtrar los ajenos. La API aplica rol, procedencia y sección, incluido el CSV. Un recurso UUID ajeno y uno inexistente comparten una respuesta 404 segura. La disponibilidad global de `ProcessingStatus` no sustituye la autorización ni el bloqueo del periodo elegido.

| Operación bajo `/api/v1` | ADMIN | TUTOR | DIRECTOR | RESEARCHER | Verificación principal |
| --- | --- | --- | --- | --- | --- |
| `POST /alerts/sync` | Sí, CSRF | 403 | 403 | 403 | Predicciones actuales del estudio; conteos separados, repetición sin casos/decisiones/auditoría adicionales |
| `GET /alerts` | Todo el estudio | Secciones propias | Consulta | 403 | Periodo obligatorio; búsqueda, sección, estado, severidad, orden estable y paginación SQL |
| `GET /alerts/{id}` | Sí | Propio; ajeno/inexistente 404 | Sí | 403 | Fuente que motivó el caso separada de evaluación actual; proyección pública e historia auditada |
| `PATCH /alerts/{id}` | Sí, CSRF | Propio, CSRF | 403 | 403 | `expected_version` estricto; cierre con motivo/fecha del servidor; terminales y cambios efectivos |
| `POST /interventions` | Sí, CSRF | Caso propio, CSRF | 403 | 403 | Caso activo, `expected_alert_version`, UUID `creation_key`; origen/matrícula/actor derivados |
| `PATCH /interventions/{id}` | Sí, CSRF | Propia, CSRF | 403 | 403 | Versión, terminales, fecha efectiva explícita/no futura y actividad pendiente después de cerrar el caso |
| `GET /reports/summary` | Todo el estudio | Secciones propias | Consulta | 403 | Conjunto autorizado completo; denominadores, agregados independientes y filtros reales |
| `GET /reports/export.csv` | Todo el estudio | Secciones propias | Consulta | 403 | Mismos filtros/alcance del resumen; conjunto completo, JSON Error ante fallo y auditoría de solicitud |

Las ocho operaciones se añaden a las 19 anteriores: **27 operaciones** en OpenAPI 0.5.0. `POST /predictions/run` conserva el permiso ADMIN y CSRF y amplía su resultado con seguimiento transaccional. No se añaden entrenamiento HTTP, activación HTTP, borrado, comunicaciones ni operaciones ficticias de S6.

## API y PostgreSQL real aislado

Estado final de este bloque: **COMPROBADO: 269 aprobadas, cero fallidas y cero omitidas**, con 248 avisos/deprecaciones. [JUnit final](../../tests/evidence/s5-backend-final.xml): 371,204 s; ejecución terminal: 371,39 s. [Entorno final](../../tests/evidence/s5-backend-final-environment.json): Linux/Python 3.12.12 y PostgreSQL 17.6 dentro de Docker, base `riesgo_escolar_test_b8da4342296d`; las consultas y servicios utilizan `riesgo_app`. El propietario solo migra. Las cuentas, estudio, artefactos y revisiones de fixture pertenecen exclusivamente a bases/almacenamiento aislados.

La ejecución anterior [s5-backend-complete](../../tests/evidence/s5-backend-complete.xml) también comprobó 269 aprobadas, cero fallidas y cero omitidas, en 481,21 s, con 248 avisos. Su [entorno](../../tests/evidence/s5-backend-complete-environment.json) fue `riesgo_escolar_test_100f0424276e`. La ejecución final añadió a la prueba existente la comprobación explícita de inferencia histórica/`ignored_stale` y aprobó nuevamente toda la suite; no se redujo cobertura para obtener el resultado.

| Criterio | Comprobación significativa | Evidencia final |
| --- | --- | --- |
| Base limpia y upgrade desde S4 | Alembic 0003→0004; 15 tablas, fingerprints de las 14 anteriores conservados, columnas/índices mínimos y permisos | `s5-backend-final.xml`, `s5-backend-final-environment.json` |
| Procedencia | CSV y artefactos registrados; modelo compatible; vínculo predicción/matrícula/origen/estudio; rechazo de sección del mismo año ajena al manifest | Pruebas de política, FK y sección registrada en `test_s5_followup.py` |
| Política `followup-policy-v1` | MEDIUM/HIGH crean/actualizan; LOW sin caso registra decisión; LOW con caso conserva revisión humana; ausencia/abstención no inventa riesgo/caso | Respuestas `FollowupResult` y conteos DB |
| Repetición e historia | Una decisión por predicción; una alerta activa por matrícula; cierre no vuelve a crear con la misma predicción; nueva revisión/predicción conserva evidencia anterior; inferencia `as_of` anterior cuenta `ignored_stale` y no retrocede fuente/versión ni registra otra decisión | Pruebas de repetición, revisiones, fuente y terminales |
| Responsable y estado | Tutor activo o null; no ADMIN por defecto; cambio de fuente conserva apertura, responsable y trabajo humano | Casos con tutor ausente/inactivo y fuente actualizada |
| Versiones y creación | Versiones estrictas; cambio efectivo incrementa una vez; misma clave/actor/payload original reutiliza después de editar; carga diferente da 409 | Pruebas de digest original, conflicto y creación concurrente |
| Atomicidad | Fallo después de seguimiento/auditoría revierte casos, actividades, predicciones y eventos de esa operación | Pruebas de rollback de sync, inferencia y mutaciones |
| Concurrencia | Sync simultáneo, edición y creación concurrentes; exclusión con inferencia/edición observada mediante `pg_blocking_pids`; ningún cambio humano perdido | Pruebas con barreras/eventos y observación DB |
| Cierre de periodo | Sync, edición de caso, edición de actividad e inferencia esperan el lock real; tras confirmar cierre rechazan 409 sin cambio parcial | Cuatro pruebas observadas de periodo; sin sleeps arbitrarios |
| Permisos y CSRF | Cuatro roles, recurso propio/ajeno/inexistente, CSV propio, CSRF ausente/incorrecto y REAL bloqueado | Pruebas API con autenticación real |
| Resumen y CSV | 60 matrículas; varios casos/actividades sin multiplicación, página de cinco frente a exportación completa, filtros y denominator cero | `ReportSummary`, CSV analizado y comparaciones de conjuntos |
| Protección de CSV | UTF-8 BOM, quoting, controles/prefijos de fórmula, comillas/separadores/Unicode; DB conserva el texto original | Casos parametrizados de CSV y hashes de descarga |
| Timeline | Apertura única, eventos efectivos desde auditoría inmutable, realizadas/canceladas/cierre y paginación | `TimelineEventPage` y comprobación de IDs/eventos |
| Falta de modelo | Casos/historia accesibles; evaluación actual pendiente, porcentajes sin denominador null; sync rechaza modelo no disponible | Prueba de desactivación exclusivamente aislada |

Las clases controladas de algunas predicciones y las revisiones mínimas solo prueban lógica de software. Las pruebas no cambian el criterio ML, no ajustan datos para alcanzar métricas y no acreditan eficacia o la hipótesis de la tesis. Se conserva la regresión S1–S4 y sus deprecaciones; una corrección del 403 histórico a 404 para detalle/historial ajenos implementa la respuesta segura exigida en S5.

## Recorrido real de interfaz aislada

Estado final: **COMPROBADO: una prueba de importación y cinco pruebas S5 aprobadas, cero fallidas**. Runner: [test_s5_browser.py](../../infra/test_s5_browser.py). Prefijo de cierre: `s5-complete-final`; reportes de [importación](../../tests/evidence/s5-complete-final-import-playwright.json), [seguimiento y roles](../../tests/evidence/s5-complete-final-playwright.json) y [entorno](../../tests/evidence/s5-complete-final-environment.json). La base fue `riesgo_escolar_test_browser_f1042afbf1b0`, con `riesgo_app`; el entorno activo quedó intacto y el CSV temporal se retiró.

Se conserva [s5-complete](../../tests/evidence/s5-complete-playwright.json), que falló en TUTOR al comprobar la URL directa ajena mientras su consulta seguía pendiente. La repetición exige la respuesta real 404 del navegador antes de comprobar su mensaje; no cambia el criterio ni simula esa respuesta. La imagen web final también comprobó el resumen de Inicio en los tres roles de consulta.

| Pantalla/acción | Qué debe comprobarse | Evidencia |
| --- | --- | --- |
| Importación registrada | CSV exacto, preview sin escrituras académicas, confirmación real y 60 estudiantes/360 cortes | `s5-complete-final-import-playwright.json` |
| Primera evaluación por UI ADMIN | Botón real de Modelos: 55 predicciones creadas, cinco abstenciones y seguimiento en la misma transacción | `s5-complete-final-response-samples.json`, captura `first-ui-inference-followup-created` |
| Alertas ADMIN | Sin mutación al abrir; sincronización explícita, repetición y segunda inferencia con cero predicciones nuevas/55 reutilizadas | `s5-complete-final-playwright.json`, captura `admin-alerts` |
| Inicio ADMIN/TUTOR/DIRECTOR | GET real del resumen compacto con página de una fila, denominador autorizado y enlaces de Alertas/Reportes habilitados | Respuesta `ReportSummary`; capturas `*-home-followup` en los tres tamaños |
| Lista y detalle | Filtros servidor, tabla, código/sección, motivo/fuente, evaluación actual, responsable, fecha y capacidades | Respuestas públicas y capturas de casos |
| Planificación TUTOR | Dos actividades propias; PLANNED no cuenta como realizada; fecha programada con zona | Captura `tutor-plan-form` y respuestas de creación |
| Realización/cancelación | Una DONE con fecha efectiva distinta de programada y una CANCELLED con null; solo DONE cuenta como realizada | Capturas `tutor-done-form`, `tutor-case-completed` |
| Conflicto efectivo 409 | Otra petición real cambia OPEN→IN_REVIEW; cierre con versión anterior rechaza, conserva motivo y exige GET/revisión explícita antes de reenviar | Captura `tutor-real-version-conflict`; `Error` y `AlertDetail` reales |
| Cierre e historial | RESOLVED humano, terminal; actividades conservan estado; timeline sin apertura duplicada | Capturas de caso concluido y `tutor-student-followup` |
| Propio/ajeno | Lista propia; UUID ajeno/inexistente 404 equivalentes; PATCH ajeno 404; URL directa no presenta código ajeno | Captura `tutor-foreign-safe404` y respuestas reales |
| DIRECTOR | Consulta y descarga; sin controles de escritura; PATCH API 403 | `director-case`, `director-reports` |
| RESEARCHER | Inicio limitado, rutas directas protegidas, API de casos/resumen/exportación 403 | `researcher-restricted` |
| Reportes y descarga | Fórmulas de conteo, denominadores, filtros sin resultados, recarga/atrás/adelante; CSV completo, no solo página | Capturas de reportes por rol y `*-csv.json` |
| Sesión y teclado | Login/sync por teclado; navegación; cookie HttpOnly, caché/estado por actor/contexto, logout y revocación | Casos por rol y pruebas de sesión |

La comparación/registro/activación necesarios para preparar este fixture se hacen por CLI solo en el entorno aislado. La **primera inferencia se ejecuta desde la interfaz**, no por Python antes del recorrido. El reporte de entorno deriva sus conteos de esa respuesta real de navegador.

La respuesta efectiva de esa primera inferencia seleccionó 60 cortes: **55 predicciones creadas, cero reutilizadas y cinco abstenciones**. El seguimiento creó **51 casos**, registró cuatro decisiones sin alerta y omitió cinco cortes sin evaluación suficiente. La siguiente inferencia reutilizó las 55 predicciones y no creó casos adicionales. La actividad de TUTOR produjo un registro DONE, otro CANCELLED y cierre RESOLVED del mismo caso mediante un conflicto 409 real y revisión explícita. Se comprobó el GET/PATCH ajeno seguro y su URL directa; el resumen compacto de Inicio tuvo una fila y el denominador propio para cada rol.

Las descargas reales conservaron el conjunto autorizado completo: [ADMIN, 60 filas](../../tests/evidence/s5-complete-final-admin-csv.json), [TUTOR, 30 filas](../../tests/evidence/s5-complete-final-tutor-csv.json) y [DIRECTOR, 60 filas](../../tests/evidence/s5-complete-final-director-csv.json), con 19 cabeceras, BOM UTF-8 y hash SHA-256 de la respuesta. Se guardaron metadatos, no el CSV con textos de actividades.

## Simulaciones de fallos de UI, separadas

Estado final: **COMPROBADO en aislamiento**, con anotaciones de simulación en los reportes Playwright. No acreditan una caída real de PostgreSQL ni una respuesta positiva fabricada.

| Rama | Parte real | Parte simulada | Resultado esperado |
| --- | --- | --- | --- |
| Preview desactualizado durante la regresión de importación | Preview y confirmación final sobre el CSV registrado mediante API real | Se responde una vez con HTTP 409 `IMPORT_PREVIEW_STALE` | Se conserva el archivo y se vuelve a obtener una versión real antes de confirmar; esta rama no acredita concurrencia backend |
| Resultado incierto de planificación | POST 201 crea en DB; repetición explícita devuelve 200 y el mismo recurso | Se trunca únicamente el cuerpo de la primera respuesta | Se mantiene exactamente el payload/creation_key, sin reintento automático ni duplicado |
| CSV 503 | Autenticación, resumen y comportamiento de la interfaz | Respuesta JSON Error 503 del GET de exportación | Mensaje claro, cero descarga aparente, sin reintento automático |
| Respuesta tardía entre sesiones | GET ADMIN de sección ajena a TUTOR y login posterior TUTOR | Se retiene la entrega de la respuesta real | Cancelación/descarte; sin filas, borradores o caché ADMIN en la sesión TUTOR |

El conflicto de versión 409 del recorrido principal es **real**, producido por dos escrituras/versión de PostgreSQL; no se confunde con las simulaciones HTTP anteriores.

## Revisión activa mínima

Estado final: **COMPROBADO: cuatro pruebas de rol aprobadas y una omisión intencional**, en [navegador activo](../../tests/evidence/s5-active-final-playwright.json). Runner: [review_s5.py](../../infra/review_s5.py); prefijo final `s5-active-final`. Se usaron las cuatro cuentas privadas de Windows existentes, sin recrearlas.

Se conserva la [primera revisión activa fallida](../../tests/evidence/s5-active-complete-playwright.json) y su [estado antes/después](../../tests/evidence/s5-active-complete-environment.json): ADMIN agotó la espera de respuesta de sincronización, TUTOR/DIRECTOR encontraron cero casos y RESEARCHER aprobó su restricción. Quedaron **cero alertas, actividades y decisiones**, y las cuentas, datos, predicciones, modelo y archivos privados se conservaron; solo aumentaron sesiones/auditoría de acceso. El diagnóstico de lectura confirmó las operaciones ADMIN disponibles y el modelo compatible. La prueba envía ahora Enter después de comprobar que el botón está habilitado; la repetición pasó sin cambiar el permiso productivo ni simular éxito. La [bitácora](../../tests/evidence/s5-check-incidents.json) conserva la carrera de preparación del botón y los demás fallos intermedios.

1. ADMIN incorporó explícitamente las 55 predicciones existentes mediante la UI de sincronización. La repetición e inferencia reutilizaron las 55 predicciones, sin volver a crearlas ni duplicar casos.
2. TUTOR actuó sobre un solo caso de su sección: dos actividades simuladas, una DONE y otra CANCELLED, paso a revisión/cierre RESOLVED y evidencia conservada. El runner reconoce sus objetivos de prueba para reanudar un intento sin planificar otro par en otro caso.
3. DIRECTOR consultó casos/resumen/CSV sin mutaciones; RESEARCHER permaneció restringido. TUTOR no recibió ni descargó información ajena. Los tres roles de consulta comprobaron Inicio y su resumen propio.
4. Se conservaron 60 estudiantes, 360 cortes, un modelo, artefactos y 55 predicciones previas. El [estado activo](../../tests/evidence/s5-active-final-environment.json) registra **51 alertas, 55 decisiones y dos actividades** después del recorrido; sesiones 57→61 y auditoría 174→297. No hubo regeneración ni reentrenamiento.

Evidencia adicional: [respuestas activas sanitizadas](../../tests/evidence/s5-active-final-response-samples.json) y metadatos CSV de [ADMIN](../../tests/evidence/s5-active-final-admin-csv.json), [TUTOR](../../tests/evidence/s5-active-final-tutor-csv.json) y [DIRECTOR](../../tests/evidence/s5-active-final-director-csv.json). La **omisión intencional** fue la rama de fallos HTTP/resultado incierto, aprobada en aislamiento y excluida del entorno activo; no se contabiliza como una aprobación activa.

## Visual, integración y límites

Inspección final **COMPROBADA de 27 PNG** en **1440 × 900, 768 × 1024 y 390 × 844**, enumerados en [revisión visual final](../../tests/evidence/s5-ui-final-visual-review.json): Alertas ADMIN, Reportes de tres roles, Inicio de tres roles, recurso ajeno 404 y conflicto real 409. Se vieron los archivos originales; no se modificaron capturas. La [revisión anterior](../../tests/evidence/s5-ui-first-visual-review.json) conserva la inspección de 30 imágenes, incluidos planificación, realización, caso concluido y seguimiento del estudiante.

La automatización comprobó ausencia de desborde global. En las capturas finales se confirmó legibilidad de códigos y cantidades, ayuda para desplazamiento, resumen compacto y mensaje ajeno seguro. Las tablas mantienen scroll horizontal interno en tamaños pequeños, y el detalle con formularios/historia sigue siendo largo en móvil. Ver un PNG no acredita su respuesta HTTP: el 404 se comprobó por separado en la prueba funcional. No equivale a una auditoría completa de accesibilidad, lectores de pantalla, hardware táctil o todos los navegadores.

La [validación documental/contractual](../../tests/evidence/s5-contracts.json) aprobó **292 comprobaciones, 66 respuestas reales, 119 tipos de campos mapeados, 15 tablas y 27 operaciones en 26 paths**. Esto se distingue de las pruebas funcionales PostgreSQL. El [build](../../tests/evidence/s5-build.json) comprobó tipos frontend OpenAPI 0.5.0, regeneración reproducible, typecheck/build Windows, imágenes Docker y `pip check` sin dependencias rotas; versiones/locks se conservaron.

La [migración activa](../../tests/evidence/s5-upgrade-active.json) conservó los datos previos. La [persistencia](../../tests/evidence/s5-persistence.json) comprobó **las 15 tablas, cuentas/credenciales, auditoría y archivos idénticos tras recrear contenedores sin borrar volúmenes**, con 297 eventos y 61 sesiones tanto antes como inmediatamente después de esa recreación. Luego comprobó login, logout y revocación de ADMIN/TUTOR/DIRECTOR/RESEARCHER, conservando los datos escolares y archivos; los nuevos accesos se contabilizan por separado.

El [checker agregado S5](../../tests/evidence/s5-review.json) quedó **COMPROBADO**. Verificó las 27 operaciones registradas frente al contrato, las 66 respuestas sanitizadas, los resultados finales y la conservación de cuentas/sesiones/auditoría anteriores, datos, modelo y archivos privados. Sus conteos finales son **305 eventos de auditoría y 65 sesiones**, después de comprobar los cuatro accesos/revocaciones posteriores a la recreación; las 51 alertas, 55 decisiones y dos actividades permanecieron iguales.

También comprobó locks/dependencias, núcleo matemático ML, migraciones antiguas, ADR y evidencias históricas sin modificaciones; hashes del respaldo coincidentes y entorno histórico detenido. SHA inicial y HEAD al cierre: `e9349f26b3f0b301cd4d5f50bbec0a7532110e85`; no se hizo commit, push ni despliegue externo. No se ejecutó el checker de base vacía ni se reinterpretó el cierre S4 de cero alertas/intervenciones. Las evidencias S0–S4 y las iteraciones S5 fallidas permanecen conservadas.

S6, restauración final integrada, revisión académica y habilitación REAL permanecen fuera de alcance. Las pruebas de este sprint no acreditan eficacia pedagógica, rendimiento escolar del modelo ni la hipótesis de la tesis.
