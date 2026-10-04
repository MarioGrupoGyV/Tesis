# Estado S2.1 — Windows y retiro del flujo de demostración

Fecha: 3 de octubre de 2026 America/Lima; evidencias UTC del 4 de octubre.
**S2.1 implementado. S3, S4, S5 y S6 no iniciados.**

## Revisión inicial e inventario

SHA inicial: `2310d0034529cf79c4461de7e7e5fe2be457650c`, exactamente el cierre S2
indicado. Git estaba limpio; no había diferencias locales posteriores. Se trabajó
sin reset, clean ni checkout. No se creó commit: HEAD final sigue siendo ese SHA,
con cambios locales revisables. No hubo push ni despliegue externo.

Se revisaron AGENTS, README, cierres S0/S1/S2, criterios, ADR, plan/Inicio, contrato,
SQL y snapshot, migración, Compose, configuración, semillas, backend, pruebas y UI.

| Dependencia anterior | Resolución S2.1 |
|---|---|
| DEMO en producto, configuración, origen público y auditoría de acceso | Retirado del flujo activo; acceso audita ACCOUNT_ACCESS, no atribuye origen escolar |
| REAL bloqueado incluso para contexto | Contexto institucional legible; procesamiento bloqueado con INSTITUTIONAL_PROCESSING_NOT_READY |
| seed_demo, prepare_demo, compose.seed y credenciales predeterminadas | Retirados; prepare general sin cuentas y bootstrap interactivo explícito |
| run_linux_tests.py | Renombrado run_backend_tests.py; runtime sigue siendo Linux dentro de Docker |
| WSL/Bash/Make como instrucciones al operador | No necesarios; comandos PowerShell/Python coordinan Docker Desktop |
| Dockerfiles, rutas Linux, init-app-role.sh | Conservados como componentes internos del contenedor |
| CSV de ejemplo y smoke/Playwright con cuentas del producto | Retirados; bytes fabricados solo en fixtures aislados y nuevo runner de navegador |
| Plan de escuela ficticia/generador/entrenamiento demo | Sustituido por módulo predictivo sujeto a protocolo; algoritmos académicos conservados |

## Respaldo y transición

El entorno anterior era riesgo-escolar-demo, base riesgo_escolar_demo, volúmenes
riesgo-escolar-demo_db_data y riesgo-escolar-demo_import_data; secretos en
.local/secrets, conservados. Tenía tres cuentas, un periodo, dos secciones, dos
estudiantes, dos matrículas, tres cortes y tres lotes. No tenía modelos/predicciones.
Las consultas de origen devolvieron DEMO para periodo/estudiantes; no se reetiquetó
ningún registro ni se eliminó contenido cuya procedencia pudiera requerir revisión.

Respaldo privado fuera de Git:
`C:\Users\mario\OneDrive\Escritorio\tesis-riesgo-escolar\.local\backups\20261004T033452Z`.
Contiene database.dump, imports.tar, copia de configuración y secretos anteriores.
No publicar esa carpeta. El entorno original y la restauración están detenidos.

Restauración en `riesgo-restore-20261004t033452z`, sin puertos publicados:
trece tablas coinciden por cantidad/hash; CSV restaurados coinciden por hash binario
del archivo tar reconstruido. Evidencia pública sin secretos:
`tests/evidence/s2-1-backup.json`. El primer intento se conserva también privado,
en 20261004T033425Z, y su contenedor quedó detenido. No se ejecutó down -v, TRUNCATE,
DROP ni borrado de datos. La herramienta puntual está en infra/history/archive_s2.py
y rechaza ejecutarse sobre el Compose nuevo; no es una opción de arranque anterior.

El entorno activo nuevo es riesgo-escolar, base riesgo_escolar, volúmenes
riesgo-escolar_db_data e import_data, secretos .local/runtime-secrets. Las trece
tablas tienen cero registros y no hay CSV escolares. Se comprobó después de recrear
contenedores sin semilla. Un marcador de infraestructura (no CSV escolar) comprueba
el volumen privado. Evidencia: `s2-1-runtime.json`.

