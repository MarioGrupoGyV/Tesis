# Infraestructura Windows / Docker Desktop — S5

El operador usa PowerShell y Docker Desktop. Los Dockerfiles y `db/init-app-role.sh`
son componentes Linux internos de Docker; no se exige Bash, WSL ni Make en Windows.
Se conservan versiones, hashes/locks, puertos y volúmenes del proyecto
`riesgo-escolar`: DB `riesgo_escolar`, secretos privados `.local/runtime-secrets`,
`db_data`, `import_data` y `ml_data`. Puertos por defecto locales: web 15173,
API 18000 y PostgreSQL 55432. Las cuatro cuentas/credenciales Windows S2.2 se
conservan sin regeneración, restablecimiento ni semillas de arranque.

Contrato vigente **0.5.0**, **27 operaciones en 26 paths**, **15 tablas** tras
`0004_followup`. `0001`–`0003` permanecen intactas. La nueva migración agrega
evidencia mínima de decisiones por predicción y clave/digest original de creación
de actividades; mantiene tablas existentes y controles de integridad. La ejecución
usa `riesgo_app`; `compose.migrate.yaml` presta el propietario únicamente a Alembic.
No ejecutar `Esquema.sql` ni autogeneración sobre metadata para actualizar la DB.

## Actualizar y operar la instalación existente

Desde la raíz del repositorio:

```powershell
docker compose build api web
py -3.12 infra/manage.py migrate
docker compose up -d --wait api web
docker compose ps
docker compose exec -T api python -m pip check
```

`manage.py prepare/up/migrate/restart/down` mantiene una acción por llamada.
`prepare` conserva secretos completos existentes; `up` prepara, compila, migra y
arranca. `restart` reinicia sin semillas; `down` detiene sin borrar volúmenes.
`bootstrap-admin` y `configure` son herramientas interactivas de preparación
explícita, no parte de la actualización de estas cuatro cuentas existentes.

S5 incorpora seguimiento SYNTHETIC mediante ADMIN y cuentas autorizadas, con
CSRF/versiones y auditoría atómica. Sincronizar incorpora las predicciones
existentes sin reentrenar. `predictions/run` confirma inferencia, seguimiento y
auditoría juntos. Reportes/CSV aplican alcance del servidor; REAL permanece bloqueado.
Consulte [backend/README](../backend/README.md),
[ADR 008](../docs/adr/008-seguimiento-reportes-s5.md) y
[manual S5](../docs/manuals/Manual_Seguimiento_Reportes_S5.md).

## Suite y recorrido aislados S5

Usar un sufijo nuevo en cada revisión. Los ejemplos generan un sello para evitar
sobrescribir informes previos; si dos ejecuciones ocurren en el mismo segundo,
elegir otro sufijo. Las credenciales de prueba solo viven en memoria/entorno del
proceso hijo; no se publican en argumentos, capturas ni informes.

```powershell
$s5Revision = Get-Date -Format 'yyyyMMdd-HHmmss'
$env:TEST_REPORT_NAME = "s5-backend-$s5Revision"
docker compose -f infra/compose.test.yaml build tester
docker compose -f infra/compose.test.yaml run --rm tester

$env:BROWSER_REPORT_PREFIX = "s5-isolated-$s5Revision"
py -3.12 infra/test_s5_browser.py
```

`run_backend_tests.py` exige Linux/Python 3.12.12 dentro de Docker, crea una nueva
DB PostgreSQL de prueba y migra a head antes de pytest; conserva bases anteriores.
`test_s5_browser.py` crea otra DB aislada y cuatro cuentas efímeras. Allí, y solo
allí, prepara/importa el CSV registrado y compara/registra/activa un modelo de
fixture. El navegador recorre importar → evaluar → alertas → planificar → realizar/
cancelar → cerrar → resumen → CSV contra API/PostgreSQL reales. La web de prueba
usa 15174 y almacenamiento privado propio `browser_imports`/`browser_ml`.
El runner detiene aquellos servicios al finalizar. Sus resultados no son métricas
escolares ni modifican el estudio activo.

## Revisión activa y persistencia

La revisión activa es una operación explícita con efectos de simulación:
sincroniza seguimiento y registra el mínimo previsto de dos actividades
(DONE/CANCELLED) y un caso concluido, o comprueba sus recursos ya existentes.
Sus acciones se conservan junto con auditoría. No regenera ni reentrena; verifica
las cuatro cuentas y preserva estudiantes/cortes/modelo/predicciones/archivos
anteriores. IDs del estudio y periodo actuales:

