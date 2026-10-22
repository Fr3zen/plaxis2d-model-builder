"""Package only the public allowlist, with portable paths and content hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = ['README.md', 'LICENSE', 'VERSION', 'requirements.txt', 'CONTRIBUTING.md',
              'SECURITY.md', 'THIRD_PARTY_NOTICES.md', 'CHANGELOG.md', '.gitignore',
              '.gitattributes', 'generate_strata.py', 'example_boreholes.json',
              'RELEASE_VALIDATION.json']
APP_FILES = ['builder.py', 'worker.py', 'build_distribution.py', 'run_builder.cmd', '基坑自动建模.cmd',
             '检查与预览.cmd', '基坑建模模板.xlsx', '使用说明.md', '跨电脑使用与配置修改说明.md']
IMPORT_FILES = ['excel_to_plaxis.py', 'plaxis_worker.py', 'test_excel_to_plaxis.py',
                '导入Excel钻孔.cmd', '钻孔数据模板.xlsx', 'build_template.mjs', '使用说明.md']

def public_files():
    paths = [ROOT / x for x in ROOT_FILES]
    paths += [ROOT/'excavation-builder'/x for x in APP_FILES]
    paths += [ROOT/'excel-import'/x for x in IMPORT_FILES]
    for folder, patterns in [('docs', ['*.md']), ('.github', ['*.md', '*.yml']),
                             ('tools', ['*.py']), ('excavation-builder/pitbuilder', ['*.py', '*.json']),
                             ('excavation-builder/tests', ['*.py'])]:
        for pattern in patterns:
            paths += list((ROOT/folder).rglob(pattern))
    paths += [ROOT/'excavation-builder/authoring/build_template.mjs']
    paths += [ROOT/'excavation-builder/examples'/x for x in
              ['demo.json', 'advanced.json', 'prestress.json', 'four_calculation_types.json']]
    unique = sorted(set(paths), key=lambda p: p.relative_to(ROOT).as_posix())
    for p in unique:
        if not p.is_file():
            raise ValueError('Missing release file: '+str(p.relative_to(ROOT)))
        if p.is_symlink() or ROOT.resolve() not in p.resolve().parents:
            raise ValueError('Unexpected external file')
    return unique

def package(output):
    output = Path(output).resolve()
    if ROOT.resolve() in output.parents:
        raise ValueError('Write ZIP outside the source tree')
    if output.exists():
        raise FileExistsError('Refusing to overwrite an existing release')
    paths = public_files()
    manifest = [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size,
                 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for p in paths:
            info = zipfile.ZipInfo('plaxis-strata/'+p.relative_to(ROOT).as_posix(), (2026,10,22,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, p.read_bytes())
        info = zipfile.ZipInfo('plaxis-strata/MANIFEST.json', (2026,10,22,0,0,0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, json.dumps(manifest, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('ZIP CRC failed')
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix+'.sha256').write_text(digest+'  '+output.name+'\n', encoding='utf-8')
    return {'archive': output.name, 'files': len(paths), 'bytes': output.stat().st_size, 'sha256': digest}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(package(parser.parse_args().output), ensure_ascii=False, indent=2))
