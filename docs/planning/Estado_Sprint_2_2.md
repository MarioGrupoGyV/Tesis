# Estado Sprint 2.2 — revisión local de acceso

## Alcance y referencia

Completado únicamente S2.2: revisar S2.1, crear explícitamente cuatro accesos locales
y comprobar las funciones existentes. Sin datos de colegio, CSV activo, semillas al
arranque, habilitación institucional, S3–S6, commit, push ni despliegue externo.

SHA inicial y final de HEAD: `eb0bfdee140e35bb104405c6dcaa7920b344215b`.
El checkout comenzó limpio. Los cambios S2.2 permanecen locales y sin commit.
La entrega vacía de S2.1 se conserva como hecho histórico.

Se revisaron AGENTS, README, cierre S2.1, ADR 004, plan, criterios, Inicio, contratos,
migraciones, routers, servicios y frontend. [Matriz completa](Matriz_verificacion_S2_2.md).

## Confirmación S2.1

Windows/PowerShell, Docker Desktop con contenedores Linux: proyecto `riesgo-escolar`,
base `riesgo_escolar`, aplicación con `riesgo_app`, web/api/db saludables. Volúmenes
`riesgo-escolar_db_data` y `riesgo-escolar_import_data`, secretos privados nuevos en
`.local/runtime-secrets`; API sin secreto del propietario ni credenciales de semilla.
Revisión vigente `0002_institutional_boundary`, consultada como propietario.

Versiones fijadas conservadas: Python 3.12.12, PostgreSQL 17.6, Node 24.14.1 y npm
11.20.0. Host observado: PowerShell 7.6.5, Docker 29.7.2, Compose 5.5.1 y launcher
Python 3.12.0; este último solo orquesta, no ejecuta la suite backend.
Manifiestos, locks, migración 0001/snapshot, contrato 0.2.0 y tipos regenerados
conservan su contenido respecto al SHA inicial. `infra/check_runtime.py` intacto.

El entorno `riesgo-escolar-demo` sigue detenido. El respaldo privado indicado por
`tests/evidence/s2-1-backup.json` existe y ambos hashes coinciden; ese informe conserva
la restauración previa de las 13 tablas y CSV. No se repitió la restauración ni se
modificaron sus archivos/volúmenes. Evidencia: `tests/evidence/s2-2-review.json`.

## Cuentas y acceso privado

Antes: cero usuarios y cero registros escolares. Se crearon estas cuentas por el
encargo, mediante bootstrap/configuración existentes y transacciones con auditoría
bajo riesgo_app; nunca por INSERT manual o semillas:

| Rol | Correo | ID |
|---|---|---|
| ADMIN | revision.local.admin@example.com | 7a4ee76f-aee1-4712-a35b-88cc3d78ea2c |
| TUTOR | revision.local.tutor@example.com | df354a4d-d596-45ec-b9c7-55ba58608085 |
| DIRECTOR | revision.local.director@example.com | 254a5ba3-f174-48bc-9bab-7b6f8284fd38 |
| RESEARCHER | revision.local.researcher@example.com | e4a4633c-eb68-4188-ad0d-f0972c141af7 |

Cada contraseña aleatoria tiene 40 caracteres y es distinta. PostgreSQL guarda solo
su hash. Windows Credential Manager conserva las entradas genéricas
`SeguimientoEscolar/S2.2/ADMIN`, `/TUTOR`, `/DIRECTOR`, `/RESEARCHER` bajo el mismo
usuario Windows que ejecutó la preparación. No son correos de personas ni se envió correo.

Para ingresar, abrir http://localhost:15173 y consultar la entrada privada local:

```powershell
py -3.12 infra/windows_credentials.py ADMIN
```

Sustituir el rol para las otras cuentas. Se abre una ventana con contraseña oculta;
el operador puede mostrarla allí. El helper no imprime secretos ni los escribe en
archivos. tkinter está disponible; la ventana con contraseña no se abrió durante
las capturas. Las automatizaciones reciben los secretos en memoria/stdin o entorno
del proceso hijo, sin argumentos visibles, trazas ni reportes de cuerpos sensibles.

La preparación repetida reutilizó las mismas cuatro cuentas. La comparación exacta
en memoria confirmó que no cambian tablas, hashes de contraseña, auditoría ni archivos:
`s2-2-accounts.json`, `s2-2-accounts-repeat.json`, `s2-2-accounts-idempotency.json`.

## Defecto corregido y comprobaciones

La primera revisión activa tuvo **4 aprobadas y 1 fallida**: RESEARCHER recibía una
tarjeta de error genérica y otra que invitaba a configurar un periodo. Se corrigió
`frontend/src/app/App.tsx`: explica el acceso limitado sin solicitar catálogos. Los
permisos del backend no cambian. Se conserva evidencia `s2-2-active-first-*` del fallo.

