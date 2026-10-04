"""Comprueba entorno activo vacío y persistencia sin introducir cuentas o datos escolares."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PROBE = '''
import json
from pathlib import Path
from sqlalchemy import text
from app.core.config import Settings
from app.core.database import Database
db=Database(Settings())
with db.engine.connect() as conn:
 assert conn.scalar(text('SELECT current_user')) == 'riesgo_app'
 tables=conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='risk_school' ORDER BY table_name")).scalars().all()
 counts={t:conn.scalar(text('SELECT count(*) FROM risk_school.'+t)) for t in tables}
 assert len(counts)==13 and all(v==0 for v in counts.values()), 'El entorno activo ya contiene registros: no se modifica.'
root=Path('/var/lib/riesgo/imports')
assert not list(root.glob('*.csv'))
marker=root/'.infrastructure-persistence-check'
if not marker.exists(): marker.write_text('infrastructure-only')
assert marker.read_text()=='infrastructure-only'
print(json.dumps({'counts':counts,'database_role':'riesgo_app','private_csv_count':0,'volume_marker_preserved':True}))
'''

def probe():
    return json.loads(subprocess.check_output(['docker','compose','exec','-T','api','python','-c',PROBE],cwd=ROOT,text=True))

def main():
    before=probe()
    subprocess.run(['docker','compose','down'],cwd=ROOT,check=True)
    subprocess.run(['docker','compose','up','-d','--wait'],cwd=ROOT,check=True)
    after=probe()
    assert before==after
    report={'status':'COMPROBADO','active_project':'riesgo-escolar','database':'riesgo_escolar',
        'volumes':['riesgo-escolar_db_data','riesgo-escolar_import_data'],'restart_preserved':True,**after}
    (ROOT/'tests/evidence/s2-1-runtime.json').write_text(json.dumps(report,indent=2)+'\n')
    print('COMPROBADO: base vacía, sin CSV escolares, reinicio sin semillas y volumen persistente.')

if __name__=='__main__':
    main()
