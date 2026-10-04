# Pruebas S2.2

Evidencias S0/S1/S2/S2.1 conservadas como historia, sin regenerarlas.
Nuevos resultados s2-2-*: backend en contenedor Linux/Python 3.12.12, PostgreSQL 17.6
aislado, host Windows. Aplicación y concurrencia usan riesgo_app; propietario solo
migra/prepara fixtures y verifica triggers contra manipulación del propietario.

Semillas retiradas: sus casos se reemplazan por bootstrap explícito, repetición,
rollback, configuración y contexto vacío. El motor S2 se prueba con un monkeypatch
de política limitado a pytest, sin interruptor de configuración ni modo demo.
Origen REAL en esas filas es la forma del esquema institucional, pero son fixtures
fabricados identificados por su base aislada; nunca se presentan como datos del colegio.

Las pruebas de catálogo REAL ahora comprueban lectura autorizada; importación conserva
bloqueo real en pruebas sin parche. El modelo de fixture queda inactivo: se comprueba
ausencia de riesgo vigente e historial sin permitir activación operativa.

Playwright usa runner test_browser.py y cuatro cuentas en base aislada, con contraseña
en memoria; comprueba teclado, contexto vacío, cookies, CSRF y revocación.
Se retiraron CSV de ejemplo no usados; las pruebas fabrican sus bytes en memoria.

review_browser.py realiza además el encargo explícito de acceso en localhost activo
con las cuatro credenciales privadas Windows. Evidencias active/isolated separadas;
active-first conserva el fallo inicial del estado del investigador. El reporter
publica solo títulos, estado y duración: nunca cuerpos, argumentos, trazas o secretos.
