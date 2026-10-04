> Cierre histórico: no es una guía de arranque vigente. Consultar [Estado S2.1](Estado_Sprint_2_1.md). Los resultados originales se conservan.

# Estado del Sprint 1 — Base ejecutable DEMO

Fecha: 3 de octubre de 2026 (America/Lima).
**S1 COMPLETADO. Estado histórico al cierre de S1.**

Actualización posterior: [Estado S2](Estado_Sprint_2.md) documenta la implementación
S2 y resuelve los pendientes de suite Linux/Python 3.12.12 y respuestas 503 del
contrato mediante OpenAPI 0.1.2. Los resultados originales de S1 se conservan debajo;
S3–S6 siguen pendientes.

Se leyeron AGENTS.md, plan, Inicio_Codex_y_skills.md, contrato OpenAPI 0.1.1,
Esquema_demo.sql, Conciliacion_SQL_API.md y Sprints_y_aceptacion.md.
Se mantienen las decisiones de S0, sus versiones, archivos de bloqueo y evidencias.
Solo se usaron cuentas y contexto sintéticos; no se cargaron registros de menores.

## Qué se implementó

- Compose ejecutable para web, api y db, Dockerfiles fijados, healthchecks, dependencia
  de salud y volumen PostgreSQL conservado. Host loopback: 15173/18000/55432.
- Configuración DEMO, secretos aleatorios fuera de Git/contexto Docker, rol interno
  riesgo_app separado de riesgo_owner. La API normal no recibe secretos del dueño
  ni las contraseñas de las cuentas demo.
- Alembic 0001_demo_schema: las 13 tablas, restricciones, índices y triggers del SQL
  conciliado; permisos sin DDL, DELETE o TRUNCATE para riesgo_app y sin UPDATE de
  cortes, predicciones o auditoría. Snapshot congelado junto a la revisión.
- Semilla explícita e idempotente: administrador, tutor, directivo, DEMO-2026,
  secciones 1/A y 2/A; el tutor está asignado solo a 1/A. Tres cuentas, un periodo,
  dos secciones, cero estudiantes. Contraseñas Argon2 y credenciales locales
  aleatorias de desarrollo, sin valores de producción.
- Ocho operaciones de 0.1.1: GET health/live, GET health/ready, POST auth/login,
  GET auth/me, GET auth/csrf, POST auth/logout, GET periods y GET sections.
- Sesiones de ocho horas con cookie HttpOnly/SameSite=Lax y Secure bajo HTTPS,
  digests en DB, CSRF por HMAC, Origin exacto en login y límites por IP/correo.
  Logout y auditoría transaccionales; el servidor consulta actividad, rol y alcance.
- Acceso web mínimo S1: formulario, restauración de sesión, catálogos autorizados y
  cierre de sesión; estados de carga/vacío/error/éxito y marca DEMO. Tipos generados
  desde el contrato, sin tokens en almacenamiento del navegador.
- Scripts reproducibles de arranque, migración, semilla, pruebas y persistencia;
  actualización del README, documentación por área y ADR 002.

No se implementaron importación, estudiantes, ML, alertas, intervenciones ni
reportes. Sus tablas existen como diseño migrado, sin recorridos de negocio.
La navegación y pantallas completas de S4 no se consideran entregadas.

## Comprobaciones ejecutadas

Comandos desde la raíz. En este equipo se usaron .venv-s0 y .venv-s1 según la
función. Docker y herramientas nativas de Node necesitaron ejecución fuera de la
restricción de consola de Codex; las comprobaciones efectivas se indican abajo.

