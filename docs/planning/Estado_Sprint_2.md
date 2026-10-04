> Cierre histórico: no es una guía de arranque vigente. Consultar [Estado S2.1](Estado_Sprint_2_1.md). Los resultados originales se conservan.

# Estado del Sprint 2 — Importación y estudiantes DEMO

Fecha de cierre: 3 de octubre de 2026 (America/Lima; evidencias UTC del 4 de octubre).
**S2 COMPLETADO. S3–S6 no iniciados.** Solo se usaron datos sintéticos.

## Resultado y archivos

Se leyeron AGENTS, README, cierre S1, aceptación de sprints, conciliación, ADR y
contratos vigentes. Se conservan S1, sus versiones, locks y la migración de trece
tablas. No fue necesario modificar el SQL de diseño ni otorgar nuevos permisos.

- `backend/app/api/v1/{imports,students}.py`, `schemas/s2.py`, `models/s2.py`,
  `services/{imports,students,csv_validation}.py` y `repositories/{imports,students}.py`:
  seis operaciones de importación y consulta, con permisos y respuestas públicas.
- `core/{config,errors,import_storage,upload_limit}.py` y `main.py`: almacenamiento
  privado, límites, errores sanitizados y contrato 0.1.2. Se mantienen sesiones/CSRF.
- `compose.yaml`, `infra/docker/api.Dockerfile`, `.env.example`: volumen privado
  persistente para CSV. El volumen PostgreSQL existente se conserva.
- `infra/compose.test.yaml`, `docker/test.Dockerfile`, `run_linux_tests.py` y
  `backend/tests/test_s2_imports.py`: suite Linux con PostgreSQL separado y base
  nueva por ejecución. `conftest.py` comparte preparación sin eliminar pruebas S1.
- `infra/db/init-app-role.sh`: usa el nombre real de POSTGRES_DB al conceder acceso,
  en lugar del nombre fijo de la demo. `test_s1.py` conserva la suite local S1.
- OpenAPI 0.1.2, tipos frontend regenerados, `infra/check_s0.py`, documentación,
  Makefile, muestras sintéticas y `infra/smoke_s2.py`. El reporte Playwright admite
  otro destino para conservar las evidencias históricas. `smoke_s1.py` admite
  estudiantes existentes al comparar persistencia.

La vista previa no crea estudiantes, matrículas ni cortes. La confirmación los
crea junto con auditoría en una transacción; revalida versión y estado observado,
bloquea series concurrentes y conserva revisiones. Solo ADMIN importa; las consultas
aplican rol/sección y devuelven pendiente de evaluación cuando falta predicción
vigente. Los CSV quedan fuera del checkout bajo claves internas, sin descarga pública.

## Comprobaciones ejecutadas

| Comprobación | Resultado | Evidencia en tests/evidence |
|---|---|---|
| Suite completa S1, **antes de desarrollar importación**, Linux/Python 3.12.12 y PostgreSQL 17.6 aislado | COMPROBADO: 57 aprobadas, 16.82 s, sin omitidas | s2-baseline-s1-linux.xml y su -environment.json |
| Primera suite ampliada | FALLIDO y corregido: 95 aprobadas, 2 fallidas, 51.10 s | s2-first-linux.xml y su -environment.json |
| Suite ampliada tras corrección | COMPROBADO: 102 aprobadas, 49.93 s | s2-expanded-linux.xml y su -environment.json |
| Suite final, incluidos 10000 registros y lectura concurrente | COMPROBADO: **104 aprobadas**, 80.75 s, 0 fallidas, 0 omitidas | s2-pytest-linux.xml y s2-pytest-linux-environment.json |
| Validación documental SQL/API, tipos, Compose y respuestas | COMPROBADO: **224 comprobaciones**; 13 tablas, 27 rutas contractuales, 102 correspondencias de tipos | s2-contracts.json; s2-response-samples.json |
| Generación TypeScript desde OpenAPI 0.1.2 y build frontend | COMPROBADO: tsc + Vite, 18 módulos, build Linux dentro de Compose | Comandos e imágenes abajo |
| Regresión de navegador de S1, tres roles y credenciales inválidas | COMPROBADO: **4 aprobadas**, 23.3 s | s2-s1-playwright.json |
| HTTP real con riesgo_app, confirmación/revisión/permisos/CSRF | COMPROBADO | s2-runtime.json |
| Detener/recrear servicios sin borrar volúmenes | COMPROBADO: mismas 13 tablas y mismos 3 archivos privados; sesión conservada | s2-runtime.json |

La suite final usa `riesgo_escolar_demo_s2_test_2e2e90987305` en el proyecto aislado
`riesgo-escolar-s2-tests`, sin puertos publicados ni acceso a la base operativa.
Cada ejecución crea otra base; no se borraron bases ni volúmenes. El propietario
solo prepara/migra y verifica fixtures; las peticiones y conexiones concurrentes
usan **riesgo_app**. `pip check` pasó en el contenedor con dependencias bloqueadas.

