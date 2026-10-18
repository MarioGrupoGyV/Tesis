# Guion de la sustentación: resultados reales y registro en vivo

Duración: **parte A (resultados reales) 3–4 min** y **parte B (registro en vivo) 8–10 min**. La parte B se hace en la **instalación hermana de
demostración** (`demo-vivo`, puerto 15174), que tiene los mismos datos reales que la instalación de siempre (`riesgo-escolar`, puerto 15173) **más** un periodo
aparte y rotulado, `DEMO-VIVO`. Procedimiento para dejarla lista: [Procedimiento_Preparar_Activa.md](Procedimiento_Preparar_Activa.md); lista del día:
[Lista_Dia_Sustentacion.md](Lista_Dia_Sustentacion.md).

## Qué es real y qué no (decirlo al principio de la parte B)

| | Datos | Modelo | Dónde se ve |
|---|---|---|---|
| Resultados del colegio | 60 estudiantes reales, B1 y B2 (periodo `REAL-2026`) | Random Forest, exploratorio local | Indicadores, Modelos, Alertas (simulación retrospectiva) |
| Registro en vivo | Estudiante **inventado**, escrito en la sala | SVM técnico sintético del periodo `DEMO-VIVO` | Estudiantes, Alertas, Reportes del periodo `DEMO-VIVO` |

**Por qué el registro en vivo no usa el modelo de los datos reales.** Un registro manual no se mezcla con los datos del colegio: el sistema no evalúa mediciones
manuales dentro de un periodo real, y permitirlo exigiría aflojar las reglas de integridad de la base (se decidió no hacerlo; ver ADR 012, Bloque 6). Por eso el flujo
completo (registro, medición, evaluación, alerta, intervención, reporte) se muestra en un periodo sintético rotulado «Registro de demostración, no es dato del
colegio» y no entra en ningún indicador de `REAL-2026`.

## Cuenta

**ADMIN en todos los pasos** (es quien crea estudiantes, registra mediciones, evalúa y gestiona casos). DIRECTOR solo consulta, y se puede mostrar al final para enseñar
la vista de solo lectura. No hace falta ninguna cuenta nueva: la sección de la demostración tiene como responsable la cuenta de relleno sin acceso, y el tutor no inicia sesión.

## Valores para escribir (comprobados el 2026-10-18 en una copia con este mismo modelo: SVM, semilla 1729)

| Estudiante | Promedio | Asistencia % | Actividades % | Participación | Incidencias | Resultado | Caso |
|---|---|---|---|---|---|---|---|
| `DEMO-ALTO` | 7 | 50 | 40 | 1 | 8 | **Alto** | se abre |
| `DEMO-BAJO` | 18 | 98 | 95 | 3 | 0 | **Bajo** | no se abre |
| `DEMO-MEDIO` (opcional) | 12 | 75 | 70 | 2 | 4 | **Medio** | se abre |

Corte: 15/04/2025 18:00; «disponible desde» 15/04/2025 17:00; inicio de la ventana 16/03/2025 (todo dentro del periodo, que es 2025). La participación es 1–3 porque el modelo
sintético usa esa escala (con 4 o 5 la evaluación se rechaza, correctamente). Otro medio comprobado: 15 / 90 / 85 / 2 / 1. **Cuidado:** 10 / 65 / 60 / 2 / 5 da Alto, no Medio.
Los resultados dependen del modelo entrenado en cada instalación: repetir en el ensayo general. **Para el ensayo general usa otros códigos** (`ENSAYO-ALTO`, `ENSAYO-BAJO`):
un código ya usado devuelve «alumno existente» y la demo del día debe empezar con los suyos limpios.

## Parte A: resultados reales (3–4 min, en `riesgo-escolar`, puerto 15173)

| Min | Pantalla | Qué mostrar | Qué decir |
|---|---|---|---|
| 0:00 | **Indicadores**, periodo `REAL-2026`, bimestre B1 | Panel «Detección validada (fuera de muestra)»: **87,3 % ± 2,4** (B1); luego B2: **100 % ± 0** | «De los estudiantes con riesgo medio o alto, esto habría detectado el modelo si no los hubiera visto (validación cruzada, 20 repeticiones). Ningún alto se confundió con bajo.» |
| 1:15 | misma pantalla, tarjeta **PDER del sistema · en muestra** | 100 % | «Este 100 % es de funcionamiento: el modelo se ajustó con esos mismos 60 estudiantes. La medida de calidad es la de arriba.» |
| 2:00 | **Modelos** | Random Forest, «exploratorio local, sin validación externa» | «Cuatro algoritmos comparados; Random Forest queda primero por regla fija y empata técnicamente con SVM.» |
| 3:00 | **Alertas** | Casos marcados «simulación retrospectiva» | «Se generaron ahora sobre cortes pasados: no son alertas emitidas en su momento.» |

## Parte B: registro en vivo (8–10 min, en `demo-vivo`, puerto 15174)

