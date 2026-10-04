# Plan de desarrollo del sistema de riesgo escolar

Proyecto de tesis de Mario Alexander Romero Capitanich · 3 de octubre de 2026

La primera entrega será una aplicación web interna que permita importar registros, revisar estudiantes, estimar riesgo académico, gestionar alertas, registrar intervenciones y exportar reportes. El plazo indicado es un día y los datos institucionales están en trámite. Por ello, esta entrega se organizará como una demo funcional con datos sintéticos, seguida por una fase de implementación y evaluación institucional. El desarrollo del software y la demostración de la hipótesis de tesis tendrán entregables y calendarios distintos.

El nombre de trabajo de la aplicación será **Seguimiento Escolar**. No cambia el título académico de la tesis. Este plan define la arquitectura y los contratos para iniciar la programación; no acredita que la aplicación ya esté implementada.

Actualización técnica de Sprint 0 (3 de octubre de 2026): contrato vigente 0.1.1.
Las decisiones exactas están en `../adr/001-arquitectura.md`; las diferencias de
SQL/API, fechas y permisos en `Conciliacion_SQL_API.md`; aceptación y dependencias
en `Sprints_y_aceptacion.md`. Solo se preparó S0, sin iniciar S1 ni alterar el estudio.

## 1 Alcance académico y decisiones iniciales

El documento de tesis plantea un sistema predictivo con Machine Learning para gestionar el rendimiento escolar y los riesgos académicos en un colegio privado de Lima. La unidad de análisis es el estudiante de secundaria y la población inicial es de 60 estudiantes. El estudio propone un diseño preexperimental de un grupo con mediciones pretest y postest, y un censo de estudiantes elegibles. El número definitivo dependerá de la permanencia, la suficiencia de registros y las autorizaciones. El número de observaciones de entrenamiento puede ser mayor que el número de estudiantes, pero esas observaciones no constituyen estudiantes independientes.

La guía V07 exige coherencia entre variables, indicadores, unidad de análisis, instrumentos, métodos de análisis y aspectos éticos. No exige una tecnología concreta, una cantidad de módulos, microservicios ni una metodología de programación. Los sprints de este plan son una decisión de desarrollo. Las funciones del producto deben producir evidencia vinculada con los objetivos del estudio.

| Objetivo del documento | Función del sistema | Evidencia que debe conservarse |
|---|---|---|
| OE1 Analizar datos académicos | Importación, calidad, historial y tablero | Archivo fuente autorizado, validaciones, diccionario y registros con fechas |
| OE2 Implementar y evaluar un modelo | Preparación de variables, entrenamiento y predicción | Particiones por estudiante, métricas por clase, matriz de confusión y versión del modelo |
| OE3 Generar reportes y alertas | Alertas, intervenciones y exportaciones | Fecha de señal, responsable, acción realizada, oportunidad y reporte reproducible |

**Fechas del estudio.** El texto ubica O1 en el primer bimestre de 2026 y O2 en el segundo. Al 3 de octubre esos periodos ya transcurrieron. Si el sistema no estuvo funcionando durante O2, no corresponde describir ese periodo como una intervención prospectiva realizada. Se debe acordar con el asesor una reprogramación hacia periodos todavía observables o un rediseño retrospectivo. Los registros históricos pueden apoyar el desarrollo y la evaluación técnica; no reemplazan evidencia de uso real del sistema en el momento afirmado. No se modificará automáticamente el documento de tesis.

La tesis de referencia aporta ejemplos de visualización y menciona Python, FastAPI y PostgreSQL. Su resumen describe estudiantes de primaria y registros de 2024, mientras que este proyecto considera secundaria y 2026. Su diseño y sus resultados no se trasladarán a este estudio. Tampoco se adoptará un porcentaje de exactitud como resultado esperado por analogía.

## 2 Dos entregas con criterios distintos

**Entrega de un día.** Un recorrido completo en localhost, con persistencia real en PostgreSQL y un modelo local entrenado con datos sintéticos. La interfaz tendrá una marca visible de DEMO. El CSV exportado incluirá el origen sintético. La API bloqueará el procesamiento institucional hasta completar el protocolo y los controles de la fase siguiente.

**Entrega para evaluación de tesis.** Datos autorizados, criterios de riesgo aprobados, fechas del estudio corregidas si corresponde, predicciones con información disponible al momento del corte y mediciones comparables. Esta entrega requiere acceso institucional y el transcurso de los periodos observados. Una demo terminada no constituye una tesis validada.

| Prioridad | Incluido en el primer día | Se completa después de la demo |
|---|---|---|
| Esencial | Login, roles, estudiantes, importación CSV y tablero | Autorizaciones y reglas institucionales definitivas |
| Esencial | Random Forest de demo, riesgo bajo medio alto y trazabilidad | Comparación completa de Random Forest, SVM y XGBoost con datos autorizados |
| Esencial | Alertas, intervenciones y reporte CSV | Mediciones pretest postest congeladas y exportación para SPSS |
| Esencial | Pruebas del recorrido principal y reinicio reproducible | Pruebas ampliadas, respaldo restaurado y piloto con usuarios |
| Opcional | Gráfico de evolución simple y guía integrada | PDF, importación XLSX y explicación local del modelo |

Se dejan para otra etapa los portales de familias o alumnos, pagos, matrícula administrativa, mensajería automática, chatbots, integración con plataformas externas y módulos de contabilidad. Los algoritmos se ejecutarán localmente y no necesitan una API de IA pagada. Las licencias, el alojamiento y cualquier costo institucional se verifican por separado.

