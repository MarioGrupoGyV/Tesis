# Sprints, dependencias y criterios de aceptación de la demo

Fecha de planificación: 3 de octubre de 2026 (America/Lima).

Este registro desarrolla el orden de `Plan_tesis_riesgo_escolar.md` e `Inicio_Codex_y_skills.md`. La entrega inicial comprendió S0; la autorización posterior comprende exclusivamente S1. Su evidencia está en `Estado_Sprint_1.md`. Los criterios de S2 a S6 describen trabajo futuro y no constituyen evidencia de implementación o pruebas ejecutadas. La coordinación contrasta cada criterio con el contrato y las decisiones vigentes antes de aceptar un sprint.

## Estado y alcance

| Sprint | Estado al redactar | Entrada / dependencia | Salida prevista |
|---|---|---|---|
| S0 Contratos y entorno | COMPLETADO: evidencia en Estado_Sprint_0.md y tests/evidence/s0-checks.json | Fuentes de planificación y repositorio inicial | Estructura, entorno diagnosticado, versiones fijadas, SQL/API reconciliados, README y este registro |
| S1 Base ejecutable | COMPLETADO: evidencia en Estado_Sprint_1.md y tests/evidence/s1-* | S0 documentado y herramientas necesarias disponibles | Compose ejecutable, migración limpia de 13 tablas, contexto demo, sesiones/CSRF, permisos y persistencia comprobados |
| S2 Importación y estudiantes | PENDIENTE; no iniciado | S1 aceptado y contrato de importación vigente | Vista previa y confirmación atómica, estudiantes e historial con alcance por sección |
| S3 Modelo y predicción demo | PENDIENTE; no iniciado | S2 aceptado, variables y fechas acordadas; interfaz de inferencia tipada | Generador sintético, baseline, RF, manifiesto e inferencia persistida |
| S4 Interfaz didáctica | PENDIENTE; no iniciado | Contrato de S0 para diseño; S1 para conexión; S2 y S3 para los flujos iniciales | Pantallas con API real; cierre final después de integrar S5 |
| S5 Alertas, intervenciones y reportes | PENDIENTE; no iniciado | S3 aceptado; sesiones, matrículas y API de S1-S2 | Casos únicos, seguimiento versionado, auditoría y exportación autorizada |
| S6 Integración y entrega | PENDIENTE; no iniciado | S1-S5 aceptados y S4 conectado también con seguimiento/reportes de S5 | Pruebas integradas, capturas reales, persistencia tras reinicio y manual de demo |

Secuencia principal: **S0 → S1 → S2 → S3 → S5 → S6**. S4 puede preparar componentes después de congelar el contrato y conectarse progresivamente con S1-S3. Su aceptación completa requiere S5: las pantallas de Alertas, intervenciones y Reportes no se aceptan con respuestas inventadas ni datos fijos que simulen el recorrido.

Las estimaciones originales son 45 min, 1 h 45 min, 1 h 45 min, 1 h 30 min, 2 h 30 min, 1 h 15 min y 2 h 30 min respectivamente. Suponen un entorno preparado y no garantizan terminar la demo en un día. Una herramienta faltante debe figurar como dependencia pendiente, con su efecto sobre S1, y nunca como una comprobación aprobada.

## Reglas de aceptación comunes

- Solo datos sintéticos DEMO. Solicitudes de procesamiento REAL devuelven `REAL_MODE_NOT_READY`; matrículas, cortes, modelos y predicciones nunca mezclan orígenes.
- Cada ruta aplica rol y alcance de sección en el servidor, desde la matrícula. El investigador no accede a casos operativos por defecto; la exportación institucional aprobada pertenece a otra fase.
- La sesión usa cookie HttpOnly, SameSite y Secure bajo HTTPS; el servidor conserva solo digests de sesión y CSRF. Las escrituras exigen CSRF y el login comprueba Origin. No se guardan tokens en localStorage ni contraseñas, tokens o filas personales en logs.
- Los eventos se guardan en UTC y se presentan en America/Lima. Se conserva inicio de ventana, corte, disponibilidad de fuente y objetivo; solo se usan entradas disponibles en el corte.
- Los cambios operativos y su auditoría se confirman en la misma transacción. Cortes corregidos crean revisiones; predicciones y auditoría no se sobrescriben. Periodos bloqueados rechazan escrituras y no hay borrado de evidencias desde la interfaz.
- Repetir CSV y periodo reutiliza el lote; repetir corte y modelo reutiliza la predicción. Como máximo existe una alerta activa por matrícula. `expected_version` protege ediciones de alertas e intervenciones y un conflicto devuelve 409.
- Ausencia de datos o predicción se comunica como pendiente o información insuficiente; nunca se sustituye por riesgo bajo. Planificada no equivale a intervención realizada y completar exige fecha efectiva.
- Todo informe y manifiesto identifica origen sintético. Las métricas sintéticas son evidencia técnica de desarrollo y no resultados del colegio ni validación de la hipótesis de tesis.
- Se acepta un recorrido con persistencia y comprobaciones, no solamente una pantalla. Cada comprobación se registra como COMPROBADO, FALLIDO o NO EJECUTADO con comando, entorno, salida y archivo de evidencia.

