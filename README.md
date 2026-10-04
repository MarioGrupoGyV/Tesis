# Seguimiento Escolar

**S5: Alertas, intervenciones y Reportes conectados a API/PostgreSQL.**
El seguimiento pertenece al Estudio con datos sintéticos registrado. Conserva las
cuatro cuentas S2.2, sus credenciales privadas, el modelo y las predicciones previas.
No regenera ni reentrena el estudio activo. REAL sigue bloqueado; no hay resultados
escolares ni hipótesis validada. S6 y la revisión académica quedan pendientes.

Consultar [manual de seguimiento y reportes](docs/manuals/Manual_Seguimiento_Reportes_S5.md),
[ADR 008](docs/adr/008-seguimiento-reportes-s5.md),
[cierre S5](docs/planning/Estado_Sprint_5.md) y
[matriz S5](docs/planning/Matriz_verificacion_S5.md).
La preparación y simulación previa se documentan en el
[manual del estudio](docs/manuals/Manual_Estudio_Sintetico.md).

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

No se envían correos ni se guardan contraseñas en archivos de cuentas. La preparación
explícita S2.2 utilizó `infra/review_accounts.py` mediante los servicios existentes;
nunca se ejecuta al arrancar. Conserva las cuatro cuentas actuales y sus credenciales;
no repitas su preparación en S3.1. Esa revisión no configuró periodos/secciones ni
habilitó importación. Detalles y resultados históricos en
[Estado S2.2](docs/planning/Estado_Sprint_2_2.md) y su [matriz](docs/planning/Matriz_verificacion_S2_2.md).

Para crear posteriormente un usuario autorizado, periodo o sección:

```powershell
py -3.12 infra/manage.py configure
```

Se autentica un administrador y el operador elige `usuario`, `periodo` o `seccion`.
Todos los valores proceden del operador; no se inventan calendarios ni tutores.
Se rechazan duplicados y se audita en la misma transacción. Crear contexto REAL no
autoriza importación institucional. El contexto SYNTHETIC se prepara exclusivamente
con `infra/study.py generate`, según el [manual del estudio](docs/manuals/Manual_Estudio_Sintetico.md).

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

Estos comandos utilizan prefijos nuevos. Sustituye `s5-nueva` por un sello distinto
para cada ejecución, conserva los reportes existentes y ejecuta desde la raíz:

```powershell
$env:TEST_REPORT_NAME = 's5-nueva-backend'
docker compose -f infra/compose.test.yaml build tester
docker compose -f infra/compose.test.yaml run --rm tester
$env:BROWSER_REPORT_PREFIX = 's5-nueva-aislado'
py -3.12 infra/test_s5_browser.py
npm run generate:api --workspace frontend
npm run typecheck --workspace frontend
npm run build --workspace frontend
.\.venv-s0\Scripts\python.exe infra/check_s0.py
docker compose exec -T api python -m pip check
git diff --check
```

Si faltan las herramientas documentales:

```powershell
py -3.12 -m venv .venv-s0
.\.venv-s0\Scripts\python.exe -m pip install --require-hashes -r infra/requirements-s0.txt
```

Las pruebas backend usan Linux/Python 3.12.12 dentro de Docker y una base nueva
`riesgo_escolar_test_<id>` de PostgreSQL aislado, sin puerto publicado. El propietario
aplica migraciones y `riesgo_app` ejecuta la aplicación. Se comprueban regresión,
integridad, versiones, rollback y concurrencia mediante locks observados en DB.
Los fixtures y artefactos de prueba no son datos ni resultados institucionales.
Las pruebas históricas del motor REAL sustituyen el bloqueo solo mediante monkeypatch
de pytest; no existe interruptor institucional operativo.

El runner de navegador necesita Chromium (`npx playwright install chromium` si falta),
puerto 15174 y otra base nueva. Comprueba CSV registrado → importar → evaluar desde
la interfaz → alertas → actividades → cerrar → resumen → CSV. Compara cuatro roles,
sección propia/ajena, 409 efectivo, teclado y tres tamaños. Las simulaciones HTTP de
fallos de UI se identifican aparte y solo se ejecutan en ese entorno aislado.

Para aplicar la versión sin recrear cuentas ni volúmenes:

