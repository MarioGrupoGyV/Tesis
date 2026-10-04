"""Validación documental de S0; no conecta a DB ni ejecuta módulos de negocio."""
from pathlib import Path
import hashlib
import json
import re
import sys

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate
from pglast import ast, parse_sql

ROOT = Path(__file__).resolve().parents[1]
checks = []


def check(condition, description):
    if not condition:
        raise ValueError(description)
    checks.append(description)


def load_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def pins(path):
    content = (ROOT / path).read_text(encoding="utf-8")
    return {
        re.sub(r"[-_.]+", "-", name.lower()): version
        for name, version in re.findall(
            r"^([\w.-]+)(?:\[[^\]]+\])?==([^\s;\\]+)", content, re.M
        )
    }


def run():
    check(sys.version_info[:2] == (3, 12), "Intérprete de validación Python 3.12")
    required_dirs = [
        "frontend/src/app", "frontend/src/components", "frontend/src/lib",
        *[f"frontend/src/features/{name}" for name in
          ("auth", "dashboard", "students", "imports", "alerts", "reports", "models")],
        *[f"backend/app/{name}" for name in
          ("api/v1", "core", "models", "schemas", "repositories", "services")],
        *[f"backend/app/ml/{name}" for name in ("features", "train", "evaluate", "predict")],
        "backend/migrations/versions", "backend/tests", "docs/planning",
        "docs/research", "docs/adr", "docs/manuals", "infra", "tests/e2e", "tests/evidence",
    ]
    check(all((ROOT / path).is_dir() for path in required_dirs), "Estructura de carpetas del plan")
    contract_path = ROOT / "docs/planning/Contrato_API.yaml"
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    validate(contract)
    check(contract["info"]["version"] == "0.4.0", "OpenAPI 3.1 válido, versión 0.4.0")
    for path, methods in contract["paths"].items():
        for method, operation in methods.items():
            if method not in ("get", "post", "patch", "put", "delete") or path == "/health/live":
                continue
            expected = "Health" if path == "/health/ready" else "Error"
            check(operation["responses"]["503"]["content"]["application/json"]["schema"]["$ref"] ==
                  f"#/components/schemas/{expected}", f"503 sanitizado {method} {path}")
    sql_path = ROOT / "docs/planning/Esquema.sql"
    sql = sql_path.read_text(encoding="utf-8")
    statements = parse_sql(sql)
    tables = {stmt.stmt.relation.relname: stmt.stmt for stmt in statements
              if isinstance(stmt.stmt, ast.CreateStmt)}
    expected_tables = {
        "app_users", "user_sessions", "academic_periods", "grade_sections", "students",
        "enrollments", "import_batches", "academic_snapshots", "model_versions",
        "predictions", "alerts", "interventions", "audit_events", "synthetic_studies",
    }
    check(set(tables) == expected_tables, "Sintaxis SQL analizada y 14 tablas de diseño")
    columns = {name: {c.colname: c for c in table.tableElts if isinstance(c, ast.ColumnDef)}
               for name, table in tables.items()}
    public = contract["components"]["schemas"]
    type_mapping = {
        "uuid": ("string", "uuid"), "date": ("string", "date"),
        "timestamptz": ("string", "date-time"), "text": ("string", None),
        "bpchar": ("string", None), "int2": ("integer", None),
        "int4": ("integer", None), "bool": ("boolean", None), "numeric": ("number", None),
    }
    direct = {
        "User": "app_users", "Period": "academic_periods", "Section": "grade_sections",
        "Snapshot": "academic_snapshots", "Prediction": "predictions",
        "ImportBatch": "import_batches", "Alert": "alerts", "Intervention": "interventions",
        "Model": "model_versions", "AuditEvent": "audit_events",
    }
    matched = 0
    for schema_name, table_name in direct.items():
        for field, definition in public.get(schema_name, {}).get("properties", {}).items():
            if field not in columns[table_name]:
                continue  # Joins y campos derivados documentados en la conciliación.
            col = columns[table_name][field]
            sql_type = col.typeName.names[-1].sval
            if sql_type not in type_mapping:  # JSONB validado por esquema/proyección.
                continue
            expected_type, expected_format = type_mapping[sql_type]
            actual = definition.get("type", [])
            actual = [actual] if isinstance(actual, str) else actual
            check(expected_type in actual and
                  (not expected_format or definition.get("format") == expected_format),
                  f"Tipo SQL/API {schema_name}.{field}")
            matched += 1
    check("UNIQUE (grade, code, school_year)" in sql and
          "school_year" in public["Period"]["required"], "Año de periodo e identidad grado/sección/año")
    check("FOREIGN KEY (supersedes_id, enrollment_id, cutoff_at, data_origin)" in sql,
          "Revisión vinculada a la misma matrícula/corte/origen")
    check("AT TIME ZONE 'UTC'" not in sql and "AT TIME ZONE 'America/Lima'" in sql,
          "Comparación de días académicos en America/Lima")
    commit = contract["paths"]["/imports/{id}/commit"]["post"]["requestBody"]
    check(commit["required"] and "expected_preview_version" in
          commit["content"]["application/json"]["schema"]["required"] and
          "preview_version" in public["ImportBatch"]["required"] and
          "preview_state" in columns["import_batches"], "Confirmación ligada a versión y estado de preview")
    for path, methods in contract["paths"].items():
        for method, operation in methods.items():
            if method not in ("get", "post", "patch", "put", "delete"):
                continue
            if method in ("post", "patch", "put", "delete") and path != "/auth/login":
                check(any(p.get("name") == "X-CSRF-Token" and p.get("required")
                          for p in operation.get("parameters", [])), f"CSRF especificado {method} {path}")
            if "RESEARCHER" in operation.get("x-roles", []):
                check(path in ("/auth/me", "/auth/csrf", "/auth/logout", "/processing/status"),
                      f"Investigador restringido {path}")
    uid = "00000000-0000-4000-8000-000000000001"
    prediction = {key: uid for key in ("id", "enrollment_id", "snapshot_id", "model_id")}
    prediction.update(data_origin="REAL", risk_level="LOW", cutoff_at="2026-10-03T16:00:00Z",
                      target_date="2026-10-04", predicted_at="2026-10-03T16:01:00Z",
                      probabilities_calibrated=False, probability_low=None,
                      probability_medium=None, probability_high=None)
    samples = [
        ("Prediction", prediction, True),
        ("Prediction", {**prediction, "probability_low": 0.5}, False),
        ("Prediction", {**prediction, "probabilities_calibrated": True}, False),
    ]
    for name, instance, expected in samples:
        # Las muestras utilizadas solo contienen esquemas locales sin referencias externas.
        validator = Draft202012Validator(public[name], format_checker=FormatChecker())
        check(validator.is_valid(instance) == expected, f"Muestra contractual {name}: esperado {expected}")
    response_samples = ROOT / "tests/evidence/s3-1-response-samples.json"
    if response_samples.exists():
        for sample in json.loads(response_samples.read_text(encoding="utf-8")):
            schema = {"$ref": f"#/components/schemas/{sample['schema']}", "components": contract["components"]}
            validator = Draft202012Validator(schema, format_checker=FormatChecker())
            validator.validate(sample['body'])
            check(True, f"Respuesta real contra contrato: {sample['schema']}")
    lock = load_json("package-lock.json")["packages"]
    for file, entry in (("package.json", ""), ("frontend/package.json", "frontend")):
        manifest = load_json(file)
        for group in ("dependencies", "devDependencies"):
            for name, version in manifest.get(group, {}).items():
                check(bool(re.fullmatch(r"\d+\.\d+\.\d+", version)) and
                      lock[entry][group][name] == version, f"Pin npm {name}")
                resolved = lock.get(f"node_modules/{name}") or lock.get(f"frontend/node_modules/{name}")
                check(resolved and resolved["version"] == version and resolved.get("integrity"),
                      f"Versión e integridad npm {name}")
    for base in ("backend/requirements", "backend/requirements-dev", "infra/requirements-s0"):
        source, locked = pins(base + ".in"), pins(base + ".txt")
        check(all(locked.get(name) == version for name, version in source.items()), f"Pins Python {base}")
        chunks = re.split(r"(?m)^(?=[\w.-]+==)", (ROOT / (base + ".txt")).read_text(encoding="utf-8"))
        check(all("--hash=sha256:" in chunk for chunk in chunks if re.match(r"[\w.-]+==", chunk)),
              f"Hashes Python {base}")
    runtime, dev = pins("backend/requirements.txt"), pins("backend/requirements-dev.txt")
    check(all(dev.get(name) == version for name, version in runtime.items()), "Lock desarrollo coherente con runtime")
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    sprint = compose["x-sprint"]["current"]
    if sprint == "S0":
        check(compose["services"] == {} and not compose["x-sprint"]["runtime-implemented"], "Compose S0 sin servicios implementados")
    elif sprint in ("S1", "S2", "S2.1", "S3", "S3.1"):
        services = compose["services"]
        check(set(services) == {"web", "api", "db"} and compose["x-sprint"]["runtime-implemented"],
              "Compose S1 web/api/db implementados")
        check(services["db"]["image"] == "postgres:17.6-bookworm", "PostgreSQL conserva tag S0")
        check(any(str(v).startswith("db_data:") for v in services["db"]["volumes"]), "Volumen persistente de PostgreSQL")
        for name in ("web", "api", "db"):
            check("healthcheck" in services[name], f"Healthcheck Compose {name}")
            check(all(str(p).startswith("127.0.0.1:") for p in services[name]["ports"]),
                  f"Puerto localhost {name}")
        check("DATA_ORIGIN" not in services["api"]["environment"] and "REAL_MODE_ENABLED" not in services["api"]["environment"], "Sin selector de modo operativo")
        check("owner_database_url" not in services["api"]["secrets"] and
              "demo_credentials" not in services["api"]["secrets"], "API sin secretos de migración/semilla")
        check((ROOT / services["api"]["build"]["dockerfile"]).exists() and
              (ROOT / services["web"]["build"]["dockerfile"]).exists(), "Dockerfiles S1 presentes")
        check("python:3.12.12-slim-bookworm" in (ROOT / "infra/docker/api.Dockerfile").read_text(),
              "Python conserva tag S0")
        check("node:24.14.1-bookworm-slim" in (ROOT / "infra/docker/web.Dockerfile").read_text(),
              "Node conserva tag S0")
        if sprint in ("S2", "S2.1", "S3", "S3.1"):
            check("import_data" in compose["volumes"] and
                  "import_data:/var/lib/riesgo/imports" in services["api"]["volumes"], "CSV privado persistente fuera del checkout")
            check(services['api']['environment']['IMPORT_STORAGE_DIR'] == '/var/lib/riesgo/imports',
                  "Ruta de importación interna, no derivada del nombre del cliente")
        if sprint in ('S3','S3.1'):
            check('ml_data:/var/lib/riesgo/ml' in services['api']['volumes'] and
                  services['api']['environment']['ML_STORAGE_DIR'] == '/var/lib/riesgo/ml',
                  'Almacenamiento ML privado persistente')
            check('/models/{id}/activate' not in contract['paths'] and '/models/train' not in contract['paths'],
                  'Sin activación ni entrenamiento HTTP')
    else:
        raise ValueError(f"Estado Compose no reconocido: {sprint}")
    result = {
        "status": "COMPROBADO", "scope": f"Contratos documentales e infraestructura {sprint}; sin pruebas funcionales",
        "checks": len(checks), "sql_statements": len(statements), "tables": len(tables),
        "mapped_field_types": matched, "api_paths": len(contract["paths"]),
        "contract_samples": len(samples),
        "hashes": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in (contract_path, sql_path, ROOT / "package-lock.json")},
        "limitations": ["No ejecuta DDL/PLpgSQL", "No prueba permisos en servidor",
                        "No build, migración, ML, UI ni persistencia"],
    }
    evidence_name = "s0-checks.json" if sprint == "S0" else "s3-1-contracts.json"
    (ROOT / "tests/evidence" / evidence_name).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    try:
        run()
    except Exception as error:
        print(f"FALLIDO: {error}", file=sys.stderr)
        sys.exit(1)
