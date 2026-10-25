# Guion de la sustentación: resultados reales y registro en vivo

Actualizado en el Bloque 9 (2026-10-25): regla de referencia **RIESGO_V2** (sin participación, [ADR 013](../adr/013-riesgo-v2-sin-participacion.md)), modelo **SVM** y
demostración en vivo con **el mismo SVM del estudio real** ([ADR 014](../adr/014-copia-demo-svm-real.md)).

Duración: **parte A (resultados reales) 3–4 min** y **parte B (registro en vivo) 8–10 min**. La parte B se hace en la **instalación hermana de demostración**
(`demo-vivo`, puerto 15174), que tiene los mismos datos reales que la instalación de siempre (`riesgo-escolar`, puerto 15173) **más** un periodo aparte y rotulado,
`DEMO-VIVO`. Procedimiento: [Procedimiento_Preparar_Activa.md](Procedimiento_Preparar_Activa.md); lista del día: [Lista_Dia_Sustentacion.md](Lista_Dia_Sustentacion.md).

## Qué es real y qué no (decirlo al principio de la parte B)

| | Datos | Modelo | Dónde se ve |
|---|---|---|---|
| Resultados del colegio | 60 estudiantes reales, B1 y B2 (periodo `REAL-2026`) | SVM, exploratorio local | Indicadores, Modelos, Alertas (simulación retrospectiva) |
| Registro en vivo | Estudiante **inventado**, escrito en la sala, en el periodo `DEMO-VIVO` | **El mismo SVM del estudio real** (misma huella) | Estudiantes, Alertas, Reportes del periodo `DEMO-VIVO` |

**Un solo modelo.** En `demo-vivo` el periodo `DEMO-VIVO` lo evalúa una copia del SVM real: el mismo archivo del modelo (huella
`45fb6c6b…38261`, idéntica en las dos instalaciones), no un modelo reentrenado ni sintético. En pantalla se lee **«Modelo: SVM del estudio real»**. El estudiante
inventado y su evaluación quedan **solo** en `DEMO-VIVO`: no cambian los 60 estudiantes, los 120 registros ni ninguna cifra de `REAL-2026` (comprobado automáticamente).

## Cuenta

**ADMIN en todos los pasos.** DIRECTOR solo consulta. La sección de la demostración tiene como responsable la cuenta de relleno sin acceso; no hace falta otra cuenta.

## Valores para escribir (comprobados el 2026-10-25 en `demo-vivo` con el SVM del estudio real)

Se piden **cuatro datos** de la **revisión de mitad de bimestre** (la participación ya no se pide ni se muestra):

| Estudiante | Notas obtenidas hasta la fecha | Asistencia hasta la fecha (%) | Tareas entregadas hasta la fecha (%) | Incidencias hasta la fecha | Resultado | Caso |
|---|---|---|---|---|---|---|
| `DEMO-ALTO` | 7 | 50 | 40 | 6 | **Alto** | se abre |
| `DEMO-MEDIO` | 14.5 | 85 | 70 | 0 | **Medio** | se abre |
| `DEMO-BAJO` | 18 | 98 | 95 | 0 | **Bajo** | no se abre |

Fecha y hora de la revisión de mitad de bimestre: 15/04/2025 18:00; «disponible desde» 15/04/2025 17:00; inicio de la ventana 16/03/2025 (el periodo de demostración es 2025).
El caso Medio está **dentro de su clase**: en una rejilla de prueba sus 81 vecinos inmediatos (±0,5 en notas, ±2,5 en asistencia y tareas, ±1 incidencia) también salen Medio,
no hay ningún Bajo a dos pasos y RIESGO_V2 también lo llama Medio (2 puntos). Ojo: un perfil que «parece intermedio» como 12,5 / 82 / 66 / 3 sale Alto, y RIESGO_V2 también
lo llama Alto (5 puntos: suma un punto en cada componente y dos por incidencias). Para valores nuevos, ver la sección del jurado más abajo. En el ensayo usa otros códigos (`ENSAYO-…`): un código repetido devuelve «alumno existente».

