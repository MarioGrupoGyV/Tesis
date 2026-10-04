# Importación DEMO por API — S2

La interfaz de importación se completará en S4. Este recorrido usa **PowerShell 7**
(`Invoke-RestMethod -Form`) y los servicios preparados mediante el README raíz.
Solo introducir muestras sintéticas; no archivos de estudiantes reales.

## 1. Elegir periodo y archivo

Desde la raíz del proyecto, sin imprimir contraseñas ni tokens:

```powershell
$base = 'http://localhost:15173/api/v1'
$credentials = Get-Content .local/secrets/demo-credentials.json -Raw | ConvertFrom-Json
$login = Invoke-RestMethod -Method Post -Uri "$base/auth/login" -SessionVariable session -Headers @{Origin='http://localhost:15173'} -ContentType 'application/json' -Body (@{email=$credentials.admin.email; password=$credentials.admin.password} | ConvertTo-Json)
$csrf = @{'X-CSRF-Token'=$login.csrf_token}
$periods = Invoke-RestMethod -Uri "$base/periods" -WebSession $session
$period = $periods | Where-Object code -eq 'DEMO-2026' | Select-Object -First 1
$preview = Invoke-RestMethod -Method Post -Uri "$base/imports/preview" -WebSession $session -Headers $csrf -Form @{period_id=$period.id; file=Get-Item tests/fixtures/synthetic/valid.csv}
```

Las muestras usan el periodo y secciones de la semilla S1: valid.csv crea dos
estudiantes sintéticos; correction.csv cambia un corte de 1/A y crea revisión;
invalid.csv contiene errores de escala, precisión, fechas y duplicados;
invalid_headers.csv tiene una columna no permitida. El periodo proviene de la
solicitud, nunca del archivo. Debe ser DEMO y estar abierto.

## 2. Revisar

```powershell
$preview | Select-Object id,status,preview_version,total_rows,valid_rows,invalid_rows,planned_students,planned_enrollments,planned_snapshots
$preview.errors | Format-Table row,column,code,message
Invoke-RestMethod -Uri "$base/imports/$($preview.id)" -WebSession $session
```

Solo READY puede confirmarse. FAILED conserva errores sin crear registros
académicos. Un error estructural devuelve 422 sin lote. La primera fila de datos
es la fila 2; las cabeceras son la fila 1. Reenviar el mismo archivo/periodo
reutiliza el lote y refresca su versión mientras no esté confirmado.

## 3. Confirmar y consultar

```powershell
if ($preview.status -eq 'READY') {
    $result = Invoke-RestMethod -Method Post -Uri "$base/imports/$($preview.id)/commit" -WebSession $session -Headers $csrf -ContentType 'application/json' -Body (@{expected_preview_version=$preview.preview_version} | ConvertTo-Json)
    $result
}
$students = Invoke-RestMethod -Uri "$base/students?period_id=$($period.id)&page=1&page_size=20&sort=anon_code" -WebSession $session
$students.items
$student = $students.items | Select-Object -First 1
Invoke-RestMethod -Uri "$base/students/$($student.id)?period_id=$($period.id)" -WebSession $session
Invoke-RestMethod -Uri "$base/students/$($student.id)/timeline?period_id=$($period.id)" -WebSession $session
Invoke-RestMethod -Method Post -Uri "$base/auth/logout" -WebSession $session -Headers $csrf
```

Un 409 IMPORT_PREVIEW_STALE exige reenviar el archivo, revisar la nueva vista
previa y confirmar su versión. No se debe confirmar automáticamente tras un
conflicto. Repetir una confirmación correcta reutiliza el resultado sin duplicar.
Mientras S3 no produzca una predicción vigente, el estudiante está pendiente de
evaluación (`NOT_EVALUATED`, riesgo null).

## Formato admitido

CSV UTF-8, coma, máximo 5 MiB/10000 filas, con estas cabeceras exactas y en orden:

```text
student_code,grade,section,cutoff_at,target_date,available_at,window_start,average_grade,attendance_pct,activities_pct,participation_level,behavior_incidents,age_years
```

Código de estudiante ASCII de 3..40 caracteres: empieza con letra o número y
continúa con letras, números, guion o guion bajo. Grado 1..5 y sección del año del
periodo. Instantes RFC3339 con zona; fechas YYYY-MM-DD. Debe cumplirse inicio del
periodo ≤ ventana ≤ día de disponibilidad ≤ día de corte < objetivo ≤ fin del
periodo, usando America/Lima, y disponibilidad no posterior al instante del corte.

Los últimos seis campos permiten vacío (null). Promedio 0..20 y porcentajes
0..100 admiten hasta dos decimales con punto; participación entera 1..3, incidentes
enteros 0..2147483647, edad entera 5..25. No enviar missing_fraction ni riesgo:
el servidor calcula la fracción faltante. Dos filas del mismo estudiante/corte
(aunque expresen otra zona equivalente) son duplicadas e invalidan el lote.

Los CSV privados quedan en import_data, sin URL de descarga. Conservar los dos
volúmenes y secretos al reiniciar; no usar `docker compose down -v`. Para repetir
la comprobación automatizada de API y persistencia, ejecutar `infra/smoke_s2.py`
con el Python de .venv-s1 y sin otros recorridos activos. Ese comando importa las
muestras y recrea los contenedores. Las cuentas TUTOR/DIRECTOR no pueden importar.
