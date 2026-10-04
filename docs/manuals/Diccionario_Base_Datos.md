# Diccionario de base de datos

Revisión vigente: **0004_followup**, PostgreSQL **17.6**, esquema `risk_school`.
Son **15 tablas de aplicación y 172 columnas**. `public.alembic_version` es la
metatabla adicional de Alembic: conserva `version_num varchar(32) NOT NULL`, clave
primaria, con `0004_followup` como head. También pertenece al respaldo completo.

Este diccionario se contrastó con el [catálogo PostgreSQL restaurado S6](../../tests/evidence/s6-effective-catalog.json):
15 tablas, 172 columnas, 159 constraints, 51 índices y 12 triggers. La comparación
de columnas verificó tipos/null/defaults y precisión/escala numérica, sin diferencias;
los 41 grants de riesgo_app coinciden con el diseño (146 grants totales incluyendo
propietario). Nombres y definiciones de constraints/índices de cada tabla se toman
directamente de ese catálogo, sin publicar filas. El [reporte de restauración](../../tests/evidence/s6-restore-final-code.json)
comprobó las 15 huellas completas, Alembic y 17 archivos privados antes del login;
conservó el modelo SVM y su HMAC sin regenerar ni reentrenar. Esa igualdad no
sustituye las revisiones UI ni los criterios de cierre de S6.

Fuentes adicionales: [SQL de referencia](../planning/Esquema.sql) y
[migraciones ejecutables](../../backend/migrations/versions/0001_demo_schema.py),
[0002](../../backend/migrations/versions/0002_institutional_boundary.py),
[0003](../../backend/migrations/versions/0003_synthetic_study.py) y
[0004](../../backend/migrations/versions/0004_followup.py). Las comparaciones del
esquema PostgreSQL efectivo se registran en [Estado S6](../planning/Estado_Sprint_6.md)
y la [matriz final](Matriz_Trazabilidad_Final.md); redactar el diccionario no sustituye
esa prueba. Nunca ejecutar el SQL de referencia sobre una base existente ni usar
`stamp` para aparentar una restauración.

## Convenciones

En las tablas, **Null Sí** permite ausencia; **No** incluye PK implícitamente NOT
NULL. **Sin default** exige valor para NOT NULL o permite null si la columna es
nullable. `now()` es el instante de inicio de transacción PostgreSQL; los servicios
pueden suministrar su instante efectivo explícitamente. Los instantes `timestamptz`
se operan en UTC y se muestran en America/Lima; `date` conserva el día académico.
UUID no es una escala ni una autorización. SHA-256 usa 64 dígitos hexadecimales.

Las PK/UNIQUE generan índices PostgreSQL; abajo se enumeran todos los índices efectivos,
incluidos los generados. Las FK no usan borrado en cascada. Las comprobaciones por rol/sección,
procedencia, revisión consecutiva y política ML siguen siendo parte de los servicios.
El ORM no se usa para autogenerar este esquema.

`data_origin` conserva DEMO histórico en el dominio amplio. El CHECK adicional
`processing_origin` restringe nuevas escrituras a REAL/SYNTHETIC en nueve tablas.
La migración usa NOT VALID para no reetiquetar historia; valida el constraint cuando
no existe DEMO histórico. REAL en un campo nunca habilita procesamiento institucional.

## 1. `app_users`

Identidad local y autorización. password_hash contiene el hash Argon2; ninguna proyección pública incluye ese campo. El rol y actividad se vuelven a consultar al autorizar la sesión. La creación de cuentas es explícita, sin semilla de arranque.

| Columna | Tipo PostgreSQL | Null | Default | Restricción de columna |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | No | `gen_random_uuid()` | `PRIMARY KEY` |
| `email` | `text` | No | Sin default | `UNIQUE`; `CHECK (email = lower(email))` |
| `display_name` | `text` | No | Sin default | — |
| `password_hash` | `text` | No | Sin default | — |
| `role` | `text` | No | Sin default | `CHECK (role IN ('ADMIN', 'TUTOR', 'DIRECTOR', 'RESEARCHER'))` |
| `is_active` | `boolean` | No | `TRUE` | — |
| `created_at` | `timestamptz` | No | `now()` | — |

Restricciones efectivas PostgreSQL (incluyen PK y checks de columnas):

- `app_users_email_check`: `CHECK ((email = lower(email)))`.
- `app_users_email_key`: `UNIQUE (email)`.
- `app_users_pkey`: `PRIMARY KEY (id)`.
- `app_users_role_check`: `CHECK ((role = ANY (ARRAY['ADMIN'::text, 'TUTOR'::text, 'DIRECTOR'::text, 'RESEARCHER'::text])))`.

Índices efectivos (también los de PK/UNIQUE):

- `app_users_email_key`: `CREATE UNIQUE INDEX app_users_email_key ON risk_school.app_users USING btree (email)`.
- `app_users_pkey`: `CREATE UNIQUE INDEX app_users_pkey ON risk_school.app_users USING btree (id)`.

## 2. `user_sessions`

Sesiones de ocho horas según la configuración vigente. Guarda digests, no la cookie ni el CSRF bruto. La revocación marca revoked_at; no elimina la sesión anterior.

| Columna | Tipo PostgreSQL | Null | Default | Restricción de columna |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | No | `gen_random_uuid()` | `PRIMARY KEY` |
| `user_id` | `uuid` | No | Sin default | `REFERENCES app_users (id) ON DELETE RESTRICT` |
| `token_digest` | `char(64)` | No | Sin default | `UNIQUE`; `CHECK (token_digest ~ '^[0-9a-f]{64}$')` |
| `csrf_digest` | `char(64)` | No | Sin default | `CHECK (csrf_digest ~ '^[0-9a-f]{64}$')` |
| `expires_at` | `timestamptz` | No | Sin default | — |
| `revoked_at` | `timestamptz` | Sí | Sin default | — |
| `created_at` | `timestamptz` | No | `now()` | — |

Restricciones efectivas PostgreSQL (incluyen PK y checks de columnas):

- `user_sessions_check`: `CHECK ((expires_at > created_at))`.
- `user_sessions_csrf_digest_check`: `CHECK ((csrf_digest ~ '^[0-9a-f]{64}$'::text))`.
- `user_sessions_pkey`: `PRIMARY KEY (id)`.
- `user_sessions_token_digest_check`: `CHECK ((token_digest ~ '^[0-9a-f]{64}$'::text))`.
- `user_sessions_token_digest_key`: `UNIQUE (token_digest)`.
- `user_sessions_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES risk_school.app_users(id) ON DELETE RESTRICT`.

Índices efectivos (también los de PK/UNIQUE):

- `ix_sessions_user_expires`: `CREATE INDEX ix_sessions_user_expires ON risk_school.user_sessions USING btree (user_id, expires_at)`.
- `user_sessions_pkey`: `CREATE UNIQUE INDEX user_sessions_pkey ON risk_school.user_sessions USING btree (id)`.
- `user_sessions_token_digest_key`: `CREATE UNIQUE INDEX user_sessions_token_digest_key ON risk_school.user_sessions USING btree (token_digest)`.

## 3. `academic_periods`

Calendario y bloqueo operativo. El año delimita el catálogo de secciones. Bloquear impide nuevas escrituras; las lecturas autorizadas del contexto siguen disponibles.

| Columna | Tipo PostgreSQL | Null | Default | Restricción de columna |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | No | `gen_random_uuid()` | `PRIMARY KEY` |
| `code` | `text` | No | Sin default | — |
| `school_year` | `smallint` | No | Sin default | `CHECK (school_year BETWEEN 2000 AND 2100)` |
| `start_date` | `date` | No | Sin default | — |
| `end_date` | `date` | No | Sin default | — |
| `data_origin` | `text` | No | Sin default | `CHECK (data_origin IN ('DEMO', 'REAL', 'SYNTHETIC'))` |
| `is_locked` | `boolean` | No | `FALSE` | — |
| `created_at` | `timestamptz` | No | `now()` | — |

