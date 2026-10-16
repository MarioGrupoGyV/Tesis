# Limpieza local autorizada — 2026-10-15 (America/Lima)

El usuario solicitó dejar la base sin estudiantes y especificó conservar los
usuarios del sistema. Después eligió explícitamente vaciar también periodos,
secciones y modelos. Esta operación administrativa excepcional no añade borrado
a la interfaz ni habilita REAL, semillas o regeneración automática.

Destino comprobado: proyecto Docker `riesgo-escolar`, base `riesgo_escolar`,
volúmenes existentes `riesgo-escolar_db_data`, `riesgo-escolar_import_data` y
`riesgo-escolar_ml_data`. La aplicación sigue en `localhost:5173` y `15173`, con
la API integrada en `18000`. PostgreSQL permaneció en ejecución.

## Respaldo previo

Antes de modificar datos se creó el respaldo completo S6 con DPAPI del usuario
Windows y ACL privada, fuera del checkout:

`C:\Users\mario\AppData\Local\SeguimientoEscolar\Backups\s6-20261016T045000Z-5f4e3d304fcb.sebackup`

Incluye DB, esquema, secretos y los 25 archivos privados anteriores, incluidos
el paquete retrospectivo y su diario firmado con sus bytes originales. Se
comprobó nuevamente el descifrado y el inventario antes de limpiar. La recuperación
debe hacerse en una copia nueva según el manual S6; no sobre el activo.

El descriptor privado de origen es:

`C:\Users\mario\AppData\Local\SeguimientoEscolar\S6\active-before-student-clear-20261015-234954.json`

## Resultado efectivo

| Tabla | Antes | Después |
| --- | ---: | ---: |
| students | 60 | 0 |
| enrollments | 60 | 0 |
| academic_snapshots | 360 | 0 |
| predictions | 55 | 0 |
| alerts | 51 | 0 |
| interventions | 2 | 0 |
| followup_decisions | 55 | 0 |
| import_batches | 1 | 0 |
| synthetic_studies | 1 | 0 |
| academic_periods | 1 | 0 |
| grade_sections | 2 | 0 |
| model_versions | 1 | 0 |
| app_users | 4 | 4 |

Los cuatro registros completos de `app_users` se comprobaron idénticos antes y
después: UUID, correos, nombres, roles, hashes de contraseña, estado y fechas.
No se escribió en Credential Manager ni se renovaron accesos. Las asignaciones
de secciones desaparecen con las secciones que el usuario pidió vaciar; no se
cambió el rol ni la identidad de ninguna cuenta.

Se conservaron las sesiones y todos los eventos de auditoría existentes. Se
añadió un evento `LOCAL_DATABASE_RESET_AUTHORIZED` que identifica el respaldo y
los conteos, sin incluir filas o secretos. Una comprobación posterior de login y
logout añadió únicamente su sesión temporal y dos eventos normales de acceso;
no revocó la sesión del navegador del usuario.

La limpieza de las doce tablas fue una única transacción con bloqueo y destinos
explícitos, sin CASCADE. Se exigió coincidencia con el estado respaldado y se
comprobaron usuarios y conteos antes de confirmar. No se alteraron esquema,
triggers, restricciones, grants, roles PostgreSQL o revisión Alembic
`0004_followup`. La API conserva su usuario `riesgo_app` y sus permisos limitados.

Tras comparar los archivos activos con el inventario respaldado se retiraron
dos archivos de importación y 22 archivos de estudio/modelos/retrospectiva.
Los originales firmados permanecen en el paquete cifrado; no se reescribieron
sus contenidos. Se conservó únicamente la clave interna de infraestructura
`.internal-key` del volumen ML. Los documentos/ZIP/Excel originales del usuario,
fuera de los volúmenes de ejecución, no se tocaron. No se borró la base ni ningún
volumen Docker. API y web se pausaron brevemente y se reanudaron.

## Comprobaciones y evidencia

- Respaldo y verificación mediante `infra/backup_restore.py backup` y `verify`,
  con descriptor ACTIVE explícito. [Respaldo](../../tests/evidence/student-clear-20261015-234954-backup.json)
  y [verificación](../../tests/evidence/student-clear-20261015-backup-verified.json).
- Mantenimiento puntual autorizado con
  `.\backend\.venv\Scripts\python.exe .local/clear_active_student_data.py`.
  [Conteos y conservación](../../tests/evidence/student-clear-20261015-result.json).
- Login ADMIN existente HTTP 200 en `5173`; periodos y modelos HTTP 200 vacíos;
  retrospectiva HTTP 200 sin paquete registrado ni ejecuciones activas.
  Preparación HTTP 200 con `synthetic_ready=false` e `institutional_ready=false`.
  El antiguo periodo devuelve 404 en estudiantes, resumen y alertas.
  [Verificación HTTP y conteos después de reiniciar API](../../tests/evidence/student-clear-20261015-http.json).
- Inicio real sin periodo y con acciones dependientes deshabilitadas, sin datos
  anteriores ni un error 503. Capturas inspeccionadas:
  [1440×900](../../tests/evidence/student-clear-empty-1440x900.jpg),
  [768×1024](../../tests/evidence/student-clear-empty-768x1024.jpg) y
  [390×844](../../tests/evidence/student-clear-empty-390x844.jpg).
- `python -m unittest discover -s infra/tests -p test_s6_recovery.py -v`:
  30 pruebas aprobadas, incluidas las nativas DPAPI. El primer intento restringido
  no pudo aplicar ACL privadas; el mismo comando con permisos de ejecución
  autorizados pasó completo.
- `git diff --check`: sin errores.

Para respaldar la configuración actual fue necesario ajustar
`infra/runtime_target.py`: el guard de ACTIVE ahora reconoce también el par
exacto de orígenes de Vite en `5173` autorizado en el arreglo previo. INSTALL y
RESTORE conservan solo su par de orígenes propio. La prueba añadida en
`infra/tests/test_s6_recovery.py` rechaza orígenes ajenos y comprueba esa separación.
No se aceptan comodines ni destinos arbitrarios.

Archivos de producto/documentación afectados: `infra/runtime_target.py`,
`infra/tests/test_s6_recovery.py`, `README.md`, `Estado_Entorno_Local.md` y este
registro. El script de mantenimiento y los descriptores son privados, excluidos
de Git. Las evidencias históricas se conservan como tales.

No se ejecutaron restauración, migración, entrenamiento, inferencia, importación
ni el recorrido completo importar/evaluar/atender/exportar. Sin commit/push.
No hay incidencias pendientes para esta limpieza. Para ingresar nuevos datos será
necesario preparar expresamente un nuevo contexto conforme al alcance autorizado;
no se genera ni restaura ninguno al arrancar.
