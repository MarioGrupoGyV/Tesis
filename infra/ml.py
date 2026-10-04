"""Launcher PowerShell/Windows: ejecución ML en Docker con las versiones fijadas."""
import argparse
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('command',choices=['readiness','configuration','compatibility','train','validate'])
parser.add_argument('--key')
args = parser.parse_args()
command = ['docker','compose','exec','-T','api','python','-m','app.ml.cli',args.command]
if args.key:
    command += ['--key',args.key]
raise SystemExit(subprocess.call(command,cwd=Path(__file__).resolve().parents[1]))
