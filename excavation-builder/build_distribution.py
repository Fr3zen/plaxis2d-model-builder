"""Compatibility entry point for the public, model-free release packager."""
from pathlib import Path
import runpy

def package(output, include_models=False):
    if include_models:
        raise ValueError('Public releases do not include engineering models')
    functions = runpy.run_path(str(Path(__file__).resolve().parents[1]/'tools/package_release.py'))
    functions['package'](output)
    return Path(output)
