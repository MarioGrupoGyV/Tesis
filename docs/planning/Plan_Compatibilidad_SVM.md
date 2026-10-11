# Compatibilidad del SVM retrospectivo

Solicitud explícita del 2026-10-11. Se conserva S6, REAL operativo bloqueado y
el único entorno virtual Windows backend/.venv. Se autoriza un intérprete aislado
de inferencia dentro de Docker con Python 3.12.14, scikit-learn 1.8.0, NumPy 2.3.5,
SciPy 1.17.0 y joblib 1.5.3, coincidentes con resultados.json del ZIP.

El backend conserva sus locks y ejecuta un proceso separado con JSON por stdin;
sin fallback al intérprete incompatible, sin fit, sin copiar datos reales al repo.
Hash del modelo y paquete originales se verifican antes de deserializar.
Cada nueva ejecución comprueba versiones antes de cargar el modelo; las
advertencias se conservan y una incompatibilidad rechaza la inferencia.
Las ejecuciones históricas permanecen firmadas e intactas.

Antes de actualizar el destino activo se toma respaldo DPAPI y huellas de cuentas,
tablas y archivos. Cierre: build con versiones/hashes fijos, pruebas de aislamiento,
inferencia y API, Playwright real, evaluación de 60 B2 y reinicio de API/web con
verificación de cuentas e historial. Las evidencias nuevas no sobrescriben las
anteriores. Instalación y reproducción se documentan en el manual específico.