Restricciones efectivas PostgreSQL (incluyen PK y checks de columnas):

- `academic_periods_check`: `CHECK ((end_date > start_date))`.
- `academic_periods_code_data_origin_key`: `UNIQUE (code, data_origin)`.
- `academic_periods_data_origin_check`: `CHECK ((data_origin = ANY (ARRAY['DEMO'::text, 'REAL'::text, 'SYNTHETIC'::text])))`.
- `academic_periods_id_data_origin_key`: `UNIQUE (id, data_origin)`.
- `academic_periods_pkey`: `PRIMARY KEY (id)`.
- `academic_periods_school_year_check`: `CHECK (((school_year >= 2000) AND (school_year <= 2100)))`.
- `processing_origin`: `CHECK ((data_origin = ANY (ARRAY['REAL'::text, 'SYNTHETIC'::text])))`.

Índices efectivos (también los de PK/UNIQUE):

- `academic_periods_code_data_origin_key`: `CREATE UNIQUE INDEX academic_periods_code_data_origin_key ON risk_school.academic_periods USING btree (code, data_origin)`.
- `academic_periods_id_data_origin_key`: `CREATE UNIQUE INDEX academic_periods_id_data_origin_key ON risk_school.academic_periods USING btree (id, data_origin)`.
- `academic_periods_pkey`: `CREATE UNIQUE INDEX academic_periods_pkey ON risk_school.academic_periods USING btree (id)`.

## 4. `grade_sections`

Sección única por grado, código y año. tutor_id puede ser null. El servicio exige tutor activo y rol TUTOR al configurarlo; la FK por sí sola no acredita ese rol.

| Columna | Tipo PostgreSQL | Null | Default | Restricción de columna |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | No | `gen_random_uuid()` | `PRIMARY KEY` |
| `code` | `text` | No | Sin default | — |
| `grade` | `smallint` | No | Sin default | `CHECK (grade BETWEEN 1 AND 5)` |
| `school_year` | `smallint` | No | Sin default | `CHECK (school_year BETWEEN 2000 AND 2100)` |
| `tutor_id` | `uuid` | Sí | Sin default | `REFERENCES app_users (id) ON DELETE RESTRICT` |

Restricciones efectivas PostgreSQL (incluyen PK y checks de columnas):

- `grade_sections_grade_check`: `CHECK (((grade >= 1) AND (grade <= 5)))`.
- `grade_sections_grade_code_school_year_key`: `UNIQUE (grade, code, school_year)`.
- `grade_sections_pkey`: `PRIMARY KEY (id)`.
- `grade_sections_school_year_check`: `CHECK (((school_year >= 2000) AND (school_year <= 2100)))`.
- `grade_sections_tutor_id_fkey`: `FOREIGN KEY (tutor_id) REFERENCES risk_school.app_users(id) ON DELETE RESTRICT`.

Índices efectivos (también los de PK/UNIQUE):

- `grade_sections_grade_code_school_year_key`: `CREATE UNIQUE INDEX grade_sections_grade_code_school_year_key ON risk_school.grade_sections USING btree (grade, code, school_year)`.
- `grade_sections_pkey`: `CREATE UNIQUE INDEX grade_sections_pkey ON risk_school.grade_sections USING btree (id)`.
- `ix_sections_tutor`: `CREATE INDEX ix_sections_tutor ON risk_school.grade_sections USING btree (tutor_id)`.

## 5. `students`

Código seudónimo/sintético, actividad y elegibilidad. SYNTHETIC no finge consentimiento: los indicadores documentales pueden permanecer false. REAL sigue bloqueado aunque una fila indique elegibilidad.

| Columna | Tipo PostgreSQL | Null | Default | Restricción de columna |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | No | `gen_random_uuid()` | `PRIMARY KEY` |
| `anon_code` | `text` | No | Sin default | `UNIQUE`; `CHECK (length(anon_code) BETWEEN 3 AND 40)` |
| `data_origin` | `text` | No | Sin default | `CHECK (data_origin IN ('DEMO', 'REAL', 'SYNTHETIC'))` |
| `is_active` | `boolean` | No | `TRUE` | — |
| `eligible_for_processing` | `boolean` | No | `FALSE` | — |
| `consent_documented` | `boolean` | No | `FALSE` | — |
| `assent_documented` | `boolean` | No | `FALSE` | — |
| `created_at` | `timestamptz` | No | `now()` | — |

Restricciones efectivas PostgreSQL (incluyen PK y checks de columnas):

- `processing_origin`: `CHECK ((data_origin = ANY (ARRAY['REAL'::text, 'SYNTHETIC'::text])))`.
- `students_anon_code_check`: `CHECK (((length(anon_code) >= 3) AND (length(anon_code) <= 40)))`.
- `students_anon_code_key`: `UNIQUE (anon_code)`.
- `students_data_origin_check`: `CHECK ((data_origin = ANY (ARRAY['DEMO'::text, 'REAL'::text, 'SYNTHETIC'::text])))`.
- `students_eligibility_check`: `CHECK (((data_origin = ANY (ARRAY['DEMO'::text, 'SYNTHETIC'::text])) OR (NOT eligible_for_processing) OR (consent_documented AND assent_documented)))`.
- `students_id_data_origin_key`: `UNIQUE (id, data_origin)`.
- `students_pkey`: `PRIMARY KEY (id)`.

Índices efectivos (también los de PK/UNIQUE):

- `students_anon_code_key`: `CREATE UNIQUE INDEX students_anon_code_key ON risk_school.students USING btree (anon_code)`.
- `students_id_data_origin_key`: `CREATE UNIQUE INDEX students_id_data_origin_key ON risk_school.students USING btree (id, data_origin)`.
- `students_pkey`: `CREATE UNIQUE INDEX students_pkey ON risk_school.students USING btree (id)`.

## 6. `enrollments`

Unidad de consulta y seguimiento por estudiante/periodo. Conserva origen común con estudiante y periodo y pertenece a una sección. El servicio comprueba año y pertenencia al contexto registrado; una FK aislada no valida el manifiesto.

| Columna | Tipo PostgreSQL | Null | Default | Restricción de columna |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | No | `gen_random_uuid()` | `PRIMARY KEY` |
| `student_id` | `uuid` | No | Sin default | — |
| `period_id` | `uuid` | No | Sin default | — |
| `section_id` | `uuid` | No | Sin default | `REFERENCES grade_sections (id) ON DELETE RESTRICT` |
| `data_origin` | `text` | No | Sin default | `CHECK (data_origin IN ('DEMO', 'REAL', 'SYNTHETIC'))` |
| `created_at` | `timestamptz` | No | `now()` | — |

Restricciones efectivas PostgreSQL (incluyen PK y checks de columnas):

- `enrollments_data_origin_check`: `CHECK ((data_origin = ANY (ARRAY['DEMO'::text, 'REAL'::text, 'SYNTHETIC'::text])))`.
- `enrollments_id_data_origin_key`: `UNIQUE (id, data_origin)`.
- `enrollments_id_period_id_data_origin_key`: `UNIQUE (id, period_id, data_origin)`.
- `enrollments_period_id_data_origin_fkey`: `FOREIGN KEY (period_id, data_origin) REFERENCES risk_school.academic_periods(id, data_origin)`.
- `enrollments_pkey`: `PRIMARY KEY (id)`.
- `enrollments_section_id_fkey`: `FOREIGN KEY (section_id) REFERENCES risk_school.grade_sections(id) ON DELETE RESTRICT`.
- `enrollments_student_id_data_origin_fkey`: `FOREIGN KEY (student_id, data_origin) REFERENCES risk_school.students(id, data_origin)`.
- `enrollments_student_id_period_id_key`: `UNIQUE (student_id, period_id)`.
- `processing_origin`: `CHECK ((data_origin = ANY (ARRAY['REAL'::text, 'SYNTHETIC'::text])))`.

