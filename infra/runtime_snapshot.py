"""Instantánea solo en memoria; nunca publica hashes de contraseña ni contenido escolar."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCHOOL = ('academic_periods','grade_sections','students','enrollments','academic_snapshots',
          'import_batches','model_versions','predictions','alerts','interventions')
CODE = '''
import hashlib,json
from pathlib import Path
from sqlalchemy import text
from app.core.config import Settings
from app.core.database import Database
db=Database(Settings())
with db.engine.connect() as c:
 assert c.scalar(text('SELECT current_user'))=='riesgo_app'
 assert c.scalar(text('SELECT current_database()'))=='riesgo_escolar'
 tables=c.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='risk_school' ORDER BY table_name")).scalars().all()
 counts={t:c.scalar(text('SELECT count(*) FROM risk_school.'+t)) for t in tables}
 fingerprints={t:c.scalar(text("SELECT md5(coalesce(string_agg(row_to_json(x)::text,'' ORDER BY id),'')) FROM risk_school."+t+" x")) for t in tables}
 users=[dict(r) for r in c.execute(text('SELECT id::text,email,display_name,role,is_active FROM risk_school.app_users ORDER BY id')).mappings()]
files=sorted((str(p.relative_to('/var/lib/riesgo/imports')),hashlib.sha256(p.read_bytes()).hexdigest()) for p in Path('/var/lib/riesgo/imports').rglob('*') if p.is_file())
print(json.dumps({'counts':counts,'fingerprints':fingerprints,'users':users,'files':files}))
'''

def snapshot():
    output = subprocess.check_output(['docker','compose','exec','-T','api','python','-c',CODE],cwd=ROOT,text=True)
    return json.loads(output)

def school_unchanged(before, after):
    return all(before['fingerprints'][t]==after['fingerprints'][t] for t in SCHOOL) and before['files']==after['files']