```powershell
docker compose build api web
py -3.12 infra/manage.py migrate
docker compose up -d --wait api web
```

La revisión activa registra un mínimo de seguimiento **simulado** y conserva sus
acciones. No repetirla como si fuera una preparación sin efectos:

```powershell
$env:REVIEW_REPORT_PREFIX = 's5-nueva-activo'
py -3.12 infra/review_s5.py --study-id e3a2d28b-2f23-56ae-878c-1a8f4a257e7e --period-id c036cbcb-87db-5ed0-bcfa-bbd644928ccb
```

El cierre coordinado S5 usa `infra/check_s5.py` sobre la base poblada y evidencias
nuevas; su invocación exacta está en [Estado S5](docs/planning/Estado_Sprint_5.md).
`infra/check_runtime.py` es exclusivo de una aplicación vacía. Los checkers/revisores
S0–S4 conservan expectativas históricas y no se ejecutan sobre el seguimiento nuevo.
`infra/check_access_persistence.py` recrea sin borrar volúmenes y verifica las cuatro
cuentas, revocación y todas las tablas/archivos; el cierre S5 usa prefijo `s5`.
No ejecutar revisiones de login repetidamente: el límite es 10 intentos por IP cada
300 segundos, incluidos accesos correctos. Nunca usar `down -v`.

## Contrato, conservación y límites

Contrato vigente [OpenAPI 0.5.0](docs/planning/Contrato_API.yaml), con solo rutas
implementadas: 27 operaciones y 26 paths. [Esquema](docs/planning/Esquema.sql) es referencia; aplicar Alembic,
nunca ejecutar manualmente ese SQL. La migración 0001 y su snapshot permanecen intactos;
0002 añadió restricciones institucionales sin transformar registros anteriores.
0003 permite SYNTHETIC y activación técnica de simulación en un contexto separado,
conservando datos anteriores y la prohibición de activar REAL.
0004 añade decisiones inmutables de seguimiento y clave/digest original de intervención;
son 15 tablas de aplicación. 0001–0003 permanecen intactas.

POST de importación exige ADMIN/CSRF. REAL devuelve 422
`INSTITUTIONAL_PROCESSING_NOT_READY`; SYNTHETIC exige CSV exacto registrado por el
generador local. Preview/commit conservan versiones, transacción y reutilización.
`GET /api/v1/processing/status` informa preparación y permisos por operación;
institutional_ready sigue false. Se conservan 409 de integridad y 503 Error sanitizado;
health/ready mantiene Health. Sin modelo válido no existe riesgo calculado.

El entorno anterior permanece detenido, con sus volúmenes y secretos conservados.
Su respaldo privado restaurado es historia, no un modo de la aplicación:
[Estado S2.1](docs/planning/Estado_Sprint_2_1.md) registra ubicación y comprobación.
Los cierres S0/S1/S2 conservan hechos históricos; no deben usarse como guía operativa.

Véanse [ADR de transición](docs/adr/004-transicion-windows.md),
[criterios](docs/planning/Sprints_y_aceptacion.md) y [plan](docs/planning/Plan_tesis_riesgo_escolar.md).
No se realizaron push ni despliegues externos. HTTPS, protocolo de datos y validación
institucional permanecen pendientes; la demo anterior se retiró del producto.

## Núcleo S3 y simulación S3.1

Núcleo con dataset/manifiesto versionados, validación temporal, Pipeline y particiones
por estudiante para Dummy, Random Forest, SVM y XGBoost CPU 3.4.1. Edad/grado requieren
justificación; escalas, criterio y política de faltantes son explícitos. La selección
usa únicamente desarrollo; registro y activación requieren comandos ADMIN explícitos.
No se presentan probabilidades sin calibración. El estudio y los artefactos internos
van a `/var/lib/riesgo/ml`, privado, persistente y fuera del checkout.

Rutas S3 conservadas: `GET /api/v1/models`, `GET /api/v1/models/{id}` (ADMIN),
`POST /api/v1/predictions/run` (ADMIN/CSRF, simulación SYNTHETIC registrada) y
`GET /api/v1/predictions/{id}` (ADMIN/TUTOR/DIRECTOR, alcance por sección).
S3.1 añade `GET /api/v1/processing/status`, autenticado y general por rol, y el aviso
del servidor en inicio. REAL continúa bloqueado. Sin entrenamiento/activación HTTP. S4 usa estas operaciones en pantallas conectadas.

