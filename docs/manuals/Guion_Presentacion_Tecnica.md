# Guion de presentación técnica

Objetivo: mostrar el sistema local de **simulación**, explicar sus controles y
distinguir recuperación, instalación nueva y evaluación escolar pendiente.
No se presenta una tesis validada o eficacia de actividades. La documentación y
resultados del checkout están en [Estado S6](../planning/Estado_Sprint_6.md) y la
[matriz final](Matriz_Trazabilidad_Final.md).

## Preparación del recorrido

Usa la URL y destino identificados por la herramienta, nunca un cambio global
silencioso. Mantén contraseñas/perfiles/CSV/artefactos privados fuera de pantalla.
No abrir claves, dumps, datasets o manifiestos privados durante la presentación.
Conserva las cuentas/modelo del entorno activo y el histórico detenido.

| Destino | Qué demuestra | Acciones permitidas para el guion |
| --- | --- | --- |
| A, instalación nueva S6 | Base/secretos/volúmenes nuevos y recorrido completo | Preparación explícita, primera importación/inferencia UI y actividades simuladas |
| B, restauración S6 | Estado recuperado desde respaldo, sin generador | Consultar y repetir inferencia/sync ya resueltos; sin nuevas actividades ni reentrenamiento |
| C, aplicación activa | Uso del estado existente sin cambios de negocio | Navegar/consultar/exportar; repetición idempotente solo si está expresamente dentro de la revisión |

Para reproducir instalación/configuración/perfil/preparación usa los comandos del
[manual Windows](Manual_Instalacion_Windows.md). Para B usa
[respaldo/restauración](Manual_Respaldo_Restauracion.md). El operador elige su primer
ADMIN mediante bootstrap interactivo; cuentas automáticas exclusivas de pruebas
no se convierten en accesos predeterminados del producto.

## 1. Situar el alcance y entrar

Di: «Esta aplicación integra importación, clasificación y seguimiento de un estudio
generado. No contiene alumnos observados. REAL sigue bloqueado; decisiones y
actividades son simulaciones internas».

Entra con ADMIN sin mostrar la contraseña. Muestra aviso, periodo y secciones.
Explica que los permisos están en servidor y el estado general no equivale a
autorizar procesamiento institucional. En A muestra la aplicación inicialmente
vacía antes de preparar datos. No llamar instalación nueva a una copia del activo.

## 2. Mostrar importación reproducible en A

Preparación ADMIN explícita genera el CSV exacto registrado mediante versión,
configuración y semilla. No ocurre al arrancar. El hash demuestra identidad del
archivo, no que corresponda a datos reales. Explica cinco variables predictoras;
edad/grado son metadatos excluidos del predictor vigente.

En **Datos**: seleccionar CSV → **Revisar archivo** → consultar lote y cantidades →
marcar confirmación → **Confirmar importación**. La **primera** importación de A
debe hacerse realmente por interfaz; no importar antes por API y narrar otra cosa.
En preview hay plan, no estudiantes/cortes confirmados. El commit registra todo
junto con auditoría y puede rechazar estado desactualizado sin escrituras parciales.

Abre **Estudiantes** y aplica filtros/página. Enseña un dato faltante y el historial.
Explica UTC para instantes, días/visualización Lima y revisiones sin sobrescritura.
En B/C omite la escritura de importación: consulta el estado ya recuperado/existente.

## 3. Explicar comparación y modelo

Después del import de A, el operador ejecuta comparación/registro/activación técnica
por comandos ADMIN del manual. Son acciones explícitas, fuera de HTTP. No regenerar
o reentrenar B/C para llenar pantallas. La preparación del recorrido puede hacerse
antes de la exposición, preservando su evidencia y secuencia.

Di: «Dummy es baseline; Random Forest, SVM y XGBoost se comparan con las mismas
particiones por estudiante. Pipeline aprende imputación/codificación/escala solo
en entrenamiento. Selección usa desarrollo; la reserva prefijada queda fuera del
ajuste y elección. Estos resultados dependen del generador».

No cambiar el algoritmo tras consultar reserva ni prometer exactitud. El modelo de
B/C debe seguir siendo el respaldado/existente. La pantalla publica algoritmo,
versión, origen y estado técnico, sin particiones o etiquetas. **Aprobado para
simulación** no significa aprobado por un colegio o asesor.

## 4. Evaluar por interfaz