## S0 — Contratos y entorno

**Entrada:** AGENTS y los cuatro archivos de planificación presentes, sin implementación previa asumida.

Criterios de salida:

1. Conservar los archivos iniciales y registrar cualquier cambio deliberado de contrato o diseño; no incorporar datos reales ni modificar documentos académicos.
2. Registrar disponibilidad, versión y resultado de Git, Docker, Docker Compose, Python y Node. Distinguir una CLI encontrada, un comando que funciona, un daemon accesible y una herramienta ausente. No afirmar que PostgreSQL o servicios están ejecutándose por disponer de Docker.
3. Crear las carpetas previstas de frontend, backend, documentación, infraestructura y pruebas. Separar rutas, esquemas, servicios, repositorios y ML desde la estructura; no implementar pantallas, endpoints, migraciones, semilla o contenedores ejecutables.
4. Fijar versiones compatibles de la pila y dependencias para la demo y justificar las decisiones en `docs/adr/001-arquitectura.md`. Diferenciar compatibilidad documentada de instalación o ejecución realmente comprobada.
5. Comparar API y SQL en campos, tipos, nulabilidad, relaciones, estados y permisos. Dejar un registro de discrepancias, decisión y archivos afectados, y resolver el contrato vigente antes de programar S1. El SQL sigue siendo diseño; su migración y ejecución son S1.
6. Publicar un README con requisitos, preparación, límites de Sprint 0, herramientas pendientes y próximos pasos. Todo comando futuro se distingue de una acción ya ejecutada.
7. Registrar S1-S6 como pendientes con entradas, criterios y evidencia prevista. El cierre de S0 no declara la demo operativa.

**Evidencia de S0:** inventario/versiones y salidas de comandos de herramientas; inventario de archivos creados o modificados; revisión de estructura; ADR; registro de comparación y validación sintáctica del YAML/SQL cuando el entorno permita ejecutarla. Una revisión estática de SQL no prueba una migración ni integridad de una base creada.

**Condición para pasar a S1:** contratos y decisiones documentados, alcance congelado y herramientas de ejecución disponibles. Si falla Docker/Compose u otro requisito necesario, la preparación documental puede estar completa mientras el arranque de S1 sigue condicionado a resolver ese requisito. La coordinación debe actualizar el estado de S0 al cerrar con evidencia.

## S1 — Base ejecutable, sesiones y contexto

**Entrada:** S0 aceptado y entorno de ejecución preparado. Solo aquí se implementan Compose, configuración ejecutable, migración Alembic y semilla.

Criterios de salida:

1. Un comando documentado inicia web, API y PostgreSQL con versiones fijadas. `health/live` y `health/ready` responden según estado del proceso y conexión, sin exponer detalles internos.
2. La migración revisada crea las 13 tablas de diseño en una base PostgreSQL limpia con las restricciones acordadas en S0. No se ejecutan scripts destructivos para corregirla.
3. La semilla explícita genera contexto, periodos, secciones y cuentas sintéticas de administrador, tutor y directivo. No hay registro público ni contraseñas de producción. Reiniciar la aplicación no regenera silenciosamente registros.
4. Login, `me`, recuperación de CSRF y logout cumplen contrato. Logout revoca la sesión; una sesión vencida o revocada deja de autorizar peticiones. El login rechaza Origin no permitido y se limita el número de intentos.
5. Se verifican atributos de cookie para el entorno configurado y el uso de digests en servidor. Una escritura sin CSRF válido se rechaza. Ningún token queda en localStorage ni se expone en logs.
6. `periods` y `sections` devuelven el contexto autorizado; el tutor ve únicamente su alcance y el investigador carece de acceso operativo. No se acepta un rol enviado por el navegador como autorización.
7. Las cuentas y el contexto siguen persistidos después de detener y arrancar los servicios con el volumen conservado.