Índices efectivos (también los de PK/UNIQUE):

- `enrollments_id_data_origin_key`: `CREATE UNIQUE INDEX enrollments_id_data_origin_key ON risk_school.enrollments USING btree (id, data_origin)`.
- `enrollments_id_period_id_data_origin_key`: `CREATE UNIQUE INDEX enrollments_id_period_id_data_origin_key ON risk_school.enrollments USING btree (id, period_id, data_origin)`.
- `enrollments_pkey`: `CREATE UNIQUE INDEX enrollments_pkey ON risk_school.enrollments USING btree (id)`.
- `enrollments_student_id_period_id_key`: `CREATE UNIQUE INDEX enrollments_student_id_period_id_key ON risk_school.enrollments USING btree (student_id, period_id)`.
- `ix_enrollments_period_section`: `CREATE INDEX ix_enrollments_period_section ON risk_school.enrollments USING btree (period_id, section_id)`.

## 7. `synthetic_studies`

Registro de procedencia privada del estudio. id se suministra determinísticamente, sin DEFAULT de UUID. config/manifest/storage_key/bindings/comparison son evidencia interna; las etiquetas y resultados futuros viven en el payload privado, no en columnas públicas.

| Columna | Tipo PostgreSQL | Null | Default | Restricción de columna |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | No | Sin default | `PRIMARY KEY` |
| `period_id` | `uuid` | No | Sin default | `UNIQUE` |
| `data_origin` | `text` | No | Sin default | `CHECK (data_origin = 'SYNTHETIC')` |
| `generator_version` | `text` | No | Sin default | `CHECK (generator_version = 'synthetic-generator-v1')` |
| `seed` | `bigint` | No | Sin default | `CHECK (seed >= 0 AND seed < 4294967296)` |
| `config` | `jsonb` | No | Sin default | — |
| `manifest` | `jsonb` | No | Sin default | — |
| `csv_sha256` | `char(64)` | No | Sin default | `CHECK (csv_sha256 ~ '^[0-9a-f]{64}$')` |
| `storage_key` | `text` | No | Sin default | `UNIQUE`; `CHECK (storage_key ~ '^[0-9a-f]{32}\.json$')` |
| `payload_sha256` | `char(64)` | No | Sin default | `CHECK (payload_sha256 ~ '^[0-9a-f]{64}$')` |
| `bindings` | `jsonb` | No | `'[]'::jsonb` | `CHECK (jsonb_typeof(bindings) = 'array')` |
| `comparison` | `jsonb` | Sí | Sin default | `CHECK (comparison IS NULL OR jsonb_typeof(comparison) = 'object')` |
| `created_by` | `uuid` | No | Sin default | `REFERENCES risk_school.app_users (id)` |
| `created_at` | `timestamptz` | No | `now()` | — |

Restricciones efectivas PostgreSQL (incluyen PK y checks de columnas):

- `synthetic_studies_bindings_check`: `CHECK ((jsonb_typeof(bindings) = 'array'::text))`.
- `synthetic_studies_comparison_check`: `CHECK (((comparison IS NULL) OR (jsonb_typeof(comparison) = 'object'::text)))`.
- `synthetic_studies_created_by_fkey`: `FOREIGN KEY (created_by) REFERENCES risk_school.app_users(id)`.
- `synthetic_studies_csv_sha256_check`: `CHECK ((csv_sha256 ~ '^[0-9a-f]{64}$'::text))`.
- `synthetic_studies_data_origin_check`: `CHECK ((data_origin = 'SYNTHETIC'::text))`.
- `synthetic_studies_generator_version_check`: `CHECK ((generator_version = 'synthetic-generator-v1'::text))`.
- `synthetic_studies_id_data_origin_key`: `UNIQUE (id, data_origin)`.
- `synthetic_studies_id_period_id_data_origin_csv_sha256_key`: `UNIQUE (id, period_id, data_origin, csv_sha256)`.
- `synthetic_studies_payload_sha256_check`: `CHECK ((payload_sha256 ~ '^[0-9a-f]{64}$'::text))`.
- `synthetic_studies_period_id_data_origin_fkey`: `FOREIGN KEY (period_id, data_origin) REFERENCES risk_school.academic_periods(id, data_origin)`.
- `synthetic_studies_period_id_key`: `UNIQUE (period_id)`.
- `synthetic_studies_pkey`: `PRIMARY KEY (id)`.
- `synthetic_studies_seed_check`: `CHECK (((seed >= 0) AND (seed < '4294967296'::bigint)))`.
- `synthetic_studies_storage_key_check`: `CHECK ((storage_key ~ '^[0-9a-f]{32}\.json$'::text))`.
- `synthetic_studies_storage_key_key`: `UNIQUE (storage_key)`.

Índices efectivos (también los de PK/UNIQUE):

- `synthetic_studies_id_data_origin_key`: `CREATE UNIQUE INDEX synthetic_studies_id_data_origin_key ON risk_school.synthetic_studies USING btree (id, data_origin)`.
- `synthetic_studies_id_period_id_data_origin_csv_sha256_key`: `CREATE UNIQUE INDEX synthetic_studies_id_period_id_data_origin_csv_sha256_key ON risk_school.synthetic_studies USING btree (id, period_id, data_origin, csv_sha256)`.
- `synthetic_studies_period_id_key`: `CREATE UNIQUE INDEX synthetic_studies_period_id_key ON risk_school.synthetic_studies USING btree (period_id)`.
- `synthetic_studies_pkey`: `CREATE UNIQUE INDEX synthetic_studies_pkey ON risk_school.synthetic_studies USING btree (id)`.
- `synthetic_studies_storage_key_key`: `CREATE UNIQUE INDEX synthetic_studies_storage_key_key ON risk_school.synthetic_studies USING btree (storage_key)`.

## 8. `import_batches`

Lote y plan observado de vista previa. planned_* no son filas académicas confirmadas. preview_state es privado; la API publica conteos y errores sanitizados por fila/campo. El mismo archivo SHA-256 y periodo reutiliza el lote.

| Columna | Tipo PostgreSQL | Null | Default | Restricción de columna |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | No | `gen_random_uuid()` | `PRIMARY KEY` |
| `study_id` | `uuid` | Sí | Sin default | — |
| `period_id` | `uuid` | No | Sin default | — |
| `data_origin` | `text` | No | Sin default | `CHECK (data_origin IN ('DEMO', 'REAL', 'SYNTHETIC'))` |
| `created_by` | `uuid` | No | Sin default | `REFERENCES app_users (id)` |
| `file_name` | `text` | No | Sin default | — |
| `file_sha256` | `char(64)` | No | Sin default | `CHECK (file_sha256 ~ '^[0-9a-f]{64}$')` |
| `schema_version` | `text` | No | `'academic-v1'` | — |
| `storage_key` | `text` | No | Sin default | — |
| `status` | `text` | No | `'PREVIEW'` | `CHECK (status IN ('PREVIEW', 'READY', 'COMMITTED', 'FAILED'))` |
| `total_rows` | `integer` | No | `0` | `CHECK (total_rows >= 0)` |
| `valid_rows` | `integer` | No | `0` | `CHECK (valid_rows >= 0)` |
| `invalid_rows` | `integer` | No | `0` | `CHECK (invalid_rows >= 0)` |
| `planned_students` | `integer` | No | `0` | `CHECK (planned_students >= 0)` |
| `planned_enrollments` | `integer` | No | `0` | `CHECK (planned_enrollments >= 0)` |
| `planned_snapshots` | `integer` | No | `0` | `CHECK (planned_snapshots >= 0)` |
| `preview_version` | `integer` | No | `1` | `CHECK (preview_version >= 1)` |
| `preview_state` | `jsonb` | No | `'[]'::jsonb` | `CHECK (jsonb_typeof(preview_state) = 'array')` |
| `errors` | `jsonb` | No | `'[]'::jsonb` | — |
| `committed_at` | `timestamptz` | Sí | Sin default | — |
| `created_at` | `timestamptz` | No | `now()` | — |

