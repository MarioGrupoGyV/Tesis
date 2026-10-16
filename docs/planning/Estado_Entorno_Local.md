# Entorno Python local único

Fecha: 2026-10-11 (America/Lima). Solicitud explícita del usuario: mantener un
único entorno virtual local. El entorno vigente es `backend/.venv`.

Se creó de nuevo con Python Windows 3.12.0 y se consolidaron las distribuciones
ya instaladas en S0/S1: 73 paquetes y 24 entradas de consola regeneradas para la
nueva ruta. No se renombró simplemente un entorno existente. Los paquetes
compartidos mantienen sus versiones compatibles; pip conserva 25.2, fijado en
el lock documental. No se descargaron dependencias ni se modificaron versiones
o locks. El script histórico `update_contract.py` se conservó también en
`.local/historical-tools/update_contract_s0.py`.

La revisión automática rechazó el borrado recursivo con el motivo “blocked by
policy”. Como alternativa reversible, los dos entornos anteriores se trasladaron
fuera del repositorio, después de comprobar destinos y detener el Uvicorn que
utilizaba `.venv-s1`:

`%LOCALAPPDATA%/SeguimientoEscolar/EntornosArchivados/consolidacion-20261011-140341/`.

Dentro del proyecto queda solamente `backend/.venv`. Los directorios archivados no son
entornos de trabajo vigentes; las referencias S0/S1 en estados y evidencias
históricos se conservan como registros de ejecuciones pasadas.

Desde una terminal PowerShell en `backend`:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

Desde la raíz, la activación es `.\backend\.venv\Scripts\Activate.ps1`.
README, manual de instalación, manual del estudio, manual ML, backend e infra
utilizan ahora el entorno único en sus instrucciones operativas.

Comprobado durante la consolidación inicial en la raíz:

- `pip.exe check`: sin dependencias rotas, también después del traslado.
- `python -m pytest backend/tests/test_config_local_env.py -q`: cuatro pruebas
  aprobadas; advertencia existente de deprecación httpx/Starlette, sin cambiar locks.
- Importaciones de FastAPI, SQLAlchemy, psycopg, Uvicorn, YAML, pglast, validación
  OpenAPI, pandas, NumPy, SciPy y scikit-learn correctas.
- `infra/check_s0.py`, con prefijo nuevo: 292 comprobaciones aprobadas.
- Activación y resolución de python/pip hacia `.venv`; lanzador uvicorn.exe
  regenerado, arranque con reload y readiness HTTP 200 en puerto de prueba 18080.
- Después de archivar los entornos anteriores, readiness 200 mediante TestClient
  y un único directorio `.venv*` en la raíz.
- Los tres contenedores activos siguen running/healthy.

El mismo día se trasladó el entorno a `backend/.venv` para permitir el comando
solicitado desde `backend`. Se regeneraron la configuración, la activación y las
24 entradas de consola para la nueva ruta. Se conservaron los 73 paquetes y los
hashes de locks. La activación exacta `.\.venv\Scripts\Activate.ps1`, Python
3.12.0, `pip check`, importación de Argon2, readiness 200 mediante TestClient y
las cuatro pruebas de configuración se comprobaron de nuevo tras el traslado.
El inventario adicional queda en `.local/backend-env-relocation-after.json`.

Inventario, scripts, hashes de locks y archivo:
`.local/environment-consolidation-20261011T185907Z.json`.
La evidencia contractual nueva usa el prefijo `s6-env-unico-` en `tests/evidence`.
No se ejecutaron entrenamiento, migraciones, restauración ni un recorrido
integrado de importación/seguimiento/exportación para este cambio. XGBoost CPU y
los archivos privados del estudio permanecen en Docker; esta consolidación no
afirma compatibilidad del runtime ML completo con Windows.

## Corrección del resumen desde el frontend local — 2026-10-15 (Lima)

El usuario reportó `503` en `GET /api/v1/reports/summary` desde
`http://localhost:5173`. Vite apuntaba por defecto al Uvicorn nativo en `8000`:
ese proceso consulta la base existente pero no tiene `ML_STORAGE_DIR` ni los
archivos privados del estudio Docker. El servicio rechazaba correctamente la
lectura con `STUDY_STORAGE_UNAVAILABLE`. No se sustituyó la validación de
procedencia por una consulta sin verificar.

