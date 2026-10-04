# Conciliación vigente — 0.2.0 / S2.1

Contrato_API.yaml publica 14 rutas S1/S2; no publica rutas vacías de ML, tablero,
seguimiento, reportes o auditoría. Se retiró DEMO del origen público. REAL conserva
el significado institucional, sin afirmar autorización ni convertir registros.

La base nueva aplica 0001 intacta y 0002_institutional_boundary: nueve tablas con
origen institucional para nuevas escrituras; defaults academic-v1 y activación de
modelos bloqueada. Las claves compuestas, permisos, triggers y evidencias inmutables
se conservan. NOT VALID permite conservar evidencia histórica de otro origen sin
reetiquetar; en una base nueva las restricciones de origen quedan validadas.

Las escrituras de importación autenticadas/CSRF responden 422
INSTITUTIONAL_PROCESSING_NOT_READY antes de persistir archivo/lote. El motor S2 no
se elimina: retiene versión de preview, locks, transacción, idempotencia, límites,
fracción faltante y revisiones, comprobados exclusivamente con fixtures aislados.
Las escalas históricas aún no constituyen una decisión de escala institucional.

Contexto REAL puede leerse; ADMIN/DIRECTOR/TUTOR mantienen alcance. Sin periodos,
GET periods devuelve []. Error 503 sanitizado para operaciones de base; health/ready
conserva Health. Conflictos de integridad son 409. No hay selector de modo.

Los esquemas de historial de predicción/alerta/intervención son proyecciones públicas
de lectura para compatibilidad S2, no operaciones implementadas de S3/S5.
Tipos frontend regenerados; validador adapta correspondencias SQL y fixtures reales
de respuesta al contrato actual. Las evidencias 0.1.1/0.1.2 no se reescriben.

Véase ADR 004 y Estado_Sprint_2_1.md. La conciliación anterior está en
history/Conciliacion_SQL_API_S2.md; no es instrucción para crear datos de demostración.