## Archivos y cambios

- Renombrados Contrato_API_demo.yaml → Contrato_API.yaml, Esquema_demo.sql → Esquema.sql,
  run_linux_tests.py → run_backend_tests.py y s1.py → manage.py.
- Nuevos bootstrap_admin.py, configure_context.py, processing_policy.py y migración
  0002_institutional_boundary.py. Snapshot/revisión 0001 sin cambios.
- Servicios/repositorios/esquemas S1/S2 adaptados a origen institucional y bloqueo;
  motor transaccional, permisos, errores, sesiones y CSRF conservados.
- Compose, preparación general, Dockerfile API sin fixtures, runners backend/browser,
  verificación de entorno vacío y pruebas de bootstrap/configuración.
- UI: textos e insignias retirados, acceso/contexto vacío y tipos 0.2.0 regenerados.
- Retirados seed_demo.py, prepare_demo.py, compose.seed.yaml, Makefile, test_s1.py,
  smoke_s1.py, smoke_s2.py, capture_s1.mjs, consumidores de DEMO_CREDENTIALS_FILE y
  cuatro CSV de ejemplo no usados por la suite. s1.spec.ts pasa a access.spec.ts.
- AGENTS, README, plan, Inicio, criterios, conciliación, manuales y README de capas
  actualizados. ADR 004 registra decisiones. Planificación/manual anterior en history;
  cierres y evidencias S0/S1/S2 conservan hechos originales con aviso de vigencia.

OpenAPI **0.2.0** es incompatible deliberadamente: origen DEMO retirado, nuevo código
de bloqueo y solo catorce rutas implementadas; no publica endpoints futuros vacíos.
REAL no implica autorización. Ninguna variable salta el bloqueo. Escalas antiguas
siguen como límites del motor, pendientes de conciliación institucional antes de habilitarlo.

## Comprobaciones y entorno real

Host Windows, PowerShell **7.6.5**, Git **2.47.0.windows.1**, launcher Python **3.12.0**,
Node **24.14.1**, npm **11.20.0**, Docker **29.7.2**, Compose **5.5.1**.
Backend dentro del contenedor: Linux/Python **3.12.12**, PostgreSQL **17.6**.
No se presenta como suite nativa Windows. Versiones/locks de dependencias intactos.

| Comprobación | Resultado | Evidencia |
|---|---|---|
| Primer intento de restauración | FALLIDO: servidor temporal de inicialización detectado demasiado pronto | Copia privada 20261004T033425Z; no afectó al origen |
| Restauración repetida tras esperar TCP del servidor definitivo | COMPROBADO: trece tablas y archivos idénticos | s2-1-backup.json |
| Primera regresión adaptada | FALLIDO: 103 aprobadas, dos fallos de contexto de rol | s2-1-backend-first.xml y -environment.json |
| Regresión final ampliada | COMPROBADO: **109 aprobadas**, 45.32 s, cero fallidas/omitidas | s2-1-backend.xml y -environment.json |
| Contrato, SQL, tipos, Compose, locks y respuestas | COMPROBADO: **180 verificaciones**, catorce rutas, trece tablas | s2-1-contracts.json y s2-1-response-samples.json |
| Generación de tipos y build frontend | COMPROBADO: tsc/Vite, 18 módulos | Comandos e imágenes del entorno |
| Navegador, teclado, estados vacíos y revocación | COMPROBADO: **4 aprobadas**, 12.0 s | s2-1-playwright.json, s2-1-browser-environment.json |
| Capturas reales escritorio/tablet/móvil | COMPROBADO: acceso/contexto en 1440×900, 768×1024, 390×844 | Seis s2-1-login/empty-*.png; sin contraseña visible |
| Migración nueva, permisos, funciones/triggers e integridad | COMPROBADO con PostgreSQL; nueve restricciones de origen validadas | Suite backend y base activa |
| Reinicio/recreación sin semillas | COMPROBADO: activo vacío y volumen conservado; cuenta aislada sobrevive reinicio | s2-1-runtime.json y browser-environment.json |

