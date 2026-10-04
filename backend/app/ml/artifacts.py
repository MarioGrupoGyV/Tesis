"""Almacén interno autenticado. Sin cargas de usuarios ni rutas proporcionadas por HTTP."""
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import re
import secrets
from uuid import uuid4

import joblib

from app.ml.features import CLASSES, Dataset, FeatureConfig, MLDiagnostic
from app.ml.predict import class_mapping
from app.ml.train import ALGORITHMS, ModelBundle, versions
from app.ml.manifest import ArtifactManifest

MAX_BYTES = 64 * 1024 * 1024


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


class ArtifactStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        checkout = Path(__file__).resolve().parents[3]
        if not self.root.is_absolute() or self.root.resolve().is_relative_to(checkout):
            raise MLDiagnostic('PRIVATE_STORAGE_REQUIRED')
        self._safe(self.root)
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)

    def _safe(self, path):
        if any(p.is_symlink() for p in [path,*path.parents]):
            raise MLDiagnostic('SYMLINK_REJECTED')
        return path

    def _read(self,path):
        self._safe(path)
        flags = os.O_RDONLY | getattr(os,'O_NOFOLLOW',0)
        try:
            with os.fdopen(os.open(path,flags),'rb') as handle:
                data = handle.read(MAX_BYTES + 1)
        except OSError:
            raise MLDiagnostic('ARTIFACT_UNAVAILABLE') from None
        if len(data) > MAX_BYTES:
            raise MLDiagnostic('ARTIFACT_TOO_LARGE')
        return data

    def _key(self, create=False):
        path = self._safe(self.root/'.internal-key')
        if create and not path.exists():
            try:
                with path.open('xb') as handle:
                    os.chmod(path,0o600)
                    handle.write(secrets.token_bytes(32))
            except FileExistsError:
                pass
        key = self._read(path)
        if len(key) != 32:
            raise MLDiagnostic('TRUST_KEY_INVALID')
        return key

    def _directory(self,key):
        if not re.fullmatch(r'[0-9a-f]{32}',key):
            raise MLDiagnostic('INVALID_ARTIFACT_KEY')
        return self._safe(self.root/key)

    def save(self,bundle: ModelBundle,dataset: Dataset):
        if dataset.scope != 'ISOLATED_TEST' or bundle.manifest['scope'] != 'ISOLATED_TEST':
            from app.services.processing_policy import require_ml_protocol
            require_ml_protocol()
        if hashlib.sha256(dataset.model_dump_json().encode()).hexdigest() != bundle.manifest['dataset_hash']:
            raise MLDiagnostic('DATASET_HASH_MISMATCH')
        key = uuid4().hex
        directory = self._directory(key)
        directory.mkdir(mode=0o700)
        buffer = io.BytesIO()
        joblib.dump(bundle.pipeline,buffer)
        payloads = {'pipeline.joblib':buffer.getvalue(),'dataset.json':dataset.model_dump_json().encode()}
        if bundle.manifest['algorithm'] == 'XGBOOST':
            payloads['estimator.ubj'] = bytes(bundle.pipeline.named_steps['estimator'].get_booster().save_raw(raw_format='ubj'))
        for name, data in payloads.items():
            with (directory/name).open('xb') as handle:
                handle.write(data)
            os.chmod(directory/name,0o600)
        manifest = {**bundle.manifest,'artifact_key':key,
                    'artifact_sha256':hashlib.sha256(payloads['pipeline.joblib']).hexdigest(),
                    'files':{name:hashlib.sha256(data).hexdigest() for name,data in payloads.items()}}
        ArtifactManifest.model_validate(manifest)
        raw = canonical(manifest)
        signature = hmac.new(self._key(create=True),raw,hashlib.sha256).hexdigest()
        (directory/'manifest.json').write_bytes(canonical({'manifest':manifest,'signature':signature}))
        os.chmod(directory/'manifest.json',0o600)
        return key

    def inspect(self,key):
        directory = self._directory(key)
        try:
            envelope = json.loads(self._read(directory/'manifest.json'))
            manifest = envelope['manifest']
            signature = hmac.new(self._key(),canonical(manifest),hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature,envelope['signature']):
                raise MLDiagnostic('UNTRUSTED_ARTIFACT')
            ArtifactManifest.model_validate(manifest)
            config = FeatureConfig.model_validate(manifest['feature_schema'])
            if (manifest['manifest_version'] != 'ml-artifact-v1' or manifest['dataset_schema_version'] != 'ml-dataset-v1'
                    or manifest['versions'] != versions() or manifest['class_order'] != list(CLASSES)
                    or manifest['encoded_classes'] != [0,1,2] or manifest['algorithm'] not in ALGORITHMS
                    or manifest['artifact_key'] != key or manifest['scope'] != 'ISOLATED_TEST'
                    or manifest['data_origin'] != 'REAL' or manifest['approved'] is not False
                    or manifest['probabilities_calibrated'] is not False
                    or manifest['reference_criterion_version'] != config.criterion_version
                    or manifest['horizon_days'] != config.horizon_days):
                raise MLDiagnostic('ARTIFACT_INCOMPATIBLE')
            expected = {'pipeline.joblib','dataset.json'} | ({'estimator.ubj'} if manifest['algorithm']=='XGBOOST' else set())
            if set(manifest['files']) != expected:
                raise MLDiagnostic('ARTIFACT_FILES_INCOMPATIBLE')
            # Leer una vez a memoria y validar ANTES de joblib (evita sustitución entre hash/carga).
            payloads = {name:self._read(directory/name) for name in expected}
            if any(hashlib.sha256(data).hexdigest() != manifest['files'][name] for name,data in payloads.items()):
                raise MLDiagnostic('ARTIFACT_HASH_MISMATCH')
            if (manifest['files']['dataset.json'] != manifest['dataset_hash'] or
                    manifest['files']['pipeline.joblib'] != manifest['artifact_sha256']):
                raise MLDiagnostic('MANIFEST_HASH_MISMATCH')
            return manifest,config,payloads
        except (KeyError,TypeError,ValueError) as error:
            if isinstance(error,MLDiagnostic):
                raise
            raise MLDiagnostic('INVALID_MANIFEST') from None

    def load(self,key):
        manifest, config, payloads = self.inspect(key)
        pipeline = joblib.load(io.BytesIO(payloads['pipeline.joblib']))
        class_mapping(pipeline.classes_)
        if list(pipeline.feature_names_in_) != list(config.features):
            raise MLDiagnostic('PIPELINE_SCHEMA_INCOMPATIBLE')
        if manifest['algorithm'] == 'XGBOOST':
            from xgboost import Booster
            booster = Booster()
            booster.load_model(bytearray(payloads['estimator.ubj']))
            if bytes(booster.save_raw(raw_format='ubj')) != bytes(pipeline.named_steps['estimator'].get_booster().save_raw(raw_format='ubj')):
                raise MLDiagnostic('NATIVE_MODEL_MISMATCH')
        return ModelBundle(pipeline,config,manifest)
