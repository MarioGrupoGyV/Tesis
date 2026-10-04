# Infraestructura Windows / Docker Desktop

Desde PowerShell: py -3.12 infra/manage.py prepare/up/migrate/restart/down
(usar una acción por llamada). bootstrap-admin y configure son interactivos.

Proyecto riesgo-escolar; base riesgo_escolar; .local/runtime-secrets; volúmenes
db_data, import_data y ml_data. Conserva las cuatro cuentas/credenciales S2.2 y volúmenes actuales.
Los Dockerfiles y db/init-app-role.sh son componentes internos de Docker Linux;
no exigen Bash/WSL al operador Windows. Versiones e imágenes conservadas.

run_backend_tests.py ejecuta la suite dentro del contenedor con base aislada nueva.
test_browser.py crea otra base aislada, cuatro cuentas efímeras y contexto vacío; cada contraseña
solo vive en memoria y entorno del proceso hijo, sin trazas ni archivos de cuentas.
check_runtime.py verifica exclusivamente una instalación todavía vacía; no ejecutarlo
sobre la aplicación con cuentas y estudio SYNTHETIC.
check_s0.py valida contratos actuales, tipos, Compose y locks; no sustituye pruebas.

Preparación histórica S2.2: review_accounts.py creó explícitamente las cuatro cuentas
locales autorizadas; no repetir ni restablecerlas. windows_credentials.py permite
consultarlas en una ventana privada. review_endpoints.py conserva aquella revisión
de bloqueo total; review_browser.py se adapta al contexto sintético actual por rol.
check_access_persistence.py conserva también las cuentas y auditoría existentes al
recrear; check_runtime.py mantiene su restricción a una instalación totalmente vacía.
check_review.py conserva las comprobaciones de aquel cierre histórico.

history/archive_s2.py documenta el respaldo previo y se niega a ejecutarse sobre el
Compose actual. No forma parte del arranque. Respaldos/secrets previos privados
conservados; las evidencias históricas son inmutables.

S3 añadió ml_data en /var/lib/riesgo/ml. S3.1 guarda el estudio/artefactos sintéticos nuevos allí, privados y persistentes.
ml.py consulta readiness/configuration/compatibility y rechaza train institucional.
review_s3.py y check_s3.py pertenecen al cierre histórico S3, con listas vacías y
bloqueo total; no se ejecutan sobre el estudio actual. S3 añadió xgboost-cpu 3.4.1
con hashes y sin GPU; S3.1 conserva esa dependencia y los locks.

## S3.1 vigente

study.py generate/import/compare/register/activate/run/status requiere --admin-credential
ADMIN explícito, autentica la cuenta local existente y nunca imprime contraseña.
review_study.py ejecuta el recorrido real y revisión de cuatro roles con evidencia
sanitizada. sync_study_contract.py regenera contrato 0.4.0; check_study.py contrasta
rutas/respuestas/conservación/métricas. Informes nuevos con prefijo s3-1, históricos intactos.
Desde PowerShell, `$env:PERSISTENCE_REPORT_PREFIX = 's3-1'`,
`$env:BROWSER_REPORT_PREFIX = 's3-1'` y `$env:REVIEW_REPORT_PREFIX = 's3-1-active'`
evitan reescribir evidencias anteriores.

No ejecutar check_runtime (base vacía) ni los revisores históricos que esperan bloqueo
total/listas vacías sobre este estudio poblado. check_access_persistence conserva las
14 tablas, artefactos, usuarios, contraseñas y auditoría al recrear sin borrar volúmenes.
Manual_Estudio_Sintetico.md documenta comandos, protocolo, hashes y límites.
