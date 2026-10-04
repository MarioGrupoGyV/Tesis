# Conciliación de SQL y API — Sprint 0

Fecha: 3 de octubre de 2026, America/Lima. Contrato vigente: **0.1.1**.
Los documentos siguen describiendo una implementación futura. No se ejecutó DDL.
El coordinador integra estos cambios; la revisión independiente fue de solo lectura.

## Cambios resueltos

| Diferencia del diseño original | Decisión y documentos corregidos | Verificación futura |
|---|---|---|
| `/sections?period_id` no tenía cómo resolver el catálogo sin matrículas | Añadir `academic_periods.school_year` y `Period.school_year` (2000..2100). Seleccionar secciones del año del periodo; tutor solo sus secciones. Al matricular verificar igualdad de años en el servicio. | S1: catálogo antes de importar; S2: rechazar sección de otro año. |
| La sección A de distintos grados colisionaba | `grade_sections` única por `(grade, code, school_year)`. `code` representa A, B, etc.; el grado viaja por separado. La API mantiene `code` y `grade`. | S1: sembrar 1/A y 2/A sin colisión; S2: resolver CSV por los tres campos. |
| Vista previa solo contaba filas, sin explicar creaciones | SQL e `ImportBatch` incorporan `planned_students`, `planned_enrollments`, `planned_snapshots`. No superan filas válidas; lote máximo 10000 filas. Incluye nuevas revisiones en planned_snapshots. | S2: mostrar conteos antes de confirmar y contrastar con filas realmente insertadas. |
| Conteos iguales podían ocultar una corrección concurrente o una vista previa vieja | `preview_version` SQL/API, `preview_state` JSON privado por fila/serie y `expected_preview_version` obligatorio al confirmar. Comparar también identidad/revisión de predecesores. | S2: pestaña antigua y otra importación concurrente devuelven 409 sin escrituras. |
| API omitía límites del SQL | Límites de año, código, grado, promedio, asistencia y campos de seguimiento; hashes SHA-256 con patrón de 64 caracteres hexadecimales. | Generación de tipos y validadores en S1/S2. |
| Campos nullable podían omitirse, creando dos representaciones de ausencia | Los campos principales de corte, riesgo, probabilidades y seguimiento se devuelven obligatoriamente con `null` si falta información. Añadir `Snapshot.supersedes_id`. | S2/S3: no convertir null en cero, riesgo bajo ni cadena vacía. |
| Probabilidades independientes en API frente a invariantes SQL conjuntas | JSON Schema exige todas null o todas numéricas, y valores presentes si calibrated=true. La suma se valida en el servicio: 1 ± 0.00001, como SQL. | S3: rechazar probabilidades parciales y suma inválida. |
| DONE podía omitir fecha efectiva según el esquema API | `InterventionUpdate` exige performed_at no nulo para DONE; CANCELLED solo admite null. La fecha no futura se comprueba en el servicio. | S5: planned no cuenta como done; validación de fecha y estado. |
| Motivo/objetivo admitían espacios y límites distintos | Recortar espacios exteriores; validar texto no vacío y longitud 1..1000. SQL limita resolution_reason a 1000; OpenAPI declara patrón y normalización. | S5: vacíos/espacios, longitudes y cierre con motivo. |
| Revisión podía apuntar a otro instante del mismo estudiante | FK `supersedes_id` incorpora cutoff_at; conserva matrícula, corte y origen. Incremento correlativo y predecessor más reciente se verifican transaccionalmente. | S2: revisiones 1→2 sin sobrescritura ni cruces de cortes. |
| SQL comparaba fechas de calendario contra día UTC | Las fechas DATE académicas son días de America/Lima; TIMESTAMPTZ guarda instantes en UTC. SQL compara cutoff convertido a Lima con window_start/target_date/periodo. RFC 3339 exige zona y respuestas UTC Z. | S2: corte cercano a medianoche UTC sin cambio erróneo de día escolar. |
| API exigía métricas incluso para modelo DRAFT | Model.metrics permite null antes de evaluar. SQL mantiene objeto JSON no nulo: `{}` significa aún sin evaluación; el serializador devuelve null. EVALUATED/APPROVED requieren métricas válidas por servicio. | S3: no crear métricas ficticias ni activar sin evaluación. |

