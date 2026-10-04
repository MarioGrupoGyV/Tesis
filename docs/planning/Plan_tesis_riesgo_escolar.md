# Plan vigente del sistema de riesgo escolar

Revisión S2.1 por instrucción expresa del usuario. La planificación anterior se
conserva en history/Plan_tesis_riesgo_escolar_S2.md y no ordena el trabajo actual.

## Producto y entorno

Aplicación interna Seguimiento Escolar: acceso, importación, estudiantes, historial,
predicción, alertas, intervenciones y reportes, por iteraciones autorizadas.
Anfitrión Windows, comandos PowerShell, Docker Desktop/Compose con imágenes Linux
fijadas. React/TypeScript/Vite/Tailwind y FastAPI/SQLAlchemy/Alembic/PostgreSQL.
No cambiar versiones ni locks sin una decisión posterior.

S1/S2 aportaron sesiones, contexto, motor transaccional de importación y consultas.
S2.1 retira cuentas, semillas, datos e identidad visual de demostración del flujo
activo. La aplicación arranca vacía. Contexto se configura explícitamente por un
operador; no se inventan calendarios, escalas, secciones ni datos del colegio.

## Dependencia institucional

Información escolar de origen REAL significa institucional; no equivale a
consentimiento, autorización, calidad o preparación para tratamiento.
La importación permanece bloqueada con INSTITUTIONAL_PROCESSING_NOT_READY hasta
documentar e implementar procedencia autorizada, escala, periodo, inicio de ventana,
disponibilidad, corte, objetivo, elegibilidad y reglas de calidad. No habilitar mediante
variables de entorno. No convertir registros fabricados en institucionales.

Las aprobaciones del colegio y asesor, autorizaciones aplicables, criterios de
riesgo, etiquetas futuras verificables, denominadores y conservación son requisitos
del protocolo. Este desarrollo no modifica la metodología ni evalúa la hipótesis.
La guía académica exige coherencia de objetivos, variables, indicadores, unidad de
análisis, instrumentos, análisis y ética; los sprints son organización del software.

## S3: módulo predictivo del proyecto — pendiente

Implementar infraestructura de pipeline, trazabilidad e inferencia, con pruebas
unitarias/integración aisladas. Sin generador de una escuela ficticia ni entrenamiento
operativo con alumnos inventados. Entrenamiento y evaluación institucional requieren
dataset autorizado, etiquetas verificables y protocolo.

Conservar el alcance del plan académico previo: baseline DummyClassifier y comparación
de Random Forest, SVM y XGBoost. No sustituir el protocolo por una métrica objetivo.
Imputación, codificación, escala y cualquier remuestreo se ajustan dentro de Pipeline
y de cada partición. Separar grupos por estudiante; varios cortes no aumentan el número
de personas independientes. Solo variables disponibles al corte, sin notas finales
del horizonte, etiquetas, predicciones ni intervenciones futuras.

Guardar hash de dataset/artefacto, procedencia, semilla, parámetros, versiones, variables,
clases, soporte, particiones y métricas. Las probabilidades exigen calibración comprobada;
importancia global no explica causalmente un caso individual. Sin dataset/modelo válido,
informar Modelo no disponible o Datos insuficientes. No fabricar riesgos ni métricas.

## S4–S6 — pendientes

S4 completará las pantallas con estados de carga/vacío/error/éxito y accesibilidad.
S5 implementará seguimiento versionado, alertas únicas y exportaciones autorizadas.
S6 integrará el recorrido y evidencias, sin atribuir validación académica a pruebas
de software. No se implementan en S2.1.

Persisten UTC/America-Lima, revisiones inmutables, auditoría transaccional, permisos
por sección, CSRF, límites de CSV y paginación, idempotencia y bloqueo de periodos.
No añadir pagos, chats, portales familiares, mensajería automática ni matrícula
administrativa completa. Las decisiones pedagógicas son humanas.

Contrato público: Contrato_API.yaml 0.2.0, solo operaciones implementadas.
Esquema.sql es referencia; migraciones históricas no se reescriben. Las tablas y
endpoints de investigación que falten requieren otra iteración, nunca se simulan.
