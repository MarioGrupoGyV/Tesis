# Estado Sprint 3 — infraestructura predictiva

Fecha: 4 de octubre de 2026, America/Lima.

**Infraestructura S3 implementada y comprobada aisladamente. Entrenamiento,
evaluación, inferencia y activación institucional pendientes y bloqueados.**
No hay dataset autorizado ni modelo operativo. No se evaluó la hipótesis.
No se implementaron S4–S6 ni se crearon registros escolares en la aplicación activa.

## Referencia y conservación

SHA inicial y final de HEAD: `0c6063f65cfe84dd5d122439cc8ee899527da617`.
Coincide con la referencia publicada; el checkout comenzó limpio. Sin commit, push,
reset, clean, descartes ni despliegue externo. Cambios S3 locales revisables.

Se leyeron AGENTS, README, cierres S2.1/S2.2, matriz S2.2, plan/criterios/Inicio,
ADR anteriores, contrato, SQL y migraciones. Se registró [ADR 005](../adr/005-infraestructura-ml-s3.md)
antes del código, con criterios técnicos y habilitación institucional separada.

Se conservan cuatro cuentas S2.2, identidades/roles/hashes y entradas privadas Windows;
no se ejecutó preparación de cuentas ni restablecimientos. Al inicio había 4 usuarios,
35 eventos de auditoría y 16 sesiones. Los accesos de revisión agregan su auditoría
normal. Los diez conjuntos escolares, modelos y predicciones empezaron y terminaron en cero.

Proyecto `riesgo-escolar`, base `riesgo_escolar`, puertos 15173/18000/55432 locales,
volúmenes db_data/import_data y secretos conservados. Volumen privado **ml_data** nuevo
y vacío, montado solo en API en `/var/lib/riesgo/ml`; ningún modelo/dataset/manifiesto
de prueba se guardó en él. Entorno histórico detenido y respaldo con hashes intactos.
No se repitió restauración ni se alteró el histórico. No hay migraciones nuevas:
0001/snapshot y 0002 permanecen intactos; ambas restricciones de activación siguen vigentes.

## Implementación

- `app/ml/features`: dataset/entradas/etiquetas/configuración tipados y versionados;
  escalas explícitas, fechas Lima/UTC, horizonte, disponibilidad por variable, revisión
  y procedencia. Cinco variables; edad/grado solo con justificación y escala.
- `train`/`evaluate`: Pipeline por fold, imputación/codificación, escala SVM; cuatro
  algoritmos CPU y particiones comunes por estudiante. Folds según soporte; sin tuning,
  calibración, selección de ganador ni métricas mínimas. Métricas no estimables null.
- `manifest`/`artifacts`: manifiesto privado tipado, dataset/hash/versiones/particiones/
  parámetros/métricas/predicciones de validación, firma interna y archivos privados;
  verificación antes de joblib, rechazo de corrupción/rutas/symlinks/incompatibilidad,
  XGBoost con UBJSON nativo. Un hash/firma no autoriza un modelo institucional.
- `predict`: resultado tipado o abstención, Pipeline reutilizado, clases mapeadas por
  valor, sin riesgo LOW inventado. Probabilidades null y calibración falsa.
- ORM explícito ModelVersion/PredictionRecord, repositorio/servicio/esquemas separados.
  Selección por periodo/as_of y última revisión incorporada/disponible; predicción
  única snapshot/model, reutilización concurrente, inmutabilidad y auditoría atómica.
  No alertas/intervenciones. Modelo/artefacto/esquema incompatibles se rechazan.
- CLI de preparación/configuración/compatibilidad; entrenamiento institucional siempre
  rechazado. Sin entrenamiento HTTP/al arrancar ni flag operativo de bypass.

El SQL de referencia ahora también declara `demo_only_active_model`, restricción
heredada de 0001 que seguía en la base pero faltaba en esa referencia; se mantiene
`model_activation_pending`. No se ejecutó ese SQL ni se modificaron las migraciones.

## API 0.3.0

18 operaciones efectivamente registradas, cuatro nuevas bajo `/api/v1`:

| Operación | Permiso y resultado comprobado en activo |
|---|---|
| GET /models | ADMIN: 200 página vacía; otros roles 403; anónimo 401 |
| GET /models/{id} | ADMIN con UUID inexistente: 404; otros roles 403 |
| POST /predictions/run | ADMIN/CSRF: 422 INSTITUTIONAL_PROCESSING_NOT_READY; CSRF ausente/incorrecto 403; otros roles 403; anónimo 401 |
| GET /predictions/{id} | ADMIN/TUTOR/DIRECTOR con UUID inexistente: 404; RESEARCHER 403 |