**Evidencia ejecutada de S1:** los equivalentes PowerShell `infra/s1.py up`, `migrate`, `seed-demo`; migración limpia de 13 tablas, 57 pruebas backend, cuatro recorridos Playwright, salud, CSRF, permisos/revocación y comparación de las 13 tablas tras detener/recrear contenedores sin borrar volumen. Resultados, destinos y comandos en `Estado_Sprint_1.md`. Make no está instalado y no se declaró ejecutado. Nada de esto se atribuye a S0.

## S2 — CSV, estudiantes y cortes

**Entrada:** S1 aceptado; tablas, sesiones, roles, periodos y secciones disponibles.

Criterios de salida:

1. Vista previa, detalle y confirmación del lote cumplen las rutas y respuestas de OpenAPI. El periodo se elige en el formulario; la plantilla utiliza los 13 campos CSV descritos en Inicio: `student_code`, `grade`, `section`, `cutoff_at`, `target_date`, `available_at`, `window_start`, `average_grade`, `attendance_pct`, `activities_pct`, `participation_level`, `behavior_incidents`, `age_years`.
2. Validar UTF-8, límite de archivo, cabeceras, duplicados, origen, sección, escala y fechas antes de confirmar. Los errores indican fila, columna y corrección esperada sin escribir matrículas o cortes en la vista previa.
3. La confirmación usa una transacción con auditoría. Un CSV inválido o un fallo durante la operación no deja registros académicos parciales; un periodo bloqueado rechaza la escritura.
4. Guardar hash SHA-256, periodo, versión del esquema, usuario, cantidades y fechas del lote. Repetir el archivo para el mismo periodo o repetir la confirmación devuelve el lote/resultado existente sin duplicar matrículas ni cortes.
5. Las relaciones pertenecen al mismo estudiante y origen. Los valores faltantes permanecen faltantes; cortes corregidos crean una revisión y conservan la anterior.
6. Inicio de ventana, disponibilidad y corte respetan el orden temporal acordado; disponibilidad no es posterior al corte y el objetivo es posterior al corte y está dentro del periodo. Rechazar fuentes futuras y fechas fuera del contexto.
7. Lista, detalle y timeline de estudiantes respetan permisos, filtros permitidos, orden estable y paginación acotada. Probar tutor propio/ajeno y denegación al investigador.
8. Un corte nuevo sin evaluación aparece pendiente, aunque exista una predicción antigua en el historial. No se atribuye la predicción anterior al corte nuevo.
9. La vista previa muestra planned_students/enrollments/snapshots y preview_version. Confirmar exige expected_preview_version; una pestaña vieja o un predecesor cambiado devuelve 409 IMPORT_PREVIEW_STALE sin escrituras. Refrescar conserva el lote, incrementa la versión y requiere nueva revisión humana; COMMITTED reutiliza siempre el resultado original después de autorizar el recurso.

**Evidencia futura:** pruebas backend de importación válida, inválida, fallo/rollback, repetición y revisión; peticiones autenticadas de lista/detalle/timeline; comprobación de filas y auditoría en PostgreSQL; muestras CSV exclusivamente sintéticas. Usar `make test` con los casos correspondientes cuando se implemente; guardar cantidades antes/después y respuestas.

## S3 — Modelo y predicción demo

**Entrada:** S2 aceptado; variables admitidas, horizonte y una interfaz tipada de inferencia acordada entre backend y ML.

Criterios de salida:

1. Generar localmente 60 estudiantes sintéticos de varias secciones, con cortes tempranos y resultados posteriores separados. Documentar semilla y mecanismo sin ajustar el generador para obtener métricas altas; incluir al menos un corte insuficiente.
2. Entrenar DummyClassifier y Random Forest dentro de Pipeline. Imputación, codificación y cualquier escala se ajustan únicamente con entrenamiento de cada partición.
3. Separar grupos por estudiante y demostrar grupos disjuntos entre entrenamiento y validación. Verificar soporte por clase y justificar el número de particiones si alguna clase/grupo es insuficiente. Varios cortes del mismo estudiante no incrementan la muestra independiente.
4. Excluir etiquetas, notas finales del horizonte, predicciones e intervenciones posteriores. Probar disponibilidad en el corte y fecha objetivo futura antes de inferir.
5. Conservar hashes de dataset y artefacto, semilla, parámetros, versiones, variables, orden de clases, grupos por partición, soporte, métricas por clase y matriz de confusión. El manifiesto declara DEMO/origen sintético; no exige una exactitud mínima.
6. Consulta/activación de modelos, ejecución y consulta de predicción cumplen permisos y contrato. Solo se cargan artefactos internos registrados y compatibles con el origen; no se cargan archivos arbitrarios de usuarios.
7. Inferir con el último corte disponible hasta el instante solicitado; persistir corte, modelo, objetivo, fecha y resultado sin sobrescribirlos. Repetir corte/modelo reutiliza la predicción y no duplica resultados.
8. Datos insuficientes o modelo incompatible producen estado explicativo sin riesgo inventado. Las probabilidades solo se muestran si existen; la importancia global no se ofrece como explicación individual ni como causa.
9. El procesamiento REAL se rechaza con `REAL_MODE_NOT_READY`. SVM, XGBoost y evaluación con registros institucionales permanecen fuera de la demo.

**Evidencia futura:** `make train-demo`, manifiesto y hashes, salidas de evaluación y pruebas de separación de grupos/fuga temporal/abstención/idempotencia/origen. Guardar artefactos fuera del repositorio en la ubicación controlada y evidenciar su referencia; no publicar resultados sintéticos como resultados escolares.

## S4 — Interfaz con API real

**Entrada:** contrato congelado de S0 y base de S1; integración inicial con S2-S3. **Dependencia de cierre:** S5 para Alertas, acciones de intervención y Reportes completos.

Criterios de salida:

1. Navegación Inicio, Estudiantes, Alertas, Datos y Reportes; Modelo y Configuración solo para los roles definidos por el contrato. Las vistas consumen tipos generados desde OpenAPI o verificados frente a él.
2. Login y acciones usan sesión y CSRF sin tokens en localStorage. Una denegación del servidor produce un mensaje útil y no revela recursos ajenos.
3. Importación presenta elegir archivo, revisar resultado y confirmar; los errores y cantidades proceden de la API y se informa el resultado de confirmar o reutilizar un lote.
4. Cada pantalla presenta carga, vacío, error y éxito. Riesgo utiliza texto, icono y color; un caso sin datos suficientes o sin evaluación se distingue de riesgo bajo.
5. Indicadores muestran periodo, actualización, origen y denominador. Lista, filtros, detalle, datos académicos e historial coinciden con la API y muestran fecha del corte correcto.
6. Intervenciones se realizan desde el estudiante o alerta con contexto visible. Formularios y mensajes de conflicto siguen las reglas de S5; la interfaz no calcula oportunidad ni inventa datos de modelo.
7. Marca DEMO visible y ayuda breve para importar, evaluar y atender. Observaciones académicas se presentan en español claro, sin atribuirlas como causas del modelo ni exponer detalles internos de ingeniería al tutor.
8. Comprobar navegación por teclado, etiquetas y foco, y revisar 1440 × 900, 768 × 1024 y 390 × 844 con capturas de la aplicación real. Las tablas móviles desplazan su contenedor sin desbordar la página.
9. Las pantallas del recorrido importación → evaluación → atención → exportación funcionan con backend y persistencia reales. Componentes o respuestas simuladas no satisfacen este criterio.

**Evidencia futura:** build del frontend, pruebas de navegación con backend, capturas en las tres dimensiones y respuestas de API asociadas; comprobación manual de teclado. Registrar nombre/ruta de las capturas y tamaño efectivo; no sustituirlas por bocetos.

## S5 — Casos, intervenciones y CSV

**Entrada:** S3 aceptado y matrículas/predicciones persistidas; permisos y sesiones de S1-S2. Coordinar integración final de frontend en S4.

Criterios de salida:

