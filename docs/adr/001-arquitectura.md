> Registro histórico. El alcance operativo queda sustituido por [ADR 004](004-transicion-windows.md); se conservan aquí las decisiones y hechos de su iteración.

# ADR 001 — Arquitectura y preparación de la demo

Fecha: 3 de octubre de 2026 (America/Lima). Estado: **aceptado para S0**.
Aplicación, migraciones, modelos y recorridos: **pendientes de S1–S6**.

Registro histórico de S0. La autorización posterior de S1 y sus decisiones están
en [ADR 002](002-base-ejecutable-s1.md) y [Estado S1](../planning/Estado_Sprint_1.md).
Las versiones y archivos de bloqueo de este ADR se conservan. S2 se completa en
[ADR 003](003-importacion-s2.md) con OpenAPI 0.1.2; S3–S6 siguen pendientes.

## Contexto y decisiones

Seguimiento Escolar empieza desde cero. Esta autorización comprende solo S0:
entorno, estructura, versiones, contratos y aceptación. No cambia metodología,
población ni fechas del estudio; no carga datos reales ni inicia Sprint 1.

Monorepo con frontend, backend, docs, infra y tests. React presenta datos; FastAPI
resuelve permisos y transacciones; solo backend accede a PostgreSQL y artefactos.
Separar rutas, esquemas, servicios y repositorios; ML reside en app/ml. Los .gitkeep
son reservas de carpetas. Compose tiene `services: {}` hasta S1; los comandos Make
futuros fallan expresamente. Make es opcional y no está instalado en este Windows.

| Runtime objetivo | Versión / tag previsto para S1 |
|---|---|
| Node / npm | 24.14.1 / 11.20.0; node:24.14.1-bookworm-slim |
| Python | 3.12.12; python:3.12.12-slim-bookworm |
| PostgreSQL | 17.6; postgres:17.6-bookworm |
| Compose | Especificación sin campo version; CLI local 5.5.1 |

Se mantienen Python 3.12 y PostgreSQL 17 del plan. No usar tags latest. Los tags
exactos son objetivos; S1 verificará publicación/digests, instalación Linux y
arranque. No se descargaron imágenes en S0. Python local 3.12.0 cumple los mínimos
de dependencias, pero no demuestra haber probado 3.12.12. Actualizar ese parche al
preparar S1 o usar la imagen fijada. `.node-version` y `.python-version` fijan objetivos.

| Dependencia frontend | Versión exacta |
|---|---|
| React / React DOM | 19.3.0 / 19.3.0 |
| TypeScript | 5.9.3 |
| Vite / @vitejs/plugin-react | 8.3.2 / 6.1.1 |
| Tailwind / @tailwindcss/vite | 4.3.3 / 4.3.3 |
| @tanstack/react-query | 5.104.1 |
| react-hook-form / @hookform/resolvers | 7.89.0 / 5.9.1 |
| Zod | 4.6.5 |
| @types/react / @types/react-dom / @types/node | 19.3.0 / 19.3.0 / 24.13.6 |
| openapi-typescript | 7.13.0 |
| @playwright/test (raíz) | 1.63.0 |

Vite/plugin React requieren Node `^20.19.0 || >=22.12.0`; el plugin exige Vite 8 y
Tailwind Vite admite Vite 8. React DOM requiere React 19.3; formularios/consultas
admiten React 19. openapi-typescript requiere TypeScript 5.x: fijar 5.9.3 aunque
exista otra major. El registro npm descartó resolvers 5.3.0 (ETARGET); se corrigió
a 5.9.1 antes de generar el lock. No usar --legacy-peer-deps.

| Dependencia Python | Versión exacta |
|---|---|
| FastAPI / Pydantic | 0.142.2 / 2.13.5 |
| Uvicorn / pydantic-settings | 0.54.0 / 2.15.0 |
| SQLAlchemy / Alembic | 2.0.54 / 1.20.0 |
| psycopg[binary] | 3.3.6 |
| python-multipart / email-validator | 0.0.32 / 2.3.0 |
| pwdlib[argon2] / argon2-cffi | 0.3.1 / 25.1.0 |
| tzdata | 2026.5 |
| pandas / NumPy / SciPy | 3.0.6 / 2.5.3 / 1.18.1 |
| scikit-learn / joblib | 1.9.1 / 1.6.0 |
| pytest / HTTPX (desarrollo) | 9.1.1 / 0.28.1 |
| pip / pip-tools (solo preparación) | 25.2 / 7.5.1 |
| PyYAML / openapi-spec-validator / pglast (S0) | 6.0.2 / 0.7.2 / 7.7 |