| Min | Acción (paso 1 SIEMPRE: elegir el periodo) | Qué decir y mostrar |
|---|---|---|
| 0:00 | Iniciar sesión como ADMIN. **Estudiantes → Periodo de consulta → `DEMO-VIVO · 2025`.** | Señalar el rótulo «Registro de demostración, no es dato del colegio · datos sintéticos». «Esto es una demostración con un periodo aparte; nada de lo que escriba aquí entra en los resultados reales.» |
| 0:45 | **Nuevo estudiante**: código `DEMO-ALTO`, nombre inventado, sección «1.º · SYN-…-A» (la primera). **Guardar estudiante y matrícula.** | «El alumno y su matrícula se crean juntos y quedan auditados.» |
| 1:45 | **Nueva medición** con los valores de `DEMO-ALTO` (tabla). **Guardar medición.** | «Guardar no evalúa riesgo y no inventa una fecha objetivo: el horizonte lo define el modelo.» |
| 3:00 | **Evaluar riesgo de este estudiante.** | Mostrar «Alto», **«Modelo que hizo la evaluación: SVM (simulación técnica con datos sintéticos)»** y el horizonte del modelo. «El nivel no es una probabilidad calibrada.» |
| 4:00 | **Abrir el caso de seguimiento → Planificar actividad** (tipo Tutoría, objetivo breve, fecha 05/05/2025 14:00). | «Una actividad planificada no cuenta como realizada; las decisiones pedagógicas son humanas y no se envía nada a nadie.» |
| 5:30 | Repetir con `DEMO-BAJO`: registrar, medir, evaluar. | «Riesgo bajo no abre caso; y cuando faltan datos tampoco se rellena riesgo bajo.» |
| 7:00 | **Reportes** (mismo periodo). | Ambos alumnos, caso activo solo en `DEMO-ALTO`; **Descargar CSV**: «sin notas ni nombres». |
| 8:00 | (Opcional) **Evaluar** de nuevo a `DEMO-ALTO`. | «Es idempotente: reutiliza la evaluación y el mismo caso.» |
| 8:30 | (Opcional) **Indicadores → `REAL-2026`**. | «Los números reales son exactamente los mismos que antes de la demostración (comprobado automáticamente).» |
| 9:00 | Cierre | «Registro de demostración rotulado, en un periodo aparte, que no entra en ningún indicador.» |

Tiempos medidos del recorrido automático (sin hablar): inicio de sesión 11–18 s; registrar estudiante 3–6 s; medición 1–2 s; evaluar 2–3 s; abrir el caso y planificar 6 s;
segundo estudiante y evaluación 4–5 s; reporte 2 s; **total ≈ 20–26 s**. Los 8–10 min del guion son de explicación, no de espera del sistema.

## Plan B (si algo falla)

Capturas del mismo recorrido, ya revisadas, en `tests/evidence/`: `mejoras-06-demo-periodo-demostracion-*`, `mejoras-06-demo-evaluacion-alto-*`,
`mejoras-06-demo-caso-actividad-*`, `mejoras-06-demo-reportes-*` (tres tamaños cada una) y, para la parte A, `mejoras-051-real-indicadores-B1-*` / `-B2-*`.
Tenerlas abiertas en otra ventana. Los datos reales por alumno **no** están en las capturas.

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| El periodo `DEMO-VIVO` no aparece | Se abrió `riesgo-escolar` en lugar de `demo-vivo` | Cambiar a 15174. `riesgo-escolar` solo tiene datos reales. |
| Botón «Evaluar» deshabilitado («No hay un modelo activo…») | Periodo equivocado o modelo no activo | Revisar el periodo; en **Modelos**, el sintético debe figurar activo. Si no, plan B. |
| «Valores fuera de la escala del modelo activo» | Participación 4–5 | Corregir la medición (nueva revisión) con participación 1–3. |
| «Alumno existente» | Código ya usado en el ensayo | Usar otro código. |
| Error 5xx o sin respuesta | Servicio caído | `docker compose ps`; no usar `down -v`. Para `demo-vivo`: `runtime_target.py up --target <destino.json>`. |
| Riesgo distinto al esperado | El modelo decide | Aclararlo: es una simulación; no se promete exactitud. |

## Preguntas probables y respuestas honestas

- **¿Se probó con datos reales?** Sí, con los 60 estudiantes del colegio: una evaluación retrospectiva sobre cortes pasados y una validación cruzada fuera de muestra
  (exactitud ≈ 86 %, F1 macro 0,85; detección de riesgo medio o alto ≈ 93 % ± 1,4, y ningún alto confundido con bajo). Es análisis exploratorio local, no una validación externa.
- **¿Mide impacto?** No. NIA e intervención oportuna reales no se pueden calcular sin registros reales de intervenciones; el sistema los deja en «sin dato» y no los rellena.
  El PDER y el CRA del sistema son de funcionamiento (en muestra); la medida de calidad es la detección validada.
- **¿Hay validación externa?** No. Son 60 estudiantes (120 observaciones no independientes), el modelo es `LOCAL_EXPLORATORY` y la dispersión entre repeticiones no es un intervalo de confianza.
- **¿Random Forest es el mejor?** Queda primero por una regla fija (F1 macro medio), pero empata técnicamente con SVM: exactitud 0,863 frente a 0,857 y F1 macro 0,848 frente a 0,842, dentro de la variación entre repeticiones.
- **¿El estudiante de la demostración es real?** No. Es un registro de demostración, rotulado, en un periodo aparte, que no entra en ningún indicador ni en el modelo.
- **¿Por qué la demostración en vivo no usa el modelo de los datos reales?** Porque los registros manuales no se mezclan con los datos del colegio; el flujo se muestra con un modelo técnico sintético para no contaminar los resultados reales.
- **¿Qué pasa con la recepción de registros (PRV)?** No se informa para los datos reales: la procedencia de la recepción (126 recibidas, 6 rechazadas, 113 de 120 reportes) no está confirmada.
- **¿Las alertas son reales?** Las del periodo real son «simulación retrospectiva»: las generó el modelo ahora sobre cortes pasados.

## Limitaciones (decirlas si preguntan)

Modelo `LOCAL_EXPLORATORY` con 60 estudiantes; alertas retrospectivas; NIA e intervención oportuna reales no calculables; PRV sin procedencia confirmada; el periodo de demostración es un
registro de prueba y vive en una instalación aparte de la de siempre.