Restricciones efectivas PostgreSQL (incluyen PK y checks de columnas):

- `import_batches_check`: `CHECK (((valid_rows + invalid_rows) = total_rows))`.
- `import_batches_check1`: `CHECK (((planned_students <= valid_rows) AND (planned_enrollments <= valid_rows) AND (planned_snapshots <= valid_rows)))`.
- `import_batches_check2`: `CHECK (((status <> 'COMMITTED'::text) OR ((invalid_rows = 0) AND (committed_at IS NOT NULL))))`.
- `import_batches_created_by_fkey`: `FOREIGN KEY (created_by) REFERENCES risk_school.app_users(id)`.
- `import_batches_data_origin_check`: `CHECK ((data_origin = ANY (ARRAY['DEMO'::text, 'REAL'::text, 'SYNTHETIC'::text])))`.
- `import_batches_file_sha256_check`: `CHECK ((file_sha256 ~ '^[0-9a-f]{64}$'::text))`.
- `import_batches_id_period_id_data_origin_key`: `UNIQUE (id, period_id, data_origin)`.
- `import_batches_invalid_rows_check`: `CHECK ((invalid_rows >= 0))`.
- `import_batches_period_id_data_origin_fkey`: `FOREIGN KEY (period_id, data_origin) REFERENCES risk_school.academic_periods(id, data_origin)`.
- `import_batches_period_id_file_sha256_key`: `UNIQUE (period_id, file_sha256)`.
- `import_batches_pkey`: `PRIMARY KEY (id)`.
- `import_batches_planned_enrollments_check`: `CHECK ((planned_enrollments >= 0))`.
- `import_batches_planned_snapshots_check`: `CHECK ((planned_snapshots >= 0))`.
- `import_batches_planned_students_check`: `CHECK ((planned_students >= 0))`.
- `import_batches_preview_state_check`: `CHECK ((jsonb_typeof(preview_state) = 'array'::text))`.
- `import_batches_preview_version_check`: `CHECK ((preview_version >= 1))`.
- `import_batches_status_check`: `CHECK ((status = ANY (ARRAY['PREVIEW'::text, 'READY'::text, 'COMMITTED'::text, 'FAILED'::text])))`.
- `import_batches_study_origin_fk`: `FOREIGN KEY (study_id, data_origin) REFERENCES risk_school.synthetic_studies(id, data_origin)`.
- `import_batches_synthetic_provenance`: `CHECK (((data_origin = 'SYNTHETIC'::text) = (study_id IS NOT NULL)))`.
- `import_batches_total_rows_check`: `CHECK ((total_rows >= 0))`.
- `import_batches_total_rows_check1`: `CHECK ((total_rows <= 10000))`.
- `import_batches_valid_rows_check`: `CHECK ((valid_rows >= 0))`.
- `import_registered_csv_fk`: `FOREIGN KEY (study_id, period_id, data_origin, file_sha256) REFERENCES risk_school.synthetic_studies(id, period_id, data_origin, csv_sha256)`.
- `processing_origin`: `CHECK ((data_origin = ANY (ARRAY['REAL'::text, 'SYNTHETIC'::text])))`.

Índices efectivos (también los de PK/UNIQUE):

- `import_batches_id_period_id_data_origin_key`: `CREATE UNIQUE INDEX import_batches_id_period_id_data_origin_key ON risk_school.import_batches USING btree (id, period_id, data_origin)`.
- `import_batches_period_id_file_sha256_key`: `CREATE UNIQUE INDEX import_batches_period_id_file_sha256_key ON risk_school.import_batches USING btree (period_id, file_sha256)`.
- `import_batches_pkey`: `CREATE UNIQUE INDEX import_batches_pkey ON risk_school.import_batches USING btree (id)`.

## 9. `academic_snapshots`

Evidencia académica inmutable. Las seis mediciones aceptan null; missing_fraction se calcula en servidor sobre esas seis. Las escalas SQL heredadas no acreditan escalas institucionales; el protocolo sintético y ML aplican su configuración explícita.

| Columna | Tipo PostgreSQL | Null | Default | Restricción de columna |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | No | `gen_random_uuid()` | `PRIMARY KEY` |
| `enrollment_id` | `uuid` | No | Sin default | — |
| `period_id` | `uuid` | No | Sin default | — |
| `data_origin` | `text` | No | Sin default | `CHECK (data_origin IN ('DEMO', 'REAL', 'SYNTHETIC'))` |
| `import_batch_id` | `uuid` | No | Sin default | — |
| `window_start` | `date` | No | Sin default | — |
| `cutoff_at` | `timestamptz` | No | Sin default | — |
| `available_at` | `timestamptz` | No | Sin default | — |
| `target_date` | `date` | No | Sin default | — |
| `revision` | `integer` | No | `1` | `CHECK (revision >= 1)` |
| `supersedes_id` | `uuid` | Sí | Sin default | — |
| `average_grade` | `numeric(5, 2)` | Sí | Sin default | `CHECK (average_grade BETWEEN 0 AND 20)` |
| `attendance_pct` | `numeric(5, 2)` | Sí | Sin default | `CHECK (attendance_pct BETWEEN 0 AND 100)` |
| `activities_pct` | `numeric(5, 2)` | Sí | Sin default | `CHECK (activities_pct BETWEEN 0 AND 100)` |
| `participation_level` | `smallint` | Sí | Sin default | `CHECK (participation_level BETWEEN 1 AND 3)` |
| `behavior_incidents` | `integer` | Sí | Sin default | `CHECK (behavior_incidents >= 0)` |
| `age_years` | `smallint` | Sí | Sin default | `CHECK (age_years BETWEEN 5 AND 25)` |
| `missing_fraction` | `numeric(5, 4)` | No | Sin default | `CHECK (missing_fraction BETWEEN 0 AND 1)` |
| `schema_version` | `text` | No | `'academic-v1'` | — |
| `source_row_number` | `integer` | No | Sin default | `CHECK (source_row_number >= 2)` |
| `row_sha256` | `char(64)` | No | Sin default | `CHECK (row_sha256 ~ '^[0-9a-f]{64}$')` |
| `created_at` | `timestamptz` | No | `now()` | — |

Restricciones efectivas PostgreSQL (incluyen PK y checks de columnas):

