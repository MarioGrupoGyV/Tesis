# Frontend — Seguimiento Escolar

Interfaz S6 con estudiantes, importación, modelos, alertas y reportes del estudio
sintético registrado. Sesión HttpOnly, CSRF en memoria, sin tokens en localStorage.

Tipos generados desde el contrato vigente `docs/planning/Contrato_API.yaml`:
`npm run generate:api --workspace frontend`.
Build: `npm run build --workspace frontend`.
No cambiar dependencias ni package-lock.

## Desarrollo con la instalación integrada

Desde PowerShell en la raíz, con la instalación Docker existente en ejecución:

```powershell
npm run dev --workspace frontend
```

Abre `http://localhost:5173`. Por defecto Vite envía `/api/v1` a
`http://localhost:18000`, la API integrada que conserva los archivos privados de
importaciones, estudio y modelos en sus volúmenes. La web integrada continúa en
`http://localhost:15173`. Ambas usan la misma API y las cuentas existentes.

El `.env` de la raíz debe incluir `http://localhost:5173` y
`http://127.0.0.1:5173` en `ALLOWED_ORIGINS`, además de los orígenes de la web
integrada. Si se actualiza esa variable, aplicar solo la configuración de la API:

```powershell
docker compose up -d --no-deps --no-build --wait api
```

Vite conserva Host/Origin y la API sigue verificando Origin y CSRF. No crear
almacenes vacíos ni copiar los volúmenes a Windows para suplir archivos faltantes.
Si la API usa otro puerto, declarar `API_PROXY_TARGET` explícitamente en la sesión
PowerShell o en `frontend/.env.local` y reiniciar Vite.

Para diagnosticar cambios de backend con Uvicorn nativo en `8000`, elegirlo
explícitamente antes de arrancar Vite:

```powershell
$env:API_PROXY_TARGET = 'http://localhost:8000'
npm run dev --workspace frontend
```

Esa API de diagnóstico no tiene los volúmenes privados del entorno integrado;
no acredita el recorrido del estudio. Un resumen que necesita el estudio devuelve
`503 STUDY_STORAGE_UNAVAILABLE` cuando ese almacenamiento no está configurado.
Para volver al destino integrado, quitar la variable y reiniciar Vite:

```powershell
Remove-Item Env:API_PROXY_TARGET -ErrorAction SilentlyContinue
npm run dev --workspace frontend
```

Pruebas desde PowerShell: `py -3.12 infra/test_browser.py`.
Usa PostgreSQL aislado y cuenta efímera en puerto 15174; no la aplicación activa.
Valida teclado, login/logout, revocación y contexto vacío en 1440×900, 768×1024
y 390×844. Capturas sanitizadas en tests/evidence/s2-1-*.png.
