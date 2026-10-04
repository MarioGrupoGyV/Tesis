# Seguimiento Escolar

**S3: infraestructura predictiva con pruebas aisladas en Windows y Docker.** Se conservan
las cuatro cuentas de S2.2; sin registros escolares ni semillas al arrancar.
Importación, entrenamiento, inferencia y activación institucional siguen bloqueados.
No existe un modelo operativo ni evaluación de la tesis. S4–S6 siguen pendientes.

## Preparación y operación

El anfitrión es Windows. Docker Desktop ejecuta contenedores Linux internamente;
no necesitas instalar una distribución, abrir WSL, usar Bash ni instalar GNU Make.
Se conservan Python 3.12.12, PostgreSQL 17.6, Node 24.14.1 y npm 11.20.0 de las imágenes.
El launcher local `py -3.12` orquesta Docker; las pruebas backend no son ejecución nativa Windows.

Desde la raíz en PowerShell:

```powershell
py -3.12 infra/manage.py prepare
py -3.12 infra/manage.py up
docker compose ps
```

`prepare` genera únicamente cinco secretos de infraestructura en `.local/runtime-secrets`,
fuera de Git. No crea usuarios ni contexto. `up` construye, migra con propietario en
un contenedor temporal y arranca web/api/db. La API utiliza exclusivamente riesgo_app.

Abrir http://localhost:15173. Puertos 15173/18000/55432 ligados a 127.0.0.1.
El proyecto es `riesgo-escolar`; base `riesgo_escolar`; volúmenes
`riesgo-escolar_db_data`, `riesgo-escolar_import_data` y `riesgo-escolar_ml_data`. CSV privado en
`/var/lib/riesgo/imports`, fuera del checkout y sin URL pública.

## Primer administrador

En tu terminal PowerShell interactiva:

```powershell
py -3.12 infra/manage.py bootstrap-admin
```

Introduce tu correo, nombre y una contraseña de al menos 12 caracteres, dos veces.
La contraseña no se muestra, no se escribe en archivos y no se pasa por argumentos.
No existen valores predeterminados. La cuenta y auditoría se guardan juntas.
Repetir el comando rechaza la creación si ya existe un administrador, incluso inactivo;
no restablece contraseñas. No hay registro público.

El bootstrap anterior corresponde a instalaciones nuevas sin administrador. En este
entorno S2.2 ya existe uno: no vuelvas a crearlo ni restablezcas su contraseña.

## Acceso local de revisión S2.2

Abrir http://localhost:15173. Cuentas locales autorizadas, sin identidad de colegio:

| Rol | Correo |
|---|---|
| ADMIN | revision.local.admin@example.com |
| TUTOR | revision.local.tutor@example.com |
| DIRECTOR | revision.local.director@example.com |
| RESEARCHER | revision.local.researcher@example.com |

Las contraseñas distintas y aleatorias están en el Administrador de credenciales
de Windows del usuario que ejecutó la preparación, entradas genéricas
`SeguimientoEscolar/S2.2/<ROL>`. Para consultarlas en una ventana local, inicialmente
ocultas, usa PowerShell desde este repositorio (sustituye ADMIN por el rol):

```powershell
py -3.12 infra/windows_credentials.py ADMIN
```

No se envían correos ni se guardan contraseñas en archivos de cuentas. La herramienta
explícita `infra/review_accounts.py` crea/reutiliza solo estas cuentas mediante los
servicios existentes; nunca se ejecuta al arrancar. Si encuentra un administrador
sin credencial autorizada disponible, se detiene y conserva su identidad. La revisión
no configura periodos/secciones ni habilita importación. Detalles y resultados en
[Estado S2.2](docs/planning/Estado_Sprint_2_2.md) y su [matriz](docs/planning/Matriz_verificacion_S2_2.md).

Para crear posteriormente un usuario autorizado, periodo o sección:

```powershell
py -3.12 infra/manage.py configure
```

Se autentica un administrador y el operador elige `usuario`, `periodo` o `seccion`.
Todos los valores proceden del operador; no se inventan calendarios ni tutores.
Se rechazan duplicados y se audita en la misma transacción. Crear contexto no autoriza
importación. Las escalas y requisitos institucionales deben acordarse antes de habilitarla.

```powershell
py -3.12 infra/manage.py migrate
py -3.12 infra/manage.py restart
py -3.12 infra/manage.py down
py -3.12 infra/manage.py up
```

`down` conserva los tres volúmenes. Conservar también los secretos. No usar `down -v`.
No hay semillas en el arranque o reinicio. Los scripts internos de PostgreSQL y las
rutas Linux pertenecen a Docker, no son instrucciones para la consola del usuario.

## Comprobaciones desde PowerShell

```powershell
$env:TEST_REPORT_NAME = 's3-backend'
docker compose -f infra/compose.test.yaml build tester
docker compose -f infra/compose.test.yaml run --rm tester
$env:BROWSER_REPORT_PREFIX = 's3'
py -3.12 infra/test_browser.py
py -3.12 -m venv .venv-s0
.\.venv-s0\Scripts\python.exe -m pip install --require-hashes -r infra/requirements-s0.txt
.\.venv-s0\Scripts\python.exe infra/check_s0.py
npm ci --ignore-scripts --no-audit --no-fund
npm run generate:api --workspace frontend
npm run build --workspace frontend
git diff --check
```

