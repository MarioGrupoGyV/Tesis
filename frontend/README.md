# Frontend S1: acceso y contexto DEMO

React, TypeScript, Vite y Tailwind usan las versiones y el lock de S0. La web de
S1 permite iniciar sesión, recuperar una sesión existente, consultar periodos y
secciones autorizadas y cerrar sesión. Todas las respuestas proceden de la API.
La marca DEMO identifica las cuentas y el contexto sintéticos. Los módulos de
estudiantes, importación, predicción, seguimiento y reportes esperan sus sprints.

Desde la raíz del repositorio:

```powershell
npm ci
npm run generate:api --workspace frontend
npm run dev --workspace frontend
```

Vite escucha en `http://localhost:5173` y envía `/api/v1` a
`http://localhost:8000`. En Compose, `API_PROXY_TARGET=http://api:8000` permite el
mismo origen del navegador. Esa variable configura el servidor Vite y nunca
contiene secretos ni se usa como credencial del navegador.

```powershell
npm run typecheck --workspace frontend
npm run build --workspace frontend
```

`src/lib/api.generated.d.ts` se genera desde OpenAPI 0.1.1 y el cliente usa sus
esquemas. Las cookies se envían con `credentials: include`; la sesión permanece
en una cookie HttpOnly gestionada por el servidor. CSRF se conserva solo en
memoria, se recupera tras `me` al recargar y se envía en el encabezado del logout.
No se almacenan tokens en localStorage ni se fijan contraseñas en el frontend.

Se distinguen carga, ausencia de contexto, error y éxito. El servidor determina
los permisos; el rol mostrado es información recibida de la sesión. El selector
de periodos no habilita accesos por su cuenta. Las fechas de calendario se muestran
con zona America/Lima.

El build solo comprueba compilación. Las comprobaciones de conexión y capturas de
la aplicación ejecutada se registran en `docs/planning/Estado_Sprint_1.md`.

La captura S1 se reproduce desde la raíz con `node infra/capture_s1.mjs`, después
de arrancar y sembrar el contexto demo. Usa Chromium de Playwright y lee las
credenciales del archivo privado `.local/secrets/demo-credentials.json`; las
variables `S1_BASE_URL` y `DEMO_CREDENTIALS_FILE` permiten otras ubicaciones.
Guarda login vacío y contexto real de tutor en 1440 × 900, 768 × 1024 y 390 × 844,
con capturas completas adicionales cuando existe desplazamiento vertical.
Verifica etiquetas, foco por teclado, alcance de sección, ausencia de desbordamiento
horizontal, almacenamiento del navegador vacío y cierre con revocación. El informe
sanitizado queda en `tests/evidence/s1-ui-checks.json`. La revisión visual de esas
capturas se consigna por separado en el cierre; el script no sustituye esa revisión.
