# Matriz de verificación S4

Alcance: interfaz conectada de **Seguimiento Escolar** para el estudio SYNTHETIC
existente, contrato OpenAPI 0.4.0. REAL permanece bloqueado; la interfaz no entrena,
activa modelos ni incorpora gestión S5/S6. Referencia publicada inicial:
`90a5e8492b9bdd7d1a37ae59e105fddbd7e116a7`. Decisión vigente:
[ADR 007](../adr/007-interfaz-s4.md).

Esta matriz enumera recorridos y resultados exigidos. La suite backend, build y
los recorridos de navegador **aislados finales `s4-complete` y activos finales
`s4-active-complete` están COMPROBADOS**, incluida la repetición con reloj del
navegador adelantado. **Persistencia y checker final COMPROBADOS**. Sus informes
fallidos previos se conservan. Las pruebas
simuladas, aisladas y activas se registran por separado; un componente o su
compilación no acreditan por sí solos un recorrido. Las evidencias de S3.1 se
conservan y no sustituyen las comprobaciones nuevas de S4.

Evidencias consultadas: [primera importación final](../../tests/evidence/s4-complete-isolated-import-playwright.json),
[cuatro roles y credenciales](../../tests/evidence/s4-complete-isolated-playwright.json),
[entorno aislado](../../tests/evidence/s4-complete-browser-environment.json),
[roles activos](../../tests/evidence/s4-active-complete-playwright.json),
[preservación activa](../../tests/evidence/s4-active-complete-environment.json),
[persistencia](../../tests/evidence/s4-persistence.json),
[checker final](../../tests/evidence/s4-review.json),
[build/tipos](../../tests/evidence/s4-build.json),
[JUnit backend](../../tests/evidence/s4-backend.xml) y
[inspección visual independiente](../../tests/evidence/s4-visual-review.json),
complementada por la [revisión del coordinador](../../tests/evidence/s4-coordinator-visual-review.json).

## Pantallas, roles y operaciones

Todas las operaciones HTTP indicadas tienen prefijo `/api/v1`. El servidor
determina rol, alcance de sección, periodo, origen y compatibilidad; un control
oculto o deshabilitado en el navegador no reemplaza esa validación.