Los dos fallos iniciales de backend fueron pruebas que esperaban el error del trigger
del propietario, pero se habían movido a riesgo_app y recibían denegación de privilegio.
Solo esos casos hacen RESET ROLE para verificar protección incluso contra propietario.
Las solicitudes de aplicación S1/S2 y conexiones concurrentes siguen usando riesgo_app.

Se conservan atomicidad, rollback intermedio, concurrencia real, límites/10000 filas,
idempotencia, revisiones, fechas Lima/UTC, null, permisos propios/ajenos, CSRF y archivo
alterado. Cuatro casos de semillas/configuración demo se reemplazaron por seis casos
de bootstrap/bloqueo, dos de configuración y uno de migración: 104 − 4 + 9 = 109.
Los casos REAL de catálogo ahora comprueban lectura; el de predicción antigua usa un
modelo inactivo y conserva el resultado pendiente y el historial. No se retiran pruebas
para ocultar un fallo. La política del motor se sustituye exclusivamente en pytest;
los casos sin parche y Playwright verifican el bloqueo institucional real.

Persiste un aviso TestClient/httpx de las versiones fijadas; no se cambiaron locks
para eliminarlo. Make no se ejecutó y no es requisito. No se cargaron fixtures ni
cuentas de prueba en la base activa. No se entrenó ni activó un modelo.

## Comandos PowerShell

```powershell
py -3.12 infra/manage.py prepare
py -3.12 infra/manage.py up
py -3.12 infra/manage.py migrate
py -3.12 infra/manage.py restart
docker compose up -d --wait
docker compose -f infra/compose.test.yaml build tester
docker compose -f infra/compose.test.yaml run --rm tester
npm run generate:api --workspace frontend
.\.venv-s0\Scripts\python.exe infra/check_s0.py
py -3.12 infra/test_browser.py
py -3.12 infra/check_runtime.py
git diff --check
```

up construye frontend con tsc/Vite y migra; check_runtime realiza down/up sin -v.
El respaldo se ejecutó antes de retirar el Compose anterior, con la herramienta
puntual ahora conservada en history. Las operaciones Docker/navegador requirieron
el permiso de consola del entorno Codex; no hubo rechazo automático.

Comandos interactivos listos para el operador, **no usados para inventar una cuenta activa**:

```powershell
py -3.12 infra/manage.py bootstrap-admin
py -3.12 infra/manage.py configure
```

El primero solicita correo, nombre y contraseña sin eco, guarda hash y auditoría
atómicamente y rechaza una segunda creación. El segundo autentica ADMIN y solicita
valores de usuario/periodo/sección. Sus servicios se probaron con PostgreSQL aislado;
no se afirma ejecución manual de una contraseña de operador en la aplicación activa.

## Pendientes y límite

El operador debe crear su cuenta y configurar contexto autorizado cuando corresponda.
No hay cuentas predeterminadas. La aplicación permanece vacía y accesible en localhost:15173.

Para habilitar importación se requiere procedencia autorizada, escalas acordadas,
periodos/ventanas, fechas de corte/objetivo/disponibilidad y calidad implementados.
S3 puede abordar infraestructura predictiva y pruebas aisladas; entrenar/evaluar
institucionalmente exige dataset autorizado, etiquetas futuras y protocolo. Mantener
baseline, Random Forest/SVM/XGBoost, grupos por estudiante, Pipeline y trazabilidad.
Sin modelo: Modelo no disponible/Datos insuficientes, nunca cifras inventadas.

S4–S6, HTTPS/producción, política de retención de archivos y validación académica
siguen pendientes. Esta transición no evalúa la hipótesis ni cambia metodología.