## Permisos, relaciones y operaciones acordadas

La cookie `session` contiene el token aleatorio. El servidor conserva solo su digest.
Para recuperar CSRF sin guardar texto plano, S1 derivará un token determinista con
HMAC-SHA256 de ese token y `CSRF_SECRET`, con prefijo de dominio `csrf:v1:`.
Guardará el digest CSRF, comprobará la sesión y ambos valores con comparación
constante y devolverá el token solo al cliente autenticado. `/auth/csrf` no intenta
invertir un hash. Cookie HttpOnly, SameSite=Lax, Secure en HTTPS; Origin en login;
CSRF en escrituras; navegador sin localStorage. Tokens y secretos fuera de logs.

`assigned_to` de la alerta será el tutor activo de la sección al abrir el caso.
Si no hay tutor, será null y la interfaz indicará “Sin responsable asignado”.
La demo no ofrece reasignación manual. La actualización del caso conserva ese
responsable; cambios de tutor requieren revisar permisos según la sección actual.
FAMILY_MEETING solo registra una acción interna: no envía mensajes a familias.

| Recurso | ADMIN | TUTOR | DIRECTOR | RESEARCHER |
|---|---|---|---|---|
| Sesión propia (me/csrf/logout) | Sí | Sí | Sí | Sí |
| Periodos/secciones | DEMO | DEMO, secciones propias | DEMO | No |
| Estudiantes/cortes/predicciones/casos | DEMO | Solo sección autorizada de matrícula | DEMO, lectura | No |
| Importar/evaluar/activar modelo | Sí | No | No | No |
| Cambiar alertas/intervenciones | Sí | Solo sección autorizada | No | No |
| Resumen/CSV operativo | Sí | Solo sección autorizada | Sí | No |
| Modelos/métricas de desarrollo sanitizados | Sí | No | Lectura | Lectura |
| Auditoría administrativa | Sí | No | No | No |

Los permisos `x-roles` de OpenAPI ya coincidían con esta matriz. Son especificación;
no constituyen controles ejecutados. El servidor resolverá rol desde la sesión y
sección desde matrícula. RESEARCHER tiene lectura técnica agregada, nunca acceso
por defecto a listados de casos ni a exportaciones operativas. No existe aún una
exportación institucional aprobada ni un endpoint de investigación.

Después de autenticar y comprobar rol/alcance, cada recurso REAL devuelve
`422 REAL_MODE_NOT_READY`, incluso si el origen
solo se descubre a través del periodo o modelo. Los enums REAL/SVM/XGBOOST se
conservan como representaciones reservadas del diseño; esta fase solo procesa
DEMO y activa DUMMY/RANDOM_FOREST. No se habilita REAL mediante `.env`.

`expected_version` es una precondición de PATCH; `version` es el estado SQL.
Se requiere UPDATE condicionado por versión y auditoría en la misma transacción;
cero filas por versión desactualizada produce `409 VERSION_CONFLICT`.
El trigger que incrementa versión no sustituye esta comparación.

Los `planned_*` se calculan durante preview sobre el estado observado. Antes del
commit, el servicio compara `expected_preview_version`, revalida dentro de la
transacción y bloquea las series afectadas. `preview_state` conserva por fila el
estado observado: ids de estudiante/matrícula existentes y id/revisión del corte
predecesor (null si no existe). No se devuelve ni se registra completo en logs.
Si cambiaron creaciones/revisiones esperadas, devuelve `409 IMPORT_PREVIEW_STALE`
sin escrituras académicas y exige revisar otra vista previa. Preview puede refrescar
el mismo lote no confirmado, incrementando preview_version y auditando el cambio;
mismo hash/periodo conserva su id. Una vista previa vieja no confirma la nueva.
Un lote COMMITTED siempre devuelve su resultado original, incluso si luego se bloquea
el periodo: es una lectura idempotente, no una escritura nueva.