Orden explícito en run: sesión → rol → CSRF → protocolo → cuerpo → periodo/modelo.
El bloqueo precede a procesar información escolar. Lectura de predicción de sección
ajena devuelve el mismo 404 que inexistente, probado en PostgreSQL aislado.
Modelos públicos no exponen artefactos/hashes/particiones/métricas privadas. No se añade
activate ni entrenamiento HTTP. El 200 de ejecución se comprueba en el núcleo aislado,
no mediante activación ficticia del servicio institucional. Modelos inexistentes/no
disponibles, abstenciones, reutilización, 409/422 y 503 sanitizado quedan documentados.

Tipos frontend regenerados. App.tsx y pruebas de roles S2.2 intactos; sin pantallas S4.

## Dependencias

Python **3.12.12**, scikit-learn **1.9.1**, PostgreSQL **17.6**, Node **24.14.1**, npm
**11.20.0** y todas las versiones previas conservadas. Host Windows/PowerShell;
suite Python dentro de Linux/Docker, no ejecución backend nativa del host.

Única distribución nueva: **xgboost-cpu==3.4.1**. Requiere NumPy/SciPy ya fijados;
sin GPU ni dependencias de pago. Se añadió el pin a requirements.in y un bloque de
cinco líneas a cada lock; ningún pin/hash anterior se reemplazó. Se corrigieron los
comentarios activos que describían ML DEMO. Instalación Docker con --require-hashes,
pip check y entrenamiento/round-trip de XGBoost comprobados.

Hashes SHA256 oficiales incluidos:

| Wheel | SHA256 |
|---|---|
| Linux x86_64 manylinux_2_28 | `1f16331f5c6beb2b40fbd4bf2834333062d93c9eb38b76186a5c206841dc1809` |
| Windows amd64 | `ceb0f7c786511e1876df6ca83a6f837a3187159bde51d8dcc5cdf5e2de76e366` |

Hashes de archivos de bloqueo de este checkout Windows:
requirements.txt `a6ac22ca17fa0a53034a844066fdf37e28f1e334b10a35e1325cd990aaf113a3`;
requirements-dev.txt `1c70f637ef20d0e5049f297b9bf55d87e67c578bd66e632569f3b240d7e81899`.
La comparación de pins y hashes actuales queda en `s3-review.json`; finales de línea
pueden normalizarse por Git. No se comprobó ejecución ML nativa Windows ni ARM.

## Comprobaciones y evidencia

Todos los archivos citados a continuación están en `tests/evidence/`; reportes
S0–S2.2 sin modificaciones. No se publican datasets, particiones ni modelos de prueba.

| Comprobación | Resultado final | Evidencia |
|---|---|---|
| Suite backend completa, base nueva PostgreSQL aislada | **162 passed**, 0 fallos, 0 omitidas, 105.66 s | s3-backend.xml, s3-backend-environment.json |
| Núcleo de cuatro algoritmos | Entrenamiento/evaluación/inferencia y round-trip aprobados; 9 grupos/18 observaciones de fixture, 3 folds, semilla 1729 | s3-ml-summary.json y suite |
| Integridad de persistencia | riesgo_app, rollback intermedio, concurrencia con resultado único/una auditoría, repetición, abstención, periodo bloqueado, elegibilidad y revisión/as_of | test_s3_persistence en XML |
| Permisos/API aislados | Cuatro roles, anónimo, CSRF/protocolo, sección propia/ajena, respuesta pública, 503 sanitizado y restricciones de activación | test_s3_api/test_s3_persistence en XML |
| API activa nueva | **40 peticiones** sanitizadas, cuatro roles/cookies revocadas; ningún registro escolar nuevo | s3-active-endpoints.json |
| Contrato/SQL/Compose/locks | **197 comprobaciones**, 18 operaciones, 13 tablas, 94 campos mapeados | s3-contracts.json |
| Rutas y respuestas contra OpenAPI | 18 rutas coinciden; 40 respuestas activas y 5 muestras positivas de pruebas/servicio validadas | s3-review.json, s3-ml-response-samples.json |
| Tipos y build frontend | Regeneración OpenAPI, tsc/Vite correctos; sin pantallas nuevas | salida npm generate:api y docker compose build web de esta ejecución |
| pip check | Correcto en tester y API, sin dependencias rotas | suite y s3-review.json |
| Navegador activo | **5/5**; cuatro roles, 1440×900/768×1024/390×844, teclado/foco, restauración/logout/error | s3-active-playwright.json, 16 capturas active |
| Navegador aislado | **5/5**, mismas pruebas S2.2, cuentas efímeras en otra base | s3-isolated-playwright.json, s3-browser-environment.json, 16 capturas isolated |
| Persistencia tras recreación sin borrar volúmenes | 13 tablas y archivos idénticos; cuatro accesos/logout/revocación correctos; ML vacío conservado | s3-persistence.json |
| Conservación | Usuarios/hashes sin cambios, registros escolares cero, migraciones/locks previos preservados, histórico detenido y backup intacto | s3-review.json |
| Cierre Git | diff --check correcto; sin cambios en evidencia histórica | comando final |

