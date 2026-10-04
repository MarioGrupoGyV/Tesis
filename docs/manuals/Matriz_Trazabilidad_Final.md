# Matriz final de trazabilidad

Esta matriz corresponde exclusivamente al software local de simulación S6.
SYNTHETIC no representa población escolar observada. La comprobación final y los
destinos efectivos se registran en [Estado S6](../planning/Estado_Sprint_6.md).
Los cierres anteriores mantienen sus hechos; los enlaces siguientes acreditan
el código y los recorridos de esta iteración, sin atribuir resultados académicos.

| Requisito | Módulo y persistencia | Operaciones o comando | Prueba y evidencia S6 | Estado |
| --- | --- | --- | --- | --- |
| Instalación nueva sin precargas | runtime_target, migraciones; 15 tablas | create/up, bootstrap-admin/configure | [Instalación A](../../tests/evidence/s6-install-verified-environment.json): fotografía inicial, riesgo_app, tres volúmenes nuevos | Comprobado |
| Acceso y revocación por cuatro roles | sesiones, usuarios, contexto; app_users/user_sessions/audit_events | login/me/csrf/logout, periods/sections | [Backend completo](../../tests/evidence/s6-backend-final.xml), revisión A/B/C con cuatro roles | Comprobado |
| Administrador propio y perfil privado | operator_profiles/windows_credentials; ninguna cuenta desde el registro | operator_profiles register-profile, study status --target --operator-profile | [16 pruebas Windows](../../tests/evidence/s6-profiles-native.json), perfiles HTTP A y [compatibilidad S2.2](../../tests/evidence/s6-profiles-legacy-live.json) | Comprobado |
| Primera importación desde interfaz | Datos, servicios/repo importación; import_batches/students/enrollments/academic_snapshots | imports/preview, imports/{id}, imports/{id}/commit | [Primera importación A](../../tests/evidence/s6-install-verified-import-playwright.json), test_s2_imports en suite final | Comprobado |
| Corrección, transacción y repetición CSV | revisión inmutable, locks por series y lote | expected_preview_version, 409 IMPORT_PREVIEW_STALE | Suite final: PostgreSQL real, rollback, concurrent commits, Lima/UTC, duplicados y permisos | Comprobado |
| Estudiantes, null e historial por sección | Estudiantes; students/enrollments/academic_snapshots/predictions | students, students/{id}, students/{id}/timeline | Suite final y revisiones A/B/C: listado paginado, filtro servidor, ajeno/inexistente seguro, historial largo | Comprobado |
| Estudio generado solo explícitamente | CLI sintético y núcleo ML; synthetic_studies/model_versions, volumen ml_data | study generate/export-csv/compare/register/activate --target | A: CSV reproducible, comparación en desarrollo, firmas, registro/activación TECHNICAL_SIMULATION | Comprobado |
| Separación por estudiante y reserva | backend/app/ml; pipeline y manifiestos privados | cuatro algoritmos CPU, comparación/inferencia | test_s3_ml/test_s3_1_ml: grupos, fugas, transformaciones solo train, reserva fuera de selección, round-trip | Comprobado como software |
| Predicción o abstención sin riesgo inventado | inferencia tipada/persistencia; predictions | models, models/{id}, predictions/run, predictions/{id} | A primera inferencia UI: 55 resultados/5 abstenciones; B/C reutilización, clases/fechas en suite final | Comprobado |
| Un caso activo por matrícula y decisiones inmutables | seguimiento; followup_decisions/alerts | POST alerts/sync, alerts, alerts/{id}, PATCH alerts/{id} | test_s5_followup: idempotencia/concurrencia/409; A seguimiento UI; B/C 55 decisiones/51 casos sin reapertura | Comprobado |
| Actividad planificada, realizada o cancelada | intervenciones; interventions/audit_events | POST interventions, PATCH interventions/{id} | A: dos actividades, fecha efectiva, conflicto real PG; B/C conserva dos anteriores | Comprobado |
| Resumen y exportación autorizados | Reportes; alcance y agregados servidor | reports/summary, reports/export.csv | A/B/C CSV efectivo: ADMIN/DIRECTOR 60, TUTOR 30, RESEARCHER denegado; BOM/filtros/sin notas libres | Comprobado |
| REAL bloqueado, roles/CSRF/versiones/periodo | política institucional y dependencias HTTP | 401/403/404/409/422, processing/status | Suite final y A: periodo bloqueado real/CSRF; B/C REAL rechazado sin procesamiento | Comprobado |
| Respaldo consistente completo y protegido | backup_restore/windows_dpapi; DB y dos volúmenes de archivos | backup/verify con destino explícito | [Paquete final](../../tests/evidence/s6-backup-final-code.json), DPAPI nativo, SHARE + snapshot exportado, finally de escritores | Comprobado |
| Restauración desde estado actual sin generador | restore-check; tres volúmenes nuevos, roles/ACL/HMAC | pg_restore custom, sin migración/stamp/refit/firma | [Restauración B](../../tests/evidence/s6-restore-final-code.json), comparación de todas las tablas y 17 archivos antes de login | Comprobado |
| Paquetes/rutas/collisiones no autorizados | validadores, guards de destino y extracción | rechazo previo a restauración | [Negativos sobre paquete real](../../tests/evidence/s6-backup-negative-final.json), pruebas Windows de recuperación | Comprobado |
| Persistencia tras reinicio | DB/import_data/ml_data propios | stop/up de B sin migrar | [Persistencia B](../../tests/evidence/s6-restored-final-persistence.json): todas las tablas, Alembic/esquema/roles y archivos iguales | Comprobado |
| Indisponibilidad real y recuperación | health/ready y errores sanitizados | Health 503; Error 503 en operaciones DB | [Fallo real B](../../tests/evidence/s6-restored-final-outage-infrastructure-failure.json): DB aislada detenida con web/API, finally de recuperación | Comprobado |
| Interfaz con estados/foco/contraste | React, formularios y listado/historial | navegación, teclado, conflicto sin reintento, cambio de actor | [Inspección visual](../../tests/evidence/s6-browser-visual-review.json): PNG abiertos, tres tamaños; mocks HTTP separados de PostgreSQL real | Comprobado |
| Contrato, tipos, build y dependencias conservados | OpenAPI 0.5.0, 27 operaciones; Alembic 0004 | generate:api/typecheck/build/pip check | [Build final](../../tests/evidence/s6-build-checks.json), checker S6 valida nuevas respuestas y hashes ejecutados | Comprobado |
| Activo e histórico preservados | cuatro cuentas y entradas Windows, evidencia S5, DEMO detenido | revisión C, sin restauración activa ni eliminación | [Revisión C](../../tests/evidence/s6-active-final-environment.json), checker compara huellas iniciales y respaldo histórico | Comprobado |
| Dataset y criterio institucional autorizados | protocolo institucional no habilitado | REAL rechazado | No se incorporan datos institucionales en S6 | Pendiente institucional |
| Validación prospectiva, eficacia e hipótesis | protocolo del estudio y revisión con asesor | Fuera del cierre local | Las métricas fabricadas solo prueban funcionamiento del software | Pendiente académica |
| TLS/despliegue, portabilidad DPAPI, auditoría integral | condiciones de otro entorno | No ejecutados en S6 | [Alcance y límites](Alcance_y_Limitaciones.md) | No ejecutado |

El [diccionario](Diccionario_Base_Datos.md) documenta el catálogo efectivo;
el [mapa de endpoints](Mapa_Endpoints.md) especifica las 27 operaciones, roles,
CSRF, errores y consumidores. Las capturas/inyecciones HTTP prueban estados de
interfaz. La caída real aislada y el dump restaurado son comprobaciones diferentes.
La limpieza destructiva opcional de copias S6 está documentada y se prueba con
guards; las copias de cierre se conservan detenidas, con sus volúmenes.

Cierre local **COMPROBADO**: A 11/11, B 5/5 y C 4/4 pruebas Playwright;
269 backend, 16 perfiles Windows, 29 recuperación, seis negativos de paquete real.
[Checker aprobado](../../tests/evidence/s6-final-verification-candidate.json) valida
202 nuevas respuestas, destinos y hashes; el Estado registra la revalidación
documental final. Los pendientes institucionales/académicos anteriores conservan
su estado.
