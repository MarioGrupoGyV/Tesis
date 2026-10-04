# Inicio de la implementación en Codex

Este archivo acompaña al plan del sistema de riesgo escolar. Incluye prompts por rol e iteración y cinco procedimientos reutilizables propuestos como skills de proyecto. El contenido no instala skills ni configura agentes activos. Se puede usar inmediatamente como instrucciones de trabajo.

## 1 Preparar el repositorio

Crear un repositorio vacío llamado, por ejemplo, `tesis-riesgo-escolar`. Copiar AGENTS.md en la raíz. Colocar el plan, este archivo, el contrato YAML y el SQL en `docs/planning/`. Los documentos académicos pueden referenciarse desde `docs/research/` si contienen solo información publicable; los registros reales permanecen fuera de Git.

Estructura propuesta:

```text
frontend/
  src/app/
  src/components/
  src/features/{auth,dashboard,students,imports,alerts,reports,models}/
  src/lib/
backend/
  app/api/v1/
  app/core/
  app/models/
  app/schemas/
  app/repositories/
  app/services/
  app/ml/{features,train,evaluate,predict}/
  migrations/
  tests/
docs/{planning,research,adr,manuals}/
infra/
tests/e2e/
AGENTS.md
Makefile
compose.yaml
.env.example
```

Las llaves representan grupos de carpetas, no nombres literales. `.env.example` no contiene secretos. Los artefactos de modelos y archivos de importación se almacenan fuera del repositorio con referencias controladas. La demo es reproducible con una semilla fija; se debe evitar que un reinicio de aplicación regenere datos silenciosamente.

## 2 Prompt de coordinación para la entrega completa

```text
Implementa la demo del sistema de riesgo escolar descrita en docs/planning y AGENTS.md.
La aplicación empieza desde cero, los registros institucionales están en trámite y el
presupuesto es un día. Desarrolla el recorrido esencial con datos sintéticos identificados.

Antes de editar, lee el plan, el contrato API y el SQL. Revisa el entorno. Fija versiones
compatibles y registra los cambios necesarios en una decisión de arquitectura. Organiza
S0 a S6 y actualiza el progreso. Trabaja hasta completar el alcance de la demo; no te
detengas en una propuesta o en componentes sin conexión.

Implementa PostgreSQL real, migraciones, sesiones y permisos, CSV con vista previa y
confirmación atómica, estudiantes, Random Forest demo con baseline, alertas,
intervenciones, tablero y CSV. Bloquea el modo institucional. No inventes endpoints,
resultados académicos ni explicaciones causales. No añadas módulos fuera del plan.

Comprueba datos persistidos, idempotencia, alcance del tutor, separación por estudiante,
fechas de corte y objetivo, concurrencia y el recorrido importar evaluar atender exportar.
Ejecuta build y pruebas; revisa escritorio tablet y móvil con capturas de la aplicación real.

Si el tiempo se reduce, aplica los recortes previstos en el plan y conserva permisos,
persistencia y verificación. Termina con instrucciones de arranque, estado de cada
módulo, evidencia de comprobaciones y pendientes explícitos. Nunca llames validada
para tesis a una demo con datos sintéticos.
```

Este prompt autoriza desarrollar la demo cuando se use en el repositorio. No autoriza procesar datos personales, publicar un servidor, contactar a la institución ni modificar los documentos de investigación.

## 3 Encargos de agentes

### Coordinación y arquitectura

Leer fuentes y contratos. Mantener el alcance demo, el orden de dependencias, las decisiones y la integración. Editar configuración raíz y migraciones compartidas. Aceptar un componente cuando cumple contrato y pruebas. Entregar `docs/adr/001-arquitectura.md`, el estado de sprints y la lista final de comprobaciones.

### Backend y datos

Implementar `backend/app` excepto `ml`. Crear esquemas Pydantic y servicios de importación, autorización, estudiantes, alertas, intervenciones y reportes. Usar los 13 modelos base del SQL y pedir al integrador la migración. Verificar pertenencia a sección, transacciones, idempotencia, bloqueo real y control de versiones. No introducir dependencias de mensajería ni entrenamiento pesado en una petición.

### Frontend y experiencia

Implementar exclusivamente `frontend`. Seguir cinco entradas de navegación y el flujo didáctico del plan. Consumir API tipada, mostrar origen DEMO, estados vacíos y errores, riesgo con texto y fecha. Incorporar formularios breves e invalidación de consultas después de cambios. No inventar probabilidades ni indicadores en componentes. Entregar capturas de tres tamaños y recorrido con API.

### Machine Learning

Implementar `backend/app/ml` y comandos de generación y entrenamiento. Entregar una interfaz `predict_snapshot(snapshot, model_metadata)` acordada con backend. Crear baseline y RF sobre datos sintéticos con cortes anteriores al horizonte, separar estudiantes en evaluación y guardar manifiesto. Abstenerse ante entradas insuficientes. No usar variables posteriores al corte ni cargar artefactos arbitrarios.

