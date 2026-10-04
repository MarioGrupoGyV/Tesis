"""Comandos operativos sin entrenamiento institucional ni opción de bypass."""
import argparse
import json
from app.core.errors import AppError
from app.services.processing_policy import ml_readiness, require_ml_protocol


def main():
    parser = argparse.ArgumentParser(description='Preparación ML; protocolo institucional pendiente.')
    parser.add_argument('command',choices=['readiness','configuration','compatibility','train','validate'])
    parser.add_argument('--key',help='Identificador interno, nunca ruta de archivo')
    args = parser.parse_args()
    try:
        if args.command=='train':
            require_ml_protocol()
        elif args.command=='readiness':
            print(json.dumps(ml_readiness(),ensure_ascii=True))
        elif args.command=='configuration':
            from app.ml.features import FeatureConfig
            print(json.dumps({'institutional_configuration':None,'required_schema':FeatureConfig.model_json_schema()}))
        elif args.command=='compatibility':
            from app.ml.train import versions, ALGORITHMS
            print(json.dumps({'versions':versions(),'algorithms':ALGORITHMS,'device':'cpu','threads':1,
                              'probabilities_calibrated':False,'institutional_ready':False}))
        else:
            from app.core.config import Settings
            from app.ml.artifacts import ArtifactStore
            if not args.key or Settings().ml_storage_dir is None:
                parser.error('validate requiere --key y almacenamiento ML configurado')
            manifest,_,_ = ArtifactStore(Settings().ml_storage_dir).inspect(args.key)
            print(json.dumps({'compatible':True,'scope':manifest['scope'],'institutional_ready':False}))
    except AppError as error:
        print(json.dumps({'code':error.code,'message':error.message,'readiness':ml_readiness()},ensure_ascii=True))
        return 2
    except ValueError:
        print(json.dumps({'code':'ARTIFACT_UNAVAILABLE_OR_INCOMPATIBLE'}))
        return 2
    return 0


if __name__=='__main__':
    raise SystemExit(main())
