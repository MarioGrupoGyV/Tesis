# Desarrollo del sistema de riesgo escolar

Estas instrucciones se deben colocar en la raíz del repositorio de la tesis. Describen la implementación prevista. La fase vigente es DEMO con datos sintéticos y un presupuesto de un día. No existe una autorización implícita para cargar datos de menores ni cambiar la metodología académica.

## Fuentes del proyecto

Antes de implementar, incorporar en `docs/planning/` el plan, `Contrato_API_demo.yaml`, `Esquema_demo.sql` y `Inicio_Codex_y_skills.md`. Guardar el documento académico y sus referencias en un destino de acceso adecuado; no incorporar archivos con datos identificables al repositorio.

Prioridad: instrucciones del usuario, requisitos académicos vigentes y contratos de la iteración actual. Ante un conflicto, registrar la decisión y corregir los documentos afectados. No copiar resultados ni poblaciones de una tesis de referencia.

## Alcance vigente

- Implementar login, permisos, CSV con vista previa y confirmación, estudiantes, tablero, predicción demo, alertas, intervenciones y exportación CSV.
- Usar React TypeScript Vite Tailwind y FastAPI SQLAlchemy Alembic PostgreSQL. Fijar versiones compatibles en la primera iteración.
- Entrenar localmente DummyClassifier y Random Forest para demostrar funcionamiento. SVM y XGBoost con datos institucionales pertenecen a la siguiente fase.
- Mantener una marca DEMO visible. Todo reporte y manifiesto debe declarar origen sintético.
- Bloquear solicitudes de procesamiento REAL con `REAL_MODE_NOT_READY` hasta habilitar el protocolo en una iteración posterior.
- No añadir pagos, chats, portales de familias, integraciones ni gestión completa de matrículas administrativas.

## Reglas de implementación

- Separar rutas, esquemas, servicios y repositorios. Mantener la lógica del modelo dentro de `backend/app/ml`.
- Generar los tipos frontend desde OpenAPI o verificarlos frente al contrato. No inventar campos en un componente.
- Convertir el SQL de diseño en una migración Alembic revisada; no ejecutar scripts destructivos para corregir migraciones.
- El coordinador controla migraciones, archivos raíz y cambios de contratos. Un agente debe respetar su alcance de archivos.
- Crear primero la base ejecutable y después integrar cada recorrido. No declarar un módulo terminado solo porque existe su pantalla.
- Utilizar transacciones en importación y seguimiento. Guardar auditoría junto con el cambio.
- No enviar mensajes a familias ni a terceros. Las acciones del sistema son internas y las decisiones pedagógicas son humanas.

## Fechas y Machine Learning

- Guardar eventos en UTC y mostrarlos en America/Lima.
- Conservar inicio de ventana, fecha de corte, disponibilidad de fuente y fecha objetivo.
- Solo usar variables disponibles en el instante de predicción. No usar notas finales del horizonte, etiquetas, predicciones ni intervenciones posteriores como entradas.
- Separar grupos por estudiante. Ajustar imputación, codificación y escala dentro de Pipeline y de cada partición de entrenamiento.
- No incrementar el tamaño independiente de la muestra contando varios cortes del mismo estudiante como distintas personas.
- Guardar hash del dataset, semilla, parámetros, versiones, particiones, soporte por clase y métricas.
- Mostrar información insuficiente cuando corresponda. Nunca rellenar una predicción faltante con riesgo bajo.
- No prometer una exactitud mínima ni presentar métricas sintéticas como resultados del colegio.
- No presentar importancia global de variables como explicación individual ni correlación como causa.

## Persistencia e integridad

- No mezclar datos DEMO y REAL en matrículas, cortes, modelos ni predicciones.
- Los cortes corregidos crean nuevas revisiones. Cortes, predicciones y auditoría no se sobrescriben.
- La misma combinación corte modelo reutiliza la predicción. El mismo CSV y periodo reutiliza el lote.
- Permitir una sola alerta activa por matrícula. Una nueva evaluación actualiza un caso existente.
- Exigir `expected_version` al editar alertas e intervenciones y devolver 409 si está desactualizada.
- Una intervención planificada no cuenta como realizada. Completar exige fecha efectiva.
- Los periodos bloqueados rechazan escrituras. No eliminar evidencias desde la interfaz.

## Acceso

- Verificar en el servidor el rol y la sección de cada recurso; nunca confiar en un rol enviado por el navegador.
- Usar cookie de sesión HttpOnly, SameSite y Secure bajo HTTPS. Token de sesión almacenado solo como digest en servidor.
- Exigir CSRF en escrituras y comprobar Origin en login. No almacenar tokens en localStorage.
- Limitar intentos de login, tamaño de archivo, paginación y campos de ordenación.
- No guardar contraseñas, tokens ni filas con datos personales en logs.
- Un investigador no accede a listados de casos por defecto. Habilitar solo exportaciones expresamente aprobadas en la fase institucional.

## Interfaz

- Navegación principal: Inicio, Estudiantes, Alertas, Datos y Reportes. Modelo y Configuración dependen del rol.
- Cada pantalla tiene estados de carga, vacío, error y éxito. No dejar tablas en blanco sin explicación.
- Mostrar riesgo con texto, icono y color. No depender solo del color.
- Presentar periodo, actualización y denominador junto a indicadores.
- Situar la intervención en el contexto del estudiante o alerta. Usar español claro y acciones concretas.
- Mantener ayuda de tres pasos para importación. No poner detalles internos de ingeniería en pantallas del tutor.
- Revisar 1440 × 900, 768 × 1024 y 390 × 844; capturar evidencia de la interfaz real.

## Cierre de una iteración

Ejecutar las pruebas pertinentes y reportar: resultado, archivos cambiados, comandos y evidencia, incidencias pendientes y siguiente dependencia. Distinguir comprobado, fallido y no ejecutado. No afirmar prueba visual, base creada, modelo validado ni recorrido completo sin evidencia.

El cierre de la demo requiere build, migración en base limpia, pruebas de permisos e integridad, recorrido Playwright importar evaluar atender exportar y comprobación de persistencia después de reiniciar. Si un entorno impide una comprobación, reportarlo sin reemplazarla por una afirmación de éxito.

## Trabajo entre agentes

Coordinar primero el contrato. Delegar tareas solo si se decide usar agentes para la implementación. No editar en paralelo las mismas migraciones o los mismos archivos raíz. Backend y ML acuerdan una interfaz tipada de inferencia. Frontend consume el contrato y QA prueba el sistema integrado. Los cambios de alcance se resuelven por coordinación.