### Calidad y revisión

Implementar pruebas en `backend/tests` y `tests/e2e` según coordinación de archivos. Probar privilegios, lote inválido, confirmación repetida, evaluación repetida, conflicto 409 y bloqueo REAL. Verificar que el modelo y el corte correcto originan la predicción. Realizar el recorrido y revisar exportación. Reportar hechos comprobados, fallidos o no ejecutados.

### Documentación del estudio

Actualizar `docs` con diccionario, manual de arranque, manual de demo, matriz de trazabilidad y límites. Separar evidencia técnica de resultados académicos. Registrar las decisiones que faltan del colegio. No calcular indicadores sobre información inventada ni afirmar que un periodo pasado recibió una intervención.

Si se ejecutan agentes en paralelo, asignar una rama o área de archivos por agente. Las migraciones, OpenAPI y cambios de tipos compartidos se integran secuencialmente. Una revisión independiente de QA debe partir de los requisitos, no de la afirmación del autor de que todo funciona.

## 4 Prompts por iteración

### S0 Contratos y entorno

```text
Lee AGENTS.md y docs/planning. Revisa Docker, Python y Node. Fija versiones compatibles,
estructura y dependencias. Convierte las decisiones de la demo en requisitos y criterios
de aceptación. Compara el SQL con OpenAPI y resuelve diferencias documentadas antes
de que otros agentes implementen. No escribas aún módulos institucionales ni datos reales.
Entrega estructura, decisión de arquitectura, contrato vigente y plan S1 a S6.
```

### S1 Base ejecutable

```text
Implementa Compose para web api db, migración Alembic de las 13 tablas, configuración,
semilla demo y sesiones con CSRF. Crea administrador, tutor y directivo de demostración
sin contraseñas de producción. Implementa health, login, me, csrf, logout, periods y sections.
Comprueba base limpia, login, revocación y permisos. Conserva datos tras reinicio.
```

### S2 Importación y estudiantes

```text
Implementa imports preview detalle commit y estudiantes lista detalle timeline. La plantilla
CSV usa student_code, grade, section, cutoff_at, target_date, available_at, window_start,
average_grade, attendance_pct, activities_pct, participation_level, behavior_incidents,
age_years. El periodo se elige en el formulario y determina las fechas válidas.
Valida todas las filas antes de confirmar. No admitas datos REAL en esta fase. Usa una
transacción y el hash para idempotencia. Verifica los cortes, versiones y acceso por sección.
```

### S3 Modelo y predicción demo

```text
Genera 60 estudiantes sintéticos con varias secciones, cortes tempranos y resultados
sintéticos posteriores. Documenta el mecanismo del generador sin buscar métricas altas.
Entrena DummyClassifier y Random Forest con Pipeline y separación de estudiantes.
Guarda métricas, particiones y artefacto con hash. Implementa consulta de modelos,
activación demo, predictions run y consulta de predicción. Reutiliza corte modelo ya
evaluado. Verifica origen y fechas. Muestra abstención cuando faltan datos requeridos.
```

### S4 Interfaz didáctica

```text
Implementa Inicio Estudiantes Alertas Datos Reportes y vistas técnicas según el rol.
Conecta la API real. Implementa importación en tres pasos, filtros, detalle, ayuda breve
y marcas DEMO. Distingue riesgo de falta de evaluación. Explica datos observados sin
atribuirlos causalmente al modelo. Revisa los tres tamaños del plan y navegación con teclado.
```

### S5 Alertas e intervenciones

```text
Integra predicciones con alertas únicas por matrícula. Permite atender resolver descartar
con motivo y versión. Implementa intervenciones planificadas realizadas canceladas,
auditoría, resumen y CSV con origen y alcance. No cierres automáticamente un caso
por una predicción menor. Prueba duplicados, transiciones, concurrencia y fecha efectiva.
```

### S6 Verificación y entrega

```text
Ejecuta migraciones en base limpia, pruebas backend, build frontend y Playwright del
recorrido importar evaluar atender exportar. Verifica persistencia tras reinicio y alcance
del tutor. Captura escritorio tablet móvil. Corrige defectos encontrados y actualiza
manuales. Entrega comandos, estado real de módulos, resultados de pruebas y pendientes.
No declares evaluada la tesis ni reportes métricas sintéticas como resultados escolares.
```

## 5 Procedimientos propuestos como skills

Estas cinco especificaciones pueden convertirse posteriormente en `SKILL.md` de proyecto. Primero se usan como instrucciones desde este archivo. Para instalarlas en una cuenta o directorio de skills, seguir el mecanismo de instalación de ese entorno; no asumir que copiarlas dentro de `docs` las activa automáticamente.

### tesis-trazabilidad

**Descripción para activación.** Alinear requisitos y cambios del sistema escolar con objetivos, variables e indicadores de la tesis; usar al cambiar alcance, reglas académicas, mediciones o reportes.

