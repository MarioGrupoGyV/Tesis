# Sprints y aceptación vigente

S0, S1 y S2: cerrados bajo el alcance histórico anterior. Sus reportes/evidencias
se conservan intactos. S2.1 reemplaza las instrucciones operativas de ese alcance.

| Sprint | Estado | Dependencia y criterio de salida |
|---|---|---|
| S2.1 | Implementado; resultados en Estado_Sprint_2_1.md | Windows/PowerShell con Docker, respaldo restaurado, nuevo entorno vacío, bootstrap explícito, contrato 0.2.0, bloqueo institucional y regresión |
| S2.2 | Comprobado; Estado_Sprint_2_2.md y Matriz_verificacion_S2_2.md | Cuatro cuentas locales explícitas con credenciales privadas Windows; revisión de 14 rutas y UI por rol/tamaño; persistencia con usuarios y regresión aislada; sin registros escolares ni habilitación institucional |
| S3 | Pendiente | S2.1; pipeline e inferencia trazables. Entrenamiento/evaluación requiere datos autorizados, etiquetas verificables y protocolo |
| S4 | Pendiente | S2.1/S3 para flujos iniciales; S5 para integración completa. Pantallas reales, estados útiles, teclado y tres tamaños |
| S5 | Pendiente | Predicción válida, sesiones, matrículas y protocolo; alertas únicas, seguimiento versionado, auditoría y exportaciones autorizadas |
| S6 | Pendiente | S3–S5 integrados; recorrido completo, persistencia, restauración, documentación y evidencias verificables |

## Aceptación S2.1

1. SHA inicial y cambios registrados; no descartar trabajo. Versiones/locks conservados.
2. Respaldo privado de base/CSV restaurado en destino aislado antes de retirar el
   entorno anterior; ninguna eliminación ni conversión de origen.
3. Proyecto, base, secretos y volúmenes nuevos; cero cuentas y registros precargados.
4. Preparación/arranque/migración/parada/reinicio/pruebas desde PowerShell. Componentes
   Linux solo internos de Docker; no afirmar ejecución backend nativa Windows.
5. Primer administrador por entrada interactiva sin contraseña persistida, repetición
   rechazada, hash y auditoría atómicos. Configuración posterior con valores del operador.
6. Origen institucional en contrato; 422 INSTITUTIONAL_PROCESSING_NOT_READY en importación,
   sin archivos ni escrituras escolares. No existe bypass por variable de entorno.
7. Conservación del motor S2 con pruebas aisladas de transacciones, concurrencia,
   revisiones, integridad/409, fechas, idempotencia, permisos, CSRF y archivos alterados.
8. Migración nueva sin alterar snapshot 0001; relaciones, funciones, triggers y permisos.
9. Acceso/contexto vacío sin textos ni cuentas de demostración, tres tamaños y teclado.
10. Tipos regenerados, build, validación contractual, PostgreSQL y Playwright; resultados,
    fallos y omisiones explícitos. S3–S6 no implementados.

## Reglas siguientes

No reutilizar una escuela ficticia ni planificar un generador de 60 alumnos.
S3 conserva baseline, Random Forest, SVM y XGBoost según el plan académico, Pipeline,
separación por estudiante, prevención de fuga, trazabilidad y abstención.
No prometer precisión, fabricar riesgo bajo ni declarar evaluada la hipótesis.
S4/S5/S6 mantendrán permisos servidor/sección, UTC y días Lima, campos públicos,
evidencias inmutables, versiones esperadas y auditoría transaccional.
Los criterios previos detallados se preservan en history/Sprints_y_aceptacion_S2.md
como historia; las obligaciones de crear/entrenar/mostrar una demo quedan sustituidas.
