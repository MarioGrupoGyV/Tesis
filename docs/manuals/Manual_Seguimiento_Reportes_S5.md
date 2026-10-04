# Manual de seguimiento y reportes S5

S5 registra seguimiento **de simulación** para el Estudio con datos sintéticos.
Los códigos no representan estudiantes observados. REAL permanece bloqueado.
Una actividad o cierre aquí no acredita eficacia escolar ni una hipótesis académica.
No se envían invitaciones, mensajes o comunicaciones a familias.

## Acceso y contexto

Abre `http://localhost:15173/` y entra con tu cuenta local existente. Selecciona
el periodo y la sección autorizada en la barra superior. Los datos se solicitan
al servidor para ese alcance; la lista del tutor nunca obtiene otras secciones
para filtrarlas después en el navegador.

| Cuenta | Alertas y actividades | Reportes y CSV |
| --- | --- | --- |
| Administrador | Consulta todo el estudio, sincroniza y gestiona | Todo el alcance autorizado |
| Tutor | Consulta y gestiona únicamente sus secciones | Únicamente sus secciones |
| Directivo | Consulta; no modifica seguimiento | Consulta y descarga el alcance autorizado |
| Investigador | Inicio limitado y sesión; sin casos | No disponible |

Los periodos bloqueados permiten lectura autorizada. Todas las escrituras están
deshabilitadas y también son rechazadas por el servidor. Cambiar periodo devuelve
el detalle a la lista y limpia el borrador del contexto anterior. Cerrar sesión
cancela solicitudes y limpia datos, borradores y caché en memoria.

## Consultar y actualizar alertas

1. Abre **Alertas**. Compara código, grado/sección, severidad que motivó el caso,
   estado, responsable y actualización. Usa búsqueda por código, estado,
   severidad y orden; pulsa **Aplicar filtros**. La paginación es del servidor.
2. El administrador puede pulsar **Actualizar alertas**. La pantalla informa
   casos nuevos, fuentes actualizadas, señales bajas con caso, señales sin nueva
   alerta, decisiones reutilizadas, omitidas por antigüedad y matrículas sin
   evaluación actual. Abrir la vista nunca ejecuta esta acción automáticamente.
3. Abre el código para consultar el caso. **Motivo y fuente** explica qué
   evaluación motivó el seguimiento. **Evaluación actual** muestra la última
   revisión y resultado compatibles. Ambas pueden diferir.

Una señal media o alta vigente puede crear un caso. Repetir la sincronización
reutiliza la decisión persistida, sin duplicar caso ni auditoría. Una señal baja
conserva un caso existente para decisión humana; nunca lo resuelve automáticamente.
Una revisión pendiente o datos insuficientes conservan esos estados: no se
convierten en riesgo bajo. Cerrar un caso no permite recrearlo con la misma
predicción. Una predicción posterior puede motivar un nuevo caso.

El responsable es el tutor activo asignado por el servidor. Si no existe,
se muestra **Sin tutor asignado**. No hay gestión de usuarios ni reasignación
desde estas pantallas.

## Planificar y registrar actividades

Desde un caso activo, administrador o tutor autorizado:

1. En **Planificar actividad**, elige tipo, objetivo, fecha/hora programadas
   en Lima y notas opcionales. Objetivo hasta 1000 caracteres; notas hasta 2000.
   Usa únicamente descripciones de simulación, sin datos personales.
2. Pulsa **Planificar actividad**. Comienza **Planificada**, sin fecha efectiva.
   La programación aún no cuenta como realización.
3. En la actividad pulsa **Registrar actividad**. Puedes editar su planificación
   o cambiar a **Realizada** o **Cancelada**. Realizada exige una fecha/hora
   efectiva explícita y no futura, junto con las notas o evidencia de simulación.
   La fecha programada no se copia automáticamente como fecha efectiva.

Una actividad realizada o cancelada es terminal y conserva su evidencia. Cancelada
no tiene fecha efectiva y no cuenta como realizada. Se puede realizar o cancelar
una actividad previamente planificada después de cerrar el caso, mientras el
periodo siga abierto y la cuenta autorizada. No se crean actividades nuevas en
casos cerrados.

El tipo **Reunión familiar simulada** registra una actividad interna. No envía
una convocatoria ni implica contacto con familias.

## Cambiar estado del caso

En **Responsable y estado** elige una transición disponible y pulsa **Guardar
estado**. Abierta puede pasar a En revisión, Concluida o Descartada. En revisión
puede pasar a Concluida o Descartada. Concluir o descartar exige motivo no vacío,
hasta 1000 caracteres. La hora de cierre la registra el servidor.

Los casos cerrados no se reabren automáticamente ni admiten nuevas ediciones.
Cerrar no completa ni cancela actividades. **Concluida** significa seguimiento
terminado en la simulación; no significa una mejoría académica demostrada.

El historial del caso muestra evidencia de aperturas y cambios efectivos. Si
hay más eventos que el panel reciente, abre el **historial del estudiante**,
con páginas de eventos. Una corrección conserva las revisiones y predicciones
anteriores; el estado actual no se usa para fabricar historia.

## Conflictos y resultados inciertos

Si otra solicitud cambió el recurso, el servidor devuelve conflicto y el
formulario conserva tu borrador. Pulsa **Revisar cambios del caso** o **Revisar
cambios del registro de actividad**, lee la información actualizada y marca
**He revisado el recurso actualizado** antes de enviar nuevamente. No hay
reintentos automáticos que sobrescriban cambios ajenos.

