"""Negativas sobre copias en memoria del respaldo real, jamás sobre el activo."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tempfile
import zipfile
from backup_restore import verified_content,validate_archive,restore_check,location
from runtime_target import write_new
from windows_dpapi import protect,unprotect


def rejected(callback,expected):
    try: callback()
    except RuntimeError as error:
        if str(error)!=expected: raise
        return expected
    raise AssertionError('NEGATIVE_OPERATION_ACCEPTED')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup',type=Path,required=True)
    parser.add_argument('--existing-target',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.report.exists(): parser.error('El informe debe ser nuevo')
    original=args.backup.read_bytes();before=hashlib.sha256(original).hexdigest()
    content,manifest=verified_content(args.backup)
    cases={}
    tampered=bytearray(original);tampered[-10]^=1
    cases['native_dpapi_corruption']=rejected(lambda:unprotect(bytes(tampered)),'DPAPI_INTEGRITY_OR_IDENTITY_FAILED')
    with zipfile.ZipFile(io.BytesIO(content)) as source:
        payloads={name:source.read(name) for name in source.namelist()}
    def mutated(change):
        values=dict(payloads);change(values)
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,data in values.items(): archive.writestr(name,data)
        # Native protection/decryption of the temporary derived package; it is
        # never registered for production restoration or extracted to Docker.
        return unprotect(protect(buffer.getvalue()))
    cases['missing_original_hmac_key']=rejected(lambda:validate_archive(mutated(lambda v:v.pop('volumes/ml_data/.internal-key'))),
        'BACKUP_INVENTORY_INCOMPLETE')
    def incompatible(values):
        m=json.loads(values['manifest.json']);m['version']=999;values['manifest.json']=json.dumps(m).encode()
    cases['incompatible_real_manifest']=rejected(lambda:validate_archive(mutated(incompatible)),'BACKUP_VERSION_INCOMPATIBLE')
    cases['altered_real_dump']=rejected(lambda:validate_archive(mutated(lambda v:v.update({'database.dump':v['database.dump']+b'x'}))),
        'BACKUP_FILE_INTEGRITY_FAILED')
    with tempfile.TemporaryDirectory(prefix='s6-negative-',dir=location()) as private:
        external=Path(private)/args.backup.name;external.write_bytes(original)
        cases['unregistered_external_copy']=rejected(lambda:verified_content(external),'BACKUP_NOT_REGISTERED_OWN_PACKAGE')
    cases['existing_destination_collision']=rejected(lambda:restore_check(args.backup,args.existing_target,
        {'web':15274,'api':18101,'db':55463}),'TARGET_DESCRIPTOR_EXISTS')
    unchanged=before==hashlib.sha256(args.backup.read_bytes()).hexdigest()
    assert unchanged
    write_new(args.report,json.dumps({'status':'COMPROBADO','backup_id':manifest['id'],'cases':cases,
        'native_windows_dpapi':True,'derived_from_actual_backup':True,'original_backup_unchanged':unchanged,
        'original_cipher_sha256':before,'docker_or_active_writes':False},indent=2).encode())
    print(json.dumps({'status':'COMPROBADO','negative_cases':len(cases),'original_backup_unchanged':unchanged}))


if __name__=='__main__': main()
