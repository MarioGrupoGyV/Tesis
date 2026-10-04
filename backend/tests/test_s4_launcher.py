"""Safe local CSV export: no operational application, credentials or Docker used."""
import base64
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'infra'))
import study


@pytest.fixture
def export_payload(monkeypatch):
    content=(','.join(study.CSV_HEADERS)+'\nSYN-TEST,1,A,2025-01-02T00:00:00Z,2025-02-01,2025-01-02T00:00:00Z,2025-01-01,12,90,80,MEDIUM,0,12\n').encode()
    value={'period_id':'00000000-0000-4000-8000-000000000004',
        'csv_sha256':hashlib.sha256(content).hexdigest(),
        'csv_base64':base64.b64encode(content).decode()}
    monkeypatch.setattr(study,'internal',lambda *args,**kwargs:value)
    return value,content


def test_export_verifies_registry_hash_and_writes_only_input_csv(tmp_path,export_payload):
    payload,content=export_payload
    path=tmp_path/'input-synthetic.csv'
    result=study.export_csv({'email':'fixture','password':'private-password'},'study-fixture',path)
    assert path.read_bytes()==content
    assert result=={'study_id':'study-fixture','period_id':payload['period_id'],
        'file_name':path.name,'csv_sha256':payload['csv_sha256'],'bytes_written':len(content)}
    public=json.dumps(result)
    assert 'csv_base64' not in public and 'student_code' not in public
    assert 'private-password' not in public and str(tmp_path) not in public


def test_export_preserves_existing_file(tmp_path,export_payload):
    path=tmp_path/'existing.csv'
    path.write_bytes(b'existing evidence')
    with pytest.raises(RuntimeError,match='CSV_OUTPUT_EXISTS'):
        study.export_csv({},'study-fixture',path)
    assert path.read_bytes()==b'existing evidence'


@pytest.mark.parametrize('mutation,code',[
    ({'csv_sha256':'0'*64},'CSV_EXPORT_HASH_MISMATCH'),
    ({'csv_sha256':None},'CSV_EXPORT_HASH_REQUIRED'),
    ({'csv_sha256':'not a registry hash'},'CSV_EXPORT_HASH_REQUIRED'),
    ({'csv_base64':'not base64!'},'CSV_EXPORT_INVALID'),
    ({'csv_base64':base64.b64encode(b'labels,private\n').decode()},'CSV_EXPORT_INVALID'),
])
def test_export_rejects_corruption_before_writing(tmp_path,export_payload,mutation,code):
    payload,_=export_payload
    payload.update(mutation)
    path=tmp_path/'input.csv'
    with pytest.raises(RuntimeError,match=code):
        study.export_csv({},'study-fixture',path)
    assert not path.exists()


@pytest.mark.parametrize('name',['CON.csv','LPT1.csv','.hidden.csv','report.json','with space.csv','bad:stream.csv'])
def test_export_rejects_unsafe_filenames(tmp_path,name):
    with pytest.raises(RuntimeError,match='CSV_OUTPUT_NAME_INVALID'):
        study.export_destination(tmp_path/name)


def test_export_rejects_repo_other_git_and_relative_destinations(tmp_path,monkeypatch):
    with pytest.raises(RuntimeError,match='CSV_OUTPUT_PATH_INVALID'):
        study.export_destination(Path('input.csv'))
    repo=tmp_path/'workspace'
    repo.mkdir()
    monkeypatch.setattr(study,'ROOT',repo)
    with pytest.raises(RuntimeError,match='CSV_OUTPUT_INSIDE_GIT'):
        study.export_destination(repo/'input.csv')
    other=tmp_path/'other-checkout'
    other.mkdir()
    (other/'.git').write_text('gitdir: another directory',encoding='utf-8')
    with pytest.raises(RuntimeError,match='CSV_OUTPUT_INSIDE_GIT'):
        study.export_destination(other/'input.csv')


def test_export_requires_existing_directory_and_rejects_symlinks(tmp_path):
    with pytest.raises(RuntimeError,match='CSV_OUTPUT_DIRECTORY_REQUIRED'):
        study.export_destination(tmp_path/'missing'/'input.csv')
    link=tmp_path/'linked'
    try:
        link.symlink_to(tmp_path,target_is_directory=True)
    except (OSError,NotImplementedError):
        pytest.skip('Symlink creation requires host permission; Linux runner verifies this case')
    with pytest.raises(RuntimeError,match='CSV_OUTPUT_LINK_FORBIDDEN'):
        study.export_destination(link/'input.csv')


def test_export_cli_stdout_is_sanitized(tmp_path,export_payload,monkeypatch,capsys):
    monkeypatch.setattr(study,'credentials',lambda:{'ADMIN':{'email':'fixture','password':'private-password'}})
    code=study.main(['export-csv','--admin-credential','ADMIN','--study-id','study-fixture',
        '--output',str(tmp_path/'input.csv')])
    stdout=capsys.readouterr().out
    assert code==0 and json.loads(stdout)['bytes_written']>0
    assert not any(value in stdout for value in ('csv_base64','student_code','SYN-TEST','private-password','labels'))