| Pantalla / recorrido | Roles autorizados | Operaciones reales | Estados y resultado esperado | Estado S4 |
|---|---|---|---|---|
| Acceso y restauración | Las cuatro cuentas locales | POST `/auth/login`; GET `/auth/me`; GET `/auth/csrf` | Carga, credenciales rechazadas, límite de intentos, servicio no disponible y sesión restaurada. Sin contraseñas visibles en evidencias ni tokens en storage. | COMPROBADO aislado y activo; límite de intentos en suite backend |
| Cierre y expiración | ADMIN, TUTOR, DIRECTOR, RESEARCHER | POST `/auth/logout`; 401 de cualquier consulta autenticada | Revocación de cookie comprobada; regreso al acceso, cancelación y limpieza de caché/CSRF en memoria. Un 401 posterior no conserva registros de la sesión anterior. | COMPROBADO aislado y activo |
| Inicio y contexto | ADMIN, TUTOR, DIRECTOR | GET `/periods`; GET `/sections?period_id=…`; GET `/processing/status` | Periodo y secciones autorizados; carga, catálogos vacíos, error con reintento y aviso sintético obtenido del servidor. Cambio de periodo restablece sección, filtros y página. Sin indicadores ficticios. | COMPROBADO aislado y activo; 503 de estado UI simulado |
| Inicio limitado | RESEARCHER | GET `/processing/status`, operaciones propias de sesión | Sin catálogos escolares, estudiantes, modelos ni escrituras. El acceso directo a una vista restringida no dispara esas consultas. | COMPROBADO aislado y activo |
| Estudiantes / lista | ADMIN, TUTOR, DIRECTOR | GET `/students` con `period_id`, `section_id`, `search`, `risk_level`, `sort`, `page`, `page_size` | Buscar código, riesgo, orden y tamaño consultados al servidor; carga, vacío del contexto, filtros sin coincidencias, error, lista y paginación estable. TUTOR solo ve sus secciones. Null conserva “Sin dato”/“Sin estimación”. | COMPROBADO aislado y activo; 503 de lista UI simulado |
| Estudiante / detalle | ADMIN, TUTOR, DIRECTOR, con alcance del recurso | GET `/students/{id}?period_id=…` | Contexto, datos observados, ventana, disponibilidad, revisión y última evaluación reales. Revisión nueva sin predicción conserva pendiente. Datos insuficientes nunca se muestran como LOW. Recurso ajeno/inexistente usa el mismo aviso seguro. | COMPROBADO aislado y activo; revisión nueva fixture solo en DB aislada |
| Estudiante / historial | ADMIN, TUTOR, DIRECTOR, con alcance del recurso | GET `/students/{id}/timeline?period_id=…&page=…&page_size=…` | Carga, vacío, error, eventos paginados y cronología disponible. Selector “Eventos por página”: 5/10/20, inicialmente 5; cambiar tamaño restablece página y detalle histórico. Evidencia anterior conservada; alertas/intervenciones existentes son lectura, sin acciones de S5. | COMPROBADO aislado y activo; página 2 y cambio de tamaño efectivos |
| Evaluación histórica | ADMIN, TUTOR, DIRECTOR, con alcance del recurso | GET `/predictions/{id}` desde un evento de historial | Resultado real del corte indicado, foco al abrir/cerrar detalle, error sanitizado o aviso seguro de no disponibilidad. No atribuir la predicción histórica a una revisión posterior. Probabilidades no calibradas no se presentan como porcentajes de certeza. | COMPROBADO aislado y activo |
| Datos / preparar y revisar | ADMIN | POST `/imports/preview`; GET `/imports/{id}` | Ayuda de tres pasos, cabeceras sin filas, CSV registrado, periodo SYNTHETIC no bloqueado, CSRF y límites. Vista previa no crea registros académicos. READY/FAILED/COMMITTED y errores por fila/campo se muestran según la API. | COMPROBADO aislado y activo; CSV modificado 422 real; activo reutiliza COMMITTED |
| Datos / confirmar | ADMIN | POST `/imports/{id}/commit` con `expected_preview_version` | Confirmación humana; éxito solo después de respuesta. Lote reutilizado sin duplicados. 409 exige revisión nueva; red/503 conserva incertidumbre y no reintenta automáticamente. Cambio de contexto cancela y descarta respuestas tardías. | COMPROBADO nueva confirmación aislada; 409 stale UI simulado y confirmación posterior real. Activo consulta lote ya COMMITTED sin reimportar |
| Datos / restricciones | TUTOR, DIRECTOR, RESEARCHER; REAL; periodo bloqueado | Navegación directa y verificaciones HTTP autorizadas de QA | Roles sin permiso no llaman al importador desde UI. El servidor rechaza rol/CSRF/origen/periodo correspondientes. ProcessingStatus fallido mantiene acciones deshabilitadas. | COMPROBADO roles aislados y activos; contexto REAL en fixtures aislados, bloqueo de periodo en suite backend |
| Modelos / lista | ADMIN | GET `/models?page=…&page_size=…` | Carga, lista vacía con “Modelo no disponible”, error con reintento y paginación. Nombre, algoritmo, versión, estado, origen, actividad y registro vienen de la API. No inventar métricas ni publicar hashes, particiones o artefactos. | COMPROBADO aislado y activo; vacío únicamente antes del registro aislado |
| Modelo / detalle | ADMIN | GET `/models/{id}` | Campos públicos, compatibilidad versionada informada y alcance de simulación. Inexistente/ajeno no revela recursos. Sin controles HTTP de entrenamiento o activación. | COMPROBADO aislado y activo |
| Evaluar periodo | ADMIN; SYNTHETIC preparado | POST `/predictions/run` con `period_id`, `as_of`, cookie y CSRF | Instante actual consultado al sistema mediante Date HTTP y tiempo monótono, o fecha/hora Lima explícita. No se depende del reloj de Windows ni se altera el guard temporal del servidor. El servidor valida el periodo concreto aunque el estado general esté preparado. Resultado muestra selected/created/reused/abstenciones reales; no conserva porcentajes no calibrados ni riesgo inventado. | COMPROBADO aislado y activo; reloj del navegador adelantado diez minutos, activo sin predicciones nuevas |
| Evaluación / bloqueos y fallos | ADMIN bajo condición bloqueada; otros roles | ProcessingStatus y errores de POST `/predictions/run` | Sin periodo/modelo, REAL, periodo bloqueado, esquema incompatible y estado no consultable deshabilitan o explican la condición. 401 expira; 403/409/422/503 conservan respuesta sanitizada. Red/503 no simula éxito ni dispara retry. Cancelación y descarte tardío al salir/cambiar contexto. | COMPROBADO aislado y activo; estado 503 y pérdida de body UI simulados, inferencia positiva real; restricciones de origen/periodo en suite backend |
| Alertas / Reportes | Según la navegación de cada rol | Ninguna nueva operación | Indicados como pendientes de S5; sin tablas, indicadores, formularios o éxito simulados. | COMPROBADO en capturas aisladas y activas |

