"""CLI interna autenticada. Secretos solo por stdin del launcher Windows."""
import argparse
import base64
import json
import re
import sys
from pydantic import ValidationError
from uuid import UUID,uuid4
from sqlalchemy import select
from app.core.config import Settings
from app.core.database import Database
from app.core.errors import AppError
from app.core.security import password_verify
from app.models.s1 import AppUser
from app.services import synthetic_study as service
from app.ml.features import MLDiagnostic


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['generate','compare','register','activate','export-csv','status'])
    args=parser.parse_args()
    settings=Settings()
    database=Database(settings)
    try:
        payload=json.loads(sys.stdin.read(1000000))
        with database.session_factory() as db:
            actor=db.scalar(select(AppUser).where(AppUser.email==payload['email'],AppUser.role=='ADMIN',AppUser.is_active.is_(True)))
            if actor is None or not password_verify(payload['password'],actor.password_hash):
                raise AppError(403,'FORBIDDEN','Se requiere ADMIN autenticado.')
            del payload['password']
            request_id=uuid4()
            if args.command=='generate':
                from app.ml.synthetic import load_config,SyntheticStudyConfig
                config=load_config()
                if payload.get('config'):
                    config=SyntheticStudyConfig.model_validate(payload['config'])
                if payload.get('student_count') is not None:
                    config=SyntheticStudyConfig.model_validate({**config.model_dump(mode='json'),'student_count':payload['student_count']})
                record,reused=service.prepare(db,actor,settings,config,payload.get('seed',1729),
                    UUID(payload['tutor_id']) if payload.get('tutor_id') else None,request_id)
                result={'study_id':str(record.id),'period_id':str(record.period_id),'data_origin':'SYNTHETIC',
                    'scope':'SYNTHETIC_STUDY','csv_sha256':record.csv_sha256,'manifest':service.public_generation(record.manifest),'reused':reused}
            elif args.command=='status':
                from app.services.processing_policy import processing_status
                result=processing_status(db,actor,settings).model_dump(mode='json',by_alias=True)
            elif args.command=='activate':
                record,reused=service.activate_model(db,actor,settings,UUID(payload['model_id']),request_id)
                result={'model_id':str(record.id),'data_origin':record.data_origin,'is_active':record.is_active,
                    'approval_kind':'TECHNICAL_SIMULATION','reused':reused}
            else:
                study_id=UUID(payload['study_id'])
                if args.command=='export-csv':
                    study=service.get_study(db,study_id)
                    _,_,content=service.validate_registered(db,settings,study)
                    result={'period_id':str(study.period_id),'csv_base64':base64.b64encode(content).decode()}
                elif args.command=='compare':
                    result=service.compare_registered(db,actor,settings,study_id,request_id)
                else:
                    record,reused=service.register_model(db,actor,settings,study_id,payload.get('algorithm'),request_id)
                    result={'model_id':str(record.id),'algorithm':record.algorithm,'status':record.status,
                        'data_origin':record.data_origin,'is_active':record.is_active,'approval_kind':'TECHNICAL_SIMULATION','reused':reused}
            print(json.dumps(result,ensure_ascii=True,allow_nan=False))
    except AppError as error:
        print(json.dumps({'code':error.code,'message':error.message})); return 2
    except MLDiagnostic as error:
        code=str(error)
        if re.fullmatch(r'[A-Z0-9_]{1,80}',code) is None:
            code='ML_DIAGNOSTIC'
        message=('No hay soporte suficiente de observaciones, estudiantes o clases para la evaluación. Revisa el protocolo; no se regeneraron datos.'
                 if code.startswith('INSUFFICIENT_') else
                 'No se completó la operación ML. Revisa integridad, compatibilidad y protocolo; no se publican datos privados.')
        print(json.dumps({'code':code,'message':message})); return 2
    except ValidationError:
        print(json.dumps({'code':'SYNTHETIC_CONFIG_INVALID','message':'Configuración o esquema interno incompatibles. Revisa synthetic-study-v1 y el manual; no se publican valores de entrada.'})); return 2
    except Exception:
        # No trazas con parámetros privados; diagnóstico y rollback al salir de sesión.
        print(json.dumps({'code':'SYNTHETIC_COMMAND_FAILED','message':'No se completó el comando. Revisa configuración, procedencia, compatibilidad y conexión.'})); return 2
    finally:
        database.engine.dispose()
    return 0


if __name__=='__main__':
    raise SystemExit(main())