Transiciones de alerta: OPEN permite IN_REVIEW, RESOLVED o DISMISSED;
IN_REVIEW permite RESOLVED o DISMISSED. Resolver directamente también exige motivo
y versión. Estados cerrados no se reabren; un episodio posterior crea otro caso.

Los periodos bloqueados rechazan escrituras académicas de importación, matrícula,
predicción y seguimiento. Cambios de sesión y auditoría de lecturas siguen posibles.
La consulta de un corte nuevo no muestra una predicción antigua como riesgo actual:
EVALUATED exige corte vigente y modelo activo compatible; insuficiencia nunca es LOW.
`not_evaluated_students` incluye falta de corte, evaluación pendiente e insuficiencia;
sumado a evaluated debe igualar enrolled. La distribución de riesgo suma evaluated.

## Mapeo sin duplicar columnas

| Esquema público | Origen SQL |
|---|---|
| User | app_users, sin password_hash/email privado de autenticación |
| LoginResult/Csrf | sesión y token derivado, sin exponer digests |
| Period / Section | academic_periods / grade_sections |
| Student | students + enrollments + grade_sections + corte/predicción vigente + alerta activa |
| Snapshot | academic_snapshots; incluye vínculo de revisión, sin fila original ni clave de almacenamiento |
| Prediction | predictions; cutoff_at/target_date vienen del snapshot inmutable |
| ImportBatch / ImportCommit | import_batches; created_snapshots se obtiene de cortes del lote confirmado |
| Model | model_versions; metrics es proyección validada del JSON |
| Alert | alerts; student_id/anon_code se obtienen desde enrollments/students |
| Intervention | interventions; created_by y origen se resuelven desde sesión/recurso |
| TimelineEvent | evidencias y auditoría sanitizada; id estable del evento, sin tabla extra |
| Dashboard / ReportSummary | agregados con periodo, actualización, alcance y denominador |
| AuditEvent | audit_events; summary es sanitización, nunca el payload completo |

UUID se expone como string/uuid; DATE como string/date; TIMESTAMPTZ como
string/date-time UTC; smallint/integer como integer; numeric como JSON number finito,
no string. En S1/S2 el serializador Pydantic de Decimal debe producir ese formato.
Promedio/porcentajes aceptan como máximo dos decimales; missing_fraction se calcula
en servidor y redondea a cuatro; probabilidades se persisten a siete, con la tolerancia
de suma definida. No delegar redondeos silenciosos de CSV al motor SQL.

La base conserva campos privados: hashes de sesión/contraseña, storage_key,
artifact_key/hash, parámetros/manifiesto y metadatos de filas. Su ausencia en API es
deliberada. No añadir columnas para estados o agregados derivados.

## Trabajo que pertenece a S1–S6

Actualización S1: la migración `0001_demo_schema` ya ejecuta las 13 tablas del SQL
conciliado y concede permisos al rol interno `riesgo_app`; las cinco entidades ORM
necesarias para S1 conservan los campos públicos acordados. Contrato 0.1.1 y SQL de
diseño permanecen sin cambios. El mapeo, los permisos y la base limpia se comprobaron
según `Estado_Sprint_1.md`; las reglas de importación, ML y seguimiento siguen en
sus sprints. Los errores de DB se sanitizan como 503 Error también en auth/catálogos,
una respuesta de infraestructura que aún no enumera 0.1.1 fuera de health/ready;
se registra para una futura revisión, sin modificar el contrato vigente.

Convertir el SQL revisado en Alembic, crear propietario de migraciones y usuario
de aplicación sin DDL ni DELETE sobre evidencias, e implementar validaciones de
servicio. Las FK de tutor/assigned_to comprueban existencia, no rol: S1/S5 deben
comprobar actividad, rol y sección. Las FK compuestas impiden cruces de origen y
matrícula; la exclusividad de alerta activa y predicción corte-modelo ya existían.
Las restricciones se probarán en PostgreSQL limpio en S1/S6. S0 solo comprobó
OpenAPI, sintaxis SQL y coherencia documental, sin atribuirles ejecución funcional.
