# M1: registro académico manual local — 2026-10-16

Destino de cambios: este checkout; evidencias nuevas `tests/evidence/m1-*`.
Destino activo: `riesgo-escolar`; migrar solo después del respaldo S6 verificado.
Toda alta de comprobación se hace en PostgreSQL/copia Docker aislados.

Alumno conserva identidad y código único; nombre nullable preserva registros CSV.
Matrícula une alumno, periodo y sección del mismo año/origen. Sección añade origen
nullable para catálogos históricos, resueltos por la pertenencia registrada del
estudio, nunca por prefijos. Nuevas secciones siempre declaran REAL/SYNTHETIC.

0005 es aditiva. MANUAL no tiene lote, fila ni hash CSV. CSV conserva todos esos
campos y su contrato temporal. Medición MANUAL conserva actor/created_at del
servidor, canal, propósito PARTIAL/CLOSING_REFERENCE, disponibilidades por variable,
ventana/corte y revisión. No se inventa target_date: es null en MANUAL. El promedio
de cierre es referencia y no se admite como entrada predictiva. M1 no crea
predicciones, alertas o modelos ni permite inferencia de mediciones manuales.

ADMIN administra catálogos, identidades/matrículas y actividad del alumno; TUTOR
escribe mediciones de secciones propias; DIRECTOR consulta; RESEARCHER no accede.
Sesión, CSRF y Origin en escrituras. Cada escritura/auditoría es una transacción.
Claves por actor y operación conservan digest original mediante auditoría inmutable
y bloqueo transaccional; mismo envío reutiliza resultado, contenido distinto 409.
Versiones y bloqueo de filas serializan cambios. Revisar medición inserta nueva
fila de la misma serie/corte, motivo y expected_revision; no hereda evaluación.
Cambiar sección con mediciones se bloquea; desactivar exige motivo/confirmación,
conserva relaciones y bloquea escrituras. Cierre/reapertura explícitos, versionados.

Alta alumno+primera matrícula atómica; colisión de código nunca sobrescribe datos.
ADMIN puede buscar y seleccionar identidad existente para otra matrícula.
Normalización de código: Unicode NFKC, espacios colapsados y mayúsculas; nombres
Unicode NFC y espacios colapsados, conservando tildes. No se alteran códigos
históricos; índice normalizado impide nuevas colisiones (si hay históricas,
migración falla y exige conciliación sin borrado). Elegibilidad/consentimientos
conservan false. Registro REAL manual autorizado; importación/inferencia REAL
conservan sus gates. CSV y runtime retrospectivo congelados se conservan.