## Si el jurado pide probar otros valores

Casos comprobados el 2026-10-25 en `demo-vivo` (evaluación real con el SVM del estudio; códigos `JURADO-…` en `DEMO-VIVO`). En los 12, el nivel mostrado y el guardado
coinciden, y Medio y Alto abrieron alerta. «Estabilidad»: cuántos de los 81 perfiles vecinos (±0,5 en notas, ±2,5 en asistencia y tareas, ±1 incidencia) obtienen el mismo nivel del SVM.

| # | Notas | Asistencia % | Tareas % | Incidencias | SVM | RIESGO_V2 (puntos) | Estabilidad | Nota |
|---|---|---|---|---|---|---|---|---|
| 1 | 19 | 100 | 100 | 0 | Bajo | Bajo (0) | 81/81 | muy bajo riesgo |
| 2 | 16 | 93 | 88 | 0 | Bajo | Bajo (0) | 80/81 | |
| 3 | 15.5 | 92 | 85 | 0 | Bajo | Bajo (0) | 67/81 | **cerca del límite** Bajo/Medio |
| 4 | 15 | 90 | 80 | 0 | Medio | Bajo (0) | 69/81 | **difieren**; cerca del límite |
| 5 | 14 | 90 | 80 | 0 | Medio | Bajo (0) | 81/81 | **difieren** |
| 6 | 15 | 85 | 75 | 0 | Medio | Medio (2) | 81/81 | |
| 7 | 14.5 | 85 | 70 | 0 | Medio | Medio (2) | 81/81 | el Medio del guion |
| 8 | 13.5 | 88 | 80 | 0 | Medio | Medio (2) | 81/81 | |
| 9 | 14 | 85 | 75 | 1 | Medio | Medio (3) | 53/81 | **cerca del límite** Medio/Alto |
| 10 | 13.5 | 85 | 70 | 1 | Alto | Alto (4) | 42/81 | **cerca del límite** Medio/Alto |
| 11 | 12 | 80 | 65 | 2 | Alto | Alto (4) | 81/81 | |
| 12 | 7 | 50 | 40 | 6 | Alto | Alto (8) | 81/81 | muy alto riesgo |

Cómo explicarlo si sale un nivel «inesperado»:
- **El riesgo medio es la clase más difícil de separar.** Está entre las otras dos y depende de pequeñas diferencias en varios indicadores a la vez. Un punto de nota o una incidencia
  más pueden pasar un caso de Medio a Alto (casos 9 y 10). Por eso es la clase con más errores en la validación.
- **El modelo y la regla pueden discrepar.** RIESGO_V2 se calcula con los datos del **fin del bimestre**. El SVM predice desde la **revisión de mitad de bimestre**, lo
  que aprendió de los estudiantes reales. En los casos 4 y 5 el modelo es más cauto que la regla: los marca Medio aunque la regla diría Bajo.
- **Con estudiantes reales el Medio no es raro.**
  - De los 120 registros reales, el modelo final predijo Medio en **26** (14 en B1 y 12 en B2) y la validación (clase modal fuera de muestra) en **25**. La referencia RIESGO_V2
    tiene **26** Medio.
  - En **15** registros coinciden validación y referencia. En una rejilla uniforme de valores, el Medio solo cubre ≈ 3 %, porque la rejilla incluye muchas combinaciones que
    casi no se dan, como notas muy bajas con asistencia perfecta. Los estudiantes reales se concentran donde el Medio sí aparece.
- **Lo que nunca se hace:** cambiar o reentrenar el modelo en la sala, o elegir los valores después de ver el resultado. Si el jurado propone otros valores, se escriben y se
  muestra lo que el modelo responde, recordando que es análisis exploratorio local.

## Parte A: resultados reales (3–4 min, en `riesgo-escolar`, puerto 15173)

