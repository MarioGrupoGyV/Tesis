"""Private append-only journal. Each signed record includes its actor and action.

Shares the backed-up ML volume, but no academic tables or historical artifacts.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
from uuid import uuid4

from app.ml.retrospective import MAX_PACKAGE, PACKAGE_SHA256, RetrospectiveError, sha


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


class RetrospectiveStore:
    def __init__(self, root):
        if root is None:
            raise RetrospectiveError('RETROSPECTIVE_STORAGE_UNAVAILABLE')
        root = Path(root)
        checkout = Path(__file__).resolve().parents[2]
        if checkout.name == 'backend':
            checkout = checkout.parent
        if not root.is_absolute() or root.resolve().is_relative_to(checkout):
            raise RetrospectiveError('RETROSPECTIVE_PRIVATE_STORAGE_REQUIRED')
        self.root = self.safe(root / 'retrospective')
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def safe(self, path):
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise RetrospectiveError('RETROSPECTIVE_STORAGE_INTEGRITY')
        return path

    def read_bytes(self, name, limit=MAX_PACKAGE):
        path = self.safe(self.root / name)
        try:
            with path.open('rb') as stream:
                content = stream.read(limit + 1)
        except FileNotFoundError:
            raise RetrospectiveError('RETROSPECTIVE_NOT_FOUND') from None
        if len(content) > limit:
            raise RetrospectiveError('RETROSPECTIVE_STORAGE_INTEGRITY')
        return content

    def write_new(self, name, content):
        path = self.safe(self.root / name)
        temporary = self.safe(self.root / (uuid4().hex + '.tmp'))
        try:
            with temporary.open('xb') as stream:
                os.chmod(temporary, 0o600)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            # Atomic publication without replacing an existing record.
            os.link(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def key(self, create=False):
        if create and not self.safe(self.root / '.journal-key').exists():
            try:
                self.write_new('.journal-key', secrets.token_bytes(32))
            except FileExistsError:
                pass
        key = self.read_bytes('.journal-key', 32)
        if len(key) != 32:
            raise RetrospectiveError('RETROSPECTIVE_STORAGE_INTEGRITY')
        return key

    def save(self, name, record):
        signature = hmac.new(self.key(create=True), canonical(record), hashlib.sha256).hexdigest()
        self.write_new(name, canonical({'record': record, 'signature': signature}))

    def read(self, name):
        try:
            envelope = json.loads(self.read_bytes(name))
            signature = hmac.new(self.key(), canonical(envelope['record']), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, envelope['signature']):
                raise RetrospectiveError('RETROSPECTIVE_STORAGE_INTEGRITY')
            return envelope['record']
        except (KeyError, TypeError, ValueError) as error:
            if isinstance(error, RetrospectiveError):
                raise
            raise RetrospectiveError('RETROSPECTIVE_STORAGE_INTEGRITY') from None

    def register(self, content, record):
        if sha(content) != PACKAGE_SHA256:
            raise RetrospectiveError('RETROSPECTIVE_UNTRUSTED_PACKAGE')
        if (self.root / 'authorization.json').exists():
            self.package()
            return False
        try:
            self.write_new('package.zip', content)
        except FileExistsError:
            if self.read_bytes('package.zip') != content:
                raise RetrospectiveError('RETROSPECTIVE_STORAGE_INTEGRITY')
        try:
            self.save('authorization.json', record)
            return True
        except FileExistsError:
            self.package()
            return False

    def package(self):
        record = self.read('authorization.json')
        content = self.read_bytes('package.zip')
        if (record.get('package_sha256') != PACKAGE_SHA256 or record.get('authorized_local_processing') is not True
                or record.get('institutional_activation') is not False or sha(content) != PACKAGE_SHA256):
            raise RetrospectiveError('RETROSPECTIVE_STORAGE_INTEGRITY')
        return content

    def run_name(self, identifier):
        from uuid import UUID
        return UUID(str(identifier)).hex + '.json'

    def save_run(self, record):
        self.save(self.run_name(record['id']), record)

    def run(self, identifier):
        record = self.read(self.run_name(identifier))
        if str(record.get('id')) != str(identifier):
            raise RetrospectiveError('RETROSPECTIVE_STORAGE_INTEGRITY')
        return record

    def history(self):
        names = sorted(p.name for p in self.root.iterdir() if re.fullmatch(r'[0-9a-f]{32}\.json', p.name))
        return sorted((self.read(name) for name in names), key=lambda r: (r['executed_at'], r['id']), reverse=True)
