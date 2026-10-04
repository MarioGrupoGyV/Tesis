# Infraestructura Windows / Docker Desktop

Desde PowerShell: py -3.12 infra/manage.py prepare/up/migrate/restart/down
(usar una acción por llamada). bootstrap-admin y configure son interactivos.

Proyecto riesgo-escolar; base riesgo_escolar; .local/runtime-secrets; volúmenes
db_data e import_data. No reutiliza volúmenes ni cuentas anteriores.
Los Dockerfiles y db/init-app-role.sh son componentes internos de Docker Linux;
no exigen Bash/WSL al operador Windows. Versiones e imágenes conservadas.

run_backend_tests.py ejecuta la suite dentro del contenedor con base aislada nueva.
test_browser.py crea otra base aislada, cuatro cuentas efímeras y contexto vacío; cada contraseña
solo vive en memoria y entorno del proceso hijo, sin trazas ni archivos de cuentas.
check_runtime.py verifica el entorno activo vacío y persistencia sin registros escolares.
check_s0.py valida contratos actuales, tipos, Compose y locks; no sustituye pruebas.

S2.2: review_accounts.py prepara explícitamente las cuatro cuentas locales autorizadas;
windows_credentials.py permite consultarlas en una ventana privada. review_endpoints.py
y review_browser.py revisan la aplicación activa sin inventar registros escolares.
check_access_persistence.py conserva también las cuentas y auditoría existentes al
recrear; check_runtime.py mantiene su restricción a una instalación totalmente vacía.
check_review.py contrasta rutas/respuestas activas, archivos protegidos y respaldo.

history/archive_s2.py documenta el respaldo previo y se niega a ejecutarse sobre el
Compose actual. No forma parte del arranque. Respaldos/secrets previos privados
conservados; las evidencias históricas son inmutables.
