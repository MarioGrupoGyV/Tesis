# Operación desde PowerShell

El [README raíz](../../README.md) contiene preparación, arranque, migración,
reinicio, parada, pruebas y primer administrador.

`py -3.12 infra/manage.py bootstrap-admin` solicita correo, nombre y contraseña
sin eco. No hay credenciales predeterminadas ni archivo de cuentas.
`py -3.12 infra/manage.py configure` permite crear contexto con valores ingresados
por un administrador autenticado; no habilita procesamiento.

La importación institucional sigue bloqueada. No ejecutar recorridos de carga con
CSV inventados en la aplicación activa. El manual anterior se conserva en
history/Importacion_S2.md exclusivamente como historia.