```powershell
py -3.12 infra/ml.py readiness
py -3.12 infra/ml.py configuration
py -3.12 infra/ml.py compatibility
py -3.12 infra/ml.py train  # Rechazo esperado, código de salida 2
py -3.12 infra/study.py status --admin-credential ADMIN
```

`check_study.py` contrasta la evidencia S3.1. `check_s3.py` y `.local/s3-before.json`
pertenecen al cierre histórico S3 y sus expectativas de base vacía. Los reportes
anteriores permanecen intactos; utiliza prefijos nuevos para revisiones posteriores.
El [manual del estudio](docs/manuals/Manual_Estudio_Sintetico.md) describe generación,
importación, comparación, registro y activación explícitos. El [manual ML](docs/manuals/ML_S3.md),
[ADR 005](docs/adr/005-infraestructura-ml-s3.md) y [Estado S3](docs/planning/Estado_Sprint_3.md)
conservan la infraestructura y evidencia de aquella iteración.

## Interfaz vigente

Acceso, Inicio, Estudiantes/lista/detalle/historial, Datos/importación y Modelos
se conectan al contrato 0.5.0. Usa periodo/sección autorizados, filtros y paginación
en servidor. ADMIN importa el CSV registrado y evalúa el periodo sintético; TUTOR
consulta únicamente su sección; DIRECTOR consulta su alcance; RESEARCHER conserva
inicio limitado y sesión. Alertas y Reportes están conectados: TUTOR gestiona solo
sus secciones, DIRECTOR consulta sin mutaciones y ADMIN sincroniza predicciones
existentes. La inferencia incorpora seguimiento en la misma transacción.

No regenerar ni reentrenar el estudio existente para usar la interfaz. Para obtener
su CSV de entrada y seleccionarlo en Windows, consulta el comando export-csv del
[manual de uso S4](docs/manuals/Manual_Uso_S4.md): archivo nuevo fuera de Git, hash
verificado, sin sobrescritura ni descarga HTTP. Las escalas y fechas son supuestos
de synthetic-study-v1. El instante actual de evaluación se usa con zona explícita,
no se retrofecha al calendario simulado. La hora actual procede de la API local
(HTTP Date y tiempo monótono), con precisión de segundos; la fecha manual conserva
el instante solicitado en Lima y el servidor valida que no esté en el futuro.

[ADR 007](docs/adr/007-interfaz-s4.md), [matriz S4](docs/planning/Matriz_verificacion_S4.md)
y [Estado S4](docs/planning/Estado_Sprint_4.md) registran alcance y comprobaciones.
Solo infraestructura/simulación comprobadas; no tratamiento REAL ni tesis validada.

## Seguimiento y reportes S5

`followup-policy-v1` crea o actualiza un único caso activo ante MEDIUM/HIGH. LOW
conserva el caso previo para revisión humana; sin caso registra que no requiere
alerta. Sin evaluación actual muestra información pendiente. Repetir la predicción
reutiliza su decisión, incluso después de cerrar el caso; nunca reabre automáticamente.

Las ediciones exigen versión. Ante 409 se conserva el borrador y es obligatorio revisar
el recurso actualizado. Las actividades comienzan planificadas; realizarlas requiere
fecha efectiva explícita. Concluir un caso no completa actividades ni demuestra
mejoría académica. Toda acción descrita aquí es simulación interna, sin comunicaciones.

Reportes cuenta una matrícula por estado actual, sobre todo el alcance autorizado.
El riesgo solo incluye evaluados; los porcentajes muestran denominador y son null
cuando es cero. El CSV descarga el conjunto filtrado completo, UTF-8 con BOM, sin
notas libres o etiquetas privadas. Normaliza controles y prefijos de fórmula para
Windows sin modificar la DB. El historial conserva auditoría, contexto y fechas Lima.
El [manual S5](docs/manuals/Manual_Seguimiento_Reportes_S5.md) explica permisos,
transiciones, columnas CSV y límites. No incorpora reportes históricos ni eficacia.