- `academic_snapshots_activities_pct_check`: `CHECK (((activities_pct >= (0)::numeric) AND (activities_pct <= (100)::numeric)))`.
- `academic_snapshots_age_years_check`: `CHECK (((age_years >= 5) AND (age_years <= 25)))`.
- `academic_snapshots_attendance_pct_check`: `CHECK (((attendance_pct >= (0)::numeric) AND (attendance_pct <= (100)::numeric)))`.
- `academic_snapshots_average_grade_check`: `CHECK (((average_grade >= (0)::numeric) AND (average_grade <= (20)::numeric)))`.
- `academic_snapshots_behavior_incidents_check`: `CHECK ((behavior_incidents >= 0))`.
- `academic_snapshots_check`: `CHECK (((supersedes_id IS NULL) OR (supersedes_id <> id)))`.
- `academic_snapshots_check1`: `CHECK ((available_at <= cutoff_at))`.
- `academic_snapshots_check2`: `CHECK ((window_start <= ((cutoff_at AT TIME ZONE 'America/Lima'::text))::date))`.
- `academic_snapshots_check3`: `CHECK ((target_date > ((cutoff_at AT TIME ZONE 'America/Lima'::text))::date))`.
- `academic_snapshots_data_origin_check`: `CHECK ((data_origin = ANY (ARRAY['DEMO'::text, 'REAL'::text, 'SYNTHETIC'::text])))`.
- `academic_snapshots_enrollment_id_cutoff_at_revision_key`: `UNIQUE (enrollment_id, cutoff_at, revision)`.
- `academic_snapshots_enrollment_id_period_id_data_origin_fkey`: `FOREIGN KEY (enrollment_id, period_id, data_origin) REFERENCES risk_school.enrollments(id, period_id, data_origin)`.
- `academic_snapshots_id_enrollment_id_cutoff_at_data_origin_key`: `UNIQUE (id, enrollment_id, cutoff_at, data_origin)`.
- `academic_snapshots_id_enrollment_id_data_origin_key`: `UNIQUE (id, enrollment_id, data_origin)`.
- `academic_snapshots_import_batch_id_period_id_data_origin_fkey`: `FOREIGN KEY (import_batch_id, period_id, data_origin) REFERENCES risk_school.import_batches(id, period_id, data_origin)`.
- `academic_snapshots_missing_fraction_check`: `CHECK (((missing_fraction >= (0)::numeric) AND (missing_fraction <= (1)::numeric)))`.
- `academic_snapshots_participation_level_check`: `CHECK (((participation_level >= 1) AND (participation_level <= 3)))`.
- `academic_snapshots_pkey`: `PRIMARY KEY (id)`.
- `academic_snapshots_revision_check`: `CHECK ((revision >= 1))`.
- `academic_snapshots_row_sha256_check`: `CHECK ((row_sha256 ~ '^[0-9a-f]{64}$'::text))`.
- `academic_snapshots_source_row_number_check`: `CHECK ((source_row_number >= 2))`.
- `academic_snapshots_supersedes_id_enrollment_id_cutoff_at_d_fkey`: `FOREIGN KEY (supersedes_id, enrollment_id, cutoff_at, data_origin) REFERENCES risk_school.academic_snapshots(id, enrollment_id, cutoff_at, data_origin)`.
- `processing_origin`: `CHECK ((data_origin = ANY (ARRAY['REAL'::text, 'SYNTHETIC'::text])))`.

Índices efectivos (también los de PK/UNIQUE):

- `academic_snapshots_enrollment_id_cutoff_at_revision_key`: `CREATE UNIQUE INDEX academic_snapshots_enrollment_id_cutoff_at_revision_key ON risk_school.academic_snapshots USING btree (enrollment_id, cutoff_at, revision)`.
- `academic_snapshots_id_enrollment_id_cutoff_at_data_origin_key`: `CREATE UNIQUE INDEX academic_snapshots_id_enrollment_id_cutoff_at_data_origin_key ON risk_school.academic_snapshots USING btree (id, enrollment_id, cutoff_at, data_origin)`.
- `academic_snapshots_id_enrollment_id_data_origin_key`: `CREATE UNIQUE INDEX academic_snapshots_id_enrollment_id_data_origin_key ON risk_school.academic_snapshots USING btree (id, enrollment_id, data_origin)`.
- `academic_snapshots_pkey`: `CREATE UNIQUE INDEX academic_snapshots_pkey ON risk_school.academic_snapshots USING btree (id)`.
- `ix_snapshots_enrollment_cutoff`: `CREATE INDEX ix_snapshots_enrollment_cutoff ON risk_school.academic_snapshots USING btree (enrollment_id, cutoff_at DESC, revision DESC)`.

## 10. `model_versions`

Registro técnico de un artefacto interno. dataset_hash, artifact_key, parámetros, métricas y manifiesto no se entregan por API. APPROVED y la activación SYNTHETIC significan simulación técnica; REAL no puede activarse.

| Columna | Tipo PostgreSQL | Null | Default | Restricción de columna |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | No | `gen_random_uuid()` | `PRIMARY KEY` |
| `study_id` | `uuid` | Sí | Sin default | — |
| `name` | `text` | No | Sin default | — |
| `version` | `text` | No | Sin default | — |
| `algorithm` | `text` | No | Sin default | `CHECK (algorithm IN ('DUMMY', 'RANDOM_FOREST', 'SVM', 'XGBOOST'))` |
| `data_origin` | `text` | No | Sin default | `CHECK (data_origin IN ('DEMO', 'REAL', 'SYNTHETIC'))` |
| `dataset_hash` | `char(64)` | No | Sin default | `CHECK (dataset_hash ~ '^[0-9a-f]{64}$')` |
| `artifact_sha256` | `char(64)` | No | Sin default | `CHECK (artifact_sha256 ~ '^[0-9a-f]{64}$')` |
| `artifact_key` | `text` | No | Sin default | — |
| `feature_schema_version` | `text` | No | Sin default | — |
| `reference_criterion_version` | `text` | No | Sin default | — |
| `status` | `text` | No | Sin default | `CHECK (status IN ('DRAFT', 'EVALUATED', 'APPROVED', 'RETIRED'))` |
| `is_active` | `boolean` | No | `FALSE` | — |
| `parameters` | `jsonb` | No | Sin default | — |
| `metrics` | `jsonb` | No | Sin default | — |
| `manifest` | `jsonb` | No | Sin default | — |
| `created_by` | `uuid` | Sí | Sin default | `REFERENCES app_users (id)` |
| `created_at` | `timestamptz` | No | `now()` | — |

Restricciones efectivas PostgreSQL (incluyen PK y checks de columnas):

- `model_versions_algorithm_check`: `CHECK ((algorithm = ANY (ARRAY['DUMMY'::text, 'RANDOM_FOREST'::text, 'SVM'::text, 'XGBOOST'::text])))`.
- `model_versions_artifact_sha256_check`: `CHECK ((artifact_sha256 ~ '^[0-9a-f]{64}$'::text))`.
- `model_versions_check`: `CHECK (((NOT is_active) OR (status = 'APPROVED'::text)))`.
- `model_versions_created_by_fkey`: `FOREIGN KEY (created_by) REFERENCES risk_school.app_users(id)`.
- `model_versions_data_origin_check`: `CHECK ((data_origin = ANY (ARRAY['DEMO'::text, 'REAL'::text, 'SYNTHETIC'::text])))`.
- `model_versions_dataset_hash_check`: `CHECK ((dataset_hash ~ '^[0-9a-f]{64}$'::text))`.
- `model_versions_id_data_origin_key`: `UNIQUE (id, data_origin)`.
- `model_versions_name_version_data_origin_key`: `UNIQUE (name, version, data_origin)`.
- `model_versions_pkey`: `PRIMARY KEY (id)`.
- `model_versions_status_check`: `CHECK ((status = ANY (ARRAY['DRAFT'::text, 'EVALUATED'::text, 'APPROVED'::text, 'RETIRED'::text])))`.
- `model_versions_study_origin_fk`: `FOREIGN KEY (study_id, data_origin) REFERENCES risk_school.synthetic_studies(id, data_origin)`.
- `model_versions_synthetic_provenance`: `CHECK (((data_origin = 'SYNTHETIC'::text) = (study_id IS NOT NULL)))`.
- `processing_origin`: `CHECK ((data_origin = ANY (ARRAY['REAL'::text, 'SYNTHETIC'::text])))`.
- `synthetic_only_active_model`: `CHECK (((NOT is_active) OR COALESCE(((data_origin = 'SYNTHETIC'::text) AND (status = 'APPROVED'::text) AND (study_id IS NOT NULL) AND ((manifest ->> 'scope'::text) = 'SYNTHETIC_STUDY'::text) AND ((manifest ->> 'data_origin'::text) = 'SYNTHETIC'::text) AND ((manifest ->> 'study_id'::text) = (study_id)::text) AND ((manifest ->> 'approval_kind'::text) = 'TECHNICAL_SIMULATION'::text)), false))) NOT VALID`.

Índices efectivos (también los de PK/UNIQUE):