Procedimiento: leer el objetivo y el requisito vigente; identificar entrada, transformación y salida; mapear objetivo, dimensión, indicador y evidencia; revisar denominador, fecha y unidad de análisis; distinguir demo, evaluación técnica y medición institucional; registrar una decisión en docs/adr; actualizar contratos y matriz de trazabilidad si el cambio los afecta. No reescribir la metodología ni elegir pruebas inferenciales sin un encargo específico.

Entradas: documento académico vigente, protocolo y requisitos. Salidas: matriz objetivo función evidencia y decisión con motivo. Verificación: cada indicador usado en pantalla o reporte tiene una definición, periodo, origen y denominador; no existen conclusiones sobre datos sintéticos.

### escolar-datos-api

**Descripción para activación.** Diseñar y cambiar persistencia, contratos e importación del sistema de riesgo escolar; usar al añadir tablas, campos, endpoints, validaciones o migraciones.

Procedimiento: leer diccionario, SQL y OpenAPI; definir entidad, tipo, nulabilidad y relaciones; verificar seudónimo, origen, escala y fechas; proponer migración reversible cuando sea razonable y coordinar su autoría; definir solicitud, respuesta, autorización, errores e idempotencia; sincronizar esquemas y tipos frontend; ejecutar migración y pruebas de las restricciones cambiadas.

Entradas: requisito y contratos vigentes. Salidas: migración, esquema, tipos y documento actualizado. Verificación: un lote inválido no escribe parcialmente, las relaciones no mezclan origen ni estudiante y los cambios de versión producen 409. Registrar el entorno donde realmente se ejecutó la migración.

### escolar-ml

**Descripción para activación.** Preparar y evaluar modelos de riesgo académico con trazabilidad temporal; usar al generar datasets, entrenar, comparar algoritmos o modificar la inferencia.

Procedimiento: definir fecha de corte y resultado futuro; listar variables admitidas y excluidas; revisar disponibilidad real de fuentes; asociar cada etiqueta con criterio y horizonte; dividir por estudiante y verificar grupos y clases; ajustar transformaciones solo en entrenamiento; comparar baseline y modelos autorizados; conservar predicciones de validación, soporte y métricas; congelar el modelo antes de evaluar prospectivamente; registrar semilla, versiones, hashes y manifiesto.

Entradas: cortes y etiquetas separadas, protocolo y esquema de variables. Salidas: artefacto interno, manifiesto y reporte. Verificación: ningún grupo cruza entrenamiento y validación, ninguna entrada conoce el futuro y una predicción real no usa un modelo sintético. Las probabilidades sin calibración no se presentan como certeza. No atribuir capacidades predictivas a una clasificación retrospectiva del mismo estado.

### escolar-interfaz

**Descripción para activación.** Crear pantallas comprensibles para tutores y directivos del sistema escolar; usar al construir o revisar navegación, tablas, formularios, detalle y ayudas.

Procedimiento: identificar rol y tarea; definir acción principal; consumir el contrato vigente; diseñar carga, vacío, error y éxito; mostrar periodo, corte, denominador y origen; reducir formularios a datos necesarios; usar texto e icono para riesgo; mantener intervención junto al caso; distinguir observaciones y explicación del modelo; revisar teclado, foco y los tres tamaños del plan.

Entradas: historia, rol y contrato. Salidas: componentes integrados y capturas. Verificación: el usuario puede completar la tarea con API y recibe mensajes útiles; una pantalla aislada o con datos hardcodeados no se acepta como módulo terminado.

### escolar-verificacion

**Descripción para activación.** Cerrar iteraciones y comprobar la demostración del sistema de riesgo escolar; usar antes de declarar un módulo o una entrega terminado.

Procedimiento: leer criterios de aceptación; preparar datos sintéticos de borde; comprobar permisos, integridad, fechas, idempotencia y concurrencia; ejecutar pruebas pertinentes, build y migraciones; realizar recorrido en navegador y verificar archivos exportados; reiniciar y comprobar persistencia; contrastar cifras con consultas o respuestas de API; registrar resultado comprobado, fallido o no ejecutado.

Entradas: implementación y requisitos. Salidas: reporte y evidencia de ejecución. Verificación: reproducir importar evaluar atender exportar sin modificar manualmente tablas para simular éxito. Ninguna comprobación no ejecutada figura como aprobada. El modelo demo no cuenta como evidencia de la hipótesis.

## 6 Lista de decisiones previas al modo institucional

Resolver con colegio y asesor: escala real, periodicidad, horizonte, criterio de referencia, fechas O1 O2, calidad mínima, autorizaciones, responsables, ventanas de oportunidad, denominadores y conservación. Añadir las seis tablas de investigación del plan y contratos correspondientes. Registrar el protocolo aprobado y retirar el bloqueo REAL solo con controles implementados y comprobados.

La restricción del 30 % de datos faltantes pertenece a la elegibilidad del estudio según variables y periodos fijados. Una abstención en un corte operativo no elimina automáticamente al estudiante del censo.
