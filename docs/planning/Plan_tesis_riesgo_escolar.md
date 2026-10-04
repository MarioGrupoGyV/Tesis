# Plan vigente del sistema de riesgo escolar

Revisión S3.1 por instrucción expresa del usuario; ADR 006 autoriza un estudio nuevo SYNTHETIC. La planificación anterior se
conserva en history/Plan_tesis_riesgo_escolar_S2.md y no ordena el trabajo actual.

## Producto y entorno

Aplicación interna Seguimiento Escolar: acceso, importación, estudiantes, historial,
predicción, alertas, intervenciones y reportes, por iteraciones autorizadas.
Anfitrión Windows, comandos PowerShell, Docker Desktop/Compose con imágenes Linux
fijadas. React/TypeScript/Vite/Tailwind y FastAPI/SQLAlchemy/Alembic/PostgreSQL.
No cambiar versiones ni locks sin una decisión posterior.

S1/S2 aportaron sesiones, contexto, motor transaccional de importación y consultas.
S2.1 retiró el flujo DEMO, sus cuentas, semillas y datos del entorno activo; S2.2
creó explícitamente las cuatro cuentas locales que se conservan. No hay carga al
arrancar. S3.1 permite únicamente el contexto SYNTHETIC preparado por ADMIN, con
calendario y escalas de simulación declarados; no representan datos del colegio.

## Dependencia institucional

Información escolar de origen REAL significa institucional; no equivale a
consentimiento, autorización, calidad o preparación para tratamiento.
La importación REAL permanece bloqueada con INSTITUTIONAL_PROCESSING_NOT_READY hasta
documentar e implementar procedencia autorizada, escala, periodo, inicio de ventana,
disponibilidad, corte, objetivo, elegibilidad y reglas de calidad. No habilitar mediante
variables de entorno. No convertir registros fabricados en institucionales.

Las aprobaciones del colegio y asesor, autorizaciones aplicables, criterios de
riesgo, etiquetas futuras verificables, denominadores y conservación son requisitos
del protocolo. Este desarrollo no modifica la metodología ni evalúa la hipótesis.
La guía académica exige coherencia de objetivos, variables, indicadores, unidad de
análisis, instrumentos, análisis y ética; los sprints son organización del software.

## Cierre histórico S3: infraestructura predictiva; habilitación institucional pendiente

S3 completó infraestructura de pipeline, trazabilidad e inferencia con pruebas
unitarias/integración aisladas. En ese cierre no existían generador ni modelos
operativos. S3.1 amplía el uso local únicamente al estudio sintético autorizado.
Entrenamiento y evaluación institucional siguen requiriendo dataset autorizado,
etiquetas verificables y protocolo.

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
de software. No se implementan en S3.1.

Persisten UTC/America-Lima, revisiones inmutables, auditoría transaccional, permisos
por sección, CSRF, límites de CSV y paginación, idempotencia y bloqueo de periodos.
No añadir pagos, chats, portales familiares, mensajería automática ni matrícula
administrativa completa. Las decisiones pedagógicas son humanas.

Contrato público: Contrato_API.yaml 0.4.0, solo operaciones implementadas.
Esquema.sql es referencia; migraciones históricas no se reescriben. Las tablas y
endpoints de investigación que falten requieren otra iteración, nunca se simulan.

El cierre S3 conservó las cuentas S2.2 y el entorno sin registros escolares. Añadió
cuatro rutas de modelos/predicciones, con ejecución institucional bloqueada. Dataset y
manifiesto internos versionados; escalas/criterio/horizonte explícitos, particiones
comunes por estudiante y métricas no estimables null. Sin tuning, calibración,
selección automática ni evaluación prospectiva. Edad/grado solo con justificación.
Artefactos privados internos firmados, hashes y versiones verificados antes de carga;
XGBoost CPU conserva formato nativo. Las pruebas positivas usan fixtures temporales
y modelos de base inactivos. ADR 005 y Estado_Sprint_3.md delimitan comprobación y pendientes.

## S3.1 — Estudio con datos sintéticos

La solicitud S3.1 sustituye únicamente para el estudio sintético la prohibición
anterior de generar/importar registros. No recupera DEMO ni habilita REAL. La evidencia
S3 anterior se conserva como historia. Generación explícita ADMIN, configuración
synthetic-study-v1, CSV registrado exacto y contexto separado. Resultados futuros
separados de X; cinco variables base, Pipeline por fold, estudiantes independientes.
Desarrollo con CV de grupos y reserva externa posterior a fit_date son evaluaciones
diferentes. Selección definida antes de medir en desarrollo; reserva excluida de fit.
Comandos comparan/registran/activan solo simulación técnica, nunca al arrancar o por HTTP.
La migración 0003 mantiene valores históricos y separa orígenes; no reescribe 0001/0002.
GET /api/v1/processing/status informa preparación y permisos desde la política del
servidor, sin casos, etiquetas ni artefactos privados. REAL sigue bloqueado.

Las métricas dependen del generador y no acreditan eficacia escolar. Revisar con el
asesor objetivos/hipótesis, unidad de análisis, origen, generación, instrumentos,
análisis, discusión y generalización. Sin edición automática de documentos oficiales
ni afirmación de autorización del colegio o asesor. Manual_Estudio_Sintetico.md y
Estado_Sprint_3_1.md registran configuración, comandos, comprobaciones y límites.
