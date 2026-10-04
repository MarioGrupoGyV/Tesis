"""CSV sintético estricto; no infiere valores ni acepta información futura al corte."""
import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
import hashlib
import io
import json
import re
from zoneinfo import ZoneInfo

from app.core.errors import AppError

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10000
FEATURES = ("average_grade", "attendance_pct", "activities_pct", "participation_level", "behavior_incidents", "age_years")
HEADERS = ("student_code", "grade", "section", "cutoff_at", "target_date", "available_at", "window_start", *FEATURES)
LIMA = ZoneInfo("America/Lima")


@dataclass
class ParsedCSV:
    rows: list[dict]
    errors: list[dict]
    total: int


def issue(row, column, message, code="INVALID_VALUE"):
    return {"row": row, "column": column, "code": code, "message": message}


def file_error(code, message, row=1, field="file"):
    return AppError(422, code, message, details=[{"row": row, "field": field, "message": message}])


def day(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Usa una fecha válida AAAA-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("Usa una fecha existente AAAA-MM-DD.") from None


def instant(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", value):
        raise ValueError("Usa RFC 3339 con segundos y zona: 2026-05-01T10:00:00-05:00 o Z.")
    try:
        return datetime.fromisoformat(value).astimezone(UTC)
    except (ValueError, OverflowError):
        raise ValueError("Usa un instante existente con zona horaria válida.") from None


def number(value, low, high, decimals=False, optional=False):
    if optional and value == "":
        return None
    pattern = r"[0-9]+(?:\.[0-9]{1,2})?" if decimals else r"[0-9]+"
    if len(value) > 20 or not re.fullmatch(pattern, value):
        raise ValueError(f"Usa {'un número con punto y máximo dos decimales' if decimals else 'un entero'} entre {low} y {high}" + (", o deja vacío si falta." if optional else "."))
    result = Decimal(value) if decimals else int(value)
    if not low <= result <= high:
        raise ValueError(f"Usa un valor entre {low} y {high}.")
    return result.quantize(Decimal("0.01")) if decimals else result


def row_hash(row):
    values = {key: row[key] for key in HEADERS}
    canonical = json.dumps(values, default=lambda v: v.isoformat() if isinstance(v, (datetime, date)) else str(v),
                           sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def parse_csv(content: bytes, period) -> ParsedCSV:
    if len(content) > MAX_BYTES:
        raise file_error("CSV_TOO_LARGE", "Reduce el archivo a un máximo de 5 MiB.")
    try:
        decoded = content.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        raise file_error("CSV_ENCODING", "Guarda el archivo como CSV UTF-8.") from None
    if "\x00" in decoded:
        raise file_error("CSV_ENCODING", "Elimina caracteres NUL y guarda como CSV UTF-8.")
    reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
    try:
        header = next(reader, [])
        if tuple(header) != HEADERS:
            raise file_error("CSV_HEADERS", "Usa una sola vez las 13 cabeceras y su orden en la plantilla; no añadas etiquetas ni columnas.")
        rows, errors, seen, sections, total = [], [], {}, {}, 0
        for line in reader:
            total += 1
            source = reader.line_num
            if total > MAX_ROWS:
                raise file_error("CSV_TOO_MANY_ROWS", "Divide el archivo en lotes de máximo 10000 filas.", source)
            if len(line) != len(HEADERS) or any("\n" in v or "\r" in v for v in line):
                errors.append(issue(source, "file", "Usa exactamente 13 columnas sin saltos de línea dentro de una celda.", "CSV_COLUMNS"))
                continue
            raw = dict(zip(HEADERS, (v.strip() for v in line), strict=True))
            row = {"source_row_number": source}
            for key in HEADERS:
                value = raw[key]
                try:
                    if key == "student_code":
                        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,39}", value):
                            raise ValueError("Usa un código sintético de 3 a 40 letras ASCII, números, guion o guion bajo.")
                        row[key] = value
                    elif key == "section":
                        if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", value):
                            raise ValueError("Usa el código exacto de sección, sin nombres ni espacios, máximo 40 caracteres.")
                        row[key] = value
                    elif key in ("cutoff_at", "available_at"):
                        row[key] = instant(value)
                    elif key in ("window_start", "target_date"):
                        row[key] = day(value)
                    elif key == "grade":
                        row[key] = number(value, 1, 5)
                    elif key in FEATURES[:3]:
                        row[key] = number(value, 0, 20 if key == "average_grade" else 100, True, True)
                    else:
                        low, high = {"participation_level": (1, 3), "behavior_incidents": (0, 2147483647), "age_years": (5, 25)}[key]
                        row[key] = number(value, low, high, optional=True)
                except ValueError as exc:
                    errors.append(issue(source, key, str(exc)))
            if len(row) != len(HEADERS) + 1:
                continue
            cutoff_day = row["cutoff_at"].astimezone(LIMA).date()
            available_day = row["available_at"].astimezone(LIMA).date()
            if not period.start_date <= row["window_start"] <= available_day <= cutoff_day < row["target_date"] <= period.end_date or row["available_at"] > row["cutoff_at"]:
                errors.append(issue(source, "cutoff_at", "Respeta inicio de periodo ≤ ventana ≤ disponibilidad ≤ corte < objetivo ≤ fin de periodo, con días America/Lima.", "INVALID_DATES"))
            key = (row["student_code"], row["cutoff_at"])
            if key in seen:
                for affected in (seen[key], source):
                    errors.append(issue(affected, "student_code", "Conserva una sola fila por código y corte; las zonas equivalentes representan el mismo instante.", "DUPLICATE_ROW"))
            seen[key] = source
            section = (row["grade"], row["section"])
            if row["student_code"] in sections and sections[row["student_code"]][0] != section:
                for affected in (sections[row["student_code"]][1], source):
                    errors.append(issue(affected, "section", "Usa una sola sección por estudiante en el periodo.", "SECTION_CONFLICT"))
            sections[row["student_code"]] = (section, source)
            row["missing_fraction"] = (Decimal(sum(row[k] is None for k in FEATURES)) / 6).quantize(Decimal("0.0001"))
            row["row_sha256"] = row_hash(row)
            rows.append(row)
    except csv.Error:
        raise file_error("CSV_SYNTAX", "Corrige las comillas, delimitadores y longitud de las celdas del CSV.", max(1, reader.line_num)) from None
    if total == 0:
        errors.append(issue(1, "file", "Añade al menos una fila sintética después de la cabecera.", "EMPTY_CSV"))
    return ParsedCSV(rows, errors, total)
