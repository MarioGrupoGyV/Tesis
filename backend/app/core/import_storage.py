"""Archivo privado inmutable: rutas internas, sin nombres enviados por el cliente."""
import hashlib
import os
from pathlib import Path
import re
from app.core.errors import AppError
from app.services.csv_validation import MAX_BYTES


class ImportStorage:
    def __init__(self, directory: Path | None):
        if directory is None:
            raise AppError(503, "IMPORT_STORAGE_UNAVAILABLE", "El almacenamiento de importaciones no está disponible.")
        self.root = directory.resolve()

    def path(self, key):
        if not re.fullmatch(r"[0-9a-f]{32}\.csv", key):
            raise AppError(409, "IMPORT_FILE_INVALID", "El archivo del lote requiere revisión.")
        path = self.root / key
        if path.is_symlink():
            raise AppError(409, "IMPORT_FILE_INVALID", "El archivo del lote requiere revisión.")
        return path

    def write(self, key, content):
        path = self.path(key)
        try:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            with os.fdopen(os.open(path, flags, 0o600), "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError:
            raise AppError(503, "IMPORT_STORAGE_UNAVAILABLE", "No se pudo guardar el archivo de importación.") from None

    def read(self, key, expected_hash):
        path = self.path(key)
        try:
            with os.fdopen(os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)), "rb") as handle:
                content = handle.read(MAX_BYTES + 1)
        except OSError:
            raise AppError(503, "IMPORT_STORAGE_UNAVAILABLE", "No se pudo recuperar el archivo del lote.") from None
        if len(content) > MAX_BYTES or hashlib.sha256(content).hexdigest() != expected_hash:
            raise AppError(409, "IMPORT_FILE_CHANGED", "El archivo privado cambió; revisa su integridad antes de continuar.")
        return content

    def discard_uncommitted(self, key):
        # Solo se usa si falla la transacción que iba a crear ESTE lote nuevo.
        try:
            self.path(key).unlink(missing_ok=True)
        except OSError:
            pass  # Un huérfano no se convierte en evidencia ni se elimina otro archivo.
