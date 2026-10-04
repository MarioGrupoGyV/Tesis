# Alcance y limitaciones

Seguimiento Escolar integra software local para **simulación con datos sintéticos**.
Una prueba funcional, una comparación del generador y una validación escolar son
evidencias distintas. El cierre técnico S6 depende de instalación nueva, recorrido
integrado, recuperación completa y revisión conservadora del activo; sus resultados
están en [Estado S6](../planning/Estado_Sprint_6.md) y la
[matriz final](Matriz_Trazabilidad_Final.md). Este documento no los presupone.

## Qué ofrece el software

- Acceso de cuatro roles con sesiones, CSRF, alcance de sección y auditoría.
- CSV registrado con vista previa/confirmación, versiones, atomicidad, faltantes
  y evidencia de revisiones; estudiantes, detalle e historial autorizados.
- Núcleo ML reproducible y simulación explícita con Dummy, Random Forest, SVM y
  XGBoost CPU; artefactos internos privados y firmados, inferencia/abstención.
- Alertas/casos, actividades versionadas, cierre humano, decisión idempotente,
  resumen actual por matrícula y CSV completo filtrado autorizado.
- Operación Windows/PowerShell/Docker, herramientas de instalación/perfiles y
  recuperación con destinos aislados e información privada fuera de Git.

No hay comunicaciones a familias/terceros, pagos, chats, portal familiar, gestión
completa de matrículas, registro público, reasignación por pantalla o entrenamiento/
activación HTTP. No se añaden módulos de negocio en S6. El detalle técnico está en
[arquitectura](Arquitectura_Final.md), [API](Mapa_Endpoints.md) y
[diccionario](Diccionario_Base_Datos.md).

## Qué significa el experimento sintético

SYNTHETIC identifica trayectorias y resultados futuros fabricados por un mecanismo
versionado. No son menores observados ni datos reales anonimizados. Sus escalas,
calendario, horizonte y criterio son supuestos de synthetic-study-v1, sin atribuirlos
al colegio. Semilla/versiones/configuración determinan los hashes reproducibles.

Los 60 estudiantes/360 cortes de la configuración habitual son 60 unidades
independientes, no 360 personas. Desarrollo y reserva se fijan por estudiante y
tiempo; los cuatro algoritmos usan los mismos splits. Ajustes del pipeline se hacen
solo en train/fold. Selección usa desarrollo, sin mirar la reserva para elegir.
No se exige precisión mínima ni se altera el generador para mejorar métricas.

Comparación por grupos y reserva posterior aportan evidencia experimental
condicionada por el generador. El calendario simulado no prueba entrenamiento o
seguimiento prospectivo del colegio en esas fechas. Un algoritmo técnicamente
seleccionado/aprobado/activo es utilizable **solo para esa simulación**. Las cuentas
locales, intervenciones realizadas/canceladas y caso concluido no acreditan personas,
contactos con familias, eficacia pedagógica o mejoría académica.

## Qué no demuestra una estimación

Riesgo LOW/MEDIUM/HIGH es una clasificación bajo el criterio sintético, no una
explicación causal ni diagnóstico escolar. No hay SHAP ni explicaciones causales.
Importancia global o correlación no explican individualmente un estudiante.
Probabilidades permanecen null/no calibradas; no se presentan porcentajes de certeza.

Datos insuficientes o modelo no disponible producen abstención/pending, nunca LOW
por defecto. La elegibilidad del análisis y la política operativa de faltantes son
definiciones separadas. Datos/metadatos incorporados después de as_of no deben
entrar a esa evaluación; una revisión nueva no recibe la predicción de la anterior.

Casos actuales/históricos y actividades cuentan trabajo registrado, no impacto.
PLANNED no es DONE; DONE exige fecha efectiva. Cerrar el caso no termina actividades
automáticamente ni confirma éxito de una intervención. Un denominador cero es no
estimable. Los reportes son actuales, no un selector de eficacia o comparación histórica.

## Requisitos institucionales pendientes

REAL sigue bloqueado mediante INSTITUTIONAL_PROCESSING_NOT_READY. Crear un periodo
REAL, marcar elegibilidad, registrar un perfil ADMIN o cambiar una variable no
autoriza importación, entrenamiento, activación o inferencia institucional.

Antes de otro alcance institucional se necesitan procedencia autorizada, escalas
del colegio, criterio/etiquetas futuras verificables, calendario/horizonte/protocolo,
política de calidad/elegibilidad/faltantes, conservación y autorizaciones aplicables.
También deben diseñarse/implementarse los cambios de activación y comprobarse con
una nueva migración/protocolo revisados. No buscar ni cargar archivos personales
o información del colegio por cuenta propia.

La revisión con asesor sigue pendiente: coherencia de objetivos/hipótesis, variables,
unidad de análisis, instrumentos, mecanismo de generación, análisis, discusión,
generalización y ética. No se modifica aquí el documento académico oficial, no hay
aceptación del asesor/colegio y la hipótesis no está validada por este software.

## Límites del entorno y de la comprobación

Localhost HTTP/loopback y Vite no equivalen a despliegue externo con HTTPS. No se
realiza carga de producción, auditoría integral de seguridad, certificación WCAG,
revisión completa con lector de pantalla o todos los navegadores/dispositivos.
Chromium, teclado, foco y tres tamaños se verifican con evidencia específica,
sin convertir capturas en una certificación.

DPAPI protege el respaldo para el usuario Windows; recuperación depende del perfil/
equipo y su mecanismo de recuperación. No es una promesa de portabilidad a otra PC
o perfil ni un plan institucional completo de continuidad. Un nuevo equipo usa su
instalación/bootstrap propios. El respaldo no exporta Credential Manager.
Hash comprueba integridad; no vuelve confiable un artefacto desconocido.

La [restauración estructural comprobada S6](../../tests/evidence/s6-restore-final-code.json)
conservó tablas/Alembic/archivos, modelo SVM y clave HMAC en un destino nuevo antes
del login. Las [negativas del respaldo real](../../tests/evidence/s6-backup-negative-final.json)
comprueban protección DPAPI Windows y rechazo de seis alteraciones/colisiones.
Estos resultados no acreditan portabilidad, validación institucional o aprobación
académica; tampoco sustituyen el recorrido A o las revisiones UI B/C.

Instalación nueva, persistencia y restauración se reportan por separado. Una
inyección HTTP no acredita caída real DB; un mock no acredita DPAPI Windows. Fallos,
omisiones y pruebas obligatorias no ejecutadas deben permanecer visibles. S6 se
cierra para simulación solo con sus criterios obligatorios comprobados; no se
declara validación escolar, tesis concluida o habilitación REAL.