- `model_versions_id_data_origin_key`: `CREATE UNIQUE INDEX model_versions_id_data_origin_key ON risk_school.model_versions USING btree (id, data_origin)`.
- `model_versions_name_version_data_origin_key`: `CREATE UNIQUE INDEX model_versions_name_version_data_origin_key ON risk_school.model_versions USING btree (name, version, data_origin)`.
- `model_versions_pkey`: `CREATE UNIQUE INDEX model_versions_pkey ON risk_school.model_versions USING btree (id)`.
- `ux_active_model_origin`: `CREATE UNIQUE INDEX ux_active_model_origin ON risk_school.model_versions USING btree (data_origin) WHERE is_active`.

## 11. `predictions`

Resultado evaluado de un corte y modelo. Una abstención no crea una fila. En el módulo vigente las tres probabilidades son null y probabilities_calibrated=false; tener predict_proba no acredita calibración.

| Columna | Tipo PostgreSQL | Null | Default | Restricción de columna |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | No | `gen_random_uuid()` | `PRIMARY KEY` |
| `enrollment_id` | `uuid` | No | Sin default | — |
| `snapshot_id` | `uuid` | No | Sin default | — |
| `model_id` | `uuid` | No | Sin default | — |
| `data_origin` | `text` | No | Sin default | `CHECK (data_origin IN ('DEMO', 'REAL', 'SYNTHETIC'))` |
| `risk_level` | `text` | No | Sin default | `CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH'))` |
| `probability_low` | `numeric(8, 7)` | Sí | Sin default | — |
| `probability_medium` | `numeric(8, 7)` | Sí | Sin default | — |
| `probability_high` | `numeric(8, 7)` | Sí | Sin default | — |
| `probabilities_calibrated` | `boolean` | No | `FALSE` | — |
| `predicted_at` | `timestamptz` | No | `now()` | — |

Restricciones efectivas PostgreSQL (incluyen PK y checks de columnas):

- `predictions_check`: `CHECK ((((probability_low IS NULL) AND (probability_medium IS NULL) AND (probability_high IS NULL)) OR ((probability_low IS NOT NULL) AND (probability_medium IS NOT NULL) AND (probability_high IS NOT NULL) AND ((probability_low >= (0)::numeric) AND (probability_low <= (1)::numeric)) AND ((probability_medium >= (0)::numeric) AND (probability_medium <= (1)::numeric)) AND ((probability_high >= (0)::numeric) AND (probability_high <= (1)::numeric)) AND (abs((((probability_low + probability_medium) + probability_high) - (1)::numeric)) <= 0.00001))))`.
- `predictions_check1`: `CHECK (((NOT probabilities_calibrated) OR (probability_low IS NOT NULL)))`.
- `predictions_data_origin_check`: `CHECK ((data_origin = ANY (ARRAY['DEMO'::text, 'REAL'::text, 'SYNTHETIC'::text])))`.
- `predictions_id_enrollment_id_data_origin_key`: `UNIQUE (id, enrollment_id, data_origin)`.
- `predictions_model_id_data_origin_fkey`: `FOREIGN KEY (model_id, data_origin) REFERENCES risk_school.model_versions(id, data_origin)`.
- `predictions_pkey`: `PRIMARY KEY (id)`.
- `predictions_risk_level_check`: `CHECK ((risk_level = ANY (ARRAY['LOW'::text, 'MEDIUM'::text, 'HIGH'::text])))`.
- `predictions_snapshot_id_enrollment_id_data_origin_fkey`: `FOREIGN KEY (snapshot_id, enrollment_id, data_origin) REFERENCES risk_school.academic_snapshots(id, enrollment_id, data_origin)`.
- `predictions_snapshot_id_model_id_key`: `UNIQUE (snapshot_id, model_id)`.
- `processing_origin`: `CHECK ((data_origin = ANY (ARRAY['REAL'::text, 'SYNTHETIC'::text])))`.

Índices efectivos (también los de PK/UNIQUE):

- `predictions_id_enrollment_id_data_origin_key`: `CREATE UNIQUE INDEX predictions_id_enrollment_id_data_origin_key ON risk_school.predictions USING btree (id, enrollment_id, data_origin)`.
- `predictions_pkey`: `CREATE UNIQUE INDEX predictions_pkey ON risk_school.predictions USING btree (id)`.
- `predictions_snapshot_id_model_id_key`: `CREATE UNIQUE INDEX predictions_snapshot_id_model_id_key ON risk_school.predictions USING btree (snapshot_id, model_id)`.

## 12. `alerts`

Caso de seguimiento, fuente y trabajo humano. severity es MEDIUM/HIGH de la fuente; puede diferir del riesgo actual del último corte. LOW no cierra un caso. assigned_to conserva el tutor inicial o null; no hay reasignación por interfaz.

| Columna | Tipo PostgreSQL | Null | Default | Restricción de columna |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | No | `gen_random_uuid()` | `PRIMARY KEY` |
| `enrollment_id` | `uuid` | No | Sin default | — |
| `prediction_id` | `uuid` | No | Sin default | — |
| `data_origin` | `text` | No | Sin default | `CHECK (data_origin IN ('DEMO', 'REAL', 'SYNTHETIC'))` |
| `assigned_to` | `uuid` | Sí | Sin default | `REFERENCES app_users (id)` |
| `severity` | `text` | No | Sin default | `CHECK (severity IN ('MEDIUM', 'HIGH'))` |
| `status` | `text` | No | `'OPEN'` | `CHECK (status IN ('OPEN', 'IN_REVIEW', 'RESOLVED', 'DISMISSED'))` |
| `resolution_reason` | `text` | Sí | Sin default | `CHECK (length(resolution_reason) <= 1000)` |
| `opened_at` | `timestamptz` | No | `now()` | — |
| `updated_at` | `timestamptz` | No | `now()` | — |
| `closed_at` | `timestamptz` | Sí | Sin default | — |
| `version` | `integer` | No | `1` | `CHECK (version >= 1)` |

Restricciones efectivas PostgreSQL (incluyen PK y checks de columnas):

- `alerts_assigned_to_fkey`: `FOREIGN KEY (assigned_to) REFERENCES risk_school.app_users(id)`.
- `alerts_check`: `CHECK ((((status = ANY (ARRAY['OPEN'::text, 'IN_REVIEW'::text])) AND (closed_at IS NULL)) OR ((status = ANY (ARRAY['RESOLVED'::text, 'DISMISSED'::text])) AND (closed_at IS NOT NULL) AND (length(btrim(resolution_reason)) > 0) AND (resolution_reason IS NOT NULL))))`.
- `alerts_data_origin_check`: `CHECK ((data_origin = ANY (ARRAY['DEMO'::text, 'REAL'::text, 'SYNTHETIC'::text])))`.
- `alerts_id_enrollment_id_data_origin_key`: `UNIQUE (id, enrollment_id, data_origin)`.
- `alerts_pkey`: `PRIMARY KEY (id)`.
- `alerts_prediction_id_enrollment_id_data_origin_fkey`: `FOREIGN KEY (prediction_id, enrollment_id, data_origin) REFERENCES risk_school.predictions(id, enrollment_id, data_origin)`.
- `alerts_resolution_reason_check`: `CHECK ((length(resolution_reason) <= 1000))`.
- `alerts_severity_check`: `CHECK ((severity = ANY (ARRAY['MEDIUM'::text, 'HIGH'::text])))`.
- `alerts_status_check`: `CHECK ((status = ANY (ARRAY['OPEN'::text, 'IN_REVIEW'::text, 'RESOLVED'::text, 'DISMISSED'::text])))`.
- `alerts_version_check`: `CHECK ((version >= 1))`.
- `processing_origin`: `CHECK ((data_origin = ANY (ARRAY['REAL'::text, 'SYNTHETIC'::text])))`.

Índices efectivos (también los de PK/UNIQUE):