Si se pierde la respuesta después de escribir, el resultado puede ser incierto.
Consulta el recurso o las actividades registradas antes de repetir. En una
planificación incierta se conserva la clave y el payload del mismo intento:
repetirlo reutiliza la actividad que ya se hubiera guardado. Cambiar el contenido
representa una intención nueva y usa otra clave. No repitas una intención distinta
para tratar de comprobar si la anterior se guardó.

Los mensajes muestran errores sanitizados y una referencia de soporte cuando
está disponible. Una URL ajena o inexistente recibe el mismo resultado seguro.
Si no se puede consultar la disponibilidad, las acciones sensibles permanecen
deshabilitadas hasta volver a consultar su estado. El navegador no almacena
sesiones o CSRF en `localStorage`.

## Inicio y Reportes

Inicio añade un resumen compacto del servidor: matrículas evaluadas, sin evaluar,
con datos insuficientes, con caso activo y actividades por estado. Usa los accesos
a Alertas y Reportes según tu rol.

En **Reportes**, elige los filtros y pulsa **Aplicar filtros**. El resumen y CSV
usan todo el conjunto autorizado filtrado, no solo la página visible. No hay
selector histórico: este reporte describe el **estado actual**.

| Indicador | Unidad y significado |
| --- | --- |
| Total | Matrículas autorizadas filtradas, cada una una vez |
| Evaluadas / sin evaluar / datos insuficientes | Estados excluyentes; suman el total |
| Riesgo bajo / medio / alto | Solo matrículas evaluadas; suman las evaluadas |
| Porcentaje de riesgo | Cantidad de la clase dividida por matrículas evaluadas |
| Casos por estado | Casos registrados, incluidos los históricos cerrados |
| Matrículas con caso activo | Matrículas con caso Abierto o En revisión |
| Actividades por estado | Planificadas, Realizadas y Canceladas por separado |

Con denominador cero el porcentaje es **no estimable**, no un cero inventado.
Solo Realizada cuenta como realización. No hay porcentaje de éxito de actividad,
eficacia o mejora académica. Los cortes corresponden al calendario sintético 2025;
las acciones de seguimiento tienen su fecha operativa actual. El reporte publica
periodo, alcance, actualización y rango de últimos cortes.

La tabla por matrícula conserva una fila por registro. Casos A/R/C/D significa
Abiertos/En revisión/Concluidos/Descartados; actividades P/R/C significa
Planificadas/Realizadas/Canceladas. Un caso activo enlaza a su detalle. El código
enlaza a datos e historial del estudiante.

## Descargar CSV

Pulsa **Descargar CSV** en Reportes. Incluye todas las matrículas filtradas del
alcance autorizado, sin limitarse a la página. La petición usa la sesión vigente;
si el servidor devuelve Error JSON, no se genera un archivo con apariencia de éxito.

Nombre fijo: `seguimiento-escolar-reporte.csv`. UTF-8 con BOM para Windows;
CSV con cabeceras y quoting. Los valores ausentes son celdas vacías. Incluye
origen/alcance sintético, periodo, actualización, código, contexto, corte,
evaluación/riesgo, caso activo y conteos por estado. No incluye notas libres,
motivos narrativos, credenciales, etiquetas reservadas o métricas privadas ML.

Para impedir fórmulas, la proyección elimina controles y neutraliza con apóstrofo
los textos que, tras ignorar espacios/controles iniciales, comienzan con
`=`, `+`, `-` o `@`. Esto no cambia la base de datos. Las comillas CSV solas no
impiden fórmulas. La importación y representación exactas dependen del programa
usado para abrir el CSV; no se afirma compatibilidad universal con hojas de cálculo.

La auditoría registra la solicitud de exportación, actor, filtros/alcance,
instante y cantidad. La interfaz confirma que recibió el CSV y solicitó la
descarga; no confirma que la persona lo abrió o guardó.

## Fechas y uso con teclado

Los timestamps se muestran en **America/Lima**. Los formularios interpretan
las fechas y horas locales con zona UTC−05:00. Los campos DATE conservan su día.
La comprobación de una realización usa la hora observada de la API y el tiempo
monótono transcurrido; no se sustituye silenciosamente por el reloj de Windows.
El servidor conserva la validación definitiva de fechas y estado.

Usa Tab y Shift+Tab para recorrer filtros y formularios; Enter para activar
acciones y Escape para cerrar el menú móvil. El enlace **Ir al contenido** permite
saltar la navegación. Las tablas anchas se desplazan dentro de su región, sin
ensanchar la página. Riesgo y estado se distinguen por texto, símbolo y color.

## Comandos PowerShell para preparación técnica

Estos comandos son para quien mantiene la instalación, desde la raíz del
repositorio. El recorrido del tutor/directivo se realiza en la interfaz.

```powershell
docker compose ps
docker compose exec -T api python -m pip check
npm run typecheck --workspace frontend
npm run build --workspace frontend
docker compose build web
docker compose up -d --no-deps --wait web
git diff --check
```

La compilación Docker utiliza las versiones bloqueadas y no exige Linux, WSL,
Bash o Make al operador. No borres volúmenes ni recrees cuentas para comprobar
S5. No ejecutes un checker de base vacía sobre la aplicación con usuarios.
Las instrucciones y resultados efectivos de cierre se registran en
[Estado S5](../planning/Estado_Sprint_5.md) y su matriz, sin reescribir evidencia S4.

S6, la restauración final integrada y la revisión académica permanecen pendientes.
