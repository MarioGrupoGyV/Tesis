# Backend — Sprints 1 y 2 DEMO

S1 implementa la base FastAPI, sesiones y catálogos iniciales. S2 añade importación
CSV, estudiantes e historial con datos sintéticos.
La fuente del contrato es [OpenAPI 0.1.2](../docs/planning/Contrato_API_demo.yaml),
con las decisiones de [conciliación SQL/API](../docs/planning/Conciliacion_SQL_API.md)
y [arquitectura](../docs/adr/001-arquitectura.md). Se conservan las versiones y
los archivos de bloqueo acordados en S0.

## Capas y arranque

El punto ASGI es `app.main:app`. `create_app(settings)` permite configurar una
instancia aislada para pruebas. La aplicación recibe conexiones PostgreSQL
síncronas con SQLAlchemy y psycopg; no accede a la base desde el navegador.

| Carpeta | Responsabilidad |
|---|---|
| `app/api/v1` | Rutas HTTP y dependencias de sesión |
| `app/schemas` | Entradas y respuestas públicas S1/S2, sin campos privados |
| `app/services` | Autorización, reglas y transacciones de sesiones, catálogos e importación |
| `app/repositories` | Consultas SQLAlchemy |
| `app/models` | Proyecciones ORM de nueve entidades S1/S2; no autogenerar DDL |
| `app/core` | Configuración, conexiones, contraseñas, tokens, límites y errores |
| `app/seed_demo.py` | Semilla explícita e idempotente |
| `migrations` | Migración Alembic revisada de las trece tablas del diseño |
| `app/ml` | Estructura reservada para el procesamiento local de S3 |

Al arrancar no se crean tablas, no se ejecuta `create_all` y no se siembran
registros. Alembic crea el esquema `risk_school` y las trece tablas. El SQL de
planificación conserva su función de diseño; no se ejecuta directamente.

El migrador usa `riesgo_owner` mediante `MIGRATION_DATABASE_URL_FILE` o
`MIGRATION_DATABASE_URL`. La API y la semilla usan `riesgo_app`: sin DDL, sin
DELETE y sin UPDATE de cortes, predicciones o auditoría. Los triggers también
protegen la inmutabilidad de esas evidencias. El propietario no se utiliza en
las peticiones HTTP.

## Endpoints implementados

Todas las rutas tienen prefijo `/api/v1`.

| Método y ruta | Resultado y acceso |
|---|---|
| `GET /health/live` | Estado del proceso; público |
| `GET /health/ready` | Conexión PostgreSQL: 200 `ok` o 503 `unavailable`; público |
| `POST /auth/login` | Credenciales válidas y Origin autorizado: usuario, CSRF, vencimiento y cookie |
| `GET /auth/me` | Usuario de la sesión vigente; ADMIN, TUTOR, DIRECTOR y RESEARCHER |
| `GET /auth/csrf` | CSRF ligado a la sesión vigente; los cuatro roles |
| `POST /auth/logout` | Revoca la sesión, borra la cookie y devuelve 204; exige `X-CSRF-Token` |
| `GET /periods` | Periodos DEMO; ADMIN y DIRECTOR, o años con secciones propias para TUTOR |
| `GET /sections?period_id=<uuid>` | Secciones del año del periodo; TUTOR solo las asignadas |

S2 añade `POST /imports/preview`, `GET /imports/{id}`, `POST /imports/{id}/commit`
para ADMIN y `GET /students`, `GET /students/{id}`, `GET /students/{id}/timeline`
para ADMIN, DIRECTOR y TUTOR con alcance de sección. Véase el
[manual API](../docs/manuals/Importacion_S2.md) y [ADR 003](../docs/adr/003-importacion-s2.md).

RESEARCHER puede gestionar su sesión pero no consultar los catálogos operativos.
El servidor resuelve el rol desde `app_users` y el alcance desde la asignación
de tutor. Un rol o cabecera enviado por el navegador no modifica los permisos.
Un periodo REAL autorizado por rol/alcance se rechaza con
`422 REAL_MODE_NOT_READY`; la denegación de permisos se resuelve primero.

La cookie `session` es HttpOnly, SameSite=Lax y Path=/; usa Secure bajo HTTPS.
El token aleatorio se conserva solo como digest SHA-256. El CSRF se deriva por
HMAC-SHA256 con el dominio `csrf:v1:` y también se guarda solo como digest.
El login comprueba el Origin exacto. Las sesiones vencidas, revocadas o de una
cuenta inactiva dejan de autorizar peticiones; otro login del mismo usuario con
su cookie anterior revoca esa sesión y crea una nueva. Login y logout escriben
su auditoría en la misma transacción que el cambio.