Cobertura S2: importación válida/inválida, UTF-8/BOM, cabeceras, límites, escalas y
precisión, duplicados UTC, null y fracción faltante, sección/año/tutor, fechas
Lima/UTC, REAL y periodo bloqueado; rollback por fallo intermedio de auditoría;
repetición, revisión inmutable, estado/predecesor desactualizado; CSRF, investigador,
tutor propio/ajeno, filtros, orden y paginación; archivos alterados; 503/409/500
sanitizados; concurrencia con conexiones separadas y espera advisory comprobada
en PostgreSQL. Se prueba que una predicción antigua no se atribuye al corte nuevo.
Ese caso inserta evidencia sintética aislada: no entrena ni implementa ML.

La validación contractual incluye ocho ejemplos estáticos y once respuestas reales
sanitizadas producidas por las pruebas. Validar el contrato de 27 rutas no significa
implementar las rutas futuras. Se añadieron únicamente las seis autorizadas.

El recorrido HTTP dejó en la demo dos estudiantes, dos matrículas, tres cortes
(incluida revisión) y tres lotes. Comparó hashes/cantidades de las trece tablas y
hash agregado de tres CSV antes/después de recrear contenedores. No ejecutó semilla
durante el reinicio. La ausencia de CSRF devolvió 403; confirmar el lote inválido,
422; repetir la confirmación reutilizó el resultado.

## Fallos encontrados y resolución

1. El arranque inicial de PostgreSQL de pruebas encontró un GRANT a un nombre de
   base fijo. Se parametrizó con POSTGRES_DB; las siguientes bases aisladas migraron
   correctamente. No se borró la base operativa ni se corrigió con SQL destructivo.
2. Dos pruebas S1 de rollback de auditoría inyectaban SQLAlchemyError genérico y
   esperaban 503. El nuevo clasificador respondía 500. Se restauró esa compatibilidad
   sin modificar las aserciones S1: integridad/serialización/bloqueos siguen en 409,
   errores de programación en 500, indisponibilidad en 503. No se usa 503 para
   ocultar conflictos de integridad. Health ready conserva su respuesta Health.
3. Pytest no podía escribir su caché en el checkout del contenedor. Se configuró
   `/tmp/pytest-cache`; el aviso desapareció. Persiste un aviso de deprecación
   TestClient/httpx de las versiones fijadas; no ocasiona fallos y no se cambiaron locks.

## Comandos PowerShell ejecutados y reproducción

Desde la raíz, Docker Desktop con contenedores Linux y secretos preparados por S1:

```powershell
docker compose -f infra/compose.test.yaml build tester
$env:TEST_REPORT_NAME = 's2-baseline-s1-linux'
docker compose -f infra/compose.test.yaml run --rm tester
```

El comando anterior se ejecutó sobre S1 antes de añadir los casos S2. Ejecutarlo
ahora prueba el código actual; no reproduce históricamente aquella versión.
Durante el desarrollo se usaron también nombres s2-first-linux y s2-expanded-linux.

```powershell
docker compose -f infra/compose.test.yaml build tester
$env:TEST_REPORT_NAME = 's2-pytest-linux'
docker compose -f infra/compose.test.yaml run --rm tester
Remove-Item Env:TEST_REPORT_NAME
npm run generate:api --workspace frontend
.\.venv-s0\Scripts\python.exe infra/check_s0.py
py -3.12 infra/s1.py up
.\.venv-s1\Scripts\python.exe infra/smoke_s2.py
$env:DEMO_CREDENTIALS_FILE = (Resolve-Path .local/secrets/demo-credentials.json).Path
$env:E2E_REPORT_FILE = 'tests/evidence/s2-s1-playwright.json'
npx playwright test
git diff --check
```

`up` construyó web con Node 24.14.1/npm 11.20.0, ejecutó tsc/Vite y mantuvo Alembic
en head; API usa Python 3.12.12. Imagen API resultante:
`sha256:aa0c765b4dce348202cc148d8d496cb862e878881cd8ca7462a1efec58b629db`;
imagen web: `sha256:f608b6ce4f731ed277212790b282c9b51409957581cecbabc8dc8c7a662428b5`.
Los comandos Docker y navegador se ejecutaron con permiso de consola requerido
por el entorno Codex; no hubo rechazos de revisión automática.

## Pendientes y límite de aceptación

- S3: entrenamiento, manifiestos e inferencia real de la demo; no implementados.
- S4: pantallas de importación, estudiantes e historial. El recorrido S2 actual es
  por API; no se declara prueba visual de esas pantallas. Playwright comprueba S1.
- S5/S6: seguimiento, exportación y recorrido integral; no ejecutados ni aceptados.
- Aviso TestClient/httpx, política de retención/reconciliación de archivos huérfanos,
  backup y despliegue HTTPS/institucional quedan pendientes. El almacenamiento y
  PostgreSQL sobreviven al reinicio; esto no constituye prueba de restauración de backup.
- Make no está instalado; se usaron equivalentes PowerShell. El manual interactivo
  PowerShell 7 se documentó; la evidencia funcional equivalente proviene del script
  HTTP Python, no de una ejecución manual de cada línea del manual.

Los criterios S2 están comprobados y el proyecto queda preparado para abordar S3
cuando se autorice. REAL sigue bloqueado. No se cambió metodología académica ni se
cargaron datos reales. Véanse [ADR 003](../adr/003-importacion-s2.md) y
[manual API](../manuals/Importacion_S2.md).
