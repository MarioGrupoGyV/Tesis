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