En **Modelos**, periodo correcto → **Instante actual** → **Evaluar ahora**. En A
debe ser la primera inferencia desde UI, sin resultados creados antes por un runner
API. Muestra nuevas/reutilizadas/abstenciones y seguimiento transaccional.

Di: «Cada matrícula usa su última revisión disponible hasta as_of. Una corrección
nueva queda pendiente. Datos insuficientes no son riesgo bajo. Probabilidades no
calibradas quedan null; no mostramos porcentajes de certeza».

En B/C, una repetición autorizada debe devolver reutilización sin nuevas predicciones,
casos o actividades. No hacer entrenamiento en una petición ni retrofechar as_of al
calendario simulado. La hora actual se consulta al sistema.

## 5. Mostrar seguimiento humano

En **Alertas**, abre un caso y compara fuente frente a evaluación actual. Explica
followup-policy-v1: MEDIUM/HIGH motivan caso; LOW conserva el previo para revisión;
repetir una predicción procesada no reabre un caso cerrado.

Solo en A: entra como tutor asignado, planifica actividades de simulación, registra
una realizada con fecha efectiva y otra cancelada, concluye o descarta el caso con
motivo. Muestra estados/versiones/historial. Explica que PLANNED no cuenta como
DONE y cerrar no termina actividades ni demuestra mejora académica. Una reunión
familiar simulada no manda mensajes.

En B/C consulta las dos actividades y el caso ya concluido, sin editarlos ni crear
otras. Un conflicto real de versión puede presentarse con su captura/prueba aislada
identificada; no producirlo en el activo mediante ediciones de presentación.

Enlaces ilustrativos: [realización aislada S6](../../tests/evidence/s6-install-verified-integrated-done-form-768x1024.png),
[conflicto de versión real aislado](../../tests/evidence/s6-install-verified-integrated-real-version-conflict-390x844.png)
y [consulta activa del caso ya concluido](../../tests/evidence/s6-active-final-director-case-768x1024.png).
Identifica el destino de cada captura; no presentar las dos primeras como acciones
hechas en el activo.

## 6. Comparar roles y reportes

Cierra sesión al cambiar de cuenta. TUTOR solo recibe su sección, DIRECTOR consulta
sin botones de escritura y RESEARCHER conserva Inicio limitado sin casos/reportes.
No alterar roles o cuentas para mostrar esa diferencia.

En **Reportes**, muestra total, evaluadas/pendientes/insuficientes, denominador de
riesgo y conteos separados de casos/actividades. Aplica un filtro y descarga el CSV.
Explica: conjunto filtrado completo, no solo página; UTF-8 BOM; sin notas libres,
etiquetas privadas o credenciales. La solicitud se audita; el sistema no afirma que
la persona abrió el archivo. Estos indicadores no miden eficacia escolar.

## 7. Presentar continuidad y pruebas

Muestra diagramas de [arquitectura](Arquitectura_Final.md) y referencias a resultados
sanitizados, sin abrir el paquete privado. A prueba instalación; B restaura dump,
archivos ML/importación/configuración y HMAC; C conserva el activo. Antes del login
de B se comparan todas las tablas, Alembic y archivos. Después se separan los nuevos
eventos/sesiones legítimos de comprobación.

El [reporte estructural de recuperación S6](../../tests/evidence/s6-restore-final-code.json)
registra esa igualdad previa al login y la conservación del SVM/HMAC sin reentrenar.
El [catálogo efectivo](../../tests/evidence/s6-effective-catalog.json) se concilia en
el diccionario. Presenta por separado el recorrido posterior de interfaz y las
pruebas de instalación; no usar igualdad de hashes como único recorrido UI.

DPAPI se prueba realmente en Windows y depende de usuario/equipo. Una copia
corrupta/incompatible no debe recibir éxito ni tocar el activo. La caída real breve
de DB se realiza solo en destino aislado; no confundirla con inyección HTTP. No
demostrar apagado/backup durante exposición si compromete el uso actual: mostrar
el resultado ya comprobado con destino/fecha/código identificados.

Finaliza indicando los criterios efectivamente comprobados y pendientes de la
matriz. [Alcance y limitaciones](Alcance_y_Limitaciones.md) separa software,
experimento sintético y revisión escolar/hipótesis pendiente. No presentar una
certificación de seguridad/accesibilidad, aprobación institucional o tesis validada.
