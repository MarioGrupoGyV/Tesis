# Muestras exclusivamente sintéticas — S2

No proceden de un colegio ni de registros de personas. Usan el contexto DEMO-2026
y las secciones 1/A y 2/A creadas por la semilla S1.

- valid.csv: dos códigos DEMO-S2, valores faltantes y corte cercano al cambio de día UTC.
- correction.csv: corrección del primer corte; tras valid.csv crea revisión 2.
- invalid.csv: tres filas inválidas por escala, precisión, fechas y duplicados.
- invalid_headers.csv: columna adicional prohibida.

Los ejemplos válidos no representan resultados académicos ni predicciones.
Solo esta carpeta permite versionar CSV; las cargas privadas permanecen en el
volumen import_data, fuera del repositorio. Instrucciones en
[manual S2](../../../docs/manuals/Importacion_S2.md).