## 3 Módulos y navegación

La barra lateral tendrá cinco entradas principales: Inicio, Estudiantes, Alertas, Datos y Reportes. Modelo y Configuración estarán en una zona de administración, visible según el rol. El registro de intervenciones se abrirá desde el detalle del estudiante o la alerta, para que el usuario mantenga el contexto del caso.

| Módulo | Qué permite hacer | Entrega |
|---|---|---|
| Acceso y permisos | Iniciar sesión y limitar datos por rol y sección | Día 1 |
| Inicio | Ver estudiantes evaluados, pendientes y alertas activas | Día 1 |
| Estudiantes | Buscar, filtrar y abrir historial académico y acciones | Día 1 |
| Datos | Descargar plantilla, revisar CSV y confirmar importación | Día 1 |
| Riesgo académico | Ejecutar predicción y consultar modelo, fecha y calidad | Día 1 |
| Alertas e intervenciones | Priorizar, asignar atención y documentar seguimiento | Día 1 |
| Reportes | Exportar resumen y registros autorizados | Día 1 CSV |
| Modelo | Consultar modelo demo y métricas de desarrollo | Día 1 lectura |
| Evaluación del estudio | Registrar referencia independiente y comparar O1 O2 | Fase de tesis |
| Configuración y auditoría | Gestionar periodos, reglas, acceso y bitácora | Básica día 1 y ampliación posterior |

No se construirá un gestor completo de notas por competencias para el primer día. Se importarán cortes académicos agregados porque el objetivo principal es el seguimiento y la predicción. Si la institución requiere registros por asignatura, se añadirán tablas de cursos y calificaciones en una migración posterior, con una fórmula de agregación aprobada.

## 4 Experiencia de uso

**Inicio.** Mostrar cuatro indicadores: estudiantes con corte disponible, estudiantes evaluados, estudiantes sin predicción y alertas activas. Toda cifra tendrá periodo, fecha de actualización y denominador. Un gráfico pequeño puede mostrar la distribución del riesgo; la ausencia de predicción se presentará como categoría aparte.

**Estudiantes.** Tabla con código, grado y sección, promedio, asistencia, riesgo y última actualización. La tabla permitirá buscar por código y filtrar por sección y riesgo. El botón principal será Ver seguimiento. Una tarjeta amarilla no podrá ser el único medio para informar el riesgo: deberá incluir texto e icono.

**Detalle.** Cabecera con código del estudiante, riesgo y fecha de corte. Debajo habrá Datos académicos, Seguimiento e Historial. Mostrar datos observados como asistencia baja o actividades pendientes, sin afirmar que son explicaciones causales del modelo. La explicación de una predicción individual solo se mostrará si se implementa y valida un método local; la importancia global de variables no se presentará como explicación individual.

**Importación.** Tres pasos visibles: elegir archivo, revisar resultado y confirmar. Los errores mostrarán fila, columna y corrección esperada. Una importación con errores no guardará parcialmente los registros. La vista previa indicará cuántos estudiantes y cortes se crearán. Reimportar el mismo archivo devolverá el lote existente.

**Alertas.** Orden inicial por severidad y antigüedad. Cada caso tendrá una acción principal de atención y un responsable. Cerrar una alerta exigirá motivo; cerrar no borrará el historial. Una bajada del riesgo no cerrará automáticamente un caso con intervención pendiente.

**Ayuda integrada.** Un recorrido breve explicará cómo importar, evaluar y atender un caso. El texto será académico y comprensible: Riesgo estimado, Fecha de evaluación, Datos insuficientes y Acción de acompañamiento. Evitar términos de ingeniería en las pantallas del tutor. La demo tendrá un caso de riesgo bajo, uno medio, uno alto y uno sin información suficiente.

| Rol | Acceso previsto | Restricción principal |
|---|---|---|
| Administrador | Usuarios, importación, modelo y configuración | No altera mediciones congeladas ni registros históricos |
| Tutor | Estudiantes y alertas de sus secciones; intervenciones | La API verifica la sección en cada lectura y escritura |
| Directivo | Seguimiento institucional y reportes | No activa modelos ni cambia el criterio de evaluación |
| Investigador | Métricas agregadas y exportación de investigación aprobada | No accede a identificadores personales ni a casos operativos por defecto |

La interfaz se verificará en 1440 × 900, 768 × 1024 y 390 × 844. Los formularios tendrán etiquetas visibles, navegación con teclado y mensajes de error útiles. En móvil las tablas podrán desplazarse dentro de su contenedor, sin producir desbordamiento de toda la página.

## 5 Arquitectura y estructura del código

Se recomienda un monorepo con un backend modular. El navegador se comunica con FastAPI y solo el backend accede a PostgreSQL y a los artefactos del modelo. React presenta datos y recoge acciones; las reglas de riesgo, permisos, fechas y validaciones permanecen en el servidor.

| Capa | Tecnología propuesta | Motivo |
|---|---|---|
| Frontend | React, TypeScript, Vite y Tailwind CSS | Pantallas reutilizables, tipos y desarrollo ágil |
| Estado y formularios | TanStack Query, React Hook Form y Zod | Consultas, invalidación y validación de formularios |
| Backend | Python 3.12, FastAPI y Pydantic | API tipada y proximidad con el procesamiento ML |
| Persistencia | PostgreSQL 17, SQLAlchemy 2 y Alembic | Relaciones, restricciones y migraciones |
| Machine Learning | pandas, scikit-learn y XGBoost | Modelos indicados en la metodología |
| Verificación | pytest y Playwright | Reglas, permisos y recorrido en navegador |
| Ejecución | Docker Compose con web, api y db | Inicio reproducible en un equipo |