NumPy/SciPy fijados requieren Python >=3.12; pandas/scikit-learn >=3.11. La resolución
real se realizó con Python 3.12. SQLAlchemy usa `postgresql+psycopg://`, acceso
síncrono para la demo acotada. psycopg declara PostgreSQL 10–18; 17 es compatible.
tzdata permite ZoneInfo America/Lima en Windows. Entrenamiento local fuera de HTTP:
DummyClassifier y Random Forest; SVM/XGBoost se implementarán en fase institucional.
No servicios de IA pagados, Kubernetes, broker ni integraciones.

`package-lock.json` bloquea los workspaces raíz/frontend. requirements.txt bloquea
runtime+ML y requirements-dev.txt añade pruebas con las mismas restricciones.
infra/requirements-s0.txt separa validación documental. Los locks Python incluyen
hashes y se resolvieron en Windows: S1 comprobará instalación Linux y ajustará
dependencias condicionales si hace falta. El lock S0 incluye pip/empaquetado con
--allow-unsafe para instalar con --require-hashes. No se versionan entornos, secretos,
datos, importaciones ni artefactos. No se instalaron dependencias de aplicación.

## Contrato, seguridad e integridad

OpenAPI **0.1.1** es fuente de tipos frontend, generados al iniciar integración.
El SQL revisado tiene 13 tablas y se convertirá a Alembic en S1 sin ejecutar scripts
destructivos. Campos, proyecciones, fechas, roles y diferencias se documentan en
`../planning/Conciliacion_SQL_API.md`; seis tablas de investigación quedan fuera.

Proxy de mismo origen desde S1. Sesión HttpOnly/SameSite y Secure con HTTPS,
digests de tokens en servidor, CSRF por HMAC y Origin en login. Roles desde sesión
y sección desde matrícula, sin confiar en navegador. Credenciales demo se crearán
explícitamente en S1, fuera de Git, sin valores de producción en archivos de ejemplo.
Propietario de migraciones separado del usuario de aplicación sin DDL ni borrado
de evidencias. Es especificación de acceso, no permisos comprobados en una base.

Eventos UTC; calendario e interfaz America/Lima. Escrituras académicas de periodos
bloqueados rechazadas. Revisiones y evidencias inmutables, idempotencia,
expected_version/expected_preview_version y auditoría transaccional. REAL se rechaza
con REAL_MODE_NOT_READY; cambiar .env no lo habilita.

Interfaz interna acordada para S3: `predict_snapshot(snapshot, model_metadata)` recibe
Snapshot validado y modelo compatible del mismo origen. Resultado tipado EVALUATED
con LOW/MEDIUM/HIGH y probabilidades opcionales, o INSUFFICIENT_DATA sin riesgo.
Las seis variables disponibles al corte son la propuesta demo; no recibe etiquetas,
códigos, sección, predicciones previas ni intervenciones como features. Edad/grado
requieren justificación institucional. Solo se persisten predicciones evaluadas.
Esta decisión aún no contiene código ni valida un modelo.

## Fuentes y límites

Consulta de metadatos exactos en registry.npmjs.org y resolución npm/pip real.
Fuentes primarias: [Vite](https://vite.dev/guide/),
[openapi-typescript](https://raw.githubusercontent.com/openapi-ts/openapi-typescript/main/packages/openapi-typescript/package.json),
[Tailwind Vite](https://tailwindcss.com/docs/installation/using-vite),
[FastAPI 0.142.2](https://pypi.org/project/fastapi/0.142.2/),
[Pydantic 2.13.5](https://pypi.org/project/pydantic/2.13.5/),
[NumPy 2.5.3](https://pypi.org/project/numpy/2.5.3/),
[SciPy 1.18.1](https://pypi.org/project/scipy/1.18.1/),
[psycopg](https://www.psycopg.org/psycopg3/docs/basic/install.html),
[SQLAlchemy psycopg](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg),
[zoneinfo](https://docs.python.org/3.12/library/zoneinfo.html).

El análisis SQL no ejecuta restricciones ni valida cuerpos PL/pgSQL: pglast los
trata como texto. La resolución no sustituye instalación del backend, build,
migración o pruebas funcionales. Evidencia y pendientes en Estado_Sprint_0.md.
