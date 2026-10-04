# Backend de Seguimiento Escolar — S5

Contrato público **0.5.0**: **27 operaciones en 26 paths**, bajo `/api/v1`.
PostgreSQL contiene **15 tablas**. S5 añade seguimiento y reportes operativos del
estudio SYNTHETIC registrado; REAL conserva `INSTITUTIONAL_PROCESSING_NOT_READY`.
Los resultados de comprobación se registran en
[Estado S5](../docs/planning/Estado_Sprint_5.md); este archivo describe preparación
y funcionamiento, sin anticipar el resultado de las comprobaciones de cierre.

Las capas siguen separadas: `api/v1`, `schemas`, `services`, `repositories`,
`models` y `ml`. El usuario de ejecución es `riesgo_app`; el propietario se utiliza
solo para migración. `0001`–`0003` se conservan. La migración manual
`0004_followup` añade una tabla mínima `followup_decisions`, más clave UUID y digest
original de creación a `interventions`; reutiliza `alerts`/`interventions`, FK
compuestas, guards de origen/periodo y `ux_active_alert_enrollment`. Las entidades
se mapean explícitamente en ORM; no usar autogeneración ni ejecutar el SQL de
diseño sobre la instalación existente.

## Operaciones S5

| Operación | Roles y comportamiento |
| --- | --- |
| `POST /alerts/sync` | ADMIN y CSRF; sincroniza predicciones actuales existentes |
| `GET /alerts` | ADMIN/TUTOR/DIRECTOR; filtros, orden estable y paginación del servidor |
| `GET /alerts/{id}` | Caso autorizado, fuente, evaluación actual, actividades e historial |
| `PATCH /alerts/{id}` | ADMIN/TUTOR y CSRF; versión estricta y cambio humano de estado |
| `POST /interventions` | ADMIN/TUTOR y CSRF; caso activo, versión del caso y clave idempotente |
| `PATCH /interventions/{id}` | ADMIN/TUTOR y CSRF; edición o realización/cancelación de PLANNED |
| `GET /reports/summary` | ADMIN/TUTOR/DIRECTOR; resumen actual del conjunto filtrado completo |
| `GET /reports/export.csv` | Mismos roles/alcance/filtros; una fila por matrícula autorizada |

TUTOR se limita a sus secciones también en SQL, UUID de detalle, escritura y CSV.
DIRECTOR consulta sin mutaciones de seguimiento; RESEARCHER conserva Inicio limitado
y sesión. Recurso ajeno e inexistente comparten 404 seguro. Las secciones pertenecen
al contexto registrado del estudio. Lecturas autorizadas de periodos bloqueados
siguen disponibles; las escrituras exigen periodo abierto. Autenticación/rol/CSRF
y bloqueo institucional preceden al procesamiento del cuerpo cuando corresponde.
Los errores son JSON `Error` sanitizado con `request_id`; integridad/versiones/claves
son conflictos de dominio 409, no un 503 de disponibilidad.

## Política y transacciones

`followup-policy-v1` usa la clase pública de la predicción del último corte/revisión
y modelo activo compatible. MEDIUM/HIGH crean OPEN o actualizan la fuente del caso
activo; preservan apertura, responsable y estado humano. LOW registra una señal y
conserva el caso para revisión humana; sin caso registra NO_ALERT. Una abstención o
revisión pendiente no produce riesgo bajo ni una decisión de predicción procesada.
El responsable inicial es el tutor activo de la sección, o null.

`sync_current` no confirma internamente. En `predictions/run`, predicción,
seguimiento y auditoría se confirman juntos; cualquier fallo revierte todo.
La selección histórica por `as_of` no retrocede la fuente actual: informa
`ignored_stale`. Los locks siguen periodo compartido, modelo compartido,
matrículas ordenadas por UUID y recursos de seguimiento. Unicidad y versiones DB
respaldan la concurrencia, sin bloqueo global de proceso.