## Comprobaciones transversales

| Criterio | Comprobación requerida | Estado / evidencia |
|---|---|---|
| Contrato y tipos | Regeneración desde contrato vigente; validación documental; build; no campos inventados en componentes. | COMPROBADO: [build](../../tests/evidence/s4-build.json), cuatro comandos código 0; tipos regenerados idénticos, Node Docker 24.14.1/npm 11.20.0. [Contratos](../../tests/evidence/s4-contracts.json): 199 checks, 14 tablas, 19 rutas, 94 campos tipados. [Checker final](../../tests/evidence/s4-review.json): 16 respuestas validadas, incluyendo cuatro Error; no son 16 respuestas positivas. |
| Aislamiento de sesión/contexto | Keys incluyen usuario/rol/recurso/contexto/filtros; consultas con AbortSignal; escrituras sin retry; cleanup al desmontar. Cambiar sesión/periodo no aplica respuestas antiguas. | COMPROBADO aislado y activo: respuesta positiva real diferida en GET/POST descartada al cambiar contexto; sesión nueva sin resultados de la anterior. |
| Fechas y faltantes | Timestamp en America/Lima; DATE sin cambio de día; manual as_of Lima convertido a UTC. Null no se convierte en 0/LOW. | COMPROBADO aislado y activo: detalle/fecha objetivo, nulls, consulta histórica sin probabilidades y as_of actual/manual explícito; revisión pendiente solo aislada. Con Date del navegador adelantado diez minutos, el modo actual conserva inferencia real 200 usando hora observada de la API; precisión de segundos del encabezado, sin fallback al reloj local. |
| Autorización | Cuatro cuentas existentes, sección propia/ajena, URL directa, cookie y CSRF; RESEARCHER no amplía acceso. | COMPROBADO con cuatro cuentas fixture aisladas y las cuatro cuentas locales activas conservadas; API/PostgreSQL y navegador reales, cinco casos activos passed incluyendo credenciales rechazadas. |
| Primera importación aislada | Estudio y CSV registrados preparados exclusivamente en el entorno de prueba; preview sin académicos; confirmación atómica; estudiantes consultables. | COMPROBADO: [fase primera importación](../../tests/evidence/s4-complete-isolated-import-playwright.json), un caso passed, 16821 ms. Modelo vacío antes de registro; preview/GET/commit efectivos, confirmación explícita y versión vigente. |
| Evaluación aislada | Fixtures del núcleo preparados por CLI fuera de HTTP; inferencia del periodo por UI con nuevas/reutilizadas/abstenciones; revisión pendiente. | COMPROBADO: [fase roles](../../tests/evidence/s4-complete-isolated-playwright.json), cinco casos passed. SVM fixture registrado por CLI; predicciones iniciales 55 y cinco abstenciones; revisión solo en DB aislada. POST diferido y POST cuyo body se truncó responden 200 real antes de comprobar descarte/incertidumbre. Métricas de fixtures son evidencia de software. |
| Repetición activa | CSV ya COMMITTED y evaluación del periodo activo reutilizan evidencia. Sin generación, entrenamiento, nuevas cuentas o duplicados académicos. | COMPROBADO: [antes/después](../../tests/evidence/s4-active-complete-environment.json), cuatro cuentas, 60 estudiantes, 360 cortes, 55 predicciones y archivos privados sin cambios. El CSV vuelve como COMMITTED; la [evaluación activa inspeccionada](../../tests/evidence/s4-coordinator-visual-review.json) selecciona 60, crea cero, reutiliza 55 y conserva cinco abstenciones. Auditoría 151→161 y sesiones 44→49 aumentan por el recorrido explícito. |
| Layout y accesibilidad básica | Inspección de pantallas reales en 1440×900, 768×1024 y 390×844; teclado/foco/labels/caption; tablas con desplazamiento interno, sin desbordamiento global. | COMPROBADO: [32 PNG inspeccionados](../../tests/evidence/s4-visual-review.json): 23 aislados y nueve activos de Inicio/lista/detalle en los tres tamaños. [Coordinador](../../tests/evidence/s4-coordinator-visual-review.json): seis inspecciones de Datos/detalle de modelo/Inicio; una coincide con la revisión independiente. Tres PNG aislados pertenecen al run funcional fallido `s4-clock-final` y solo acreditan inspección visual; el panel actualizado también se inspeccionó en el run aprobado `s4-complete`. No equivale a auditoría completa de accesibilidad. |
| Estados de fallo | Carga, vacío, filtros vacíos, 401/403/404/409/422/503/red; request_id/detalles preservados. Mutación incierta conserva cautela y exige acción explícita. | COMPROBADO aislado y activo. 503 lista/ProcessingStatus, 409 stale de commit y cuerpo JSON perdido están expresamente simulados; respuestas positivas y permisos sí usan servidor/DB reales. |
| Regresión S1–S3.1 | Suite backend completa en Python 3.12.12/PostgreSQL aislado con riesgo_app; pip check y versiones/locks conservados. | COMPROBADO: [233 pruebas](../../tests/evidence/s4-backend.xml), cero fallos/errores/omisiones, JUnit 115.425 s; [Linux/Python 3.12.12/PostgreSQL 17.6 aislado](../../tests/evidence/s4-backend-environment.json). [Checker final](../../tests/evidence/s4-review.json): pip check “No broken requirements found.”; hashes de locks, núcleo ML, migraciones, cuentas y evidencias históricas conservados. |
| Persistencia | Reinicio sin borrar volúmenes; cuentas/credenciales/auditoría/artefactos/estudio conservados; entorno histórico detenido y respaldos intactos. | COMPROBADO: [recreación sin borrar volúmenes](../../tests/evidence/s4-persistence.json), contenido de las 14 tablas y archivos idéntico inmediatamente después, incluido usuarios/auditoría/sesiones. Acceso/logout/revocación posterior con los cuatro roles y conteos académicos conservados. [Checker](../../tests/evidence/s4-review.json): entorno histórico detenido, hashes de respaldos coinciden. No se usó checker de base vacía sobre la aplicación con cuentas. |