1. Riesgo medio/alto abre o actualiza un caso de la misma matrícula. Repetir evaluación o evaluar un corte nuevo no crea dos alertas activas; la restricción existe también en PostgreSQL.
2. ABIERTA permite EN_ATENCION, RESUELTA o DESCARTADA; EN_ATENCION permite RESUELTA o DESCARTADA. Resolver directamente también exige motivo y versión. Una bajada de riesgo no cierra automáticamente un caso con intervención pendiente.
3. Toda edición de alerta e intervención exige `expected_version`. Dos solicitudes con la misma versión producen un cambio y un conflicto 409, sin perder auditoría.
4. Crear/actualizar intervenciones respeta pertenencia de matrícula y alerta, rol y sección. Estado PLANIFICADA no cuenta como REALIZADA; completar exige fecha efectiva. No se borra el historial al resolver un caso.
5. Cambios de seguimiento y auditoría se guardan de forma atómica con usuario y fecha UTC. Probar rollback y rechazo en periodos bloqueados.
6. Resumen y CSV respetan el periodo y alcance del usuario, coinciden con las cifras de pantalla/API y declaran origen sintético. El investigador no recibe por defecto identificadores ni exportación de casos operativos.
7. Reportes distinguen no evaluado, información insuficiente y riesgo; los denominadores se explicitan y un denominador cero muestra No aplica. No se inventan mediciones pretest/postest ni conclusiones académicas.

**Evidencia futura:** pruebas backend de unicidad, transiciones, concurrencia, fechas efectivas, permisos y auditoría; respuestas de seguimiento; CSV descargado y contraste de filas/cifras con pantalla/API/base. Usar exclusivamente casos sintéticos y conservar evidencias sin secretos.

## S6 — Verificación integrada y entrega

**Entrada:** S1-S5 aceptados y cierre de integración de S4; comandos y manuales implementados.

Criterios de salida:

1. Ejecutar arranque documentado y migración en una base limpia de demo con versiones fijadas. Registrar build frontend y pruebas backend apropiadas a permisos, integridad, origen y ML.
2. Playwright recorre entrar/importar/evaluar/atender/exportar con API y PostgreSQL; valida respuestas, filas y contenido CSV. Incluir archivo inválido, corte insuficiente, lote repetido, evaluación repetida, tutor ajeno y conflicto de versión.
3. Reiniciar servicios conservando volumen y comprobar que lote, corte, predicción, alerta, intervención y auditoría siguen presentes. No simular persistencia insertando filas manualmente para la prueba.
4. Capturar interfaz real en las tres dimensiones y contrastar estados/indicadores con respuestas de API. Las capturas complementan el recorrido y no sustituyen las pruebas de permisos.
5. Manual de arranque y demo reproducible contiene comandos, cuentas demo, origen, límites, ruta del artefacto y el recorrido de cinco a ocho minutos. `make demo` prepara solo DEMO; no hay reinicio de datos institucionales.
6. Documentar comprobaciones como COMPROBADO, FALLIDO o NO EJECUTADO. Incluir comandos, resultados, evidencias, incidencias y siguiente dependencia. Toda limitación del entorno permanece pendiente, sin afirmaciones de éxito sustitutivas.
7. La entrega declara demo técnica con datos sintéticos. Si falta modelo/ML, informar demo incompleta en predicción y mostrar Modelo no disponible; nunca usar resultados fijos presentados como modelo. Se pueden retirar gráficos extra, animaciones o PDF, pero no permisos, persistencia ni pruebas del recorrido esencial.

**Evidencia futura:** `make up`, `make migrate`, `make test`, build frontend, ejecución Playwright, reinicio de servicios conservando volumen, capturas, CSV y reporte final de evidencias. `make demo` y `make backup` se verifican cuando estén implementados; las invocaciones precisas deben figurar en el README/manual vigente. Esta lista no indica ejecución durante S0.

## Dependencias posteriores a la demo

La fase institucional exige aprobación del colegio y asesor, autorizaciones, escala y criterio de riesgo, horizonte, fechas O1/O2, reglas de elegibilidad, ventanas de oportunidad, denominadores y conservación. Las seis tablas de investigación y sus contratos pertenecen a esa fase, igual que SVM/XGBoost, exportación SPSS aprobada y mediciones pareadas. El bloqueo REAL se conserva hasta una iteración expresamente autorizada con controles implementados y verificados.

La demo no reemplaza esos permisos ni la evidencia académica. No se cambia automáticamente la metodología y no se trasladan poblaciones o resultados de una tesis de referencia.
