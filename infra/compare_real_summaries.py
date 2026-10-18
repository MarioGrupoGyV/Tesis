"""Compara dos resúmenes agregados de la corrida real (los que escribe `run_real_study.py --public-summary`; no llevan códigos ni nombres).

    py -3.12 infra/compare_real_summaries.py <referencia.json> <nuevo.json>

Imprime IDENTICOS o la lista de rutas que difieren (con los valores agregados). Salida 0 si son idénticos, 1 si difieren, 2 si no se pudo leer un archivo.
Sirve para comprobar que cargar los mismos CSV en otra instalación da exactamente los mismos resultados (conteos, distribución, comparación de modelos,
detección validada, PDER/CRA con verificación SQL, alertas retrospectivas y modelo activo).
"""
import json
from pathlib import Path
import sys

LIMIT = 25


def differences(reference, new, path='$'):
    """Rutas JSON donde difieren (lista vacía si son idénticos)."""
    if isinstance(reference, dict) and isinstance(new, dict):
        found = []
        for key in sorted(set(reference) | set(new)):
            if key not in reference or key not in new:
                found.append((f'{path}.{key}', 'AUSENTE' if key not in reference else reference[key], 'AUSENTE' if key not in new else new[key]))
            else:
                found.extend(differences(reference[key], new[key], f'{path}.{key}'))
        return found
    if isinstance(reference, list) and isinstance(new, list):
        if len(reference) != len(new):
            return [(f'{path}[len]', len(reference), len(new))]
        return [item for index, (a, b) in enumerate(zip(reference, new)) for item in differences(a, b, f'{path}[{index}]')]
    return [] if reference == new and type(reference) is type(new) else [(path, reference, new)]


def main(argv=None):
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 2:
        print('Uso: compare_real_summaries.py <referencia.json> <nuevo.json>')
        return 2
    try:
        reference, new = (json.loads(Path(item).read_text(encoding='utf-8')) for item in arguments)
    except (OSError, ValueError):
        print('SUMMARY_UNREADABLE')
        return 2
    found = differences(reference, new)
    if not found:
        print('IDENTICOS')
        return 0
    print(f'DIFIEREN en {len(found)} rutas:')
    for path, a, b in found[:LIMIT]:
        print(f'  {path}: referencia={str(a)[:60]} nuevo={str(b)[:60]}')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