## Registro de cierre

La integración aislada final consta de dos fases: primera importación (un caso)
y navegación de cuatro roles/credenciales (cinco casos). Los casos fuera de la fase
se excluyen deliberadamente; no equivalen a omisiones de la suite backend. En la
fase roles, las duraciones fueron ADMIN 26909 ms, TUTOR 6769 ms, DIRECTOR 6005 ms,
RESEARCHER 3342 ms y credenciales rechazadas 1813 ms.

El [recorrido activo final](../../tests/evidence/s4-active-complete-playwright.json)
consta de cinco casos passed: ADMIN 32601 ms, TUTOR 9172 ms, DIRECTOR 6358 ms,
RESEARCHER 2835 ms y credenciales rechazadas 1043 ms. Mantiene el estudio existente;
no reproduce la primera importación ni el fixture de revisión pendiente en activo.
La prueba con reloj adelantado y los POST diferido/body-loss conservan respuestas
reales 200; los fallos de lectura/503 son simulaciones expresamente identificadas.

La [exportación local de CSV](../../tests/evidence/s4-csv-export.json) comprobó hash
registrado idéntico, 48010 bytes, destino fuera de Git y segundo intento rechazado
sin sobrescribir el archivo; el archivo temporal se retiró. La colección estática
de Playwright y los informes `s4-first-*`/`s4-isolated-*` se conservan por separado
y no se presentan como la ejecución final.

Límites actuales: no se provocó una caída real de PostgreSQL o conectividad en la
aplicación activa; los errores de UI simulados no acreditan esos fallos reales.
No se realizó una auditoría WCAG AA completa, lectores de pantalla ni todos los
navegadores. No se afirma haber probado cada combinación posible de vacío/error
en cada pantalla. Los controles positivos de modelos mostraron la página única
existente, sin crear modelos adicionales para fabricar una segunda página.

Persistencia y checker final están **COMPROBADOS**. Tras la recreación se mantiene
el contenido completo de 14 tablas; las comprobaciones explícitas posteriores de
acceso añaden auditoría y sesiones sin cambiar registros/modelos/cortes/predicciones.
La entrega no evalúa una hipótesis escolar ni habilita procesamiento institucional.

Se conserva el primer [recorrido activo fallido](../../tests/evidence/s4-active-playwright.json):
ADMIN falló en la repetición interceptada del POST (422 esperado 200); los otros
cuatro casos pasaron y no cambió ningún conteo académico. No se conservó el cuerpo
Error, por lo que reloj/latencia es una hipótesis y no una causa acreditada. El
[incidente aislado con reloj adelantado](../../tests/evidence/s4-clock-final-test-incident.json)
conserva otro fallo: se comprobó incertidumbre antes de que llegase el POST cuyo
cuerpo se iba a truncar. La inferencia inicial y diferida sí respondió 200.
La [comprobación aislada corregida](../../tests/evidence/s4-complete-isolated-playwright.json)
ya pasó: espera los POST reales 200 antes de comprobar descarte o incertidumbre.
