# ADR 003 — Importación y consultas académicas DEMO

Estado: aceptado para S2, 3 de octubre de 2026 (America/Lima).
Complementa ADR 001 y 002. OpenAPI pasa a 0.1.2; versiones, locks, SQL de diseño
y migración de las trece tablas permanecen intactos.

## Contrato y errores

Las operaciones que acceden a PostgreSQL documentan 503 con `Error` sanitizado.
`health/ready` conserva 503 con `Health`. Los errores de integridad, serialización
y bloqueo son 409; los fallos de programación son 500. Se conserva el tratamiento
503 de la excepción SQLAlchemyError genérica usado por S1. Nunca se devuelven SQL,
parámetros, rutas privadas ni mensajes internos del controlador.

Se añaden únicamente las seis operaciones de importación y estudiantes. ADMIN
importa; ADMIN y DIRECTOR consultan estudiantes DEMO; TUTOR consulta exclusivamente
sus secciones. RESEARCHER no consulta casos. La sesión determina el rol; las
escrituras comprueban CSRF. REAL permanece bloqueado.

## CSV y tiempo

Se exige UTF-8 (BOM opcional), coma, trece cabeceras en el orden contractual,
máximo 5 MiB y 10000 filas de datos. El cuerpo multipart también tiene límite
antes de procesar sus partes. Errores estructurales devuelven 422; errores por fila
producen un lote FAILED con fila, campo y corrección esperada. No hay aceptación parcial.

Los seis atributos académicos pueden estar vacíos y se conservan como null.
`missing_fraction` es la cantidad de atributos ausentes dividida entre seis,
redondeada a cuatro decimales. Promedio y porcentajes admiten hasta dos decimales,
sin exponentes. Fechas académicas se comparan en America/Lima; instantes con zona
se normalizan a UTC, con precisión máxima de microsegundos.

La sección se resuelve por grado, código y año del periodo. Se verifica actividad
del estudiante, elegibilidad de matrícula y asignación válida del tutor. El hash
del archivo identifica el lote; otro hash canónico por fila permite reconocer
cortes equivalentes aunque cambie la representación del CSV.

## Transacciones y concurrencia

Vista previa guarda lote, archivo y metadatos, sin estudiantes, matrículas ni cortes.
El estado observado contiene identidades, sección/tutor, fechas del periodo y
predecesores/revisiones, además de cantidades. Refrescar incrementa preview_version.
Confirmar exige expected_preview_version y revalida todo el estado; una diferencia
devuelve IMPORT_PREVIEW_STALE sin escrituras académicas.

Se bloquean periodo y contexto compartido, lote y series afectadas. Los advisory
locks de estudiantes se distribuyen en 256 grupos deterministas adquiridos siempre
en orden; esto evita agotar la memoria de locks con 10000 filas. Una colisión solo
serializa trabajo adicional. Las filas existentes se bloquean en PostgreSQL y las
restricciones de la migración siguen siendo la defensa final. lock_timeout es 10 s.

Estudiantes, matrículas, cortes, estado del lote y auditoría se confirman en una
transacción, con inserciones agrupadas por etapa. Un fallo intermedio revierte todo.
Una corrección crea revisión y supersedes_id, sin actualizar evidencia anterior.
Un lote COMMITTED autorizado reutiliza siempre el resultado, incluso después de
bloquear el periodo; no ejecuta nuevas escrituras académicas.

## Archivos y consultas

Los CSV privados se guardan en el volumen import_data, fuera del checkout, con
identificadores UUID internos. El nombre enviado nunca forma una ruta. Se usan
creación exclusiva, permisos restrictivos, fsync y comprobación SHA-256 al leer.
Un fallo de transacción elimina el archivo recién creado cuando es posible.
Un cierre abrupto entre escritura y commit puede dejar un archivo huérfano: su
reconciliación y política de conservación quedan pendientes; no se borra evidencia
automáticamente. Reiniciar conserva tanto PostgreSQL como el volumen privado.

Las consultas filtran por rol y sección, acotan paginación y usan orden estable.
Solo una predicción del corte seleccionado y modelo DEMO vigente puede atribuir
riesgo. Sin ella se devuelve NOT_EVALUATED y riesgo null. El detalle fija los IDs
del corte y predicción de su consulta inicial para evitar mezclar revisiones ante
una importación concurrente. El historial devuelve campos públicos y resúmenes
controlados. No se implementan entrenamiento, inferencia ni escrituras de seguimiento.

## Verificación

104 pruebas en Linux/Python 3.12.12 con PostgreSQL 17.6 aislado; peticiones y
confirmaciones concurrentes ejecutadas como riesgo_app. Se probó una importación
de 10000 filas, rollback, revisiones, permisos y persistencia real. Evidencias y
limitaciones en [Estado S2](../planning/Estado_Sprint_2.md).
