# Guion de demostración en vivo: registro manual → evaluación → seguimiento

Duración aproximada: **8–10 minutos**. Todo ocurre en un periodo **SYNTHETIC** con datos
ficticios: los alumnos de la demo no son personas observadas y el resultado no valida la
tesis ni el desempeño en el colegio. REAL permanece bloqueado.

## Precondiciones (preparar antes, no durante la demo)

Usar una instalación aislada o una copia de ensayo; **no** repetir bootstrap, no restablecer
contraseñas y no ejecutar limpieza sobre la instalación activa. Según
[Manual_Estudio_Sintetico.md](Manual_Estudio_Sintetico.md) y
[Manual_Instalacion_Windows.md](Manual_Instalacion_Windows.md):

1. Estudio sintético preparado (`study.py generate`) y su CSV registrado importado (`study.py import`).
2. Modelo comparado, registrado y **activado** (`study.py compare`, `register`, `activate`).
3. Cuenta ADMIN disponible y, para la parte final, TUTOR con la sección del estudio.
4. Comprobar en Modelos que hay un modelo activo; sin él el botón queda deshabilitado.

El periodo del estudio sintético usa el año 2025 (2025-01-01 a 2025-12-31). Las mediciones de
ejemplo usan un corte pasado dentro de ese periodo.

## Datos de ejemplo (ficticios) — ensayados con el modelo real

Ensayo del 2026-10-17 en una instalación **aislada** (estudio sintético semilla 1729, modelo SVM
activo). Se registró el riesgo que **devolvió el modelo**, no el esperado:

| Alumno | Promedio | Asistencia % | Actividades % | Participación | Incidencias | Riesgo observado | Caso |
|---|---|---|---|---|---|---|---|
| DEMO-ALTO | 7 | 50 | 40 | 1 | 8 | **ALTO** | Se crea |
| DEMO-BAJO | 18 | 98 | 95 | **3** | 0 | **BAJO** | No se crea |
| (intermedio A) | 12 | 75 | 70 | 2 | 4 | **MEDIO** | Se crea |
| (intermedio B) | 15 | 90 | 85 | 2 | 1 | **MEDIO** | Se crea |

Corte: 2025-04-15 18:00 (Lima); disponible desde 2025-04-15 17:00; inicio de ventana 2025-03-16.

**Importante:** el modelo sintético usa participación en categorías **1–3** (el formulario admite
1–5). Con 4 o 5 la evaluación se rechaza con el mensaje «valores fuera de la escala del modelo
activo» y no se asigna riesgo; por eso DEMO-BAJO usa participación 3. Un valor 5 en el primer
ensayo produjo ese rechazo. Otros datos intermedios (p. ej. promedio 15, asistencia 90) dan MEDIO:
si se quiere mostrar un caso MEDIO, usar la fila «intermedio A». Los resultados dependen del
modelo entrenado en cada instalación: repetir el ensayo si se regenera o reactiva.

## Guion

| Min | Acción | Qué decir |
|---|---|---|
| 0:00 | Iniciar sesión como ADMIN, abrir **Estudiantes** y elegir el periodo sintético. | «Trabajamos con datos ficticios; REAL está bloqueado hasta tener protocolo.» |
| 1:00 | **Nuevo estudiante**: código DEMO-ALTO, nombre ficticio, sección del estudio. Guardar. | «El alumno y su matrícula se crean de forma atómica y quedan auditados.» |
| 2:00 | **Nueva medición** con los valores de DEMO-ALTO. Guardar. | «Guardar no evalúa riesgo; no inventamos una fecha objetivo.» |
| 3:30 | **Evaluar riesgo de este estudiante**. Mostrar riesgo y «Horizonte del modelo». | «El horizonte lo define el modelo (corte + 14 días); no es un dato observado. El nivel no es una probabilidad calibrada.» |
| 4:30 | **Abrir el caso de seguimiento**; **Planificar actividad** (objetivo breve, fecha futura). | «Una actividad planificada no cuenta como realizada; las decisiones pedagógicas son humanas.» |
| 6:00 | Repetir con DEMO-BAJO: registrar, evaluar. | «Riesgo bajo no crea caso; tampoco se rellena riesgo bajo cuando faltan datos.» |
| 7:00 | Volver a **Evaluar** en DEMO-ALTO. | «Es idempotente: reutiliza la evaluación y el mismo caso.» |
| 7:30 | Abrir **Reportes**: ambos alumnos, caso activo solo en DEMO-ALTO; **Descargar CSV**. | «El CSV no incluye notas ni nombres.» |
| 8:30 | (Opcional) Corregir la medición de DEMO-ALTO y evaluar de nuevo. | «Una corrección crea una revisión; la evaluación anterior no se aplica a la nueva.» |

## Si algo falla

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| Botón deshabilitado «No hay un modelo activo» | Modelo no activado | Activar con `study.py activate` antes de la demo; mostrar el resto con capturas. |
| «Registra una medición antes de evaluar» | Falta medición | Guardar la medición primero. |
| «Datos insuficientes» | Falta el promedio u otras variables | Es el comportamiento correcto: no se asigna riesgo. Completar la medición (revisión). |
| «No elegible para la simulación» | Alumno creado antes del Bloque 1 | Usar un alumno nuevo. |
| 409 periodo bloqueado | Periodo cerrado | Reabrirlo en Editar periodo (ADMIN). |
| «Valores fuera de la escala del modelo activo» | Participación 4–5 u otro valor fuera de rango | Corregir la medición (nueva revisión) con participación 1–3. |
| Riesgo distinto al esperado | El modelo decide | Aclararlo: es una simulación; no se promete exactitud. |
| Error 5xx o sin respuesta | Servicio caído | `docker compose ps`; reiniciar con `docker compose up -d --wait`. No usar `down -v`. |
