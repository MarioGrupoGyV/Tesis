# Operación desde PowerShell

El [README raíz](../../README.md) contiene preparación, arranque, migración,
reinicio, parada, pruebas y primer administrador.

`py -3.12 infra/manage.py bootstrap-admin` solicita correo, nombre y contraseña
sin eco. No hay credenciales predeterminadas ni archivo de cuentas.
`py -3.12 infra/manage.py configure` permite crear contexto con valores ingresados
por un administrador autenticado; no habilita procesamiento institucional.

S3.1 permite el [Estudio con datos sintéticos](Manual_Estudio_Sintetico.md): generación
ADMIN explícita, importación del CSV exacto registrado, comparación, registro y
activación técnica para simulación local. Sus registros no corresponden a estudiantes
reales. Conserva las cuatro cuentas S2.2 y sus credenciales Windows; no repetir bootstrap.

La importación, entrenamiento y activación REAL siguen bloqueados. El generador
registrado es la única procedencia admitida para este estudio; el cliente no puede
habilitarla con un campo de origen. El [manual ML S3](ML_S3.md) describe el núcleo
reutilizado; history/Importacion_S2.md se conserva exclusivamente como historia.
S4–S6 pendientes.