Las versiones exactas de paquetes se fijarán en Sprint 0 después de comprobar compatibilidad. Se guardarán los archivos de bloqueo y no se usarán etiquetas latest. El proyecto no necesita Kubernetes, microservicios ni un broker en la demo. La inferencia de 60 estudiantes puede manejarse como operación acotada; el entrenamiento de la demo será un comando de desarrollo. El entrenamiento institucional pasará después a un trabajo persistente fuera del proceso HTTP. FastAPI advierte que las tareas intensivas pueden requerir herramientas de ejecución adicionales [W3].

La raíz contendrá frontend, backend, docs, infra y tests. En frontend se separarán app, components, features y lib. En backend se usarán app/api/v1, core, models, schemas, repositories, services y ml. Dentro de ml se distinguirán features, train, evaluate y predict. Las rutas no implementarán directamente toda la lógica de negocio.

Documentación mínima: requisitos, arquitectura, diccionario de datos, contrato OpenAPI, reglas del modelo, plan de pruebas, protocolo del estudio y manual de demo. El archivo AGENTS.md establecerá reglas para Codex. Los procedimientos propuestos como skills se entregan como instrucciones para el repositorio; su instalación permanente es una tarea distinta.

Comandos que debe implementar el proyecto: make up, make migrate, make seed-demo, make train-demo, make test, make demo y make backup. make demo inicia servicios y prepara solo el entorno de demostración. Un comando de reinicio de datos tendrá comprobación de entorno y nunca apuntará a una base institucional.

## 6 Flujos y reglas del dominio

**Importación.** Recibir CSV UTF-8 y comprobar tamaño, cabeceras y origen DEMO. Resolver códigos, periodo y sección; verificar valores y fechas; generar vista previa. Al confirmar, crear matrículas y cortes en una transacción. Guardar hash SHA-256 del archivo, versión del esquema, usuario, cantidades y fecha. Una segunda confirmación del mismo lote devuelve el resultado previo. Un lote corrupto no deja matrículas ni cortes parcialmente creados.

**Predicción.** Seleccionar el modelo activo del mismo origen que los datos y el último corte disponible de cada matrícula hasta el instante solicitado. Comprobar que el corte corresponde a una fecha anterior al resultado que se pretende anticipar. Si faltan demasiados datos o no hay modelo compatible, devolver un estado explicativo sin inventar un nivel bajo. Persistir clase, versión, corte, fecha objetivo y probabilidades solo cuando estén disponibles. Ejecutar de nuevo la misma combinación de corte y modelo reutiliza la predicción existente.

**Alerta.** Una predicción de riesgo medio o alto abre o actualiza un caso de la matrícula. La restricción de base de datos permite como máximo una alerta activa por matrícula. Cuando exista otro corte, se actualiza la referencia a la nueva predicción y se añade auditoría, sin crear una alerta idéntica. Las transiciones son ABIERTA → EN_ATENCION o RESUELTA, y EN_ATENCION → RESUELTA; también podrá descartarse con motivo desde un estado activo. Resolver directamente exige motivo y versión. Un nuevo episodio posterior puede abrir otro caso. Todo cambio se registra con usuario y fecha.

**Intervención.** El tutor registra tipo, fecha prevista, objetivo y estado. Una acción PLANIFICADA no cuenta como intervención realizada. Al marcar REALIZADA se exige fecha efectiva y se conserva la bitácora. Una alerta resuelta puede tener varias intervenciones. El frontend no calcula ni modifica de forma independiente el indicador de oportunidad.

**Autorización.** El acceso a un estudiante, corte, alerta o intervención se resuelve desde su matrícula y sección. Ocultar botones no basta: el servidor debe negar una operación fuera del alcance del tutor. Los usuarios de investigación tendrán exportaciones aprobadas y limitadas.

## 7 Modelo de datos del primer día

Se entregan 13 tablas base en Esquema_demo.sql. Es un diseño PostgreSQL para la demo, que se debe convertir en una migración Alembic al programar. No se ha ejecutado en un servidor PostgreSQL en esta entrega. Las tablas no almacenan nombres, DNI, direcciones ni datos familiares. La asociación del código con una identidad, si se necesita en el piloto, se mantendrá en un repositorio separado y restringido.

| Tabla | Campos principales | Relación y finalidad |
|---|---|---|
| app_users | id, email, password_hash, role, is_active | Usuarios internos con rol único |
| user_sessions | user_id, token_digest, csrf_digest, expires_at | Sesión revocable; sin token plano |
| academic_periods | code, start_date, end_date, data_origin, is_locked | Periodo con fechas y origen |
| grade_sections | code, grade, school_year, tutor_id | Alcance del tutor |
| students | anon_code, data_origin, eligible_for_processing | Código seudónimo y elegibilidad |
| enrollments | student_id, period_id, section_id, data_origin | Matrícula única del estudiante en el periodo |
| import_batches | period_id, file_sha256, counts, status | Vista previa, confirmación y trazabilidad |
| academic_snapshots | enrollment_id, cutoff_at, target_date, revision, variables | Corte académico inmutable |
| model_versions | algorithm, dataset_hash, metrics, manifest, is_active | Artefacto y evaluación por versión |
| predictions | snapshot_id, model_id, risk_level, probabilities | Resultado inmutable por corte y modelo |
| alerts | enrollment_id, prediction_id, severity, status, version | Caso activo y control de concurrencia |
| interventions | enrollment_id, alert_id, kind, status, performed_at | Acciones de acompañamiento |
| audit_events | actor_id, entity_type, action, recorded_at, payload | Historial de acciones sin sobrescritura |

