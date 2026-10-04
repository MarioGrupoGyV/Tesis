# Manual de uso final

Seguimiento Escolar trabaja con un **Estudio con datos sintéticos**. Los códigos
no representan estudiantes observados; actividades y cierres son simulaciones.
REAL continúa bloqueado. Este manual reúne las tareas de las pantallas conectadas;
los detalles históricos se conservan en [uso S4](Manual_Uso_S4.md) y
[seguimiento S5](Manual_Seguimiento_Reportes_S5.md).

Para instalar o administrar perfiles consulta el
[manual Windows](Manual_Instalacion_Windows.md); para recuperar una copia, el
[manual de respaldo](Manual_Respaldo_Restauracion.md). Los resultados y capturas
nuevos se identifican en [Estado S6](../planning/Estado_Sprint_6.md) y la
[matriz final](Matriz_Trazabilidad_Final.md). Las capturas enlazadas abajo pertenecen
a S6: consultas del activo o formularios del destino de instalación aislada,
identificados en cada pie. No se recrearon actividades en el activo para ilustrarlas.

## Entrar y elegir contexto

1. Abre la URL de tu instalación. En el entorno principal es
   `http://localhost:15173/`; una copia aislada tiene otra URL indicada por su operador.
2. Introduce tu correo y contraseña local. No hay cuenta/contraseña predeterminadas.
   Si ya tienes las cuentas S2.2, usa sus accesos existentes; no recrearlas.
3. Selecciona periodo y sección autorizados en la barra superior. El aviso de origen
   debe indicar que son datos sintéticos. Una aplicación recién instalada puede
   estar vacía hasta que el administrador prepare explícitamente el contexto.

La sesión puede vencer o revocarse. **Cerrar sesión** limpia consultas, borradores
y contexto; úsalo antes de cambiar de cuenta. No compartas contraseñas/cookies/
tokens en mensajes o capturas. Si aparece un límite de acceso, espera la ventana
indicada; no repitas login continuamente.

| Rol | Tareas disponibles |
| --- | --- |
| Administrador | Contexto, estudiantes, importar CSV registrado, consultar modelos/evaluar simulación, sincronizar y gestionar casos/actividades, reportes/CSV |
| Tutor | Estudiantes, casos/actividades y reportes/CSV solo de sus secciones |
| Directivo | Consultar estudiantes/casos/historial y descargar reportes, sin modificar |
| Investigador | Inicio limitado/estado general y sesión; sin casos, estudiantes, modelos o reportes por defecto |

El servidor comprueba esos permisos en cada operación. El acceso directo a una URL
no amplía el alcance. Un recurso ajeno y uno inexistente muestran el mismo aviso
seguro. Periodos bloqueados permiten lectura autorizada, pero impiden escrituras.

## Inicio y estados de pantalla

Inicio muestra periodo, alcance y aviso de simulación. En roles de consulta, el
resumen cuenta matrículas autorizadas y distingue evaluadas, pendientes y con datos
insuficientes. Los porcentajes de riesgo incluyen denominador; si no hay evaluadas
se informa que no son estimables. Las actividades realizadas se separan de las
planificadas/canceladas. Los indicadores no miden eficacia escolar.

[Captura S6, activo: Inicio ADMIN en móvil](../../tests/evidence/s6-active-final-admin-home-390x844.png).
La pantalla distingue carga, vacío, filtros sin resultados, error, bloqueo y éxito.
Si no puede consultar preparación, deshabilita acciones sensibles con un motivo;
estar conectado no significa tener permiso o un modelo compatible.

## Consultar estudiantes e historial

1. Abre **Estudiantes**. Busca por código, filtra por riesgo y elige orden/tamaño de
   página. Aplica los filtros; el servidor devuelve solo el conjunto autorizado.
2. Abre un código para ver contexto, últimas mediciones, ventana, corte, disponibilidad
   y evaluación. **Sin dato** conserva un valor faltante; **pendiente** o **datos
   insuficientes** no significan riesgo bajo.
3. Revisa el historial del estudiante. Usa la paginación y **Eventos por página**
   para recorrer eventos; una predicción histórica pertenece a su corte/revisión,
   no a una corrección posterior. Puedes consultar el caso desde el seguimiento.

Los instantes se muestran en **America/Lima**. El calendario de datos sintéticos
puede ser 2025 y las acciones operativas posteriores; no retrofechar acciones para
que parezcan observaciones escolares. Las fechas del calendario conservan su día.

## Importar el CSV registrado — solo administrador