| Comprobación | Resultado | Evidencia en tests/evidence |
|---|---|---|
| API activa, 14 operaciones y cuatro roles | 122 peticiones aprobadas; cuerpos/códigos contractuales; anónimo, Origin, CSRF y revocación | s2-2-endpoints.json, s2-2-review.json |
| Backend completo en base nueva aislada | 109 passed, 0 fallos, 0 omitidas, 117.19 s; pip check correcto | s2-2-backend.xml, s2-2-backend-environment.json |
| Contrato/SQL/Compose/locks y muestras reales | 180 comprobaciones, 13 tablas, 84 campos, 14 rutas | s2-2-contracts.json, s2-2-response-samples.json |
| Tipos frontend | Regenerados con OpenAPI 0.2.0, sin cambios de contenido | Comparación s2-2-review.json |
| Build frontend | tsc sin errores y Vite build correcto, 18 módulos; imagen activa verificada | Salida de docker compose build web de esta ejecución |
| Navegador activo después de corregir | 5/5 aprobadas, cuatro roles, tres tamaños, restauración, teclado/foco, logout y error | s2-2-active-playwright.json, s2-2-active-*.png |
| Navegador aislado ampliado | 5/5 aprobadas, cuatro cuentas efímeras, mismos criterios | s2-2-isolated-playwright.json, s2-2-browser-environment.json, capturas isolated |
| Persistencia con usuarios | 13 tablas y archivos idénticos tras recreación; cuatro accesos/logout/revocación aprobados | s2-2-persistence.json |
| Repetición de preparación | Sin cambios en cuentas, roles, credenciales, auditoría ni archivos | s2-2-accounts-idempotency.json |
| Revisión final de diff | git diff --check aprobado; sin cambios en evidencias históricas | Comando de cierre |

La recreación conservó 4 usuarios, 19 eventos de auditoría y 8 sesiones existentes
en el instante de la captura. Los accesos posteriores agregan su auditoría normal.
Los diez conjuntos escolares permanecieron en cero antes y después; no se crearon
periodos, secciones, estudiantes, matrículas, cortes, lotes, modelos, predicciones,
alertas ni intervenciones. Sin archivos de importación nuevos. La comprobación de
persistencia nueva compara el estado existente; no debilita la protección del checker vacío.

Incidencias de verificación resueltas: una consulta inicial de alembic_version como
riesgo_app devolvió 42501 (restricción correcta); se consultó con propietario. El
checker nuevo necesitó lectura UTF-8 del Git de Windows y usar el OpenAPI generado
de FastAPI para sus routers agrupados. Se corrigieron ambos diagnósticos y el
checker pasó. La primera validación documental obtuvo 169 checks antes de terminar
pytest; se repitió con sus muestras recién generadas y obtuvo 180.

Única advertencia de la suite: Starlette informa deprecación de httpx en TestClient.
No provoca fallos y se conserva la versión acordada; migración de dependencias pendiente.

## Comandos PowerShell ejecutados

Desde la raíz, con Docker Desktop disponible y dependencias ya instaladas:

```powershell
git status --short
git rev-parse HEAD
py -3.12 infra/review_accounts.py
py -3.12 infra/review_accounts.py
py -3.12 infra/review_endpoints.py
$env:REVIEW_REPORT_PREFIX = 's2-2-active-first'
py -3.12 infra/review_browser.py
Remove-Item Env:REVIEW_REPORT_PREFIX
# Tras corregir el estado del investigador:
docker compose build web
$env:TEST_REPORT_NAME = 's2-2-backend'
docker compose -f infra/compose.test.yaml build tester
docker compose -f infra/compose.test.yaml run --rm tester
py -3.12 infra/check_access_persistence.py
py -3.12 infra/review_browser.py
py -3.12 infra/test_browser.py
npm run generate:api --workspace frontend
.\.venv-s0\Scripts\python.exe infra/check_s0.py
.\.venv-s0\Scripts\python.exe infra/check_review.py
git diff --check
```

No copiar esta secuencia como bucle de logins: rige el límite de 10 intentos/300 s
por IP, incluidos los exitosos. No se desactivó ni cambió ese límite. La recreación
se hizo para comprobar persistencia y conserva volúmenes; nunca se usó down -v,
DROP o TRUNCATE sobre la aplicación ni el entorno histórico.

## Archivos y documentación

Producto: solo estado de investigador en App.tsx. Revisión local: nuevos helpers
`windows_credentials.py`, `review_accounts.py`, `review_endpoints.py`, `review_browser.py`,
`runtime_snapshot.py`, `check_access_persistence.py` y `check_review.py` en infra.
Pruebas: fixture de navegador con cuatro roles; access.spec.ts, reporter sanitizado,
configuración Playwright y runner ampliados. Los casos backend existentes se conservan;
solo cambia el destino de sus muestras a s2-2, igual que el informe de check_s0.
Evidencias nuevas siempre con prefijo s2-2, sin reescribir S2.1.

Markdown modificado: README para cuentas/método privado y checker correcto; AGENTS
para estado actual sin datos escolares; Inicio para lectura del cierre vigente;
criterios para registrar S2.2; README de infra/tests para herramientas y evidencia
nuevas. Se añaden este cierre y la matriz. Plan académico, ADR 004, conciliación,
manuales, README de otras capas y cierres históricos no necesitaron correcciones.

## Pendientes y límites

Importación institucional **bloqueada intencionalmente**; debe acordarse e implementarse
el protocolo de procedencia, escalas, periodos, ventanas, fechas y calidad. El motor
de importación aprobado con fixtures aislados no acredita procesamiento institucional.
El contexto activo sigue sin datos escolares. No se probó detalle/historial 200 con
un alumno activo inventado; esos casos se comprobaron únicamente en PostgreSQL aislado.

S3: pipeline e inferencia, datos/etiquetas autorizados para entrenamiento y evaluación.
S4: pantallas de estudiantes/importación y demás flujos. S5: alertas, intervenciones y
reportes. S6: recorrido integral y cierre. HTTPS/producción, retención y validación
académica siguen pendientes. No hay métricas ni riesgo fabricado; no se evaluó la tesis.