La matrícula conecta el estudiante con el periodo y la sección. Un corte pertenece a una matrícula; una predicción pertenece a ese corte y a un modelo. La alerta apunta a una predicción de la misma matrícula y las intervenciones se vinculan con el estudiante a través de ella. Las claves foráneas compuestas impiden mezclar orígenes DEMO y REAL y vincular una alerta con la predicción de otro estudiante.

**Variables del corte.** Promedio, porcentaje de asistencia, porcentaje de actividades entregadas, nivel de participación, cantidad de incidencias y edad al momento del corte. Grado y sección son contexto de la matrícula. La inclusión como predictores de edad o grado debe justificarse y evaluarse; la sección, el código y el nombre del tutor no se usarán para memorizar estudiantes. El esquema demo supone promedio numérico de 0 a 20 y participación codificada de 1 a 3. Estas escalas no son una afirmación sobre el colegio: se reemplazarán o confirmarán antes del piloto. Una escala AD A B C no se convertirá arbitrariamente a notas numéricas.

## 8 Integridad y extensión para la tesis

Usar UUID como identificadores internos, porcentajes entre 0 y 100, conteos no negativos y fechas UTC para eventos. Mostrar fechas en America/Lima. No convertir ausencia de datos en cero. Un corte contiene inicio de ventana, fecha de corte, último instante de disponibilidad de la fuente y fecha objetivo. Su última disponibilidad debe ser anterior o igual al corte. La fecha objetivo debe ser posterior al corte y quedar dentro del periodo definido.

Una corrección crea otra revisión de corte y conserva el original. Las predicciones y la auditoría son inmutables. Los periodos cerrados no aceptan nuevas escrituras operativas. Las alertas e intervenciones usan expected_version para evitar que dos usuarios sobrescriban cambios. Las operaciones críticas se hacen en una transacción con auditoría incluida. No habrá eliminación física de evidencias desde la interfaz.

| Tabla de la fase de tesis | Contenido mínimo | Por qué es necesaria |
|---|---|---|
| risk_criteria_versions | Criterio, escala, vigencia y aprobación | Definir bajo medio alto antes de entrenar |
| reference_labels | Matrícula, fecha objetivo, riesgo, criterio y evaluador | Referencia independiente de la predicción |
| risk_signals | Fecha de señal, fecha de registro, origen y evidencia | Conservar detección manual pretest y señal del sistema |
| study_protocols | Periodos O1 O2, ventanas de oportunidad y reglas | Congelar las definiciones del estudio |
| study_participants | Estudiante, autorizaciones, elegibilidad y motivo | Explicar censo final y exclusiones |
| study_measurements | Momento, indicadores, referencias y versión | Reproducir comparación por estudiante |

Estas seis tablas son una extensión planificada; no están incluidas en el SQL de la demo ni deben simularse como implementadas. La tabla model_versions ya admite métricas y manifiestos; un entrenamiento institucional persistente podrá añadir una tabla de trabajos y sus intentos cuando se habilite la pantalla de entrenamiento.

## 9 Contrato de la API

Todas las rutas de negocio usarán /api/v1. La autenticación será una sesión de servidor con cookie HttpOnly, SameSite y Secure en HTTPS. Las escrituras exigirán un token CSRF ligado a la sesión. El login comprobará el origen de la solicitud. No se guardarán tokens en localStorage. El primer día las cuentas se crean por semilla; no habrá registro público.

Los listados usan page desde 1, page_size de 1 a 100, filtros permitidos y orden determinista. El servidor devuelve items, total, page y page_size. Las fechas se transmiten en ISO 8601. El error tiene code, message, details y request_id. Los identificadores de petición se generan en el servidor. Se distinguen 401, 403, 404, 409 y 422 según corresponda.

