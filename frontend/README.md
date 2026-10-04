# Frontend — acceso y contexto

Seguimiento Escolar sin identidad, cuentas o textos de demostración. Estados de
acceso, error y contexto vacío. S4 completará las pantallas; S3 implementará ML.
Sesión HttpOnly, CSRF en memoria, sin tokens en localStorage.

Tipos de Contrato_API.yaml 0.2.0:
`npm run generate:api --workspace frontend`.
Build: `npm run build --workspace frontend`.
No cambiar dependencias ni package-lock.

Pruebas desde PowerShell: `py -3.12 infra/test_browser.py`.
Usa PostgreSQL aislado y cuenta efímera en puerto 15174; no la aplicación activa.
Valida teclado, login/logout, revocación y contexto vacío en 1440×900, 768×1024
y 390×844. Capturas sanitizadas en tests/evidence/s2-1-*.png.
