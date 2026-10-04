# Backend de Seguimiento Escolar

FastAPI/SQLAlchemy/Alembic, capas separadas. S2.1 conserva sesiones, CSRF, autorización
y motor de importación; procesamiento institucional bloqueado por processing_policy.
Contrato público 0.2.0 en docs/planning/Contrato_API.yaml. Solo rutas S1/S2.

La API usa riesgo_app; migraciones con propietario temporal. Ningún arranque crea
cuentas, periodos ni datos. bootstrap_admin pide entrada interactiva y configure_context
crea contexto explícito; ambas acciones auditan y rechazan duplicados sin sobrescribir.
Settings no ofrece un modo que habilite procesamiento. CSV privado fuera del checkout.

No autogenerar migraciones sobre ORM parcial. 0001/snapshot inmutables; 0002 añade
origen institucional sin actualizar datos existentes. Modelos activos bloqueados
hasta otra iteración; S3 no se implementó.

Desde PowerShell: docker compose -f infra/compose.test.yaml build tester y
docker compose -f infra/compose.test.yaml run --rm tester. Se ejecutan dentro de
Linux/Python 3.12.12 con PostgreSQL aislado. Fixtures fabricados nunca se cargan en
la aplicación activa. Consultar README raíz y Estado_Sprint_2_1.md.