| Método y ruta | Uso | Acceso |
|---|---|---|
| GET /health/live y /health/ready | Proceso disponible y conexión con base | Público; sin detalles internos |
| POST /auth/login | Abrir sesión y entregar CSRF | Público con comprobación de origen |
| GET /auth/me y /auth/csrf | Usuario y recuperación del token CSRF | Sesión vigente |
| POST /auth/logout | Revocar sesión | Sesión vigente y CSRF |
| GET /periods y /sections | Filtros y contexto académico | Administrador, tutor y directivo |
| GET /students | Lista autorizada por sección | Administrador, tutor y directivo |
| GET /students/{id} | Ficha con último corte y riesgo | Mismos roles y alcance |
| GET /students/{id}/timeline | Cortes, alertas e intervenciones | Mismos roles y alcance |
| POST /imports/preview | Revisar CSV sin crear registros académicos | Administrador |
| GET /imports/{id} | Cantidades, errores y estado del lote | Administrador |
| POST /imports/{id}/commit | Confirmar una importación válida | Administrador |
| POST /predictions/run | Evaluar últimos cortes del periodo | Administrador |
| GET /predictions/{id} | Consultar resultado, corte y modelo | Administrador, tutor y directivo con alcance |
| GET /dashboard | Indicadores del contexto autorizado | Administrador, tutor y directivo |
| GET /models y /models/{id} | Modelo, origen y métricas | Administrador y lectura técnica autorizada |
| POST /models/{id}/activate | Activar versión demo compatible | Administrador |
| GET /alerts | Lista filtrada y autorizada | Administrador, tutor y directivo |
| PATCH /alerts/{id} | Cambiar estado con motivo y versión | Administrador y tutor de la sección |
| GET /interventions | Acciones filtradas por matrícula | Administrador, tutor y directivo |
| POST /interventions | Planificar una acción | Administrador y tutor de la sección |
| PATCH /interventions/{id} | Realizar o cancelar una acción | Administrador y tutor de la sección |
| GET /reports/summary | Resumen del periodo y alertas | Administrador, tutor y directivo |
| GET /reports/students.csv | Descargar datos operativos autorizados | Administrador, tutor y directivo |
| GET /audit-events | Revisar acciones administrativas | Administrador |

Contrato_API_demo.yaml contiene cuerpos, respuestas, tipos y parámetros de estas rutas. El contrato describe implementación prevista, no un backend desplegado. Al importar un corte nuevo, el riesgo actual queda pendiente hasta evaluar ese corte; la predicción anterior se conserva en el historial. No se muestra una evaluación antigua como si correspondiera a los datos nuevos.

Los siguientes endpoints completarán la fase institucional. Son especificaciones de alcance para esa fase y no forman parte del YAML demo. Sus esquemas se formalizarán antes de implementar; no se publicarán como rutas vacías en la primera entrega.

| Método y ruta posterior | Operación prevista | Regla principal |
|---|---|---|
| GET POST /risk-criteria | Consultar y crear versiones del criterio | Administrador; criterio nuevo sin sobrescribir el anterior |
| POST /risk-criteria/{id}/approve | Registrar aprobación institucional | Exigir aprobador, fecha y evidencia |
| GET POST /reference-labels | Consultar y registrar referencias | Evaluador autorizado, horizonte y criterio; sin usar la predicción como etiqueta |
| GET POST /risk-signals | Recuperar señales manuales y del sistema | Separar occurred_at de recorded_at y guardar evidencia |
| GET POST /study/protocols | Preparar periodos, reglas y ventanas | Administrador con revisión del responsable del estudio |
| POST /study/protocols/{id}/approve | Congelar el protocolo | Una versión aprobada no se edita retrospectivamente |
| GET POST /study/participants | Registrar elegibilidad y autorizaciones | Consentimiento, asentimiento, motivo de exclusión y protocolo |
| POST /study/measurements/freeze | Calcular y congelar O1 u O2 | Una medición por estudiante, momento y versión; fuentes trazables |
| GET /study/comparison | Consultar cambios y casos pareados | Investigador y responsable autorizados; sin conclusión automática |
| GET /study/paired.csv | Exportar pares para SPSS | Columnas y diccionario según protocolo, sin identidad personal |
| POST /ml/training-runs | Iniciar entrenamiento institucional | Dataset O1 autorizado y congelado; trabajo persistente |
| GET /ml/training-runs/{id} | Consultar estado y evaluación | Versiones, algoritmo, particiones y errores sanitizados |
| GET POST /users y PATCH /users/{id} | Administrar acceso interno | Administrador; cambios auditados y sesiones revocadas si corresponde |

El protocolo necesita identificadores de los periodos pretest y postest, criterio de referencia, horizonte, variables admitidas, ventana de detección, plazo de intervención y reglas de elegibilidad. Una etiqueta de referencia necesita matrícula, fecha objetivo, riesgo, criterio, evaluador y fecha de determinación. Una medición congelada registra su versión, los valores y la procedencia de cada indicador. El retiro de autorización se gestiona según el protocolo sin borrar silenciosamente evidencias ni mantener usos no autorizados.

## 10 Diseño del Machine Learning

**Definir qué se anticipa.** La propuesta es estimar bajo, medio o alto riesgo al cierre del periodo usando datos de un corte anterior. Por ejemplo, usar información disponible hasta una fecha dentro del bimestre y compararla con una referencia del cierre. La fecha de corte y el horizonte se registran en cada observación. La definición final requiere aprobación del colegio y del asesor. Si solo existen notas finales y una etiqueta calculada con esas mismas notas, se estará clasificando el estado actual; no se habrá demostrado anticipación.

El riesgo de referencia lo establece un criterio institucional independiente, versionado antes de la evaluación. El evaluador de referencia no debe usar la predicción como etiqueta. Los campos nivel predicho, alerta posterior, intervención posterior y calificación final del horizonte no pueden entrar como variables del modelo de ese corte. Las notas y asistencia anteriores al corte sí pueden utilizarse cuando estén disponibles en ese momento.

**Demo.** Crear 60 estudiantes sintéticos con distintos perfiles y cortes de fechas anteriores a sus resultados sintéticos. Entrenar DummyClassifier como referencia y Random Forest como primer modelo. No exigir métricas altas ni ajustar el generador para obtenerlas. Mantener al menos un caso de información insuficiente. La repetición de cortes no incrementa el número de estudiantes independientes. Toda pantalla de métricas indicará Datos sintéticos, resultado de desarrollo.

