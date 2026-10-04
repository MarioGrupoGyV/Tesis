# Estado del Sprint 4

Fecha: 4 de octubre de 2026, America/Lima. Alcance exclusivo S4: interfaz de
**Seguimiento Escolar** conectada al estudio SYNTHETIC existente de S3.1.
**S4 implementado y comprobado** en aplicación activa y entorno aislado.
S5/S6 y tratamiento REAL permanecen pendientes.

## Referencia y conservación

SHA inicial y HEAD actual: `90a5e8492b9bdd7d1a37ae59e105fddbd7e116a7`.
El checkout inicial estaba limpio. No se creó un commit, no se hizo push ni
hubo despliegue externo. La dependencia S3.1 se verificó antes de implementar:
[revisión nueva](../../tests/evidence/s4-s3-1-dependency.json). ADR previa:
[007 — interfaz S4](../adr/007-interfaz-s4.md).

El estado activo de referencia contiene 60 registros sintéticos de estudiante,
360 cortes, 55 predicciones, 5 abstenciones y un modelo SVM técnicamente activo
para simulación. Son resultados de la base, nunca constantes del frontend.
Se conservan las cuatro cuentas S2.2, sus hashes de contraseña y entradas privadas
de Windows; sesiones y auditoría anteriores; los tres volúmenes, puertos,
secretos, archivos internos y respaldo del entorno histórico detenido.
La revisión genera sesiones y auditoría nuevas de acceso/reutilización, sin
sobrescribir evidencia previa. No se regeneró ni reentrenó el estudio activo.

## Qué se implementó

- Acceso/restauración/cierre, AppShell verde SE, navegación estable con recarga,
  atrás/adelante, 404 y URLs protegidas. Menú móvil por teclado/Escape y foco.
- Inicio didáctico, alcance sintético explícito y contexto autorizado de periodo
  y sección. RESEARCHER conserva solo Inicio limitado y sesión.
- Estudiantes con búsqueda de código, riesgo, orden y paginación del servidor;
  detalle con contexto, observaciones, última evaluación e historial paginado.
  Null conserva Sin dato/Sin estimación; revisión nueva pendiente no hereda riesgo.
  Riesgo lleva texto, icono y color. DATE conserva su día, horas en America/Lima.
- Datos con Preparar → Revisar → Confirmar: plantilla de solo 13 cabeceras,
  selector CSV en español, CSV exacto registrado, GET de lote, cantidades
  planificadas, errores por fila/campo, consentimiento y versión vigente.
  COMMITTED indica reutilización. Conflicto exige nueva vista previa; respuesta
  incierta exige consultar resultado, sin reintentar escrituras automáticamente.
- Modelos ADMIN con proyección pública paginada/detalle y evaluación sintética
  efectiva por periodo/as_of. Instante actual con HTTP Date de la API del mismo origen y tiempo monótono,
  de precisión de segundos y sin fallback silencioso al reloj Windows; fecha manual
  Lima explícita;
  resultados created/reused/abstenciones de API, sin métricas privadas ni confianza
  ficticia. No hay entrenamiento/activación HTTP.
- Cliente API tipado, AbortSignal, TanStack Query por usuario/rol/contexto/filtros,
  cancelación y descarte de respuestas antiguas. 401 limpia sesión/cache/CSRF.
  CSRF solo en memoria y cookies HttpOnly; ningún dato escolar o token en storage.
  Fallo de ProcessingStatus deshabilita selección/importación/evaluación hasta
  reintento. Guards del servidor mantienen REAL bloqueado.
- Extensión mínima autorizada `infra/study.py export-csv`: ADMIN autenticado,
  archivo nuevo absoluto fuera de Git, ruta/nombre/hash validados y creación
  exclusiva. El comando interno añade el hash registrado a su respuesta privada.
  Sin endpoint de descarga, contenido/base64/etiquetas/secretos en evidencias.