- `alerts_id_enrollment_id_data_origin_key`: `CREATE UNIQUE INDEX alerts_id_enrollment_id_data_origin_key ON risk_school.alerts USING btree (id, enrollment_id, data_origin)`.
- `alerts_pkey`: `CREATE UNIQUE INDEX alerts_pkey ON risk_school.alerts USING btree (id)`.
- `ix_alerts_status_severity`: `CREATE INDEX ix_alerts_status_severity ON risk_school.alerts USING btree (status, severity, opened_at)`.
- `ux_active_alert_enrollment`: `CREATE UNIQUE INDEX ux_active_alert_enrollment ON risk_school.alerts USING btree (enrollment_id) WHERE (status = ANY (ARRAY['OPEN'::text, 'IN_REVIEW'::text]))`.

## 13. `interventions`

Actividad interna de un caso. El esquema permite alert_id y la pareja de creación null para evidencia histórica; el trigger vigente exige caso activo y pareja no nula en nuevas inserciones. PLANNED no cuenta como realizada.

| Columna | Tipo PostgreSQL | Null | Default | Restricción de columna |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | No | `gen_random_uuid()` | `PRIMARY KEY` |
| `enrollment_id` | `uuid` | No | Sin default | — |
| `alert_id` | `uuid` | Sí | Sin default | — |
| `data_origin` | `text` | No | Sin default | `CHECK (data_origin IN ('DEMO', 'REAL', 'SYNTHETIC'))` |
| `created_by` | `uuid` | No | Sin default | `REFERENCES app_users (id)` |
| `kind` | `text` | No | Sin default | `CHECK (kind IN ('TUTORING', 'REINFORCEMENT', 'FAMILY_MEETING', 'OTHER'))` |
| `objective` | `text` | No | Sin default | `CHECK (length(btrim(objective)) BETWEEN 1 AND 1000)` |
| `status` | `text` | No | `'PLANNED'` | `CHECK (status IN ('PLANNED', 'DONE', 'CANCELLED'))` |
| `scheduled_at` | `timestamptz` | No | Sin default | — |
| `performed_at` | `timestamptz` | Sí | Sin default | — |
| `notes` | `text` | Sí | Sin default | `CHECK (length(notes) <= 2000)` |
| `version` | `integer` | No | `1` | `CHECK (version >= 1)` |
| `created_at` | `timestamptz` | No | `now()` | — |
| `updated_at` | `timestamptz` | No | `now()` | — |
| `creation_key` | `uuid` | Sí | Sin default | — |
| `creation_payload_sha256` | `char(64)` | Sí | Sin default | — |

Restricciones efectivas PostgreSQL (incluyen PK y checks de columnas):

- `intervention_creation_digest`: `CHECK ((((creation_key IS NULL) AND (creation_payload_sha256 IS NULL)) OR ((creation_key IS NOT NULL) AND (creation_payload_sha256 ~ '^[0-9a-f]{64}$'::text))))`.
- `interventions_alert_id_enrollment_id_data_origin_fkey`: `FOREIGN KEY (alert_id, enrollment_id, data_origin) REFERENCES risk_school.alerts(id, enrollment_id, data_origin)`.
- `interventions_check`: `CHECK ((((status = 'DONE'::text) AND (performed_at IS NOT NULL)) OR ((status <> 'DONE'::text) AND (performed_at IS NULL))))`.
- `interventions_created_by_fkey`: `FOREIGN KEY (created_by) REFERENCES risk_school.app_users(id)`.
- `interventions_data_origin_check`: `CHECK ((data_origin = ANY (ARRAY['DEMO'::text, 'REAL'::text, 'SYNTHETIC'::text])))`.
- `interventions_enrollment_id_data_origin_fkey`: `FOREIGN KEY (enrollment_id, data_origin) REFERENCES risk_school.enrollments(id, data_origin)`.
- `interventions_kind_check`: `CHECK ((kind = ANY (ARRAY['TUTORING'::text, 'REINFORCEMENT'::text, 'FAMILY_MEETING'::text, 'OTHER'::text])))`.
- `interventions_notes_check`: `CHECK ((length(notes) <= 2000))`.
- `interventions_objective_check`: `CHECK (((length(btrim(objective)) >= 1) AND (length(btrim(objective)) <= 1000)))`.
- `interventions_pkey`: `PRIMARY KEY (id)`.
- `interventions_status_check`: `CHECK ((status = ANY (ARRAY['PLANNED'::text, 'DONE'::text, 'CANCELLED'::text])))`.
- `interventions_version_check`: `CHECK ((version >= 1))`.
- `processing_origin`: `CHECK ((data_origin = ANY (ARRAY['REAL'::text, 'SYNTHETIC'::text])))`.

Índices efectivos (también los de PK/UNIQUE):

- `interventions_pkey`: `CREATE UNIQUE INDEX interventions_pkey ON risk_school.interventions USING btree (id)`.
- `ix_interventions_enrollment`: `CREATE INDEX ix_interventions_enrollment ON risk_school.interventions USING btree (enrollment_id, scheduled_at)`.
- `ux_intervention_actor_creation_key`: `CREATE UNIQUE INDEX ux_intervention_actor_creation_key ON risk_school.interventions USING btree (created_by, creation_key) WHERE (creation_key IS NOT NULL)`.

## 14. `audit_events`

Eventos añadidos junto con el cambio en una transacción. entity_id es una referencia genérica sin FK por tabla; request_id permite correlación sanitizada. payload no incluye contraseñas, cookies, tokens o filas privadas en logs/publicaciones.

| Columna | Tipo PostgreSQL | Null | Default | Restricción de columna |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | No | `gen_random_uuid()` | `PRIMARY KEY` |
| `actor_id` | `uuid` | Sí | Sin default | `REFERENCES app_users (id)` |
| `entity_type` | `text` | No | Sin default | — |
| `entity_id` | `uuid` | Sí | Sin default | — |
| `action` | `text` | No | Sin default | — |
| `request_id` | `uuid` | No | Sin default | — |
| `recorded_at` | `timestamptz` | No | `now()` | — |
| `payload` | `jsonb` | No | `'{}'::jsonb` | — |

Restricciones efectivas PostgreSQL (incluyen PK y checks de columnas):

- `audit_events_actor_id_fkey`: `FOREIGN KEY (actor_id) REFERENCES risk_school.app_users(id)`.
- `audit_events_pkey`: `PRIMARY KEY (id)`.

Índices efectivos (también los de PK/UNIQUE):

- `audit_events_pkey`: `CREATE UNIQUE INDEX audit_events_pkey ON risk_school.audit_events USING btree (id)`.
- `ix_audit_entity_time`: `CREATE INDEX ix_audit_entity_time ON risk_school.audit_events USING btree (entity_type, entity_id, recorded_at)`.

## 15. `followup_decisions`

Decisión inmutable de followup-policy-v1, única por predicción. Evita recrear un caso al repetir una predicción ya procesada, incluso tras cierre. NO_ALERT lleva alert_id=null; CREATED/UPDATED/RETAINED_LOW requieren caso.

| Columna | Tipo PostgreSQL | Null | Default | Restricción de columna |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | No | `gen_random_uuid()` | `PRIMARY KEY` |
| `prediction_id` | `uuid` | No | Sin default | `UNIQUE` |
| `enrollment_id` | `uuid` | No | Sin default | — |
| `data_origin` | `text` | No | Sin default | `CHECK (data_origin = 'SYNTHETIC')` |
| `study_id` | `uuid` | No | Sin default | — |
| `alert_id` | `uuid` | Sí | Sin default | — |
| `decision` | `text` | No | Sin default | `CHECK (decision IN ('CREATED', 'UPDATED', 'RETAINED_LOW', 'NO_ALERT'))` |
| `policy_version` | `text` | No | Sin default | `CHECK (policy_version = 'followup-policy-v1')` |
| `recorded_at` | `timestamptz` | No | `now()` | — |

Restricciones efectivas PostgreSQL (incluyen PK y checks de columnas):