La recreación capturó y conservó exactamente 4 usuarios, 51 eventos de auditoría y
24 sesiones en ese instante. Las sesiones posteriores generan solo su auditoría normal.
Se inspeccionaron capturas nuevas de administrador escritorio e investigador móvil;
los restantes roles/tamaños quedaron comprobados automáticamente por Playwright.
No se declara revisión de pantallas pendientes ni auditoría completa de accesibilidad.

Las 109 pruebas anteriores siguen presentes. S3 añade 53; la primera suite ampliada
aprobó 161 antes de añadir el caso de incompatibilidad modelo/artefacto, luego 162.
La última repetición se justificó por la validación tipada del manifiesto y guardado
de muestras contractuales; no se repitieron logins/rutas activas sin cambio funcional.
La prueba focal inicial del núcleo aprobó 34 casos (`s3-ml-first.xml`).

**Fallo de herramienta corregido:** check_s3 resolvía `/predictions/run` como la plantilla
`/predictions/{id}` y buscaba un POST inexistente. Se corrigió priorizando ruta literal
y método, y pasó con las mismas evidencias; no fue un fallo de la API.
**Advertencias pendientes:** una de Starlette/TestClient/httpx y nueve sobre el parámetro
SVC probability de scikit-learn 1.9 (se mantiene false). Sin actualización de locks
para silenciarlas; no impidieron las pruebas. Git informa normalización LF/CRLF, sin
errores de whitespace. Ninguna prueba backend falló en las ejecuciones registradas.

## Comandos PowerShell ejecutados

```powershell
git status --short
git rev-parse HEAD
docker compose -f infra/compose.test.yaml build tester
docker compose -f infra/compose.test.yaml run --rm tester python -m pytest backend/tests/test_s3_ml.py -q --tb=short -o cache_dir=/tmp/pytest-cache --junitxml=/evidence/s3-ml-first.xml
$env:TEST_REPORT_NAME = 's3-backend'
docker compose -f infra/compose.test.yaml run --rm tester
.\.venv-s0\Scripts\python.exe infra/sync_ml_contract.py
npm run generate:api --workspace frontend
docker compose build api web
docker compose up -d --wait
py -3.12 infra/ml.py readiness
py -3.12 infra/ml.py compatibility
py -3.12 infra/ml.py train  # Salida 2: bloqueo esperado
docker compose exec -T api python -m pip check
py -3.12 infra/review_s3.py
$env:REVIEW_REPORT_PREFIX = 's3-active'
py -3.12 infra/review_browser.py
$env:PERSISTENCE_REPORT_PREFIX = 's3'
py -3.12 infra/check_access_persistence.py
$env:BROWSER_REPORT_PREFIX = 's3'
py -3.12 infra/test_browser.py
.\.venv-s0\Scripts\python.exe infra/check_s0.py
.\.venv-s0\Scripts\python.exe infra/check_s3.py
git diff --check
```

Se reconstruyeron las imágenes después de los cambios correspondientes. check_s3
también ejecutó configuration y verificó códigos de salida CLI. La captura privada
previa `.local/s3-before.json` contiene comparaciones internas, no contraseñas, y no
se publica. Las credenciales Windows solo se leyeron en memoria; ninguna se copió a
documentación/logs. No se usó checker de base vacía ni down -v; no se borraron datos.

## Archivos y límites

Nuevos: módulos ML features/train/evaluate/predict/manifest/artifacts/cli, modelos ORM,
schemas/repositorio/servicio/router ML; tres módulos de pruebas S3; herramientas infra
ml/review_s3/check_s3/sync_ml_contract; ADR 005, este cierre y [manual ML](../manuals/ML_S3.md).
Modificados: configuración/main/política; requirements; Compose/Dockerfile con volumen
privado; contrato 0.3.0/SQL de referencia/tipos; checkers/runners para reportes S3 sin
reescribir históricos; README raíz/backend/infra, AGENTS, Inicio, plan y criterios.
La única modificación del test S2 es parametrizar el nombre de su archivo de evidencia.

**No ejecutado ni autorizado:** entrenamiento/evaluación/activación institucional,
predictions/run operativo exitoso, calibración, validación prospectiva, validación de
hipótesis, nuevos alumnos o recorrido integral S4–S6. Las restricciones de base impiden
activar modelos y las pruebas no las retiran. El núcleo de inferencia/persistencia
positivo usa objetos/artefactos aislados y modelos de fixture inactivos; no acredita activación.

Pendientes institucionales: dataset y etiquetas autorizados, criterio/escalas/procedencia,
calendario del estudio, política de elegibilidad/faltantes/retención, validación humana,
futura migración y proceso controlado de aprobación/activación. La base no tiene historial
de elegibilidad; as_of respeta incorporación de cortes y no reconstruye consentimientos
históricos. Calibración y evaluación prospectiva requieren diseño posterior.
S4 pantallas, S5 seguimiento/reportes y S6 integración continúan pendientes.