Alertas y Reportes están rotulados **Pendiente de implementación** sin enlaces
ficticios. No se añadieron operaciones API: continúan las 19 del contrato 0.4.0.
No cambiaron migraciones, pipelines ML, metodología, restricciones de activación,
versiones ni locks. No se introdujeron dependencias de frontend.

## Pruebas comprobadas

| Comprobación | Resultado / evidencia |
|---|---|
| Backend completo | **233 aprobadas**, 0 fallidas/errores/omitidas; 40 advertencias. Linux/Python 3.12.12, PostgreSQL 17.6 aislado y riesgo_app; base riesgo_escolar_test_e49545358c24. Incluye las 16 pruebas nuevas del launcher y conserva S1–S3.1. [JUnit](../../tests/evidence/s4-backend.xml), [entorno](../../tests/evidence/s4-backend-environment.json). |
| Primera importación UI/API/DB aislada | **1 caso aprobado**; GET modelos vacío real, estudiantes iniciales 0, preview READY sin académicos y commit real de 360 cortes/60 registros. [Informe](../../tests/evidence/s4-complete-isolated-import-playwright.json). |
| Navegación aislada | **5 casos aprobados**, cuatro roles y credenciales inválidas, API/PostgreSQL efectivos; filtros/paginación, nulls, propia/ajena, 404 seguro, historial/predicción, CSRF, recarga/atrás/adelante y logout/revocación. [Informe](../../tests/evidence/s4-complete-isolated-playwright.json), [entorno](../../tests/evidence/s4-complete-browser-environment.json). |
| Exportación local | Hash registrado/exportado idéntico: 79fedc114a952631977bbd46cabe5c5a76faeef7e7293e709d5a1a11c9b31374, 48 010 bytes. Segundo intento devuelve CSV_OUTPUT_EXISTS y conserva bytes. CSV temporal fuera de Git eliminado al concluir; upload real probado en ambos runners. [Informe](../../tests/evidence/s4-csv-export.json). |
| Contrato/documentación | **199 comprobaciones**, 14 tablas, 94 tipos de campos, 19 rutas, 54 sentencias SQL y 3 muestras documentales. No ejecuta DDL ni sustituye integración. [Informe](../../tests/evidence/s4-contracts.json). |
| Tipos/compilación | Generación OpenAPI sin diff, typecheck/build host y Docker aprobados: 77 módulos; Node 24.14.1/npm 11.20.0 en Docker. Sin dependencia nueva. [Informe](../../tests/evidence/s4-build.json). |
| Cierre integrado | Checker S4 aprobado: 16 respuestas contractuales validadas (incluyen Error), 19 rutas vigentes, cuentas/hashes, sesiones/auditoría previas, historial, locks, ML y migraciones conservados; volúmenes saludables y respaldo histórico íntegro. pip check: No broken requirements found. [Informe](../../tests/evidence/s4-review.json). |
| Aplicación activa | **5 casos aprobados** con las cuatro cuentas Windows existentes. CSV COMMITTED reutilizado; inferencia 0 nuevas/55 reutilizadas/5 abstenciones. 60 estudiantes, 360 cortes, 55 predicciones y archivos privados conservados; 0 alertas/intervenciones. La revisión activa sumó 5 sesiones y 10 eventos de acceso/cierre, sin alterar evidencia académica. [Recorrido](../../tests/evidence/s4-active-complete-playwright.json), [estado antes/después](../../tests/evidence/s4-active-complete-environment.json). |
| Persistencia | **14 tablas y archivos idénticos** tras recreación sin borrar volúmenes; login/logout/revocación de cuatro roles aprobados. Conserva usuarios, hashes/credenciales y artefactos. [Informe](../../tests/evidence/s4-persistence.json). |
| Revisión visual | Capturas reales inspeccionadas en 1440×900, 768×1024 y 390×844. [Revisión independiente](../../tests/evidence/s4-visual-review.json), [Datos/modelo/activo](../../tests/evidence/s4-coordinator-visual-review.json). Sin hallazgos visuales bloqueantes; no auditoría WCAG completa. |