Repetir una predicción reutiliza la decisión persistente sin duplicar caso,
auditoría o versión. Cerrar no habilita otro caso con esa predicción. Una predicción
posterior puede iniciar otro caso. Edición exige `expected_version`; un cambio
efectivo incrementa exactamente una vez. Cierre es terminal y exige motivo,
`closed_at` del servidor y auditoría, sin completar/cancelar actividades.

Crear una actividad exige `expected_alert_version`, `creation_key` UUID y digest
del payload original canonicalizado, incluida aquella versión. Mismo actor/clave/
payload reutiliza; otra carga devuelve 409. El digest se conserva tras las ediciones.
PLANNED empieza sin `performed_at`; DONE exige fecha efectiva explícita con zona y
no futura; CANCELLED conserva null. Terminales no se editan. Una actividad ya
planificada puede realizarse/cancelarse después del cierre del caso. El timeline
proyecta eventos auditados efectivos, sin payload privado ni apertura duplicada.

## Resumen y CSV

Resumen/CSV comparten la consulta base de estudiantes y una lectura SQL consistente.
Último corte/revisión y predicción compatible definen el estado actual por matrícula.
`total = evaluated + not_evaluated + insufficient_data` y
`evaluated = LOW + MEDIUM + HIGH`. Porcentajes de riesgo usan evaluados como
denominador; con cero devuelven null y motivo. Casos y actividades se agregan
separadamente antes de unir, evitando multiplicar matrículas. Solo DONE cuenta como
realización; ninguna cifra acredita éxito de una actividad o eficacia escolar.

CSV completo filtrado, orden código/UUID, UTF-8 con BOM, quoting y null como celda
vacía. La proyección elimina controles y ante `=`, `+`, `-`, `@` tras espacios
iniciales añade apóstrofo; la DB conserva el texto original. No exporta narrativas,
notas, etiquetas reservadas, credenciales ni métricas privadas ML. Nombre fijo
`seguimiento-escolar-reporte.csv`, attachment y no-store; también sus errores son
JSON Error. La auditoría registra solicitud, actor, filtros/alcance, instante y
conteo, sin afirmar apertura/guardado del archivo.

## Preparación y pruebas desde PowerShell

Desde la raíz del repositorio, con Docker Desktop en modo contenedores Linux:

```powershell
docker compose build api web
py -3.12 infra/manage.py migrate
docker compose up -d --wait api web
docker compose exec -T api python -m pip check

$s5Revision = Get-Date -Format 'yyyyMMdd-HHmmss'
$env:TEST_REPORT_NAME = "s5-backend-$s5Revision"
docker compose -f infra/compose.test.yaml build tester
docker compose -f infra/compose.test.yaml run --rm tester
```

El runner usa Linux/Python **3.12.12** y PostgreSQL **17.6**, crea una DB nueva de
prueba, migra con propietario y ejecuta con `riesgo_app`; no usa la DB activa.
Cada prefijo nuevo conserva informes previos. No instalar dependencias libres ni
actualizar locks para corregir deprecaciones. Los comandos de navegador, persistencia
y cierre están en [infra/README](../infra/README.md).

S3.1 conserva generador explícito, CSV/hash/bindings verificados, comparación por
grupos, reserva temporal y cuatro algoritmos CPU privados. S5 modifica únicamente
la orquestación transaccional necesaria de inferencia; no regenera ni reentrena el
estudio activo. Se conservan las cuatro cuentas S2.2, sus credenciales Windows,
sesiones, evidencias y volúmenes. Referencias: [ADR 008](../docs/adr/008-seguimiento-reportes-s5.md),
[manual S5](../docs/manuals/Manual_Seguimiento_Reportes_S5.md) y
[manual del estudio](../docs/manuals/Manual_Estudio_Sintetico.md).
S6, restauración final integrada y revisión académica siguen pendientes.