**Evaluación institucional.** Comparar DummyClassifier, Random Forest, SVM y XGBoost. Usar Pipeline y ColumnTransformer para que imputación, codificación y escalado se ajusten dentro de cada pliegue [W1]. La SVM necesita un tratamiento de escala compatible. No aplicar SMOTE ni otras transformaciones al conjunto completo antes de dividir.

Cuando haya varios cortes por estudiante, usar StratifiedGroupKFold con el estudiante como grupo y comprobar que los conjuntos de grupos no se cruzan [W2]. Cinco pliegues son una opción condicionada a la cantidad y distribución de grupos por clase. Se verificarán las clases de cada entrenamiento y validación; si no es viable se reducirá el número de pliegues con justificación. Si los datos no permiten una evaluación responsable, se informará la insuficiencia y no se fabricará una puntuación.

Priorizar F1 macro y presentar precisión, sensibilidad, F1 y soporte por clase, exactitud global y matriz de confusión. Si el asesor conserva exactitud por clase, definirla explícitamente como exactitud uno contra el resto para cada clase y señalar que puede resultar elevada por los verdaderos negativos. No confundir precisión, exactitud y sensibilidad.

Las métricas de selección en validación cruzada son evidencia de desarrollo. Una evaluación final requiere un periodo reservado o validación anidada si se ajustan hiperparámetros. Al pasar a O2 se congela el modelo; las etiquetas O2 no se usan para seleccionar o reentrenar ese modelo. Como el acompañamiento puede cambiar los resultados, se describirá que la evaluación ocurre bajo intervención y no en un escenario sin acciones.

Guardar semilla, versiones, parámetros, variables, clase y orden de etiquetas, hash del dataset, identificación de grupos por pliegue, métricas y hash del artefacto. Las probabilidades no se presentarán como certeza. Para SVM pueden omitirse si no se implementa una calibración separada que también respete los grupos. No cargar artefactos pickle enviados por usuarios; solo artefactos generados y registrados por el proceso interno.

## 11 Indicadores y evidencia del estudio

Antes del piloto se deben aprobar las definiciones de registro válido, estudiante en riesgo, detección oportuna e intervención oportuna. El documento enumera PRV, CRA, PDER y NIA, pero el desarrollo necesita especificar sus denominadores y reglas de tiempo para que sean reproducibles. Las definiciones siguientes son propuestas de operacionalización para revisar con el asesor.

| Indicador | Definición propuesta | Precaución |
|---|---|---|
| PRV | 100 × registros válidos confirmados / registros recibidos en los lotes únicos analizados | No contar reimportaciones como nuevos registros; separar recepción, rechazo y elegibilidad |
| CRA reportes | 100 × estudiantes elegibles con reporte / estudiantes elegibles | Mantener denominador y momento de cálculo |
| CRA alertas | 100 × estudiantes con riesgo medio alto según referencia y alerta emitida / estudiantes con riesgo medio alto según referencia | Denominador independiente del modelo; informar falsos positivos y oportunidad aparte |
| PDER | 100 × estudiantes en riesgo según referencia detectados dentro de la ventana acordada / estudiantes en riesgo según referencia | Usar señales manuales en O1 y señales reales del sistema en O2 |
| NIA | Número de intervenciones efectivamente realizadas por estudiante y periodo | Las acciones planificadas no cuentan |
| Intervención oportuna | Fecha efectiva dentro del plazo desde la primera señal elegible | Guardar plazo, señal y acción; una ausencia no se inventa como fecha |
| Promedio y asistencia | Valor bimestral con escala y fórmula institucional | Usar periodos y reglas comparables |

CRA se informará inicialmente como dos coberturas, de reportes y de alertas. No se combinarán en una sola cifra sin una fórmula acordada. Si el denominador es cero se mostrará No aplica, no 100 %. Separar ausencia de datos, ausencia de riesgo y ausencia de intervención.

Para comparar indicadores por estudiante se conservan pares O1 O2 con el mismo código, junto con exclusiones y motivos. La definición de detección oportuna debe especificar cómo tratar a estudiantes que no presentan riesgo en uno de los periodos. Se recomienda evaluar oportunidad entre los estudiantes con riesgo de referencia en ambos momentos y reportar aparte cambios de composición; cualquier regla alternativa deberá quedar fijada antes de mirar los resultados. No se codificará automáticamente No aplica como No para forzar McNemar.

El análisis previsto en el documento incluye descriptivos, Pearson o Spearman, t pareada o Wilcoxon, McNemar y Stuart-Maxwell. La aplicación exportará una tabla pareada para SPSS y un diccionario; la selección de pruebas se confirmará con el asesor según los datos y sus supuestos. Se reportarán tamaño efectivo, cambios, incertidumbre y limitaciones del diseño de un grupo. El software no generará automáticamente una conclusión de hipótesis aceptada.

Los consentimientos, asentimientos y la autorización del colegio se registrarán antes del procesamiento institucional. Un código vinculado a una identidad constituye seudonimización; no garantiza anonimato irreversible. Los datos reales y sus copias no se incluirán en Git, capturas públicas ni prompts de servicios externos. La política de conservación y retiro de autorización se definirá con la institución y quedará en el protocolo.

## 12 Agentes para programar

Los agentes son roles de trabajo de Codex; no son bots incorporados a la aplicación. Una persona puede ejecutarlos secuencialmente. Si se utiliza delegación, el coordinador congelará primero contratos y límites de archivos. No debe abrir seis tareas que cambien simultáneamente las mismas migraciones o los mismos archivos de configuración.

