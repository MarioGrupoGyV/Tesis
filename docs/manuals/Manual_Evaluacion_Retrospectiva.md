# Evaluación retrospectiva local

Actualización S6 del 2026-10-11. El usuario confirma autorización para procesar
localmente el archivo real. La autenticidad institucional sigue sin auditar.
No se modifica el protocolo SYNTHETIC ni se habilita REAL operativo.

## Uso en la aplicación

1. Accede como ADMIN a **Modelos** en la instalación Docker local. El panel
   **Evaluación retrospectiva B1 → B2** está separado de la evaluación sintética.
2. Pulsa **Ejecutar evaluación retrospectiva**. El servidor recibe el paquete ya
   registrado, conserva el Pipeline StandardScaler + SVC exacto, transforma las
   entradas en su orden y evalúa las 60 filas B2 sin fit ni selección nueva.
3. Consulta la fecha real en Lima, métricas, discrepancias y 60 filas numeradas.
   Descarga el reporte específico; no contiene nombres ni códigos del colegio.

El ensayo de entrada parcial recibe promedio de 0 a 20, asistencia y entrega de
0 a 1. No recibe etiquetas, notas finales, participación ni incidencias. Se
exige disponibilidad de cada variable antes o en el corte. El formulario admite
una fecha común en que las tres ya estaban disponibles; la API admite tres
instantes separados con zona horaria. Faltantes y escalas inválidas dan error,
no LOW. El ensayo no persiste un caso ni cuenta como evaluación de toda B2.

Los cortes son **21 de abril de 2026** y **30 de junio de 2026**, a las 00:00
America/Lima, exactamente como compara el script fuente. Las fechas sin zona
del Excel/CSV se interpretan en Lima. La fecha real de ejecución se registra en
UTC y se muestra en Lima; no se fecha la inferencia como abril o junio.

## Registro explícito por PowerShell

Antes de escribir, identifica un descriptor S6 actual del destino y respáldalo
con DPAPI. El registro autentica el ADMIN vigente de Credential Manager; no crea
cuentas ni imprime claves. Solo acepta este ZIP revisado por SHA-256, no uploads
HTTP de joblib, scripts del paquete ni rutas proporcionadas por el navegador.

```powershell
# Desde la raíz; elegir el descriptor actual, nunca uno anterior al build.
$destino = "$env:LOCALAPPDATA\SeguimientoEscolar\S6\active-retrospective-final.json"
$paquete = 'C:\Users\mario\OneDrive\Escritorio\Downloads\Calculos_y_modelo_evaluacion_retrospectiva.zip'
$fuente = 'C:\Users\mario\OneDrive\Escritorio\Downloads\registro_academico_60_estudiantes.xlsx'
$pythonDocumental = 'C:\Users\mario\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
.\backend\.venv\Scripts\python.exe infra/register_retrospective.py --target $destino --package $paquete --source $fuente --document-python $pythonDocumental --evaluate
```

El Python documental es el runtime integrado para lectura de Excel; no es un
nuevo entorno virtual ni sustituye backend/.venv. No se necesita WSL/Bash/Make.
La ruta depende de la instalación: consultar load_workspace_dependencies si cambia.
La auditoría entrega solo hashes y agregados; no copia nombres ni filas del Excel.
El paquete exacto y el certificado agregado se guardan en el volumen privado
`ml_data/retrospective`; al servidor nunca se envía el Excel con nombres.

Un registro repetido reutiliza la autorización/paquete original. Cada evaluación
completa obtiene UUID, fecha real y actor nuevos y conserva el histórico. El
registro y su acción auditada se publican juntos en un sobre HMAC inmutable, con
publicación atómica y sin sobrescritura. No se añaden tablas ni migraciones.
El diario separado se respalda junto con el volumen ML y su clave; las filas de
predicciones/casos del estudio sintético permanecen intactas.

## Interpretación y límites

40 propuestas no significan 40 notificaciones ni 40 intervenciones. Esta ejecución
no envía mensajes, no abre casos operativos y no registra actividades realizadas.
Los contadores cero se refieren a lo generado por esta evaluación; no afirman
que nunca existieron actuaciones anteriores del colegio. Las 120 predicciones y
79 alertas históricas del Excel se conservan en el original y no se importan a DB.

La evaluación temporal usa B2 de los mismos 60 estudiantes, no una cohorte externa.
La selección declarada es por F1 macro en cinco folds B1 (SVM 0,897008 frente a RF
0,843223). La aplicación no reelige con B2, no reproduce el entrenamiento al
arrancar y no mezcla participación/incidencias finales en X. Verifica scaler
media/varianza/n=60 y vectores de soporte contra B1 sin fit.

El artefacto se guardó con scikit-learn 1.8.0; el proyecto conserva 1.9.1. El
resultado entre versiones se identifica **CROSS_VERSION_EXPERIMENTAL** y conserva
las tres advertencias. La coincidencia de estas 60 clases acredita el ensayo
observado, no compatibilidad general ni activación productiva. scikit-learn
[no respalda cargar modelos entre versiones](https://scikit-learn.org/stable/model_persistence.html).

Para sustentar la tesis faltan autorización documental/procedencia institucional,
validación pedagógica del criterio RIESGO_V1 y de su escala, evidencias externas
de que los timestamps reflejan disponibilidad real, y una validación posterior
planificada con población adecuada. No deducir causalidad, eficacia escolar,
alertas históricamente anticipadas ni desempeño de una cohorte nueva.

La auditoría del original comprueba fechas declaradas y transformación, no la
autenticidad de sus fuentes. Los campos posteriores al corte sirven solo para
recalcular la referencia al cierre. Dos promedios finales cambian al redondear
con Decimal HALF_UP; no cambian etiquetas ni predicciones B2.