Se cambió el destino predeterminado del proxy Vite a la API integrada en
`http://localhost:18000`. `API_PROXY_TARGET` explícito sigue teniendo prioridad;
el contenedor web conserva su destino explícito `http://api:8000`. Se añadieron
los dos orígenes locales exactos de `5173` a la configuración Docker, conservando
los de `15173`, `changeOrigin: false` y las comprobaciones de Origin/CSRF.
Se aplicó únicamente la configuración de la API; DB, web y volúmenes existentes
no se recrearon. No se copiaron archivos privados a Windows ni se crearon
almacenes alternativos. El Uvicorn nativo continúa siendo un diagnóstico separado,
sin acceso a los volúmenes privados ni acreditación del recorrido completo.

Archivos modificados:

- `frontend/vite.config.ts`: destino integrado por defecto.
- `compose.yaml` y `.env.example`: orígenes explícitos de desarrollo local.
- `.env` privado existente: mismos orígenes, sin cambios de puertos o secretos.
- `frontend/README.md` y `backend/README.md`: operación integrada y selección
  explícita de la API nativa de diagnóstico.
- Este estado y las evidencias enlazadas a continuación.

Comprobado:

- `docker compose up -d --no-deps --no-build --wait api`: API healthy, con los
  volúmenes existentes; sin build de imágenes, migración ni reinicio de la base.
- `npm run build --workspace frontend`: TypeScript y Vite aprobados. El primer
  intento dentro de la restricción de ejecución falló con `spawn EPERM`; el mismo
  comando con ejecución autorizada finalizó correctamente, sin modificar locks.
- Verificación HTTP real en `5173` usando solo ADMIN del almacén Windows, con
  contraseña/cookie/CSRF únicamente en memoria: login `200`, resumen `200`,
  preparación `200`, misma sesión/identidad reconocida en `15173`. Resumen:
  60 matrículas sintéticas, 55 evaluadas, 0 pendientes y 5 con datos insuficientes.
- Sin sesión y después del logout: resumen `401`. Login con origen no autorizado:
  `403 ORIGIN_NOT_ALLOWED`. Logout sin CSRF: `403`; con CSRF: `204`. La sesión
  temporal de comprobación se cerró sin revocar la sesión del navegador del usuario.
- Inicio real recargado en `5173`: resumen visible sin el error. Revisión visual
  en 1440×900, 768×1024 y 390×844; tamaño del navegador restaurado al terminar.
- `git diff --check`: sin errores de whitespace.

Evidencias:

- [Resultados HTTP sanitizados](../../tests/evidence/s6-local-api-summary-fix.json).
- [Inicio en escritorio](../../tests/evidence/s6-local-summary-fix-1440x900.jpg).
- [Inicio en tableta](../../tests/evidence/s6-local-summary-fix-768x1024.jpg).
- [Inicio en móvil](../../tests/evidence/s6-local-summary-fix-390x844.jpg).

Sin incidencias pendientes para el 503 reportado. No se ejecutaron entrenamiento,
inferencia, importación, migraciones, recuperación ni el recorrido completo
importar/evaluar/atender/exportar. Las comprobaciones de acceso añadieron solo los
eventos normales de autenticación. No se modificaron cuentas, observaciones,
predicciones, casos o intervenciones. Dependencia operativa: Docker Desktop y la
API integrada deben estar disponibles; un destino diferente exige declarar
`API_PROXY_TARGET` y sus orígenes de forma explícita. Sin commit ni push.

## Limpieza autorizada de datos y configuración — 2026-10-15 (Lima)

Después del arreglo de conexión, el usuario solicitó vaciar estudiantes y luego
confirmó vaciar también periodos, secciones y modelos, conservando usuarios.
La base operativa está vacía y las cuatro cuentas se comprobaron idénticas.
Se conservan auditoría, accesos y un respaldo DPAPI completo verificado del estado
anterior. Conteos, comandos, archivos y evidencias en
[Estado de limpieza local](Estado_Limpieza_Local.md). No regenerar datos al arrancar.
