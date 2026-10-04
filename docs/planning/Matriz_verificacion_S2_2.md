# Matriz de verificación S2.2

Prefijo `/api/v1`; contrato **0.2.0**, 14 operaciones efectivamente registradas.
A=ADMIN, T=TUTOR, D=DIRECTOR, R=RESEARCHER. Todos los accesos autenticados usaron
credenciales del rol correspondiente. `X-Role: ADMIN` no eleva al investigador.
El UUID de consulta inexistente fue `00000000-0000-4000-8000-000000000222`.

## API activa

Cada fila está **COMPROBADA**. Peticiones sanitizadas, respuestas y códigos por caso:
[s2-2-endpoints.json](../../tests/evidence/s2-2-endpoints.json), 122 peticiones.
[s2-2-review.json](../../tests/evidence/s2-2-review.json) valida esas respuestas contra
el contrato y contrasta las rutas efectivas de FastAPI. No hay cookies reutilizables
ni contraseñas en estos informes; `csrf_token` se redacta antes de escribir.

| Método y ruta | Estado funcional | Resultado real / criterio |
|---|---|---|
| GET /health/live | Implementado | Anónimo y A/T/D/R: 200 Health |
| GET /health/ready | Implementado | Anónimo y A/T/D/R: 200 Health; fallo DB conserva Health, probado aisladamente |
| POST /auth/login | Implementado | A/T/D/R: 200 con Origin permitido; Origin ausente/ajeno 403; contraseña incorrecta 401 |
| GET /auth/me | Implementado | A/T/D/R: 200 identidad real; anónimo/cookie revocada 401 |
| GET /auth/csrf | Implementado | A/T/D/R: 200 token; anónimo/cookie revocada 401 |
| POST /auth/logout | Implementado | A/T/D/R: 204 con CSRF; ausente/incorrecto 403; anónimo 401; cookie anterior revocada |
| GET /periods | Implementado | A/T/D: 200 lista vacía; R: 403; anónimo/revocado: 401 |
| GET /sections | Implementado | Periodo inexistente A/T/D: 404, R: 403; anónimo 401. Sin period_id: 422 incluso R por orden de validación |
| GET /students | API implementada | Periodo inexistente A/T/D: 404, R: 403; anónimo 401. Sin period_id: 422; no se fabrica listado |
| GET /students/{id} | API implementada | UUID/periodo inexistentes A/T/D: 404, R: 403; anónimo 401 |
| GET /students/{id}/timeline | API implementada | UUID/periodo inexistentes A/T/D: 404, R: 403; anónimo 401 |
| POST /imports/preview | Bloqueado intencionalmente | A + CSRF: 422 INSTITUTIONAL_PROCESSING_NOT_READY; T/D/R: 403 FORBIDDEN; A sin CSRF/incorrecto: 403; anónimo 401 |
| GET /imports/{id} | API implementada | A: 404 lote inexistente; T/D/R: 403; anónimo 401 |
| POST /imports/{id}/commit | Bloqueado intencionalmente | A + CSRF: 422 INSTITUTIONAL_PROCESSING_NOT_READY; T/D/R: 403; A sin CSRF/incorrecto: 403; anónimo 401 |

Las escrituras de importación se rechazaron antes de exigir archivo o modificar datos.
No se cargó CSV en la aplicación activa. Los diez conjuntos de registros escolares
continuaron vacíos y el almacenamiento privado no cambió. No se introdujo ningún bypass.

## Pantallas y funciones

| Pantalla/función | Rol | Estado y criterio | Evidencia nueva |
|---|---|---|---|
| Login | Todos | COMPROBADO: etiquetas, tabulación correo/contraseña, envío por Enter y error de credenciales | active-login-*, active-invalid-login; Playwright activo/aislado |
| Restauración de sesión | A/T/D/R | COMPROBADO tras recargar en cada tamaño; identidad servidor; sin tokens en localStorage/sessionStorage | active-{rol}-*; 4 pruebas por entorno |
| Inicio/contexto vacío | A/T/D | COMPROBADO: periodos/secciones vacíos explicados; sin riesgo, cifras ni escuela inventada | active-admin/tutor/director-* |
| Inicio del investigador | R | FALLIDO inicialmente: error genérico más consejo de configurar contexto prohibido. CORREGIDO Y COMPROBADO: explicación del alcance sin catálogos | active-first-researcher-1440x900 frente a active-researcher-* |
| Logout | A/T/D/R | COMPROBADO: foco, Enter, mensaje de éxito, cookie antigua 401 | Playwright y endpoints |
| Bootstrap/configuración de cuentas | ADMIN | COMPROBADO con servicios existentes y riesgo_app; cuenta/auditoría atómicas; repetición sin cambios | accounts, accounts-repeat, accounts-idempotency; suite backend |
| Persistencia | A/T/D/R | COMPROBADO: recreación sin borrar volúmenes, 13 tablas/archivos idénticos; login y revocación posteriores | persistence |
| Estudiantes/detalle/historial | A/T/D | API comprobada; pantallas PENDIENTES S4. Casos con registros y secciones propias/ajenas solo en base aislada | backend.xml y response-samples |
| Importación | ADMIN | BLOQUEADO INTENCIONALMENTE en activo; motor transaccional comprobado aisladamente con fixtures/monkeypatch pytest; interfaz PENDIENTE S4 | endpoints y backend.xml |
| Tablero de riesgo, ML y evaluación | Según futuro contrato | PENDIENTE S3/S4; no hay modelo, entrenamiento ni evaluación institucional en esta revisión | Inventario de rutas y App.tsx |
| Alertas, intervenciones, reportes/exportación | Según futuro contrato | PENDIENTE S5 y su interfaz S4; carpetas/DTO/diseños no acreditan implementación | Inventario de rutas y servicios |
| Recorrido integral e institucional | — | NO EJECUTADO; depende de protocolo, datos autorizados y S3–S6 | Límites de Estado S2.2 |

Los prefijos de evidencia anteriores significan `tests/evidence/s2-2-...`.
Capturas finales: 16 activas y 16 aisladas, incluyendo login, cuatro roles en
1440×900, 768×1024 y 390×844 y error de credenciales. Sin desplazamiento horizontal;
foco/etiquetas comprobados por Playwright. Se inspeccionaron visualmente capturas
actuales de los cuatro roles, escritorio/tablet/móvil y error de login. No se afirma
una auditoría completa de accesibilidad ni un recorrido de pantallas pendientes.

## Regresión aislada

**COMPROBADO:** 109 pruebas con PostgreSQL 17.6, Linux/Python 3.12.12 y riesgo_app
para operaciones de aplicación. Se conservan permisos propios/ajenos, periodo bloqueado,
UTC/días Lima, null/precisión/límites, atomicidad/rollback, concurrencia, revisiones,
idempotencia, archivos alterados, CSRF, revocación, 409 de integridad y 503 sanitizado.
Los fixtures son exclusivamente de prueba. El propietario solo prepara/migra o
verifica restricciones; no reemplaza al usuario de aplicación en los recorridos.

**PENDIENTE técnico:** advertencia de deprecación httpx/Starlette; no cambia los locks
en este sprint. **NO EJECUTADO:** nueva restauración del respaldo histórico; se
comprobaron existencia/hashes y la evidencia de restauración S2.1 sin alterarlo.