- `followup_decisions_alert_id_enrollment_id_data_origin_fkey`: `FOREIGN KEY (alert_id, enrollment_id, data_origin) REFERENCES risk_school.alerts(id, enrollment_id, data_origin)`.
- `followup_decisions_check`: `CHECK ((((decision = 'NO_ALERT'::text) AND (alert_id IS NULL)) OR ((decision <> 'NO_ALERT'::text) AND (alert_id IS NOT NULL))))`.
- `followup_decisions_data_origin_check`: `CHECK ((data_origin = 'SYNTHETIC'::text))`.
- `followup_decisions_decision_check`: `CHECK ((decision = ANY (ARRAY['CREATED'::text, 'UPDATED'::text, 'RETAINED_LOW'::text, 'NO_ALERT'::text])))`.
- `followup_decisions_pkey`: `PRIMARY KEY (id)`.
- `followup_decisions_policy_version_check`: `CHECK ((policy_version = 'followup-policy-v1'::text))`.
- `followup_decisions_prediction_id_enrollment_id_data_origin_fkey`: `FOREIGN KEY (prediction_id, enrollment_id, data_origin) REFERENCES risk_school.predictions(id, enrollment_id, data_origin)`.
- `followup_decisions_prediction_id_key`: `UNIQUE (prediction_id)`.
- `followup_decisions_study_id_data_origin_fkey`: `FOREIGN KEY (study_id, data_origin) REFERENCES risk_school.synthetic_studies(id, data_origin)`.

Índices efectivos (también los de PK/UNIQUE):

- `followup_decisions_pkey`: `CREATE UNIQUE INDEX followup_decisions_pkey ON risk_school.followup_decisions USING btree (id)`.
- `followup_decisions_prediction_id_key`: `CREATE UNIQUE INDEX followup_decisions_prediction_id_key ON risk_school.followup_decisions USING btree (prediction_id)`.
- `ix_followup_decisions_alert`: `CREATE INDEX ix_followup_decisions_alert ON risk_school.followup_decisions USING btree (alert_id, recorded_at)`.

## Revisiones, decisiones y transiciones

- Corrección académica: nueva fila con `revision` y `supersedes_id`; la FK conserva
  matrícula, corte y origen. El servicio bloquea la serie, exige revisión anterior + 1
  y confirma junto con auditoría. No actualiza el corte anterior. Nueva revisión
  sin evaluación compatible queda pendiente; no hereda el riesgo anterior.
- Predicción: UNIQUE `(snapshot_id,model_id)`. Repetir reutiliza el resultado; el
  control de concurrencia conserva la evidencia previa. Solo resultados evaluados
  se insertan. El mapeo de clases usa `classes_`, no posición supuesta.
- Caso: índice parcial único por matrícula cuando OPEN/IN_REVIEW. OPEN permite
  IN_REVIEW/RESOLVED/DISMISSED; IN_REVIEW permite RESOLVED/DISMISSED. Cerrados son
  terminales con motivo y hora servidor. Repetir una decisión no reabre ni crea otro.
- Actividad: PLANNED permite edición/DONE/CANCELLED. DONE exige `performed_at`
  explícito no futuro; CANCELLED lo conserva null. Una actividad planificada antes
  del cierre puede completarse/cancelarse después si el periodo sigue abierto.
- Versiones: el servicio compara la esperada y el trigger exige incremento exacto
  de una versión por UPDATE. Un no-op evita UPDATE y no incrementa. La creación de
  actividad compara versión del caso y digest **original** por actor/UUID; el digest
  se conserva después de editarla. Los terminales no se reescriben.

## Funciones y triggers efectivos

| Función / trigger | Tablas y momento | Protección |
| --- | --- | --- |
| `deny_evidence_mutation` / `snapshots_immutable` | academic_snapshots, BEFORE UPDATE/DELETE | Corte inmutable; insertar otra revisión |
| `deny_evidence_mutation` / `predictions_immutable` | predictions, BEFORE UPDATE/DELETE | Predicción inmutable |
| `deny_evidence_mutation` / `audit_immutable` | audit_events, BEFORE UPDATE/DELETE | Auditoría añadida, sin sobrescritura |
| `check_snapshot_period` / `snapshot_period_guard` | academic_snapshots, BEFORE INSERT | Periodo abierto; ventana/corte/objetivo dentro del calendario, día Lima |
| `check_prediction_study` / `prediction_study_guard` | predictions, BEFORE INSERT | Lote del corte y modelo corresponden al mismo estudio SYNTHETIC |
| `check_study_evidence` / `study_evidence_guard` | synthetic_studies, BEFORE UPDATE/DELETE | Procedencia inmutable; bindings/comparison solo se incorporan una vez |
| `check_followup_change` / `alert_change_guard` | alerts, BEFORE INSERT/UPDATE | Caso nuevo OPEN/version1; contexto/asignación/apertura preservados; terminales, fuente no anterior y versión exacta |
| `check_followup_change` / `intervention_change_guard` | interventions, BEFORE INSERT/UPDATE | Nueva PLANNED con caso activo/clave/digest; terminales y evidencia original inmutables; fecha efectiva no futura |
| `check_followup_provenance` | Llamada por los guards de seguimiento | Periodo FOR SHARE abierto, SYNTHETIC, predicción/lote COMMITTED/modelo/estudio coherentes, sección/año registrados |
| `check_followup_decision` / `decision_provenance_guard` | followup_decisions, BEFORE INSERT | Estudio y decisión corresponden a la clase LOW/MEDIUM/HIGH y a la procedencia |
| `deny_evidence_mutation` / `decisions_immutable` | followup_decisions, BEFORE UPDATE/DELETE | Decisión inmutable |
| `deny_evidence_mutation` / `alerts_no_delete`, `interventions_no_delete` | alerts/interventions, BEFORE DELETE | Conserva evidencia de seguimiento |

Las funciones PL/pgSQL fijan `search_path=risk_school,pg_catalog`.
No son un protocolo de autorización institucional. Los servicios comprueban el
modelo compatible y corte actual; una FK no convierte una fuente antigua en vigente.

## Roles y permisos recuperables

El esquema y objetos pertenecen a `riesgo_owner`, usado para migración y tareas de
recuperación. La API usa `riesgo_app`: LOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE y
NOREPLICATION. Conexiones UTC; no CREATE en public; PUBLIC sin acceso general al
esquema risk_school. La aplicación recibe CONNECT a su DB y USAGE en risk_school.

| Privilegio riesgo_app | Tablas |
| --- | --- |
| SELECT/INSERT/UPDATE | app_users, user_sessions, academic_periods, grade_sections, students, enrollments, import_batches, model_versions, alerts, interventions, synthetic_studies |
| SELECT/INSERT | academic_snapshots, predictions, audit_events, followup_decisions |
| DELETE/TRUNCATE/DDL | Ninguna tabla de aplicación |

No hay RLS: la API aplica el alcance en el servidor para cada recurso/consulta,
incluido CSV. No se entrega una conexión DB al navegador ni a cada rol escolar.
EXECUTE de las funciones usadas se concede a riesgo_app y se retira de PUBLIC.
Alembic se opera por el propietario, sin conceder su modificación a la API.

Un dump de DB incluye objetos, datos, ownership y ACL, pero no crea por sí mismo
los roles globales ni respalda los volúmenes. La recuperación debe crear los dos
roles y restaurar grants/ownership sin operar la API como owner. Consulta el
[manual de respaldo](Manual_Respaldo_Restauracion.md). Restaurar los archivos ML
incluye `.internal-key` de HMAC: no reentrenar ni volver a firmar para reparar una copia.

## Datos privados y límites

Importaciones, payloads, datasets, etiquetas, particiones y artefactos permanecen
en los volúmenes privados fuera del checkout/web. Este manual describe campos y
restricciones, sin publicar filas, hashes de contraseña, tokens, claves o manifiestos
privados. Auditoría y sesiones completas sí forman parte de la fotografía/restauración,
pero los reportes públicos solo registran conteos y fingerprints globales permitidos.

No hay tablas nuevas de resultados escolares, eficacia, protocolo institucional o
etiquetas observadas de menores. La descripción del esquema no valida la tesis.
