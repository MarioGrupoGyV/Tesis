"""JSON/CSV deterministas privados; claves internas, integridad antes de leer."""
import hashlib
import json
import os
import re
from pathlib import Path
from app.core.errors import AppError


class StudyStorage:
    def __init__(self, root):
        if root is None:
            raise AppError(503,'STUDY_STORAGE_UNAVAILABLE','Almacenamiento del estudio no disponible.')
        from app.ml.artifacts import ArtifactStore
        self.root = ArtifactStore(Path(root)).root / 'studies'
        if self.root.is_symlink():
            raise AppError(409,'STUDY_INTEGRITY_ERROR','Revisa la integridad del estudio privado.')
        self.root.mkdir(mode=0o700,exist_ok=True)

    def path(self,key):
        if not re.fullmatch(r'[0-9a-f]{32}\.json',key):
            raise AppError(409,'STUDY_INTEGRITY_ERROR','Identificador privado incompatible.')
        path = self.root/key
        if any(p.is_symlink() for p in (path,*path.parents)):
            raise AppError(409,'STUDY_INTEGRITY_ERROR','Revisa la integridad del estudio privado.')
        return path

    def write(self,key,value):
        content = json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        path = self.path(key)
        digest = hashlib.sha256(content).hexdigest()
        if path.exists():
            self.read(key,digest)
            return digest
        try:
            flags = os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0)
            with os.fdopen(os.open(path,flags,0o600),'wb') as f:
                f.write(content); f.flush(); os.fsync(f.fileno())
        except OSError:
            raise AppError(503,'STUDY_STORAGE_UNAVAILABLE','No se pudo guardar el estudio privado.') from None
        return digest

    def read(self,key,digest):
        try:
            with os.fdopen(os.open(self.path(key),os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)),'rb') as f:
                content = f.read(64*1024*1024+1)
        except OSError:
            raise AppError(503,'STUDY_STORAGE_UNAVAILABLE','No se pudo recuperar el estudio privado.') from None
        if len(content)>64*1024*1024 or hashlib.sha256(content).hexdigest()!=digest:
            raise AppError(409,'STUDY_INTEGRITY_ERROR','El estudio privado cambió; no se procesaron datos.')
        try:
            return json.loads(content)
        except ValueError:
            raise AppError(409,'STUDY_INTEGRITY_ERROR','Formato privado incompatible.') from None
