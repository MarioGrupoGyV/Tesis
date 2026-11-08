# ADR 015: sección «Estudio real» de solo lectura y conjunto real cerrado

- Estado: aceptado por el usuario (Bloque 10 de la fase de mejoras, [ADR 011](011-fase-mejoras-tesis.md)); 2026-11-08.
- Relacionado: [ADR 013](013-riesgo-v2-sin-participacion.md) (RIESGO_V2) y [ADR 014](014-copia-demo-svm-real.md) (demo-vivo).

## Contexto

Para la sustentación el usuario quiere ver los 60 estudiantes reales, sus datos y sus resultados en un apartado propio, sin confundirlos con los
estudiantes que se registran en vivo en `DEMO-VIVO`, y que ese conjunto no se pueda modificar mientras esté cerrado. También pidió retirar cinco
avisos de pantalla.

## Decisión

1. **Sección «Estudio real»** (`/estudio-real`, navegación principal; ADMIN, TUTOR y DIRECTOR, no RESEARCHER). Muestra solo periodos `REAL`. Por estudiante
   y bimestre: promedio, asistencia, actividades e incidencias de la revisión de mitad de bimestre que usó la referencia; el nivel que estimó el modelo
   REAL activo sobre ese corte; el nivel de referencia RIESGO_V2 del fin del bimestre; y el estado del último caso. Resumen por bimestre con los
   conteos Bajo/Medio/Alto del modelo y de la referencia. Solo códigos; el código abre la ficha.
2. **Consulta de solo lectura** `GET /real-set` (contrato 0.16.0, 55 operaciones). No escribe, no evalúa y no audita. Un periodo que no es `REAL`
   responde 404, igual que uno inexistente. TUTOR solo ve sus secciones; RESEARCHER recibe 403.
3. **Cerrado = periodo bloqueado.** Se reutiliza `academic_periods.is_locked`, que el servidor ya hace cumplir en registro manual, mediciones, importación,
   evaluación por estudiante y por lote, protocolo/estudio REAL y seguimiento (`PERIOD_LOCKED`, 409). La sección muestra «Conjunto cerrado» o
   «Conjunto abierto» y, para ADMIN, un botón «Cerrar conjunto» con confirmación. Reabrir solo desde Estudiantes → Periodos. No hay regla nueva de
   base de datos ni migración.
4. **Avisos retirados** a pedido del usuario: el aviso REAL «Datos reales locales — análisis exploratorio, no demuestra eficacia escolar» (Inicio,
   Alertas, ficha del caso, Reportes y Protocolo), la nota de Alertas sobre el cierre de casos, el párrafo de Indicadores con la fecha de cálculo,
   el fin del bimestre y la ventana, el aviso de alertas retrospectivas y la nota bajo la tabla de Estudiantes. La marca «simulación retrospectiva»
   de cada alerta y la etiqueta «Exploratorio local» de los indicadores se conservan.

## Consecuencias

- Las reglas de `AGENTS.md` que pedían mostrar la fecha de actualización junto a los indicadores y el aviso exploratorio en pantalla ceden ante la
  instrucción explícita del usuario para estas pantallas. Los manuales conservan esas aclaraciones.
- Con `REAL-2026` cerrado no se pueden concluir ni editar sus casos ni volver a ejecutar su estudio: es el efecto buscado. Reabrir es un cambio
  explícito del administrador.
- Pruebas: `backend/tests/test_b14_real_set.py` (niveles iguales a la predicción del modelo activo, sin escrituras al consultar, 404 para SYNTHETIC,
  alcance por rol y rechazo de escrituras tras cerrar) y `tests/e2e/estudio-real-b10.spec.ts` (pantalla real, avisos ausentes).

## Despliegue (2026-11-08)

- Principal `riesgo-escolar`: respaldo previo `s6-20261108T074547Z-2273e86fb7b9` (COMPROBADO); imágenes API `b10` y web `b10a`; `REAL-2026` cerrado por API con ADMIN;
  respaldo con el cierre `s6-20261108T080502Z-198c447fd148` (COMPROBADO). Interruptor de la copia de demostración apagado.
- `demo-vivo` recreada desde ese respaldo: `s6-restore-a8b11e5e230d` (15174, `b10a`, descriptor `S6\demo-vivo-v10a-<fecha>.json`, perfil `demo-vivo-v10a`), con la
  copia del SVM (misma huella `45fb6c6b…38261`) y `REAL-2026` cerrado. `DEMO-VIVO` sin estudiantes de ensayo.
- 2026-11-08, después: `demo-vivo` se eliminó a pedido del usuario; queda solo la principal con `REAL-2026` cerrado y la copia del SVM apagada.
- En ambas: «Estudio real» con 60 estudiantes, 40 con caso; el modelo marca Medio/Alto a 38 en B1 y 37 en B2. Suite del servidor: 564 aprobadas, 11 omitidas, 0 fallidas.
