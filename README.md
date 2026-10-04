# Seguimiento Escolar

**S2.1: Windows con PowerShell y Docker Desktop.** Sin cuentas ni registros escolares precargados.
La importación institucional permanece bloqueada. No es una habilitación de producción
ni una evaluación de la tesis. S3–S6 no están implementados.

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
`riesgo-escolar_db_data` y `riesgo-escolar_import_data`. CSV privado en
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

El entorno entregado sigue sin cuentas: el operador debe introducir sus datos.
Las pruebas de acceso usan cuentas efímeras únicamente en PostgreSQL aislado.

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

`down` conserva ambos volúmenes. Conservar también los secretos. No usar `down -v`.
No hay semillas en el arranque o reinicio. Los scripts internos de PostgreSQL y las
rutas Linux pertenecen a Docker, no son instrucciones para la consola del usuario.

## Comprobaciones desde PowerShell

```powershell
docker compose -f infra/compose.test.yaml build tester
docker compose -f infra/compose.test.yaml run --rm tester
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

## Contrato, conservación y límites

Contrato vigente [OpenAPI 0.2.0](docs/planning/Contrato_API.yaml), con solo rutas
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