Los seis casos finales aislados usan la base
`riesgo_escolar_test_browser_4cc550d5c8db`. El runner genera/compara/registra/activa
únicamente allí mediante los comandos explícitos S3.1; después prueba inferencia
por interfaz/API. Una revisión adicional es fixture mínimo exclusivo de esa base,
protegido por APP_ENV=test y nombre de DB, y conserva predicción anterior. No amplía
el generador ni habilita correcciones operativas. La inferencia posterior registra
1 evaluación nueva, reutiliza 54 y conserva 5 abstenciones únicamente en el aislado.
Esto comprueba software y activación técnica sintética; no evaluación institucional.

Las respuestas GET de otro alcance y POST de inferencia **efectivamente procesadas**
se retuvieron antes de devolverlas para comprobar cancelación/cambio ADMIN→TUTOR:
no se aplicaron datos de la sesión anterior. No son respuestas positivas inventadas. El reloj Date del navegador se adelantó
10 minutos sin alterar performance ni peticiones; la inferencia actual real fue 200
con as_of derivado de la hora de API. Se conservan las dos respuestas interceptadas
200 (diferida y lectura perdida) en diagnóstico sanitizado.

## Ramas HTTP simuladas, fallos y omisiones

Se identifican en los JSON y nombres `http-simulated-*`:

- 503 del listado de estudiantes y 503 de ProcessingStatus: estado de error/reintento,
  datos sensibles deshabilitados y recuperación posterior con GET real.
- IMPORT_PREVIEW_STALE 409 del commit: exige repreview real y nuevo consentimiento,
  mantiene 0 estudiantes hasta el commit real. No acredita por sí solo un conflicto
  concurrente del motor, comprobado separadamente por su suite PostgreSQL conservada.
- Pérdida del cuerpo JSON después de POST de inferencia real 200: muestra resultado
  incierto, una sola llamada y ninguna repetición automática. No acredita una caída
  de infraestructura activa. No se simulan respuestas positivas ni datos escolares.

Los informes finales usan `s4-complete-*` aislado y `s4-active-complete-*` activo.
Sus casos están aprobados; las ejecuciones intermedias también se conservaron.
El primer activo `s4-active-*` contiene un ADMIN fallido (POST interceptado 422);
no se guardó su cuerpo Error, por lo que su causa no se afirma.
`s4-clock-final-*` aprobó la inferencia con reloj adelantado y el POST diferido 200,
pero falló al exigir el aviso antes de recibir la respuesta truncada. Se corrigió
la sincronización de la prueba, sin aumentar timeout ni cambiar guards.
[Incidente aislado](../../tests/evidence/s4-clock-final-test-incident.json).
[Incidencias](../../tests/evidence/s4-check-incidents.json): intento de pytest nativo
Windows no ejecutó pruebas porque no existe ese módulo; no se instaló, la suite
corrió en Docker. Un build intermedio rechazó dos contadores no publicados por
ImportCommit; corregido usando solo created_snapshots y build final aprobado.
Un comando inicial de lectura Docker bajo sandbox encontró permiso denegado del
pipe; se repitió con acceso autorizado. No se modificaron datos para resolverlos.

Las 40 advertencias backend corresponden a deprecaciones existentes de
Starlette/TestClient/httpx y SVC(probability=False). No justificaron actualizar locks.
No se ejecutaron pytest nativo Windows, auditoría completa WCAG/lector de pantalla,
pruebas de hardware táctil, estrés/carga, tratamiento REAL ni recorrido S5/S6.
El bloqueo por periodo, validaciones/rollback/concurrencia y núcleo ML conservan
pruebas backend; no todos sus errores se forzaron por la UI. No se ejecutó el checker
de base vacía ni se eliminó/restauró/resembró el estudio activo.

## Comandos PowerShell reproducibles