| Agente | Responsabilidad | Entrega y límite |
|---|---|---|
| Coordinación y arquitectura | Alcance, contrato, prioridades e integración | Controla raíz, configuración y migraciones compartidas |
| Backend y datos | Permisos, tablas, importación, alertas e intervenciones | backend excepto app/ml; contratos acordados |
| Frontend y experiencia | Pantallas, filtros, formularios y ayuda | frontend; no inventa reglas del servidor |
| Machine Learning | Variables, entrenamiento, evaluación e inferencia | backend/app/ml y manifiestos del modelo |
| Calidad y revisión | Pruebas de permisos, integridad, uso y demo | tests y evidencias; reporta defectos verificables |
| Documentación del estudio | Trazabilidad, manual, decisiones y límites | docs; no fabrica resultados ni reescribe la metodología sin encargo |

Cada encargo indicará objetivo, archivos permitidos, dependencia, criterios de aceptación y formato de reporte. El resultado debe incluir cambios, comando ejecutado, salida relevante y asuntos pendientes. El integrador verifica el conjunto y resuelve cambios de contrato. Si un agente necesita otro campo o endpoint, solicita el cambio al coordinador en vez de inventar uno.

## 13 Skills propuestas para el repositorio

Una skill define un procedimiento reutilizable; el agente define quién lo aplica. Inicio_Codex_y_skills.md contiene el contenido propuesto y las instrucciones de uso. Son procedimientos de proyecto preparados para copiar o adaptar; no están instalados permanentemente en una cuenta.

| Skill propuesta | Activación | Resultado verificable |
|---|---|---|
| tesis-trazabilidad | Cambiar requisitos, indicadores o alcance | Matriz objetivo función evidencia y decisión versionada |
| escolar-datos-api | Cambiar tablas, importaciones o endpoints | Migración, tipos, contrato y prueba de integridad |
| escolar-ml | Entrenar, evaluar o predecir | Manifiesto, particiones, métricas y comprobación de fuga |
| escolar-interfaz | Crear o revisar pantallas | Flujo entendible, estados y comprobación responsive |
| escolar-verificacion | Cerrar sprint o preparar demo | Recorrido probado, pruebas y limitaciones declaradas |

AGENTS.md reúne reglas permanentes. Las skills especializadas se invocan según la tarea y no se cargan todas por defecto. El mismo estándar se aplicará a prompts cortos por sprint: alcance concreto, entradas, criterios de aceptación y evidencia. Se evitarán prompts generales como Haz todo profesional sin contratos ni pruebas.

## 14 Plan de ejecución de un día

Se plantean siete iteraciones técnicas cortas. El término sprint aquí organiza trabajo; no implica aplicar Scrum formal con sprints de pocas horas. Las duraciones son estimaciones para una persona con apoyo de Codex y un entorno preparado. El recorrido esencial tiene un presupuesto de 12 horas efectivas más hasta 2 horas de contingencia, sin garantía de finalización exacta.

| Iteración | Tiempo | Alcance y criterio de salida |
|---|---|---|
| S0 Contratos | 0 h 45 min | Congelar alcance demo, reglas, estructura, esquema y API; confirmar que Docker funciona |
| S1 Base ejecutable | 1 h 45 min | Compose, migración, semilla, login y roles; reinicio conserva los datos |
| S2 Datos | 1 h 45 min | CSV, vista previa, confirmación atómica, estudiantes y cortes; errores y duplicados probados |
| S3 Predicción demo | 1 h 30 min | Generador sintético, baseline, Random Forest y manifiesto; corte y grupos comprobados |
| S4 Interfaz | 2 h 30 min | Inicio, lista, detalle y asistente de importación con API real; estados vacíos y errores |
| S5 Seguimiento | 1 h 15 min | Alertas, intervenciones y CSV; una acción realizada queda persistida y auditada |
| S6 Integración | 2 h 30 min | Pruebas, recorrido de navegador, capturas, manual y arranque limpio reproducible |

Las dependencias principales son S0 → S1 → S2 → S3 → S5 → S6. S4 puede empezar con el contrato de S0 y componentes base, pero su aceptación requiere integración con la API. Si hay agentes paralelos, S4 y S3 pueden avanzar después de fijar interfaces; el integrador seguirá controlando migraciones y archivos raíz.

Si a mitad del día falla la base o la importación, se retiran gráficos adicionales, animaciones y PDF. Se conserva el recorrido esencial. Si el entrenamiento no queda disponible, se muestra Modelo no disponible y se declara demo incompleta en predicción; nunca se sustituye por un resultado hardcodeado presentado como ML. No se recortan los controles de permisos, la persistencia ni las pruebas del recorrido principal.

## 15 Fase institucional y cierre de tesis

| Etapa posterior | Entregables | Dependencia |
|---|---|---|
| T0 Protocolo y acceso | Fechas aprobadas, autorizaciones, criterio, horizonte y ventanas | Colegio y asesor |
| T1 Datos reales | Diccionario, trazabilidad, elegibilidad y etiquetas independientes | T0 y entrega autorizada de registros |
| T2 Modelos | RF SVM XGBoost, evaluación honesta y modelo congelado | T1 y suficiencia de grupos por clase |
| T3 Piloto | Uso por tutores, mejoras de comprensión y registro real de acciones | Modelo y permisos preparados |
| T4 Mediciones | O1 O2, exclusiones, pares y exportación SPSS | Periodos efectivamente observados |
| T5 Sustentación | Resultados, limitaciones, capturas autorizadas y manual | Análisis revisado con el asesor |

