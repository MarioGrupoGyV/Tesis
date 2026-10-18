"""Bloque 6: cada punto de entrada resuelve el mapeo ORM en un proceso NUEVO.

Las pruebas importan la aplicación completa y por eso no veían que `app.synthetic_cli generate` fallaba en su propio proceso con
NoReferencedTableError (el modelo del estudio apunta por FK a tablas que nadie había importado). El ensayo de la instalación hermana lo destapó.
"""
import os
from pathlib import Path
import subprocess
import sys

import pytest

MODULES = ['app.synthetic_cli', 'app.configure_context', 'app.bootstrap_admin', 'app.ml.cli', 'app.services.synthetic_study',
           'app.services.identities', 'app.models.synthetic', 'app.models.protocol', 'app.services.indicators', 'app.main']
CODE = ("import importlib,sys;importlib.import_module(sys.argv[1]);"
        "from sqlalchemy.orm import configure_mappers;configure_mappers();"
        "from app.models.base import Base;Base.metadata.sorted_tables;print('ok')")


@pytest.mark.parametrize('module', MODULES)
def test_entry_point_resolves_the_orm_mapping_in_a_fresh_process(module):
    env = {**os.environ, 'APP_ENV': os.environ.get('APP_ENV', 'test')}
    result = subprocess.run([sys.executable, '-c', CODE, module], cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True)
    assert result.returncode == 0, (module, result.stderr.strip().splitlines()[-1:] if result.stderr else '')
    assert result.stdout.strip() == 'ok'
