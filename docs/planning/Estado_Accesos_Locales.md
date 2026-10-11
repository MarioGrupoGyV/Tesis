# Accesos locales vigentes

Fecha: 2026-10-11 (America/Lima). Destino: instalación activa `riesgo-escolar`,
base `riesgo_escolar`, acceso `http://localhost:15173`.

El usuario solicitó reemplazar los cuatro usuarios anteriores y utilizar
contraseñas más cortas y fáciles. Las claves foráneas de auditoría, sesiones,
importaciones, modelos, estudios, secciones, alertas e intervenciones requieren
conservar las identidades existentes. Se sustituyeron correo, nombre y contraseña
de cada acceso, conservando sus UUID, roles y asignaciones; no se eliminaron filas
históricas ni se crearon cuentas duplicadas. Esta autorización explícita sustituye
la obligación anterior de mantener los valores originales de las credenciales S2.2.

| Rol | Correo vigente |
| --- | --- |
| ADMIN | admin@example.com |
| TUTOR | tutor@example.com |
| DIRECTOR | director@example.com |
| RESEARCHER | investigador@example.com |

Las cuatro contraseñas son distintas, tienen 13 caracteres y combinan dos palabras
cortas con tres números. Se conserva el mínimo de 12 caracteres del validador y el
hash Argon2. No hay semillas ni contraseñas predeterminadas de arranque. Las entradas
`SeguimientoEscolar/S2.2/<ROL>` del usuario Windows ahora contienen los accesos
vigentes. Para consultar uno desde PowerShell en la raíz:

```powershell
py -3.12 infra/windows_credentials.py ADMIN
```

Elegir TUTOR, DIRECTOR o RESEARCHER para los otros accesos. El visor permite mostrar
la contraseña localmente sin imprimirla ni escribirla en texto plano.

La operación explícita se ejecutó con `.venv-s1/Scripts/python.exe` mediante el
script local `.local/replace_local_access.py`, usando un descriptor ACTIVE nuevo,
la identidad PostgreSQL `riesgo_app`, autenticación del administrador existente,
locks y una transacción. Se revocaron cinco sesiones y se añadieron nueve eventos
de auditoría en esa transacción. Las contraseñas anteriores ya no verifican.
Las doce tablas del estudio ajenas a acceso/auditoría conservaron filas y hashes.

Antes del cambio se guardaron los valores necesarios para recuperar los accesos
en un respaldo DPAPI privado y se comprobó descifrado exacto. Este archivo respalda
el cambio de accesos; no constituye un respaldo completo de la instalación S6:

`%LOCALAPPDATA%/SeguimientoEscolar/Backups/access-replacement-ed56ae87-0678-45f0-902d-8cddbd9e9758.access-dpapi`.

El informe público, sin contraseñas ni hashes de contraseña, está en el mismo
directorio: `access-replacement-ed56ae87-0678-45f0-902d-8cddbd9e9758.json`.
Contiene identidades, fingerprints y resultados de la verificación API por rol.
La primera comprobación de `/auth/me` usó por error el campo `email`, ausente en
ese contrato; se corrigió para comprobar UUID y rol. La comprobación final exige
login 200, sesión 200 con identidad/rol correctos y logout 204 para cada cuenta.
Las pruebas generan sus propios eventos de autenticación, adicionales a los nueve
eventos del reemplazo.

No se ejecutó restauración, entrenamiento ni modificación de datos escolares.
Los informes históricos S2.2/S6 describen sus ejecuciones anteriores; sus correos
y credenciales no sustituyen este estado vigente. Una renovación futura requiere
otra instrucción explícita del usuario.