Los trabajos de programación de T0 a T3 pueden necesitar días o semanas adicionales. Las mediciones dependen del calendario escolar; no pueden comprimirse a unas horas ni asignarse automáticamente como dos semanas. El plazo de un día cubre la primera demo, no todas estas etapas.

La principal amenaza de validez es atribuir al sistema cambios que también pueden deberse al paso del tiempo, las asignaturas, la maduración o acciones del colegio. Otra amenaza es evaluar una etiqueta definida con los mismos valores finales usados para predecir. El protocolo y los registros temporales permitirán identificar esas limitaciones, aunque no eliminan las propias del diseño preexperimental.

## 16 Verificación y demostración

| Comprobación | Resultado necesario para cerrar la demo |
|---|---|
| Arranque | Un comando documentado inicia web api db y carga exclusivamente la demo |
| Autorización | El tutor no lee ni modifica una matrícula ajena; investigador no abre casos operativos |
| Importación | Un CSV inválido no crea registros; repetir el lote no duplica cortes |
| Predicción | Fecha de corte anterior a objetivo; sin variables futuras; grupos disjuntos en validación |
| Seguimiento | Repetir evaluación no duplica alerta activa; conflicto de versión devuelve 409 |
| Intervención | Planificada no suma como realizada; fecha efectiva exigida al completar |
| Origen | Datos y modelos sintéticos marcados; modo institucional bloqueado en fase demo |
| Interfaz | Uso completo en escritorio y revisión tablet móvil con capturas reales |
| Persistencia | El caso permanece después de reiniciar servicios |
| Exportación | CSV coincide con la pantalla, declara origen y respeta alcance del usuario |

El recorrido de cinco a ocho minutos será: entrar como administrador, importar un CSV de ejemplo, revisar los estudiantes, ejecutar evaluación, abrir un caso de riesgo alto, entrar como tutor, registrar una intervención y descargar el reporte. Mostrar después un archivo inválido y un estudiante con datos insuficientes. El reinicio de demo estará disponible solo en desarrollo y no será un botón de producción.

Pruebas mínimas de backend: alcance del tutor, lote atómico, idempotencia, ventanas temporales, exclusión de variables futuras, separación de grupos, unicidad de alertas, concurrencia y bloqueo de origen real. Una prueba Playwright recorrerá importar, evaluar, atender y exportar, verificando respuestas y persistencia. El build del frontend y las migraciones sobre una base limpia también deben pasar. Las capturas manuales o pruebas no ejecutadas se registran como pendientes.

## 17 Decisiones que debe confirmar la institución

Antes de habilitar el uso real, confirmar la escala de notas y participación, frecuencia y disponibilidad de registros, definición del riesgo, fecha de predicción, horizonte, personas responsables, fechas del estudio y documentación de autorizaciones. También acordar las ventanas de detección e intervención, la regla de exclusión por más del 30 % de datos faltantes y los denominadores finales de PRV CRA y PDER.

La regla del documento para excluir estudiantes con más del 30 % de datos faltantes debe aplicarse a las variables y periodos establecidos en el protocolo, no a un conjunto de columnas que cambie después de ver el resultado. El sistema puede abstenerse ante un corte insuficiente sin excluir silenciosamente al estudiante del estudio.

Para reducir riesgo técnico, se elige una sola base de datos, un backend y una librería principal de componentes. Los modelos locales evitan depender de servicios de inferencia de pago. Para reducir riesgo académico, ninguna captura de demo ni métrica sintética se copiará como resultado real del colegio.

## 18 Fuentes y archivos de trabajo

Fuentes académicas consultadas: LIMA_NORTE_PI_ROMERO_TRUJILLO(2).docx, introducción, metodología y anexos de operacionalización, consistencia y extracción; Guía de elaboración del proyecto de investigación y tesis V07, páginas 7 y 8 sobre metodología y ética; y TESIS_WONG_CHANDUVI -AGUIRRE_LUQUE .pdf, resumen y descripción de tecnologías. La planificación técnica no modifica estos documentos.

[W1] scikit-learn. Common pitfalls and recommended practices. https://scikit-learn.org/stable/common_pitfalls.html

[W2] scikit-learn. StratifiedGroupKFold. https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.StratifiedGroupKFold.html

[W3] FastAPI. Background Tasks. https://fastapi.tiangolo.com/tutorial/background-tasks/

[W4] PostgreSQL. Constraints. https://www.postgresql.org/docs/current/ddl-constraints.html

[W5] XGBoost. Python Package Introduction. https://xgboost.readthedocs.io/en/stable/python/python_intro.html

Consulta técnica realizada el 3 de octubre de 2026. Las referencias web documentan mecanismos de las herramientas; las elecciones de alcance y arquitectura son propuestas para este proyecto.

Archivos complementarios: AGENTS.md contiene reglas de desarrollo; Inicio_Codex_y_skills.md contiene los encargos y procedimientos propuestos; Esquema_demo.sql contiene las 13 tablas base; Contrato_API_demo.yaml define la API del primer día. Estos archivos permiten comenzar la implementación sin asumir que ya existe una aplicación, una base desplegada o un modelo validado con estudiantes reales.