Desde la raíz, con Docker Desktop disponible y sin repetir logins en bucle
(límite vigente 10 intentos/IP/300 s, incluidos accesos correctos):

```powershell
$env:TEST_REPORT_NAME = 's4-backend'
docker compose -f infra/compose.test.yaml build tester
docker compose -f infra/compose.test.yaml run --rm tester
npm run generate:api --workspace frontend
npm run typecheck --workspace frontend
npm run build --workspace frontend
docker compose build web
docker compose up -d --no-deps --wait web
$env:BROWSER_REPORT_PREFIX = 's4-complete'
py -3.12 infra/test_browser.py
$env:REVIEW_REPORT_PREFIX = 's4-active-complete'
py -3.12 infra/review_browser.py --study-id e3a2d28b-2f23-56ae-878c-1a8f4a257e7e --period-id c036cbcb-87db-5ed0-bcfa-bbd644928ccb
$env:PERSISTENCE_REPORT_PREFIX = 's4'
py -3.12 infra/check_access_persistence.py
.\.venv-s0\Scripts\python.exe infra/check_s0.py
.\.venv-s0\Scripts\python.exe infra/check_s4.py --isolated-prefix s4-complete --active-prefix s4-active-complete
docker compose exec -T api python -m pip check
git diff --check
```

Los runners necesitan Node/npm/Chromium de Playwright ya preparados. Para ejecuciones
posteriores elige prefijos nuevos comenzados por s4 y conserva los reportes actuales;
el checker usa esos prefijos. La instantánea privada `.local/s4-before.json` pertenece
a este cierre y no contiene contraseñas. El comando de persistencia recrea contenedores
sin `-v`, conserva los volúmenes y comprueba acceso/revocación de los cuatro roles.

Para obtener un CSV nuevo del estudio **existente**, sin generar/reentrenar:

```powershell
$carpetaEstudio = Join-Path $env:LOCALAPPDATA 'SeguimientoEscolar\ArchivosEntrada'
New-Item -ItemType Directory -Path $carpetaEstudio -Force | Out-Null
$archivoEstudio = Join-Path $carpetaEstudio 'estudio-s4-entrada.csv'
py -3.12 infra/study.py export-csv --admin-credential ADMIN --study-id e3a2d28b-2f23-56ae-878c-1a8f4a257e7e --output $archivoEstudio
Get-FileHash -LiteralPath $archivoEstudio -Algorithm SHA256
```

El archivo debe ser nuevo; si existe usa otro nombre. No pasar contraseñas por
argumentos ni descargar artefactos privados. En Datos, Seleccionar CSV abre el
selector local. Plantilla de cabeceras y CSV registrado son archivos distintos.
[Manual de uso](../manuals/Manual_Uso_S4.md) y
[matriz pantalla/rol/endpoint/estado/evidencia](Matriz_verificacion_S4.md).

## Archivos y siguiente dependencia

Frontend: App/main/styles, AppShell/UI compartida, cliente API/format/navigation y
features auth/home/students/imports/models. Launcher/QA: study.py, respuesta mínima
synthetic_cli export-csv, browser_fixture, test_s4_launcher, runners, reporter,
Playwright/config y Compose aislado/Dockerfile tester; nuevo check_s4 y adaptación
no destructiva de check_s0. Compose activo cambia únicamente marcador de fase S4.
Markdown: AGENTS, README, plan, criterios, Inicio, ADR007, manual, matriz y este cierre.
Evidencias nuevas exclusivamente s4. El listado exacto se registra en
[s4-changed-files.json](../../tests/evidence/s4-changed-files.json).

S4 deja las pantallas conectadas de simulación. S5 debe implementar sus operaciones
reales de alertas/intervenciones/reportes/exportación antes de habilitarlas; S6
comprobará su integración completa. REAL requiere protocolo y revisión institucional
pendientes. Ninguna métrica sintética valida el colegio ni la hipótesis de tesis.