El archivo se obtiene por preparación/exportación explícita del administrador,
según [instalación](Manual_Instalacion_Windows.md) y
[protocolo del estudio](Manual_Estudio_Sintetico.md). Usa el CSV exacto registrado;
no lo edites manualmente para cargar notas propias. La plantilla de cabeceras no
contiene estudiantes ni sustituye ese archivo.

### 1. Preparar

En **Datos**, selecciona el periodo sintético abierto y **Seleccionar CSV**. UTF-8,
máximo 5 MiB/10000 filas y 13 cabeceras previstas. Mantén faltantes vacíos, sin
rellenarlos con ceros, etiquetas o riesgo. Pulsa **Revisar archivo** una vez.

### 2. Revisar

Lee estado, cantidades y errores por fila/campo. Vista previa no crea estudiantes,
matrículas o cortes. Cantidades previstas son un plan. Un lote inválido no permite
confirmar; solicita un archivo registrado correcto. **Consultar lote** recupera
el estado guardado. Si aparece **Se reutilizó la importación existente**, ya se
confirmó ese archivo/periodo: abre sus estudiantes, sin crear duplicados.

### 3. Confirmar

En lote listo sin errores, marca la casilla de revisión y pulsa **Confirmar
importación** una vez. Espera respuesta; el servidor revalida versión/estado y
confirma con auditoría. Cambiar archivo/contexto invalida la vista previa.
Ante conflicto vuelve a **Revisar archivo de nuevo**. Si la respuesta se pierde,
usa **Consultar resultado del lote** antes de repetir; no hay reintento automático.

REAL no está habilitado, incluso si existe un periodo de ese origen. No elijas
archivos del colegio o de menores para probar el formulario.

## Evaluar una simulación — solo administrador

La comparación/registro/activación se preparan por comandos explícitos; la pantalla
no entrena ni activa modelos. No repetir esos pasos en el estudio activo para usarlo.

1. Selecciona el periodo y abre **Modelos**. Consulta algoritmo, versión, estado y
   origen. **Aprobado para simulación** es una aprobación técnica.
2. En **Evaluar periodo**, conserva **Instante actual** y pulsa **Evaluar ahora**
   cuando esté disponible. La hora procede del sistema, no del reloj de Windows.
3. Revisa cortes seleccionados, evaluaciones nuevas/reutilizadas y abstenciones,
   junto con conteos de seguimiento. Abre estudiantes o alertas para comprobar.

**Elegir fecha y hora (America/Lima)** conserva tu instante explícito y no admite
futuro. Una fecha anterior puede no tener datos/modelo incorporados entonces.
No elegir automáticamente 2025 porque el calendario sea simulado. La misma
combinación corte/modelo reutiliza el resultado. Abstención conserva motivo y no
crea un riesgo bajo; no hay porcentajes de certeza sin calibración comprobada.

Si se pierde confirmación, consulta registros antes de repetir. Modelo incompatible,
periodo bloqueado o preparación insuficiente tienen un diagnóstico visible.

## Consultar y gestionar un caso

Administrador y tutor autorizado gestionan; directivo solo consulta.

1. En **Alertas**, usa código, estado, severidad, orden y página. La severidad del
   caso pertenece a su fuente; el riesgo actual puede haber cambiado o ser pendiente.
2. Abre un caso. **Motivo y fuente** explica su origen; **Evaluación actual** indica
   último corte/revisión compatible. **Sin tutor asignado** conserva responsable null.
3. Solo ADMIN puede **Actualizar alertas** explícitamente. Abrir la pantalla no
   sincroniza. El resultado diferencia casos nuevos, fuentes actualizadas, señales
   bajas, reutilización y matrículas sin evaluación suficiente.

MEDIUM/HIGH actuales pueden motivar un caso. LOW conserva el previo para decisión
humana; no lo resuelve. Repetir la predicción ya procesada no duplica ni reabre el
caso cerrado. Una nueva predicción posterior puede motivar otro caso con historia.

[Captura S6, activo: lista de Alertas](../../tests/evidence/s6-active-final-admin-alerts-1440x900.png).

## Planificar, realizar o cancelar una actividad

Desde un caso activo propio:

1. En **Planificar actividad**, selecciona tipo, objetivo, fecha/hora programadas
   en Lima y notas opcionales. Usa textos de simulación, sin datos personales.
2. Pulsa **Planificar actividad**. Comienza **Planificada**: todavía no cuenta como
   realizada. Objetivo hasta 1000 caracteres; notas hasta 2000.
