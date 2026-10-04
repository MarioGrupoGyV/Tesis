# Seguimiento Escolar — tesis de riesgo escolar

**S1: base ejecutable DEMO con datos sintéticos. S2–S6 pendientes.**

Compose ejecuta web, API y PostgreSQL. S1 incluye salud, acceso, sesión, CSRF,
periodos y secciones autorizadas. La semilla crea tres cuentas, un periodo y dos
secciones; no crea estudiantes. Importación, predicción, alertas, intervenciones y
reportes pertenecen a los siguientes sprints. No cargar datos reales.

## Documentación

- [Instrucciones](AGENTS.md) y [plan](docs/planning/Plan_tesis_riesgo_escolar.md).
- [Arquitectura y versiones S0](docs/adr/001-arquitectura.md) y [decisiones S1](docs/adr/002-base-ejecutable-s1.md).
- [Conciliación SQL/API](docs/planning/Conciliacion_SQL_API.md), [API 0.1.1](docs/planning/Contrato_API_demo.yaml) y [SQL de diseño](docs/planning/Esquema_demo.sql).
- [Criterios S1–S6](docs/planning/Sprints_y_aceptacion.md), [cierre S0](docs/planning/Estado_Sprint_0.md) y [resultados S1](docs/planning/Estado_Sprint_1.md).

## Requisitos

Docker y Compose con contenedores Linux; Python 3.12 para los comandos de preparación.
En este Windows funcionan Docker 29.7.2, Compose 5.5.1 y `py -3.12` (3.12.0).
La API usa Python **3.12.12** en Docker, la base PostgreSQL **17.6**, y web Node
**24.14.1** / npm **11.20.0**. Los locks de S0 se conservan.

Para desarrollar y comprobar el frontend también se necesita Node 24.14.1 y npm
11.20.0 locales. Git 2.47.0 está disponible. Make es opcional y no está instalado.
`python` global usa 3.11.9: utilizar el launcher explícito para crear los entornos.

## Arranque en PowerShell

Desde la raíz, con Docker Desktop iniciado y acceso a los registros de imágenes y
dependencias en el primer arranque:

```powershell
py -3.12 infra/s1.py up
py -3.12 infra/s1.py seed-demo
docker compose ps
```

`up` prepara secretos aleatorios si no existen, construye las imágenes, inicia la
base, aplica Alembic y espera la salud de API y web. `seed-demo` es explícito e
idempotente. Reiniciar no ejecuta la semilla.

Abrir **http://localhost:15173**. Las cuentas son administrador, tutor y directivo;
sus correos y contraseñas de demostración están en `.local/secrets/demo-credentials.json`.
Consultar ese archivo local para ingresar. No publicarlo ni incorporarlo a Git.
No hay contraseña fija, registro público ni contraseña de producción.

Puertos del host: web **15173**, API **18000**, PostgreSQL **55432**, todos ligados a
127.0.0.1 para esta demo. La web llama `/api/v1` por proxy de mismo origen.
`.env.example` contiene opciones públicas, sin secretos; puede copiarse a `.env`.
Al cambiar puertos, actualizar también `ALLOWED_ORIGINS`. Para los scripts de
pruebas, proporcionar `DB_PORT`, `S1_BASE_URL` y `DEMO_CREDENTIALS_FILE` como variables
de entorno si se usan valores distintos de los documentados.
La preparación automática usa `.local/secrets`; una ubicación alternativa de Compose
requiere disponer allí de los mismos seis archivos privados.

```powershell
py -3.12 infra/s1.py migrate
py -3.12 infra/s1.py restart
py -3.12 infra/s1.py down
py -3.12 infra/s1.py up
```

`down` conserva `riesgo-escolar-demo_db_data`. Conservar también los archivos de
secretos para mantener el acceso a esos datos. Las credenciales existentes no se
reemplazan; una configuración incompleta requiere revisión.
La migración se aplica con una credencial de propietario en un contenedor temporal;
la API normal usa un rol sin DDL ni borrado de evidencias.

## Comprobaciones

Los resultados ejecutados y sus límites están en [Estado S1](docs/planning/Estado_Sprint_1.md).
Para repetirlos, instalar los locks sin regenerarlos:

```powershell
py -3.12 -m venv .venv-s0
.\.venv-s0\Scripts\python.exe -m pip install --require-hashes -r infra/requirements-s0.txt
.\.venv-s0\Scripts\python.exe infra/check_s0.py
py -3.12 -m venv .venv-s1
.\.venv-s1\Scripts\python.exe -m pip install --require-hashes -r backend/requirements-dev.txt
.\.venv-s1\Scripts\python.exe -m pip check
.\.venv-s1\Scripts\python.exe infra/test_s1.py prepare-db
.\.venv-s1\Scripts\python.exe infra/test_s1.py pytest
npm ci --ignore-scripts --no-audit --no-fund
npm run generate:api --workspace frontend
npm run build --workspace frontend
npx playwright install chromium
$env:DEMO_CREDENTIALS_FILE = (Resolve-Path .local/secrets/demo-credentials.json).Path
npx playwright test
.\.venv-s1\Scripts\python.exe infra/smoke_s1.py
```

`check_s0.py` conserva las validaciones documentales y comprueba Compose S1; no
sustituye las pruebas funcionales. `prepare-db` crea/migra una base de prueba aislada
`riesgo_escolar_demo_s1_test`, sin borrar la demo. Las pruebas backend usan rollback.
`smoke_s1.py` comprueba HTTP real y detiene/recrea los tres servicios sin eliminar
el volumen; ejecutarlo sin otros recorridos en curso. Compara cantidades y hashes
de las 13 tablas, prueba sesiones conservadas y luego las revoca.

En Codex, Docker y algunas herramientas nativas requieren ejecutar fuera de la
restricción de consola; ese permiso se usó para las comprobaciones registradas.
GNU Make ofrece `up`, `migrate`, `seed-demo`, `restart`, `down`, `test` y `check-s0`
como equivalentes, indicando `PYTHON` del entorno adecuado. `train-demo`, `demo` y
`backup` siguen pendientes de sus sprints.

## Estructura y límites

```text
frontend/src/{app,components,lib,features/{auth,dashboard,students,imports,alerts,reports,models}}
backend/app/{api/v1,core,models,schemas,repositories,services,ml/{features,train,evaluate,predict}}
backend/{migrations/versions,tests}
docs/{planning,research,adr,manuals}
infra/{docker,db}
tests/{e2e,evidence}
```

Los originales y las evidencias S0 se conservan. El contrato vigente sigue siendo
0.1.1; los tipos frontend se generan desde él. Alembic contiene una copia congelada
del SQL revisado, no se ejecuta el documento de planificación directamente. S1 usa
cinco entidades ORM; las ocho restantes solo existen en la migración, sin módulos
de negocio. No usar autogeneración sobre ese ORM parcial.

La sesión usa cookie HttpOnly/SameSite y digests en servidor; CSRF permanece en
memoria del navegador. La demo local HTTP usa `Secure=false`; HTTPS exige
`SESSION_COOKIE_SECURE=true` y orígenes explícitos. REAL permanece bloqueado y no
se habilita cambiando una variable. No hay datos de menores ni modelo entrenado.