Los eventos se guardan en UTC y las fechas de respuesta se normalizan a UTC.
Las respuestas no se almacenan en caché. Los errores incluyen un UUID de
solicitud generado por el servidor, sin valores de contraseñas, cookies, secretos
o parámetros privados. El comando Uvicorn de Compose desactiva los logs de
acceso y la aceptación de cabeceras de proxy no confiables.

## Configuración y secretos

No se carga `.env` automáticamente desde Python. Compose establece las variables
y monta archivos de secretos; las pruebas usan una configuración explícita.

| Variable | Requisito o valor predeterminado |
|---|---|
| `APP_ENV` | `development` o `test` |
| `DATA_ORIGIN` | Solo `DEMO` |
| `REAL_MODE_ENABLED` | `false`; `true` impide el arranque, no habilita REAL |
| `DATABASE_URL_FILE` / `DATABASE_URL` | DSN `postgresql+psycopg://` de `riesgo_app`; el archivo tiene prioridad |
| `CSRF_SECRET_FILE` / `CSRF_SECRET` | Secreto de al menos 32 bytes; el archivo tiene prioridad |
| `ALLOWED_ORIGINS` | CSV de orígenes exactos HTTP(S), sin comodines ni rutas; Compose usa localhost/127.0.0.1:15173 |
| `SESSION_COOKIE_SECURE` | `false` para HTTP local; `true` obligatorio si se configura un origen HTTPS |
| `SESSION_TTL_SECONDS` | 28800: ocho horas; rango admitido 60..86400 |
| `LOGIN_ATTEMPT_LIMIT` | 10 intentos por ventana, por IP y correo normalizado |
| `LOGIN_WINDOW_SECONDS` | 300 segundos |
| `LOGIN_MAX_KEYS` | 10000 claves; memoria acotada con expiración y control de concurrencia |
| `IMPORT_STORAGE_DIR` | Ruta absoluta privada fuera del checkout; Compose usa /var/lib/riesgo/imports con volumen persistente. Si falta, importación responde 503. |
| `DEMO_CREDENTIALS_FILE` | Archivo JSON requerido solo al ejecutar la semilla |

`infra/s1.py prepare` genera secretos locales en `.local/secrets`, excluido de
Git, y conserva los existentes. Las credenciales demo son aleatorias, sin
contraseñas predeterminadas ni de producción. El archivo JSON contiene `admin`,
`tutor` y `director`, cada uno con `email` y `password`; la semilla valida correos
distintos y contraseñas de 12..200 caracteres. Nunca imprime esas credenciales.
Compose monta ese archivo únicamente mediante el override de la semilla.

La semilla requiere una base cuyo nombre contenga `demo` y un contexto sin
periodos REAL. Crea tres cuentas, el periodo DEMO-2026 y las secciones 1/A
(con tutor) y 2/A (sin tutor), con identificadores UUID deterministas y auditoría
sintética. Repetirla no duplica filas ni cambia contraseñas o contexto existentes;
una diferencia provoca un error y rollback. Reiniciar no vuelve a ejecutarla.

El limitador de login reside en un único proceso y cuenta también los intentos
correctos. Con el proxy local las peticiones comparten su IP. Su memoria se
restablece al reiniciar la API; las sesiones y auditorías permanecen en PostgreSQL.
Un despliegue con varios procesos necesitará decidir un límite compartido antes
de utilizar datos institucionales.

## Preparación y pruebas

Ejecutar desde la raíz del repositorio, con Docker/Compose disponibles:

```powershell
py -3.12 infra/s1.py up
py -3.12 infra/s1.py seed-demo
py -3.12 infra/s1.py restart
py -3.12 infra/s1.py down
```

`up` prepara secretos, construye web/API, inicia PostgreSQL, migra y arranca los
servicios. `seed-demo` es una acción separada. `migrate` permite repetir
`alembic upgrade head` sin duplicar la revisión. `down` conserva el volumen;
no usar `down -v` para comprobar persistencia.

Para pruebas PostgreSQL en una base aislada con dependencias bloqueadas:

```powershell
docker compose -f infra/compose.test.yaml build tester
docker compose -f infra/compose.test.yaml run --rm tester
```

El contenedor usa Linux/Python 3.12.12 y PostgreSQL 17.6 en red/volumen separados.
Crea una base nueva por ejecución; las solicitudes usan riesgo_app. Incluye las
57 pruebas S1 y 47 de S2. `infra/test_s1.py` queda como regresión local solo de S1.
No sustituir PostgreSQL por SQLite. Resultados y omisiones en
[Estado S2](../docs/planning/Estado_Sprint_2.md).

## Límite del sprint

S2 no incluye entrenamiento, inferencia, tablero ni escrituras de alertas,
intervenciones o reportes. La interfaz de importación/estudiantes corresponde a S4.
No hay registro público, procesamiento REAL, datos de menores ni mensajes a terceros.
Health ready confirma conexión, no la disponibilidad de módulos S3–S6.
