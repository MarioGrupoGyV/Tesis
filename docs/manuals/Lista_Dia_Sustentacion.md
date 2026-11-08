# Lista para el ensayo general y el día de la sustentación

Sistema único desde el 2026-11-08 ([ADR 016](../adr/016-grupo-pruebas-en-la-principal.md)): `riesgo-escolar`, <http://localhost:15173>, con dos conjuntos separados:
- **`REAL-2026`**: los 60 estudiantes reales, **cerrado** (nadie lo puede modificar). Se ve en **Estudio real**, Indicadores y Modelos ([ADR 015](../adr/015-conjunto-real-cerrado.md)).
- **`PRUEBAS`**: grupo de demostración (rótulo «Registro de demostración, no es dato del colegio»), con 60 estudiantes sintéticos de base (`SYN-…`). Ahí se registra
  el estudiante nuevo en vivo y lo evalúa la copia del SVM del estudio real.

`real-tesis` (<http://localhost:5173>) es la copia de referencia de la corrida real: úsala solo para comparar, no para presentar. Guion: [Guion_Demo_Manual.md](Guion_Demo_Manual.md).
Preparación previa: [Procedimiento_Preparar_Activa.md](Procedimiento_Preparar_Activa.md). **No hace falta internet** para nada de esto.

## El día anterior (ensayo general, con tiempo)

- [ ] Docker Desktop encendido. En la raíz del repositorio: `docker compose ps` → `api`, `web` y `db` *healthy*.
- [ ] Abrir <http://localhost:15173> e iniciar sesión con tu ADMIN.
- [ ] **Estudio real** → «Conjunto cerrado» y «60 de 60 estudiantes». Si dijera «Conjunto abierto», ciérralo con **Cerrar conjunto**.
- [ ] **Indicadores → REAL-2026 → B1/B2**: detección validada 86,2 % ± 1,6 (B1) y 100 % ± 0 (B2) del SVM; PDER «en muestra» 100 %; 40 alertas.
- [ ] **Modelos**: activa «SVM del estudio real (copia de demostración)», con estado «Copia de demostración (periodo PRUEBAS)».
- [ ] (Opcional) Ensayo de la parte B en `PRUEBAS` con códigos de ensayo (`ENSAYO-ALTO`, `ENSAYO-MEDIO`, `ENSAYO-BAJO`). **Quedan registrados en `PRUEBAS`**: los
  estudiantes no se pueden borrar. Resultado esperado: Alto y Medio con caso, Bajo sin caso, y «Modelo: SVM del estudio real» junto al resultado.
- [ ] Hacer un **respaldo del día** (`backup_restore.py backup`) y verificarlo (`verify`). Anotar el nombre del paquete.
- [ ] Revisar que las **capturas del plan B** abren (`tests\evidence\mejoras-09-e2e-*`, `mejoras-09-principal-*` y `mejoras-10-*`).
- [ ] Equipo: batería al 100 % y cargador, modo «no suspender», notificaciones silenciadas, zoom del navegador al 100 %, una sola sesión del navegador, proyector probado.

## El día, 30 minutos antes

- [ ] `docker compose ps` → `api`, `web` y `db` *healthy*.
- [ ] Sesión iniciada en 15173 con tu ADMIN.
- [ ] La demostración usa `DEMO-ALTO`, `DEMO-MEDIO` y `DEMO-BAJO`: confirmar en **Estudiantes → `PRUEBAS · 2025`** que **no existen todavía**. Si existen, añadir `-2`.
- [ ] Capturas del plan B abiertas en una ventana aparte, sin datos por alumno.
- [ ] Este guion impreso o en una segunda pantalla.

## Qué NO abrir ni mostrar

- **Fichas de estudiantes de `REAL-2026`** (si algún día se cargan los nombres, solo se ven en la ficha). En «Estudio real» se ven códigos reales: mostrar el resumen, sin abrir fichas.
- La carpeta `%LOCALAPPDATA%\SeguimientoEscolar\ResultadosReales` (CSV por alumno, informes completos) y `ConversionExcelReal`.
- La carpeta de respaldos `Backups` y cualquier copia restaurada con datos reales (`restore-check`): contienen datos de menores.
- Credenciales: no proyectar el Administrador de credenciales ni el terminal con los comandos del procedimiento.

## Si algo falla durante la sustentación

1. Mantener la calma y pasar al **plan B** (capturas revisadas del mismo recorrido). Decirlo con naturalidad: «lo vemos en las capturas del ensayo».
2. Error 5xx o sin respuesta: `docker compose ps`; reiniciar solo `api` y `web` con `docker compose restart api web`. Nunca `down -v` ni detener la base.
3. «Modelo no disponible» al evaluar: el estudiante no está en `PRUEBAS` (cambiar el periodo de consulta) o la copia está apagada (el `.env` debe tener
   `DEMO_REAL_MODEL_COPY=true`; después `docker compose up -d --no-deps --wait api`).

## Después

- [ ] Conservar el último respaldo verificado. Están protegidos con DPAPI: solo se abren con tu usuario de Windows en este equipo; copiarlos a otro equipo no permite restaurarlos allí.
