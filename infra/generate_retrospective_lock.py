"""Explicit lock maintenance; metadata only from PyPI, no model or data access."""
import json
from pathlib import Path
import urllib.request

PACKAGES = {'numpy': '2.3.5', 'scipy': '1.17.0', 'scikit-learn': '1.8.0',
            'joblib': '1.5.3', 'threadpoolctl': '3.6.0'}

if __name__ == '__main__':
    lines = ['# Reference inference: CPython 3.12.14, Linux x86_64; wheels only.',
             '# Direct and transitive inference dependencies; published PyPI SHA-256.']
    for name, version in PACKAGES.items():
        with urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{version}/json', timeout=30) as response:
            metadata = json.load(response)
        wheels = [item for item in metadata['urls'] if item['filename'].endswith('.whl') and
                  ('py3-none-any' in item['filename'] or ('cp312-cp312' in item['filename'] and
                   'manylinux' in item['filename'] and 'x86_64' in item['filename']))]
        if not wheels:
            raise RuntimeError('REFERENCE_WHEEL_MISSING')
        lines.append(f'{name}=={version} ' + '\\')
        for index, item in enumerate(wheels):
            lines.append('    --hash=sha256:' + item['digests']['sha256'] +
                         (' ' + '\\' if index < len(wheels) - 1 else ''))
    path = Path(__file__).resolve().parents[1] / 'backend/requirements-retrospective.txt'
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'versions': PACKAGES, 'lock': str(path)}))
