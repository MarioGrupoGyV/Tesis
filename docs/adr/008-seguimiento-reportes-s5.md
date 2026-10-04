# ADR 008 — Seguimiento y reportes S5

Estado: aceptada antes de programar, 4 de octubre de 2026, America/Lima.
SHA inicial: `e9349f26b3f0b301cd4d5f50bbec0a7532110e85`; checkout limpio.

## Alcance y contrato

S5 conecta Alertas, intervenciones, resumen operativo y CSV al estudio SYNTHETIC
registrado. REAL sigue bloqueado. No cambia ML, artefactos, metodología, cuentas,
locks ni versiones; no regenera el estudio. OpenAPI 0.5.0 añade ocho operaciones
efectivas (27 en total) y amplía el resultado de inferencia/estado de procesamiento.
No hay comunicaciones, gestión de usuarios, entrenamiento HTTP ni S6.

ADMIN consulta y modifica todo el estudio y sincroniza. TUTOR consulta y modifica
solo sus secciones; no sincroniza ni evalúa. DIRECTOR solo lee. RESEARCHER conserva
Inicio limitado/estado general y sesión. UUID inexistente o ajeno da el mismo 404.
Todas las escrituras exigen CSRF, periodo desbloqueado y procedencia registrada.
Las lecturas autorizadas de periodos bloqueados siguen disponibles.

## Política y evidencia

`followup-policy-v1`: únicamente MEDIUM/HIGH del último corte/revisión y modelo
compatible activo motivan un caso. LOW registra una señal y conserva el caso para
revisión humana. Faltantes/abstención nunca generan LOW ni casos. El responsable
inicial es el tutor activo, o null. Un caso activo conserva apertura, responsable
y estado de trabajo cuando cambia la fuente. Nunca retrocede a cortes antiguos.

La migración manual 0004 añade una tabla mínima `followup_decisions` (una decisión
inmutable por prediction_id, FK compuestas a matrícula/origen/caso y estudio) y
creation_key/digest original a interventions. Reutilizar una predicción no duplica
decisión/auditoría/versiones; cerrar no permite otro caso para esa predicción.
Una predicción posterior puede crear otro caso conservando historia. Se mantienen
ux_active_alert_enrollment y las migraciones 0001–0003 intactas.

OPEN permite IN_REVIEW/RESOLVED/DISMISSED; IN_REVIEW permite RESOLVED/DISMISSED.
Cerrar es terminal y exige motivo y hora del servidor; no cierra actividades.
Intervenciones nuevas PLANNED; PLANNED permite editar/DONE/CANCELLED. DONE exige
fecha efectiva explícita con zona y no futura; CANCELLED conserva null. Terminales
no se editan. Versiones estrictas: un cambio efectivo incrementa exactamente una.
Creación exige expected_alert_version y UUID creation_key: mismo actor/clave y
payload ORIGINAL reutilizan; otra carga da 409, incluso después de editarla.

## Transacciones y concurrencia

Orden común: periodo (FOR SHARE), estudio registrado consultado y modelo (FOR SHARE), matrículas ordenadas por UUID,
alertas e intervenciones. La exclusión de matrícula coordina sync/inferencia y
ediciones; el lock de periodo serializa con su cierre. Importación ya toma locks
de periodo/series y de las mismas matrículas antes de escribir revisiones. Restricciones de DB respaldan
unicidad, procedencia, transiciones, evidencia y bloqueo; no lock global en memoria.
Inferencia, seguimiento y auditoría se confirman juntos. Sync es reutilizable sin
commit interno; el límite de servicio confirma o revierte la operación completa.

Conteos de seguimiento separados: created (casos nuevos), updated (cambio de fuente),
retained_low (señal LOW con caso), no_alert (LOW sin caso), reused (decisión existente),
ignored_stale (predicción solicitada que ya no es actual), skipped_missing (matrícula
sin evaluación actual). No se registra una abstención como predicción procesada.

## Resumen y CSV

Unidad: matrícula autorizada actual, última revisión y modelo compatible, compartida
con lecturas de estudiantes. Total=evaluados+sin evaluar+datos insuficientes;
evaluados=LOW+MEDIUM+HIGH. Casos por estado, matrículas con caso activo y actividades
por estado se agregan separadamente antes de unir; no multiplican matrículas.
Porcentajes indican denominador; cero produce null y explicación, sin eficacia.

Resumen/CSV comparten filtros reales: periodo, sección, código, riesgo, estado de
evaluación y estado de caso. CSV completo filtrado, una fila por matrícula, orden
por código/UUID. UTF-8 con BOM para Windows, null como celda vacía, quoting CSV.
Textos que tras quitar controles/espacios comienzan =,+,-,@ reciben apóstrofo;
controles se eliminan de la proyección, no de DB. No notas/motivos/etiquetas/ML
privado. Nombre fijo, attachment/no-store. Auditoría registra solicitud/filtros/
alcance/instante/conteo, nunca apertura o guardado por el usuario. Cada lectura usa
una consulta consistente para filas y agregados.

## Criterios de cierre

Pruebas PostgreSQL con riesgo_app: clean/upgrade, permisos/origen, locks, política,
repetición/revisión/LOW, terminales/versiones/idempotencia/rollback/concurrencia,
conteos/CSV/timeline. Recorrido real aislado completo y revisión activa mínima sin
alterar 60 estudiantes/360 cortes/55 predicciones previas. Tipos/build/contrato/pip,
persistencia y capturas inspeccionadas en tres tamaños. Evidencias nuevas s5;
fallos/simulaciones/omisiones se distinguen. S6/restauración final y revisión
académica siguen pendientes; métricas operativas sintéticas no son eficacia escolar.