Cifras de la tesis (predicción por estudiante, **clase modal** de las 20 repeticiones fuera de muestra del SVM, RIESGO_V2): **kappa 0,728**; **exactitud 82,5 % (99/120)**;
**detección 91,9 % (68/74)**: 85,4 % (35/41) en B1 y 100 % (33/33) en B2; **falsas alarmas 15,2 % (7/46)**. Si se cita el **92,4 %**, aclarar que es el **promedio de las 20
repeticiones** (detección validada del panel), no la clase modal.

| Min | Pantalla | Qué mostrar | Qué decir |
|---|---|---|---|
| 0:00 | **Indicadores**, periodo `REAL-2026`, bimestre B1 | Panel «Detección validada (fuera de muestra)»: **86,2 % ± 1,6** (B1); luego B2: **100 % ± 0** (promedio de 20 repeticiones) | «De los estudiantes con riesgo medio o alto, esto habría detectado el modelo si no los hubiera visto. Por estudiante, con la clase modal, es 91,9 % en total.» |
| 1:15 | misma pantalla, tarjeta **PDER del sistema · en muestra** | 100 % | «Este 100 % es de funcionamiento: el modelo final se ajustó con esos mismos 60 estudiantes. La medida de calidad es la de arriba.» |
| 2:00 | **Modelos** | SVM, «exploratorio local, sin validación externa» | «Cuatro algoritmos comparados con la misma regla fija (F1 macro medio); con RIESGO_V2 queda primero SVM.» |
| 3:00 | **Alertas** | 40 casos marcados «simulación retrospectiva» | Ver «Las 40 alertas» abajo. |

### Las 40 alertas (para responder si preguntan)

Las generó el **modelo final** (SVM entrenado con los 120 registros) al evaluar cada revisión de mitad de bimestre, no las predicciones de validación. Ese modelo marcó Medio o Alto
a **38 registros en B1** y **37 en B2**. El sistema mantiene **una sola alerta abierta por estudiante**, así que se cuentan estudiantes: B1 abrió **38**; en B2 se actualizaron 35 de
ellas y se abrieron **2** nuevas (estudiantes marcados solo en B2): **38 + 2 = 40**. Los 3 estudiantes marcados solo en B1 siguen con su alerta abierta: una evaluación Baja no cierra un
caso. Con las predicciones de **validación** (fuera de muestra) el SVM marca Medio o Alto a 37 en B1 y 38 en B2; por eso no coinciden exactamente con 38 y 37.

## Parte B: registro en vivo (8–10 min, en `demo-vivo`, puerto 15174)

| Min | Acción (paso 1 SIEMPRE: elegir el periodo) | Qué decir y mostrar |
|---|---|---|
| 0:00 | Iniciar sesión como ADMIN. **Estudiantes → Periodo de consulta → `DEMO-VIVO · 2025`.** | Señalar el rótulo «Registro de demostración, no es dato del colegio». «Nada de lo que escriba aquí entra en los resultados reales.» |
| 0:45 | **Nuevo estudiante**: código `DEMO-ALTO`, nombre inventado, la primera sección. **Guardar estudiante y matrícula.** | «El alumno y su matrícula se crean juntos y quedan auditados.» |
| 1:45 | **Nueva medición** con los cuatro datos de `DEMO-ALTO`. **Guardar medición.** | «Son los datos de la revisión de mitad de bimestre. Guardar no evalúa ni inventa una fecha objetivo.» |
| 3:00 | **Evaluar riesgo de este estudiante.** | Mostrar «Alto» y **«Modelo: SVM del estudio real»**. «Es el mismo modelo de los resultados; el nivel no es una probabilidad calibrada.» |
| 4:00 | **Abrir el caso de seguimiento → Planificar actividad** (Tutoría, objetivo breve, 05/05/2025 14:00). | «Una actividad planificada no cuenta como realizada; las decisiones son humanas.» |
| 5:30 | Repetir con `DEMO-MEDIO` y con `DEMO-BAJO`. | «Medio también abre caso; Bajo no. Sin datos suficientes, el sistema no rellena riesgo bajo.» |
| 7:00 | **Reportes** (mismo periodo). | Los tres alumnos; casos activos en `DEMO-ALTO` y `DEMO-MEDIO`; **Descargar CSV**: «sin notas ni nombres». |
| 8:30 | (Opcional) **Indicadores → `REAL-2026`**. | «Los números reales no cambiaron con la demostración.» |
| 9:00 | Cierre | «Mismo modelo del estudio, estudiante de demostración en un periodo aparte que no entra en ningún indicador.» |

