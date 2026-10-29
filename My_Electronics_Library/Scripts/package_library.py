#!/usr/bin/env python3
"""Package only after the user explicitly ends collection and authorizes packaging."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--confirm-collection-complete',action='store_true',help='Use only after the user explicitly says collection is complete / start packaging')
    args=ap.parse_args()
    if not args.confirm_collection_complete:
        raise SystemExit('Not packaged: explicit user confirmation of completed collection is required.')
    path=ROOT/'Reports/validation_results.json'
    if not path.exists():raise SystemExit('Run validate_library.py first.')
    report=json.loads(path.read_text(encoding='utf-8'))
    if report['errors'] or not report['kicad_cli_version'].startswith('8.'):
        raise SystemExit('Not packaged: KiCad 8 validation has unresolved errors.')
    for rel,expected in report['input_sha256'].items():
        f=ROOT/rel
        if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest()!=expected:
            raise SystemExit('Validation is stale; rerun it after changing: '+rel)
    progress_path=ROOT/'Reports/progress.json'
    progress=json.loads(progress_path.read_text(encoding='utf-8'))
    progress['interaction']['final_packaging_authorized']=True
    progress['interaction']['collection_closed']=True
    progress['packaging_validation_utc']=report['utc']
    progress['next_action']='依安裝教學註冊；仍待確認的硬體資料保持原狀態，不因打包而宣稱 Verified。'
    progress_path.write_text(json.dumps(progress,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    destination=ROOT.parent/'dist'/'My_Electronics_KiCad8_Library.zip'
    destination.parent.mkdir(parents=True,exist_ok=True)
    staging=destination.with_suffix('.zip.tmp')
    with zipfile.ZipFile(staging,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for f in sorted(ROOT.rglob('*')):
            rel=f.relative_to(ROOT)
            if not f.is_file() or any(x.startswith('.') or x=='__pycache__' for x in rel.parts) or f.suffix in ('.pyc','.lck','.bak'):
                continue
            info=zipfile.ZipInfo('My_Electronics_Library/'+rel.as_posix(),date_time=(2026,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,f.read_bytes())
    with zipfile.ZipFile(staging) as z:
        if z.testzip() is not None:raise SystemExit('ZIP integrity test failed.')
        names=set(z.namelist())
        for required in ['README.md','INSTALL_GUIDE_zh-TW.md','Config/sym-lib-table.example','Config/fp-lib-table.example','Scripts/build_library.py','Scripts/validate_library.py','Reports/validation_report.md']:
            if 'My_Electronics_Library/'+required not in names:raise SystemExit('ZIP missing '+required)
    staging.replace(destination)
    print(destination)


if __name__=='__main__':main()
