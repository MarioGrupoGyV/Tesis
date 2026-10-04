# Backend de Seguimiento Escolar

FastAPI/SQLAlchemy/Alembic, capas separadas. S2.1 conserva sesiones, CSRF, autorización
y motor de importación; procesamiento institucional bloqueado por processing_policy.
Contrato público 0.3.0 en docs/planning/Contrato_API.yaml. Rutas S1/S2 y cuatro rutas S3.

La API usa riesgo_app; migraciones con propietario temporal. Ningún arranque crea
cuentas, periodos ni datos. bootstrap_admin pide entrada interactiva y configure_context
crea contexto explícito; ambas acciones auditan y rechazan duplicados sin sobrescribir.
Settings no ofrece un modo que habilite procesamiento. CSV privado fuera del checkout.

No autogenerar migraciones sobre ORM parcial. 0001/snapshot inmutables; 0002 añade
origen institucional sin actualizar datos existentes. Modelos activos bloqueados
hasta otra iteración; S3 añade ORM explícito de modelos/predicciones sobre las tablas
existentes sin DDL. Conserva ambas restricciones de activación.

app/ml/features, train, evaluate y predict implementan el núcleo probado aisladamente;
artifacts/manifest verifican procedencia interna, hashes y compatibilidad antes de
cargar. Servicios, repositorio y esquemas públicos ML están separados. Ningún arranque
ni petición HTTP entrena. Persistencia snapshot/model reutilizable y auditoría atómica.
Solo cinco variables básicas; configuración explícita de escalas, etiquetas futuras,
faltantes y opcionales justificados. Sin calibración ni activación automática.

Desde PowerShell: docker compose -f infra/compose.test.yaml build tester y
docker compose -f infra/compose.test.yaml run --rm tester. Se ejecutan dentro de
Linux/Python 3.12.12 con PostgreSQL aislado. Fixtures fabricados nunca se cargan en
la aplicación activa. Consultar README raíz, Estado_Sprint_3.md y docs/manuals/ML_S3.md.