| Comprobación | Comando / entorno | Resultado y evidencia |
|---|---|---|
| Documentos, estructura, SQL/OpenAPI, tipos, locks y Compose S1 | .venv-s0/Scripts/python.exe infra/check_s0.py | COMPROBADO: 184 verificaciones, 13 tablas, 35 sentencias, 102 campos tipados, 27 rutas del contrato y ocho ejemplos. tests/evidence/s1-contracts.json. No es prueba funcional. |
| Dependencias backend Windows | pip install --require-hashes -r backend/requirements-dev.txt; pip check en .venv-s1 | COMPROBADO: instalación con hashes, sin dependencias rotas. Python local 3.12.0; no se confunde con el runtime Docker. |
| Dependencias y build Linux | docker compose build api web; ejecutado también por infra/s1.py up | COMPROBADO: Python --require-hashes y npm ci; tsc --noEmit + Vite build, 18 módulos. Sin cambios de locks. |
| Build frontend Windows | npm ci --ignore-scripts; npm run generate:api --workspace frontend; npm run build --workspace frontend | COMPROBADO fuera de la restricción de consola. Tipos de 0.1.1 generados. |
| Arranque documentado | .venv-s0/Scripts/python.exe infra/s1.py up; docker compose ps | COMPROBADO: web/api/db healthy. Node 24.14.1, npm 11.20.0, Python API 3.12.12, PostgreSQL 17.6, Compose 5.5.1. tests/evidence/s1-environment.json. |
| Migración en DB limpia | infra/test_s1.py prepare-db, Alembic upgrade head; también infra/s1.py migrate para la demo | COMPROBADO: DB riesgo_escolar_demo_s1_test sin tablas risk_school, 0 → 13, revisión 0001_demo_schema. tests/evidence/s1-database.json. La DB de prueba ya estaba creada vacía por una preparación previa; no se borró para simular limpieza. La demo riesgo_escolar_demo también quedó migrada. |
| Semilla explícita e idempotencia | infra/s1.py seed-demo y repetición | COMPROBADO: creación inicial 3 usuarios/1 periodo/2 secciones; repeticiones crean 0/0/0. Cero estudiantes. tests/evidence/s1-seed.json y pruebas backend. |
| Backend PostgreSQL | .venv-s1/Scripts/python.exe infra/test_s1.py pytest | COMPROBADO: 57 passed, cero fallos, 33.64 s. tests/evidence/s1-pytest.xml. DB de prueba aislada, rollback por prueba. |
| Configuración tras ocultar entradas en errores | pytest backend/tests/test_s1_seed.py -q -k configuration | COMPROBADO: dos casos pasaron; imagen API reconstruida. No cambió el comportamiento de las 57 pruebas previas. |
| Navegador con API/DB reales | npx playwright test, credenciales privadas por DEMO_CREDENTIALS_FILE | COMPROBADO: cuatro recorridos, cero fallos, 16.3 s. tests/evidence/s1-playwright.json. |
| Interfaz real S1 | node infra/capture_s1.mjs | COMPROBADO: acceso vacío y contexto tutor en 1440×900, 768×1024 y 390×844; seis capturas exactas y cuatro completas, revisión visual y teclado. tests/evidence/s1-ui-checks.json y s1-ui-*.png. Sin desbordamiento horizontal. |
| HTTP, CSRF, revocación y persistencia | .venv-s1/Scripts/python.exe infra/smoke_s1.py | COMPROBADO: tres roles; salud/login/me/csrf 200, logout sin CSRF 403, logout válido 204, cookie revocada 401. Trece tablas idénticas antes/después de compose down / up --wait sin -v ni semilla. Las tres sesiones anteriores sobreviven al reinicio y luego se revocan. tests/evidence/s1-runtime.json. |
| Conservación de S0 | hashes SHA-256 y comparación literal del snapshot SQL sin BEGIN/COMMIT | COMPROBADO: package-lock.json, tres requirements bloqueados, contrato 0.1.1 y SQL sin cambios; snapshot coincidente. tests/evidence/s1-environment.json. |
| Archivos públicos y diferencias | revisión de secretos generados en 137 archivos públicos; git diff --check | COMPROBADO: cero contraseñas/claves privadas en archivos versionables; sin errores de espacios. tests/evidence/s1-private-config-check.json. Git solo avisa de conversión LF/CRLF en tres archivos Windows. |

Las 57 pruebas incluyen atributos Secure bajo HTTPS simulado, errores públicos
sin detalles de DB, digests, Origin, CSRF ajeno/ausente, limitación por IP/correo,
vencimiento, usuario inactivo, rol cambiado en servidor, alcance del tutor,
denegación al investigador, REAL, 13 tablas/FK/índices, privilegios del rol real,
auditoría inmutable, rollback conjunto y semilla repetida.
El runtime Compose real usa riesgo_app; los recorridos HTTP también verifican que
las operaciones funcionan con ese rol restringido.

En la prueba de persistencia había tres cuentas, un periodo, dos secciones, siete
filas de sesión y 17 eventos de auditoría, además de ocho tablas vacías del trabajo
futuro. Cantidades y hashes coincidieron exactamente tras recrear los contenedores.
Cerrar las tres sesiones al final añade su auditoría; no es pérdida de datos.
Esta comprobación de S1 no prueba persistencia de futuros lotes/predicciones/casos.