```powershell
$env:REVIEW_REPORT_PREFIX = "s5-active-$s5Revision"
py -3.12 infra/review_s5.py `
  --study-id e3a2d28b-2f23-56ae-878c-1a8f4a257e7e `
  --period-id c036cbcb-87db-5ed0-bcfa-bbd644928ccb

$env:PERSISTENCE_REPORT_PREFIX = "s5-$s5Revision"
py -3.12 infra/check_access_persistence.py
```

Persistencia recrea contenedores con `down/up`, **sin `-v`**. Compara las 15 tablas
y archivos justo después de recrear; después comprueba login/logout/revocación de
los cuatro roles. Conserva cuentas, contraseñas, auditoría y seguimiento. No usar
`check_runtime.py` sobre esta instalación poblada: su comprobación es exclusivamente
para una instalación todavía vacía.

## Contrato, tipos, build y cierre

```powershell
py -3.12 infra/sync_followup_contract.py
npm run generate:api --workspace frontend
npm run typecheck --workspace frontend
npm run build --workspace frontend
.\.venv-s0\Scripts\python.exe -X utf8 infra/check_s0.py
git diff --check
```

El generador utiliza los esquemas del código y la imagen API; actualiza el contrato
revisado, no crea rutas ficticias. `check_s0.py` valida contrato/tipos/SQL/Compose/
locks actuales y escribe `s5-contracts.json`; no sustituye pruebas de ejecución.
`check_s5.py` contrasta conservación del baseline privado S5, evidencia backend,
navegador, contrato, persistencia, dependencias, volúmenes, respaldos y entorno
histórico detenido. Es un cierre coordinado sobre la base poblada:

```powershell
.\.venv-s0\Scripts\python.exe -X utf8 infra/check_s5.py `
  --backend-prefix $env:TEST_REPORT_NAME `
  --isolated-prefix $env:BROWSER_REPORT_PREFIX `
  --active-prefix $env:REVIEW_REPORT_PREFIX
```

El checker requiere además el conjunto documental de cierre vigente y los informes
`s5-persistence.json`, `s5-build.json`, `s5-contracts.json`, `s5-response-samples.json`;
escribe `s5-review.json`. El ejemplo de persistencia con sello genera otra evidencia
y no reemplaza por sí solo ese informe de cierre. Antes de repetir herramientas que
escriben un nombre fijo, conservar la evidencia ya cerrada y coordinar un nuevo
paquete/prefijo; no presentar un informe histórico como resultado de la nueva
ejecución. Los resultados comprobados/fallidos/no ejecutados se registran en
[Estado S5](../docs/planning/Estado_Sprint_5.md) y su matriz.

## Herramientas y evidencias históricas

`review_accounts.py` creó explícitamente las cuentas S2.2; no repetir sobre esta
instalación. `windows_credentials.py` permite consultarlas en una ventana privada.
`review_endpoints.py`/`check_review.py` preservan la revisión histórica de bloqueo;
`review_s3.py`/`check_s3.py` esperan modelos/listas vacías del cierre S3. No son el
checker del estudio poblado actual. `history/archive_s2.py` documenta el respaldo
previo y se niega a operar sobre Compose actual. Respaldos, secretos y evidencias
S0–S4 se conservan.

S3 añadió `ml_data` privado en `/var/lib/riesgo/ml` y xgboost-cpu 3.4.1 con hashes.
`ml.py readiness/configuration/compatibility` conserva consultas técnicas y `train`
institucional sigue rechazado. S3.1 conserva `study.py generate/import/compare/
register/activate/run/status` con ADMIN explícito; no repetir generación/comparación/
registro/activación sobre el estudio activo para comprobar S5. S4 conserva
`study.py export-csv`, hash verificado y destino privado fuera de Git sin overwrite.

`review_study.py`/`check_study.py` y `sync_study_contract.py` pertenecen al cierre
0.4.0 de S3.1; `test_browser.py`/`review_browser.py`/`check_s4.py` pertenecen al cierre
S4, que tenía cero alertas/intervenciones. Conservar sus informes y comandos como
históricos; S5 usa los runners/checker indicados arriba. El manual del estudio
documenta protocolo/hashes/límites; S6, restauración final integrada y revisión
académica permanecen pendientes.