3. En la actividad, **Registrar actividad** permite editar planificación o cambiar
   a **Realizada**/**Cancelada**. Realizada exige fecha/hora efectiva explícita y
   no futura. La fecha programada no se copia automáticamente como realización.

Realizada/Cancelada son terminales y conservan evidencia. Cancelada no tiene fecha
efectiva ni cuenta como realizada. Puedes terminar una actividad planificada antes
de cerrar el caso mientras el periodo siga abierto y tengas acceso. No se planifican
actividades nuevas en casos cerrados. **Reunión familiar simulada** es un registro
interno: no envía invitaciones o mensajes.

[Captura S6, instalación aislada: formulario de realización](../../tests/evidence/s6-install-verified-integrated-done-form-768x1024.png).

## Concluir o descartar el caso

En **Responsable y estado**, elige transición disponible y **Guardar estado**.
Abierta puede pasar a En revisión, Concluida o Descartada; En revisión puede pasar
a Concluida/Descartada. El cierre exige motivo no vacío hasta 1000 caracteres;
el sistema registra la hora. Un caso cerrado no admite otra edición ni reapertura
automática. Cerrar no completa/cancela sus actividades y no demuestra mejoría.

El historial conserva cambios efectivos. Si el panel reciente está truncado,
consulta el historial paginado del estudiante. Las revisiones/evaluaciones anteriores
no se sobrescriben. [Captura S6, activo: consulta del caso concluido por DIRECTOR](../../tests/evidence/s6-active-final-director-case-768x1024.png).

## Conflicto o resultado incierto

Si otro cambio adelantó la versión, el formulario conserva tu borrador. Pulsa
**Revisar cambios del caso** o **Revisar cambios del registro de actividad**, lee
la información actualizada y marca **He revisado el recurso actualizado** antes
de reenviar. Si falla esa consulta, las escrituras siguen deshabilitadas.

[Captura S6, instalación aislada: conflicto real de versión y borrador conservado](../../tests/evidence/s6-install-verified-integrated-real-version-conflict-390x844.png).

Si una planificación pierde respuesta, puede haberse guardado. Comprueba las
actividades antes de repetir. El intento incierto conserva su clave/contenido
original; repetirlo reutiliza la actividad existente. Cambiar contenido representa
otra intención. Nunca se reintenta automáticamente una escritura incierta.

Los errores muestran referencia de soporte cuando existe. Comunica esa referencia,
sin adjuntar contraseñas, tokens, etiquetas, payloads o artefactos privados.

## Reportes y descarga

1. En **Reportes**, revisa periodo, alcance, generación y rango de cortes. Aplica
   código/riesgo/estado de evaluación/caso. Los agregados cubren todo el conjunto
   filtrado, aunque la tabla esté paginada.
2. Cada fila es una matrícula; casos y actividades se cuentan por estado. Riesgo
   usa evaluadas como denominador. Cero evaluadas significa porcentaje no estimable.
3. Pulsa **Descargar CSV** para obtener todo el conjunto filtrado autorizado, no
   solo la página. Tutor recibe solo su sección; investigador no puede descargar.

CSV `seguimiento-escolar-reporte.csv`: UTF-8 con BOM, 19 columnas, ausencias vacías,
sin notas/motivos libres/etiquetas o ML privado. Protección de fórmulas/controles en
la exportación no modifica DB. El mensaje confirma recepción y solicitud de
descarga, no que una persona abrió/guardó el archivo. Fallo JSON no genera un CSV
aparente. [Captura S6, activo: Reportes DIRECTOR](../../tests/evidence/s6-active-final-director-reports-1440x900.png).

## Teclado y pantallas pequeñas

Tab/Shift+Tab recorren controles; Enter activa acciones; Escape cierra el menú
móvil. **Ir al contenido** salta la navegación. Tablas anchas se desplazan dentro
de su región; usa el mensaje de desplazamiento. Riesgo/estado incluyen texto,
símbolo y color. **Ir al historial** salta al panel y mueve el foco; su paginación
lleva al encabezado de los eventos, sin volver a recorrer todo el detalle largo.
[Captura S6, activo: historial largo TUTOR en móvil](../../tests/evidence/s6-active-final-tutor-student-history-long-390x844.png).
El historial usa páginas; no exige cargar todos sus eventos. Casos cerrados y
actividades terminales muestran su evidencia, sin formularios nuevos inaplicables.
Un borrador de conflicto permanece visible para revisarlo, con la escritura bloqueada
si la versión/capacidad actual no admite ese cambio.

La revisión documentada de tres tamaños no es una certificación completa de
accesibilidad o lector de pantalla. Las correcciones y capturas S6 se registran
con su evidencia real; estas capturas no equivalen a una auditoría completa.