## Criterios S1

| Criterio | Estado |
|---|---|
| Comando de arranque y salud live/ready | COMPROBADO; ready devuelve unavailable/503 si falla DB, live conserva ok en prueba de backend. |
| Migración revisada de 13 tablas en base limpia | COMPROBADO, PostgreSQL 17.6. |
| Semilla explícita con tres perfiles, sin datos reales | COMPROBADO e idempotente. |
| Login/me/csrf/logout, vencimiento, revocación, Origin y límite | COMPROBADO en pruebas y recorridos reales. |
| Cookie, digests y rechazo de escritura sin CSRF | COMPROBADO; HTTP local y Secure HTTPS simulado diferenciados. |
| Roles y alcance en periods/sections | COMPROBADO: tutor una sección; admin/directivo dos; investigador denegado. |
| Contexto y sesiones conservados tras detener/arrancar | COMPROBADO con comparación de trece tablas y cookie anterior. |

## Incidencias resueltas

- Primer arranque db FALLIDO por puerto 5432 ocupado. Se eligió 55432 para esta demo,
  sin tocar el servicio ajeno; puertos web/API también se separaron.
- Primer arranque web FALLIDO por EACCES en caché Vite al usar node sin privilegios.
  Se dio propiedad de /workspace a node; posterior build/up healthy.
- Build nativo Windows FALLIDO dentro de la restricción por spawn EPERM/Tailwind.
  La misma build fuera de esa restricción pasó; no se cambiaron dependencias.
- Preparación local PostgreSQL demoró por resolución de localhost en este Windows.
  Los scripts de comprobación usan 127.0.0.1 y connect_timeout=5. La migración limpia
  y las pruebas completas luego pasaron; no se eliminó la base.
- Se ocultaron entradas en errores Pydantic de configuración para evitar revelar
  secretos de variables de entorno; se reconstruyó la API.

## Pendientes y límites

- El handler de errores de DB devuelve un 503 Error sanitizado en auth/catálogos;
  0.1.1 enumera 503 solo en health/ready. Documentar esta respuesta transversal en
  una futura revisión de contrato. El contrato actual se conservó íntegro.
- Pytest informa una deprecación TestClient/httpx de Starlette. No impide las pruebas;
  no se migró a httpx2 porque las versiones acordadas siguen vigentes.
- NO EJECUTADO: suite pytest completa dentro de Linux/Python 3.12.12. La suite se
  ejecutó en Windows/Python 3.12.0 con PostgreSQL real; instalación/migración/API y
  recorridos HTTP sí se comprobaron en las imágenes Linux fijadas.
- NO EJECUTADO: HTTPS real/despliegue institucional, múltiples workers, rotación de
  secretos, respaldo y restauración. La demo es local HTTP; Secure HTTPS se probó
  en TestClient. Vite sirve desarrollo; limitador en memoria por proceso.
- NO EJECUTADO: Make (herramienta opcional ausente); los equivalentes PowerShell
  funcionaron. train-demo/demo/backup permanecen reservas de sus siguientes sprints.
- NO EJECUTADO por alcance: CSV, estudiantes, entrenamiento/predicción, alertas,
  intervenciones, reportes y recorrido integrado de S6. No se afirma aceptación
  S2–S6, validación de modelo ni resultado académico.
- REAL sigue bloqueado; escala, horizonte, autorizaciones y protocolo institucional
  conservan sus dependencias académicas.

## Archivos y siguiente dependencia

Nuevos: backend/app (capas y semilla S1), backend/migrations y alembic.ini,
backend/tests, frontend/index.html/configuración/src de acceso y tipos generados,
infra/docker, infra/db, overrides Compose y scripts S1, playwright.config.ts,
tests/e2e/s1.spec.ts, evidencias s1-*, ADR 002 y este estado.

Modificados: compose.yaml, .env.example, .gitignore, .gitattributes, .dockerignore
(nuevo), Makefile, frontend/package.json (solo comandos), README por áreas,
infra/check_s0.py, registro de sprints y notas de seguimiento en ADR 001/conciliación.
AGENTS, plan, Inicio, contrato, SQL, versiones y locks se conservan.
No se borraron datos ni evidencias S0.

**La base está preparada para iniciar S2 cuando el usuario lo autorice.**
S2 depende de importación con vista previa/versiones/confirmación, estudiantes y
cortes, sobre la base/permisos de S1 y el contrato vigente. No se inició ese trabajo.