Las pruebas backend usan una base nueva `riesgo_escolar_test_<id>` en otro proyecto
Compose sin puerto de base publicado. Conservan sesiones, atomicidad, concurrencia,
revisiones, fechas, permisos e idempotencia. La política bloqueada se sustituye
**solo mediante monkeypatch de pytest** para comprobar el motor; no existe interruptor
operativo. Las filas fabricadas son fixtures aislados, no datos institucionales.

El runner de navegador necesita Chromium de Playwright instalado (`npx playwright
install chromium` si falta), usa puerto 15174 y otra base nueva. No guarda la contraseña
de prueba en archivos y no toca la aplicación activa. Comprueba teclado, acceso,
contexto vacío y revocación en escritorio, tablet y móvil.

`py -3.12 infra/check_runtime.py` comprueba únicamente una aplicación todavía vacía,
recrea contenedores y conserva un marcador de infraestructura en el volumen. Rechaza
ejecutarse si ya hay registros; no borra ni inventa datos para que pase.

Con las cuentas actuales usa `py -3.12 infra/check_access_persistence.py`: captura
el estado, recrea sin eliminar volúmenes y verifica cuentas, roles, auditoría,
archivos y acceso. `py -3.12 infra/review_endpoints.py` revisa las 14 rutas activas;
`py -3.12 infra/review_browser.py` revisa los cuatro roles en localhost usando el
almacén privado. No ejecutar revisiones de login repetidamente: el límite vigente
es 10 intentos por IP cada 300 segundos y también cuenta accesos correctos.

## Contrato, conservación y límites

Contrato vigente [OpenAPI 0.3.0](docs/planning/Contrato_API.yaml), con solo rutas
implementadas. [Esquema](docs/planning/Esquema.sql) es referencia; aplicar Alembic,
nunca ejecutar manualmente ese SQL. La migración 0001 y su snapshot permanecen intactos;
0002 añade restricciones institucionales sin transformar registros anteriores.

POST de importación exige ADMIN/CSRF y devuelve 422
`INSTITUTIONAL_PROCESSING_NOT_READY`, sin guardar archivos ni filas académicas.
Contexto vacío es consultable. Se conservan 409 de integridad y 503 Error sanitizado;
health/ready mantiene Health. Sin modelo válido no existe riesgo calculado.

El entorno anterior permanece detenido, con sus volúmenes y secretos conservados.
Su respaldo privado restaurado es historia, no un modo de la aplicación:
[Estado S2.1](docs/planning/Estado_Sprint_2_1.md) registra ubicación y comprobación.
Los cierres S0/S1/S2 conservan hechos históricos; no deben usarse como guía operativa.

Véanse [ADR de transición](docs/adr/004-transicion-windows.md),
[criterios](docs/planning/Sprints_y_aceptacion.md) y [plan](docs/planning/Plan_tesis_riesgo_escolar.md).
No se realizaron push ni despliegues externos. HTTPS, protocolo de datos y validación
institucional permanecen pendientes; la demo anterior se retiró del producto.

## Infraestructura predictiva S3

Núcleo con dataset/manifiesto versionados, validación temporal, Pipeline y particiones
por estudiante para Dummy, Random Forest, SVM y XGBoost CPU 3.4.1. Edad/grado requieren
justificación; escalas, criterio y política de faltantes son explícitos. No se activa
un ganador ni se presentan probabilidades sin calibración. Los artefactos internos
van a `/var/lib/riesgo/ml`, privado y fuera del checkout; en activo permanece vacío.

Rutas nuevas: `GET /api/v1/models`, `GET /api/v1/models/{id}` (ADMIN),
`POST /api/v1/predictions/run` (ADMIN/CSRF, bloqueado por protocolo) y
`GET /api/v1/predictions/{id}` (ADMIN/TUTOR/DIRECTOR, alcance por sección).
Sin entrenamiento HTTP, activación ni nuevas pantallas.

```powershell
py -3.12 infra/ml.py readiness
py -3.12 infra/ml.py configuration
py -3.12 infra/ml.py compatibility
py -3.12 infra/ml.py train  # Rechazo esperado, código de salida 2
py -3.12 infra/review_s3.py
$env:REVIEW_REPORT_PREFIX = 's3-active'
py -3.12 infra/review_browser.py
$env:PERSISTENCE_REPORT_PREFIX = 's3'
py -3.12 infra/check_access_persistence.py
.\.venv-s0\Scripts\python.exe infra/check_s3.py
```

`check_s3.py` es el cierre de esta revisión y necesita su captura privada previa
`.local/s3-before.json` y evidencias generadas. No crea cuentas. Los reportes antiguos
S2.2 permanecen intactos; utiliza prefijos nuevos para revisiones posteriores.
Detalle de esquema, límites, confianza de artefactos y comandos en el
[manual ML](docs/manuals/ML_S3.md), [ADR 005](docs/adr/005-infraestructura-ml-s3.md)
y [Estado S3](docs/planning/Estado_Sprint_3.md).