Tiempos medidos del recorrido automático (sin hablar, 2026-10-25): registrar estudiante ≈ 1 s; medición < 1 s; evaluar ≈ 1–1,5 s; abrir el caso y planificar ≈ 1 s; reporte ≈ 1 s;
**total ≈ 9–10 s** para los tres estudiantes. Los 8–10 min del guion son de explicación.

## Plan B (si algo falla)

Capturas del mismo recorrido, revisadas, en `tests/evidence/`: `mejoras-09-e2e-periodo-demostracion-*`, `mejoras-09-e2e-evaluacion-alto-*`, `mejoras-09-e2e-caso-actividad-*`,
`mejoras-09-e2e-evaluacion-medio-*`, `mejoras-09-e2e-evaluacion-bajo-*`, `mejoras-09-e2e-reportes-*` (tres tamaños) y las pantallas `mejoras-09-demo-vivo-*-1440x900.png`.
Para la parte A, `mejoras-09-principal-*` (datos reales tapados en las capturas). Los datos reales por alumno **no** están en las capturas.

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| El periodo `DEMO-VIVO` no aparece | Se abrió `riesgo-escolar` | Cambiar a 15174. |
| «No hay un modelo activo para este periodo» | Periodo equivocado | Revisar el periodo; en **Modelos** debe figurar activa «SVM del estudio real (copia de demostración)». Si no, plan B. |
| «Modelo no disponible» al evaluar | La instalación no tiene encendida la copia de demostración | Usar 15174 (en 15173 está apagada a propósito). Plan B. |
| «Alumno existente» | Código ya usado | Usar otro código. |
| Error 5xx | Servicio caído | `runtime_target.py up --target <demo-vivo.json>`; nunca `down -v`. |
| Riesgo distinto al esperado | Valor tecleado distinto | Revisar los cuatro datos; no se promete exactitud. |

## Preguntas probables y respuestas honestas

- **¿Por qué ya no está la participación?** La institución confirmó que no existe un registro original de la participación en aula. Se definió RIESGO_V2 (cuatro componentes;
  Alto ≥ 4, el 50 % del máximo como en V1) **antes** de reentrenar; V1 se conserva para trazabilidad.
- **¿Se probó con datos reales?** Sí, con los 60 estudiantes: evaluación retrospectiva y validación cruzada fuera de muestra (kappa 0,728 y exactitud 82,5 % por estudiante; detección
  91,9 %). Es análisis exploratorio local, no validación externa.
- **¿El modelo de la demostración es el mismo?** Sí: el mismo archivo del SVM (misma huella). Solo se registra aparte para el periodo de demostración (ADR 014).
- **¿SVM es el mejor?** Queda primero por la regla fija (F1 macro 0,792 frente a 0,776 de Random Forest; exactitud 0,826 frente a 0,813), con diferencias del orden de la
  variación entre repeticiones.
- **¿Mide impacto?** No. NIA e intervención oportuna reales quedan «sin dato» por falta de intervenciones reales registradas.
- **¿Hay validación externa?** No. 60 estudiantes (120 observaciones no independientes), modelo `LOCAL_EXPLORATORY`.
- **¿Las alertas son reales?** Las de `REAL-2026` son «simulación retrospectiva» (ver «Las 40 alertas»).

## Limitaciones (decirlas si preguntan)

Modelo `LOCAL_EXPLORATORY` con 60 estudiantes; alertas retrospectivas; NIA e intervención oportuna reales no calculables; PRV sin procedencia confirmada; el SVM predice Medio en
una franja estrecha; la demostración vive en una instalación aparte de la de siempre.
