# ADR 002 — Base ejecutable DEMO y seguridad de S1

Fecha: 3 de octubre de 2026 (America/Lima). Estado: aceptado para S1.
Complementa ADR 001; no cambia versiones, locks, contrato 0.1.1 ni metodología.

## Servicios y configuración

Compose tiene exactamente web, api y db, con healthchecks, dependencias y un
volumen nombrado para PostgreSQL. Puertos del host 15173/18000/55432 en 127.0.0.1:
el puerto 5432 estaba ocupado por otro proyecto y no se modificó ese servicio.
La web usa Vite con proxy de mismo origen hacia api:8000. Es servidor de desarrollo
para la demo local; despliegue institucional y TLS no se implementan en S1.

Se instalaron las dependencias Python en Linux con --require-hashes y npm ci con
el lock vigente. La imagen Node fijada incluye otro parche de npm; el Dockerfile
instala explícitamente npm 11.20.0. API y web usan usuarios sin privilegios. Vite
necesita escribir su caché y configuración temporal: /workspace pertenece a node.

infra/prepare_demo.py genera claves independientes y contraseñas aleatorias de
demostración en .local/secrets, excluidas de Git y del contexto de build. No imprime
ni reemplaza los valores. Compose monta archivos como secrets; la API permanente
recibe solo la URL de riesgo_app y la clave CSRF. Credenciales del migrador y de las
cuentas se montan únicamente con overrides en tareas temporales. Los secrets de
Compose local son archivos del host; no equivalen a una bóveda institucional.

## Migración y permisos

Alembic 0001_demo_schema congela el SQL conciliado en un archivo contiguo .sql,
sin BEGIN/COMMIT porque la transacción la controla Alembic. Mantiene las 13 tablas,
relaciones, restricciones, índices y triggers del diseño. La ejecución SQLAlchemy
usa no_parameters=True para preservar los % de las funciones PL/pgSQL.
Los futuros cambios requieren revisiones nuevas y revisadas.

riesgo_owner crea el esquema y aplica migraciones. riesgo_app no es superusuario,
no tiene CREATE, DELETE ni TRUNCATE; tampoco UPDATE de cortes, predicciones o
auditoría. Tiene SELECT/INSERT y UPDATE de tablas mutables acordadas. No hay RLS
en S1: el alcance de cada usuario se verifica en servicios backend; el navegador
nunca se conecta a PostgreSQL. Las credenciales de DB son internas de la aplicación.

El arranque API no ejecuta create_all, migración ni semilla. El ORM representa solo
las cinco entidades usadas en S1; target_metadata=None evita autogenerar una
migración que borre las ocho tablas aún sin módulo. No se soporta downgrade
destructivo: se rechaza explícitamente para conservar evidencias.

## Semilla y sesión

La semilla exige DB de nombre demo y ausencia de periodos REAL, toma un bloqueo
transaccional y usa UUID estables. Crea ADMIN, TUTOR y DIRECTOR activos, DEMO-2026,
1/A asignada al tutor y 2/A sin tutor. Repetir con la misma configuración reutiliza
filas; valores diferentes requieren revisión y no sobrescriben cuentas. No crea
estudiantes, matrículas, cortes, modelos, predicciones ni casos.

Las contraseñas usan Argon2. La cookie session contiene 32 bytes aleatorios
codificados; el servidor guarda SHA-256 de sesión y CSRF. CSRF se deriva con HMAC
de la clave privada y sesión, permitiendo recuperarlo sin guardar el token bruto.
Cookie HttpOnly, SameSite=Lax, Path=/, duración ocho horas; Secure bajo HTTPS.
La demo local liga HTTP a loopback. HTTPS exige configuración explícita Secure y
orígenes exactos; no se confía en X-Forwarded-* ni X-Role.

Login exige Origin permitido y limita intentos por IP y correo normalizados como
digests: diez por cinco minutos, estructura en memoria acotada. Este límite es
para un proceso demo; un despliegue con múltiples trabajadores requerirá una
política compartida. Una sesión vencida, revocada o de usuario inactivo devuelve
401. Roles y secciones se vuelven a consultar en servidor. Logout exige CSRF,
revoca la sesión y audita en la misma transacción; repetir una cookie revocada no
autoriza. Frontend conserva CSRF solo en memoria, sin localStorage/sessionStorage.

RESEARCHER puede autenticarse, pero no consultar los catálogos operativos.
El tutor recibe únicamente años/secciones asignados. El procesamiento REAL sigue
bloqueado; cambiar REAL_MODE_ENABLED=true impide iniciar la configuración.

## Contrato y consecuencias

Se implementan ocho operaciones de 0.1.1: live, ready, login, me, csrf, logout,
periods y sections. Los tipos frontend se generan desde el documento vigente.
Los otros endpoints siguen sin implementar; no se responde con datos ficticios.

Los errores SQLAlchemy se sanitizan como 503 Error también en autenticación y
catálogos para informar indisponibilidad sin exponer la base. El contrato vigente
solo enumera 503 en health/ready: esta respuesta transversal de infraestructura
queda registrada como diferencia pendiente de documentar en una futura revisión
del contrato, que en S1 se conserva íntegro. Campos y respuestas del recorrido
normal, CSRF y permisos se verificaron contra 0.1.1.

Las comprobaciones ejecutadas y pendientes se registran en Estado_Sprint_1.md.
S2-S6 y la fase institucional conservan sus dependencias y requieren autorización.
