"""Offline release checks; no PLAXIS connection or calculation."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import os

ROOT = Path(__file__).resolve().parents[1]

def main():
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    commands = [
        (ROOT/'excavation-builder', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v']),
        (ROOT/'excel-import', [sys.executable, '-m', 'unittest', 'discover', '-s', '.', '-p', 'test_excel_to_plaxis.py', '-v'])]
    for cwd, command in commands:
        result = subprocess.run(command, cwd=str(cwd), env=env)
        if result.returncode:
            return result.returncode
    with tempfile.TemporaryDirectory(prefix='plaxis_release_') as d:
        out = Path(d)/'smoke.p2dx'
        result = subprocess.run([sys.executable, str(ROOT/'excavation-builder/builder.py'),
                                 '--excel', str(ROOT/'excavation-builder/基坑建模模板.xlsx'),
                                 '--output', str(out), '--validate-only'], env=env)
        if result.returncode:
            return result.returncode
        report = json.loads((Path(d)/'smoke_builder/report.json').read_text(encoding='utf-8'))
        if out.exists() or report['status'] != 'input_validated':
            raise RuntimeError('Unexpected smoke result')
    print('Offline checks passed. No PLAXIS model created or calculated.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
