# Conciliación vigente — 0.4.0 / S3.1

Nueva decisión ADR 006; los cierres S2.1/S2.2/S3 conservan sus hechos anteriores.
19 operaciones reales: S1/S2/S3 más GET /processing/status. Origen público REAL o
SYNTHETIC; cambio incompatible frente a 0.3.0. No entrenamiento/activación HTTP.

0003 conserva 0001/0002, nueve dominios de origen, defaults academic-v1, índices,
claves compuestas, triggers y permisos. Sustituye institutional_origin por
processing_origin (REAL/SYNTHETIC, NOT VALID conserva DEMO histórico). Sustituye
los dos guards activos por synthetic_only_active_model: aprobación técnica,
SYNTHETIC_STUDY y registro de procedencia. REAL no puede activarse. Los consentimientos
no se fabrican: SYNTHETIC es elegible como simulación, consentimiento/asentimiento false.

Tabla privada mínima synthetic_studies (14 en total), payload con CSV/etiquetas/resultado
futuro fuera del checkout y hash. Configuración/manifiesto de generación inmutables;
bindings y comparison solo se incorporan una vez. Lotes y modelos incluyen study_id:
FK compuesta de origen, FK exacta de CSV/periodo y trigger de predicción del mismo estudio.
No nuevos endpoints de investigación ni exposición de etiquetas o archivos privados.

Imports verifica registro/hash/contexto; el cliente no declara origen. Preserva parser,
5 MiB/10000 filas, fechas Lima/UTC, null/precisión, previews versionadas, transacción,
locks, idempotencia y auditoría. REAL devuelve INSTITUTIONAL_PROCESSING_NOT_READY.
Archivo sintético no registrado/modificado devuelve UNREGISTERED_SYNTHETIC_FILE 422.
Errores de integridad/conflicto son 409; 503 sanitizado solo indisponibilidad de DB/
almacenamiento. Health/ready mantiene Health. Autenticación/rol/CSRF preceden al cuerpo.

Modelos publican origen, esquema/criterio y estado técnico; no hashes, métricas privadas,
particiones, etiquetas ni rutas. Predicciones son null en probabilidades no calibradas,
unicidad snapshot/model, origen coherente y alcance servidor. Una abstención no crea riesgo.
Tipos regenerados y validador adaptado. Evidencias históricas intactas.
