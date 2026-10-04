# Manual de uso — Seguimiento Escolar, S4

> Operación vigente S6: consultar [instalación Windows](Manual_Instalacion_Windows.md) y [uso final](Manual_Uso_Final.md). Los comandos históricos `infra/study.py` de este documento ahora requieren `--target` explícito y ADMIN o perfil privado. Alembic vigente: `0004_followup`. Este manual conserva el alcance y las evidencias de su iteración.

La aplicación permite consultar e importar información del **Estudio con datos
sintéticos** y solicitar estimaciones de su modelo. Los registros y resultados
no corresponden a estudiantes reales. El procesamiento REAL permanece bloqueado.
Comparar modelos o ejecutar una estimación en este estudio no demuestra eficacia
escolar ni valida la tesis.

Abre [Seguimiento Escolar local](http://localhost:15173/). Usa tu cuenta existente;
no se crean cuentas ni registros al entrar. Las comprobaciones y capturas de S4 se
documentan por separado en su cierre y matriz de evidencia.

## Acceso y permisos

Ingresa tu correo y contraseña en **Iniciar sesión**. No pegues contraseñas en
comandos, documentos o capturas. Si utilizas las cuentas de revisión S2.2, conserva
sus entradas privadas de Windows; no ejecutes nuevamente su creación.

| Rol | Qué puede consultar | Acciones disponibles |
|---|---|---|
| Administrador | Inicio, contexto autorizado, estudiantes, detalle, historial y modelos | Importar el CSV registrado y evaluar un periodo sintético compatible cuando el servidor lo permita |
| Tutor | Inicio y estudiantes de sus secciones autorizadas, con detalle e historial | Consulta; sin importación ni evaluación administrativa |
| Directivo | Inicio y estudiantes del alcance autorizado, con detalle e historial | Consulta; sin importación ni evaluación administrativa |
| Investigador | Inicio de alcance limitado y estado general del estudio | Consultar el alcance y cerrar sesión; sin contexto escolar, estudiantes, Datos o Modelos |

La aplicación verifica permisos también en el servidor. Una dirección escrita
manualmente no concede acceso. Un recurso inexistente o fuera de tu alcance muestra
un estado seguro sin revelar información de otras secciones.

Usa **Cerrar sesión** al terminar. Si la sesión caduca, vuelve al acceso; la aplicación
limpia la información de esa sesión. No se guardan credenciales ni registros escolares
en localStorage.

## Inicio, navegación y contexto

En escritorio, usa el menú lateral. En una pantalla pequeña, abre **Abrir menú**;
puedes cerrar el menú con Escape y seguir usando el teclado. El foco visible indica
dónde estás. Atrás, adelante y recarga permiten volver a rutas de consulta estables.

Las entradas principales son Inicio, Estudiantes, Alertas, Datos y Reportes. Datos
y la entrada secundaria Modelos son administrativas. **Alertas y Reportes siguen
pendientes de S5**: no se ofrecen acciones de gestión, intervención o exportación
de reportes en estas pantallas.

Para consultar información:

1. Selecciona **Periodo de consulta** entre los que devuelve el servidor.
2. Elige una **Sección autorizada** o mantén **Todas las autorizadas**.
3. Abre Estudiantes o una acción de orientación disponible en Inicio.

Cambiar periodo reinicia la sección incompatible y los filtros dependientes.
El tutor recibe únicamente sus secciones; no se descarga un listado global para
filtrarlo después. Si no hay periodos o secciones, la pantalla indica el estado
vacío y orienta a consultar al administrador. No inventa un contexto.

El aviso del estudio y la disponibilidad de acciones provienen del servidor.
Si no se puede consultar ese estado, las acciones sensibles permanecen deshabilitadas
hasta **Volver a intentar** o **Volver a comprobar**. Un estado general disponible
no garantiza que cualquier periodo sea compatible con el modelo activo.

## Estudiantes: lista, filtros y detalle

En Estudiantes, compara código sintético, grado/sección, promedio, asistencia,
último corte, estado de evaluación y riesgo estimado. Los códigos no son nombres
de personas reales.

Puedes buscar un código de hasta 40 caracteres, filtrar riesgo bajo/medio/alto,
ordenar por código, riesgo mayor o corte más reciente y elegir registros por página.
Pulsa **Aplicar filtros**. **Limpiar filtros** recupera la consulta sin esos filtros.
La paginación y el total vienen del servidor; el total de una página no se presenta
como un indicador global del colegio.

| Estado o valor | Cómo interpretarlo |
|---|---|
| Sin dato | La medición está ausente; no equivale a cero |
| Sin evaluar | El corte actual todavía no tiene una predicción vigente |
| Datos insuficientes | Faltan variables necesarias para estimar; se conserva sin riesgo inventado |
| Evaluado | Existe una predicción válida para el corte indicado |
| Bajo, Medio o Alto | Clase estimada sobre datos sintéticos, identificada por texto, icono y color |

Abre el código para consultar contexto, datos observados, ventana, corte, objetivo,
revisión y última evaluación. **Observación** y **estimación** son distintas: una
predicción anterior no evalúa automáticamente una nueva revisión. Sin una predicción
válida, el detalle conserva el estado pendiente o de datos insuficientes.

El historial muestra eventos persistidos y dispone de paginación. Usa **Consultar
evaluación** para ver una predicción del historial y **Cerrar detalle** para volver
a sus eventos. Los resultados antiguos conservan su fecha y corte; no sustituyen la
evaluación vigente. El seguimiento existente puede consultarse, pero su edición y
creación corresponden a S5.

Las horas se muestran en America/Lima. Las fechas de inicio de ventana y objetivo
conservan su día. Una probabilidad ausente o no calibrada no se presenta como un
porcentaje de confianza; los porcentajes de asistencia y actividades son mediciones.

## Datos: conseguir el archivo registrado

Solo ADMIN puede importar. Esta versión acepta el **CSV exacto del generador local
registrado**, con su periodo y hash verificados por el servidor. Un nombre de archivo,
una etiqueta SYNTHETIC o una plantilla completada manualmente no acreditan procedencia.

Para seleccionar desde Windows el CSV del estudio existente, ejecuta en PowerShell,
desde la raíz del proyecto:

```powershell
$directorioEstudio = Join-Path ([System.IO.Path]::GetTempPath()) 'SeguimientoEscolar-S4'
New-Item -ItemType Directory -Path $directorioEstudio -Force | Out-Null
$archivoEstudio = Join-Path $directorioEstudio 'estudio-sintetico.csv'
py -3.12 infra/study.py export-csv --admin-credential ADMIN --study-id e3a2d28b-2f23-56ae-878c-1a8f4a257e7e --output $archivoEstudio
Get-FileHash -LiteralPath $archivoEstudio -Algorithm SHA256
```

La exportación usa la credencial ADMIN existente de Windows, la autentica en el
servidor y verifica el hash antes de escribir. La salida muestra el nombre del CSV,
su tamaño y `csv_sha256`; el hash de `Get-FileHash` debe coincidir, sin importar
mayúsculas/minúsculas. No imprime contenido, etiquetas futuras o credenciales.

El destino debe ser una ruta absoluta, con carpeta existente, fuera del proyecto y
de cualquier checkout Git. El archivo debe tener un nombre válido con extensión
`.csv`; se rechazan enlaces simbólicos y nombres especiales. **No se sobrescriben archivos**:
si el archivo ya existe, consérvalo y selecciona ese archivo, o usa otro nombre nuevo
para una exportación explícita. La carpeta temporal es local; no la agregues a Git.

Este comando copia únicamente el CSV de entrada ya registrado. **No genera otro
estudio ni vuelve a entrenar el modelo**. No ejecutes generate/compare/register/activate
para diseñar o probar S4 sobre el entorno activo. La exportación local facilita la
selección del archivo y no constituye el módulo Reportes.

## Datos: importar en tres pasos

### 1. Preparar archivo

Comprueba el periodo de destino, pulsa **Seleccionar CSV** y elige el **Archivo CSV
registrado**. El formato
es UTF-8, con máximo 5 MiB, hasta 10 000 registros y estas 13 cabeceras en su orden:

```text
student_code,grade,section,cutoff_at,target_date,available_at,window_start,average_grade,attendance_pct,activities_pct,participation_level,behavior_incidents,age_years
```

**Descargar cabeceras CSV** guarda únicamente esa línea, sin filas de estudiantes.
Sirve para conocer el formato; no reemplaza el archivo registrado.

El protocolo `synthetic-study-v1` usa calendario simulado 2025, zona America/Lima,
ventana de 30 días y objetivo 14 días después del corte. Sus escalas son supuestos:
promedio 0–20, asistencia/actividades 0–100 con hasta dos decimales, participación
1/2/3 e incidencias enteras 0–12. Edad y grado son metadatos CSV, no variables del
predictor. Conserva los faltantes vacíos; no añadas etiquetas ni resultados futuros.
Consulta [el protocolo sintético](Manual_Estudio_Sintetico.md) para sus decisiones.

Pulsa **Revisar archivo**. Crear la vista previa no crea estudiantes, matrículas
o cortes. Si la disponibilidad está bloqueada, el periodo es REAL o está cerrado,
la selección y el envío permanecen deshabilitados con un motivo visible.

### 2. Revisar validaciones

Revisa el estado del lote, registros del archivo, válidos y con errores. **Consultar
lote** obtiene su estado guardado del servidor. Los errores indican fila, columna
y lo esperado; no se confirma un lote inválido. Solicita al administrador un CSV
registrado correcto, en lugar de editar manualmente el archivo y perder su identidad.

En un lote **Listo para confirmar**, las cantidades de estudiantes, matrículas y
cortes **previstos** son un plan. Todavía no representan datos confirmados.

Si aparece **Se reutilizó la importación existente**, el servidor devolvió un lote
COMMITTED: el mismo archivo ya se importó en ese periodo. Consultarlo no crea
duplicados y no requiere otra confirmación. Usa **Ver estudiantes del periodo**.

### 3. Confirmar importación

Para un lote READY sin errores, marca la casilla que confirma que revisaste las
validaciones y deseas importar ese archivo sintético en el periodo seleccionado.
Pulsa **Confirmar importación** una vez y espera el resultado.

La solicitud incluye la versión de vista previa observada; el servidor vuelve a
validarla y guarda los registros junto con auditoría en una transacción. Al completarse,
se actualizan las consultas afectadas y se abre el listado del periodo correspondiente.

Cambiar archivo o periodo invalida la vista previa. Ante un **409**, vuelve a
**Revisar archivo de nuevo**: consultar el lote con GET no sustituye una nueva
validación del plan. Si se pierde la respuesta o el servicio devuelve un resultado
incierto, usa **Consultar resultado del lote** antes de volver a confirmar. No hay
reintento automático de escritura; un resultado ya confirmado se reutiliza.

## Modelos y evaluación sintética

ADMIN puede consultar Modelos y abrir su detalle. Se muestran únicamente campos
públicos: algoritmo, versión, estado técnico, uso activo, origen, fecha de registro
y versiones de esquema/criterio disponibles. **Aprobado para simulación** no significa
validado para alumnos reales. La pantalla no publica métricas de entrenamiento,
particiones, archivos privados o controles de entrenar y activar.

Para solicitar una estimación:

1. Selecciona el periodo sintético autorizado y abre Modelos.
2. En **Evaluar periodo**, conserva **Instante actual** y pulsa **Evaluar ahora**,
   cuando el servidor indique disponibilidad.
3. Revisa cortes seleccionados, evaluaciones nuevas, reutilizadas y abstenciones.
   Puedes consultar los motivos y abrir **Consultar estudiantes**.

**Instante actual** se envía a la API como UTC. Si eliges **Elegir fecha y hora
(America/Lima)**, escribe una hora de Lima; la pantalla la interpreta como UTC−05:00
y la convierte a UTC, aunque Windows use otra zona horaria. No se admiten fechas
futuras. Una hora anterior puede carecer de cortes o del modelo disponible en ese
instante y el servidor conserva ese límite.

El calendario de las observaciones es 2025, pero su incorporación y la creación
del modelo ocurrieron después. No selecciones septiembre de 2025 automáticamente
como instante operativo ni retrofeches registros para obtener un resultado.

Se usa la última revisión disponible hasta el instante solicitado y el modelo activo
compatible. Repetir la ejecución reutiliza predicciones existentes del mismo corte/modelo.
Las abstenciones permanecen sin estimación; nunca significan riesgo bajo. Ante modelo
no disponible, incompatibilidad o periodo bloqueado, revisa el motivo y consulta al
administrador. Si se pierde la respuesta, consulta los registros antes de repetir.

## Mensajes y ayuda

La interfaz distingue carga, vacío, ausencia de resultados con filtros, bloqueo,
error y éxito. Usa la opción de reintento de una **consulta** cuando corresponda;
una escritura requiere una nueva acción explícita. Si se alcanzó un límite de
solicitudes, espera antes de continuar; no desactives ese límite.

Al pedir ayuda, comunica la referencia de soporte que muestra el error sanitizado.
No adjuntes contraseñas, cookies, tokens CSRF, archivos privados de modelos o etiquetas.
Si cambias de cuenta, cierra primero la sesión para que contexto y consultas anteriores
se limpien.

S4 no habilita procesamiento institucional, gestión de alertas/intervenciones,
reportes ni cambios de metodología. Esas dependencias y la revisión académica se
conservan en sus documentos correspondientes.

## Hora del sistema

Evaluar ahora usa la hora observada de la API local (cabecera HTTP Date) más el
tiempo transcurrido monótono. La precisión es de segundos; no depende del reloj ni
la zona del anfitrión Windows. Si esa referencia no se puede consultar, se muestra
un aviso para actualizar la vista o elegir fecha/hora en Lima. La fecha manual
se conserva como solicitud y el servidor sigue rechazando instantes futuros.
