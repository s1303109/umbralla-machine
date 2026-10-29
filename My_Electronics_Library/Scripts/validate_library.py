#!/usr/bin/env python3
"""Validate active libraries using Python and an actual KiCad 8 CLI."""
import argparse
import collections
import csv
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from sexpr import child, children, parse, properties, walk

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--kicad-cli', default=os.environ.get('KICAD_CLI', 'kicad-cli'))
    args = ap.parse_args()
    errors, warnings, checks, commands, pinrows = [], [], [], [], []
    symtables = parse((ROOT / 'Config/sym-lib-table.example').read_text())
    fptables = parse((ROOT / 'Config/fp-lib-table.example').read_text())
    libs = {str(child(n, 'name')[1]): str(child(n, 'uri')[1]) for n in children(symtables, 'lib')}
    fplibs = {str(child(n, 'name')[1]): str(child(n, 'uri')[1]) for n in children(fptables, 'lib')}
    expand = lambda p: ROOT / p.replace('${MY_KICAD_LIB_DIR}/', '')
    fps = {}
    repeated = json.loads((ROOT / 'Sources/repeated_pads.json').read_text())
    for nick, path in fplibs.items():
        for file in sorted(expand(path).glob('*.kicad_mod')):
            f = parse(file.read_text(encoding='utf-8'))
            if int(child(f, 'version')[1]) > 20240108:
                errors.append(f'Newer-than-KiCad8 footprint: {file.name}')
            if str(f[1]) != file.stem:
                errors.append(f'Footprint name differs from filename: {file.name}')
            key = nick + ':' + str(f[1])
            if key in fps:
                errors.append(f'Duplicate footprint: {key}')
            fps[key] = f
            counts = collections.Counter(str(p[1]) for p in children(f, 'pad') if p[1])
            actual = {n: c for n, c in counts.items() if c > 1}
            if actual != repeated.get(str(f[1]), {}):
                errors.append(f'Unexpected repeated pads: {key}: {actual}')
            for model in children(f, 'model'):
                path = str(model[1])
                if not path.startswith('${MY_KICAD_LIB_DIR}/') or not expand(path).is_file():
                    errors.append(f'Missing/nonportable model: {key}: {path}')
    symbols = {}
    base = json.loads((ROOT / 'Sources/espressif_pin_baseline.json').read_text())
    fixes = json.loads((ROOT / 'Sources/symbol_corrections.json').read_text())
    spec = json.loads((ROOT / 'Sources/yd_esp32_s3.json').read_text())
    external = {item['category']+'_Custom:'+item['symbol']:item for item in json.loads((ROOT/'Sources/external_parts.json').read_text())}
    for nick, path in libs.items():
        root = parse(expand(path).read_text(encoding='utf-8'))
        if int(child(root, 'version')[1]) > 20231120:
            errors.append(f'Newer-than-KiCad8 symbol library: {nick}')
        for s in children(root, 'symbol'):
            key = nick + ':' + str(s[1])
            if key in symbols:
                errors.append(f'Duplicate symbol: {key}')
            symbols[key] = s
            p = properties(s)
            for field in ('Datasheet', 'Manufacturer', 'MPN', 'Description', 'Source'):
                if not p.get(field):
                    if field=='Datasheet' and key in external and external[key]['status']!='Verified':
                        warnings.append(f'尚無完整模組原廠資料表：{key}；僅依所列照片／接線資料建介面。')
                    else:
                        errors.append(f'Missing {field}: {key}')
            pins = [{'number': str(child(v, 'number')[1]), 'name': str(child(v, 'name')[1]), 'type': str(v[1])} for v in walk(s, 'pin')]
            counts = collections.Counter(v['number'] for v in pins)
            if any(v > 1 for v in counts.values()):
                errors.append(f'Duplicate symbol pins: {key}')
            if any('hide' in v[1:] for v in walk(s, 'pin')):
                errors.append(f'Unexpected hidden pin: {key}')
            expected = None
            if key in external:
                expected = [{'number':num,'name':label,'type':typ} for num,label,typ,side in external[key]['pins']]
            if str(s[1]) in base:
                expected = base[str(s[1])] + [{'number': n, 'name': label, 'type': 'no_connect'} for n, label in fixes['additions'].get(str(s[1]), {}).items()]
            elif str(s[1]) == 'ESP32-S3-WROOM-1-N16R8':
                expected = [dict(x) for x in base['ESP32-S3-WROOM-1']]
                for v in expected:
                    if v['number'] in ('28', '29', '30'):
                        v.update(type='no_connect', name='RESERVED_PSRAM/IO' + {'28':'35', '29':'36', '30':'37'}[v['number']])
            elif str(s[1]) == spec['symbol']:
                expected = []
                for side, names in [('J1', spec['left']), ('J2', spec['right'])]:
                    for i, label in enumerate(names, 1):
                        typ = 'passive' if label in ('3V3','5V','GND') else 'input' if label == 'EN' else 'no_connect' if 'RESERVED' in label else 'bidirectional'
                        expected.append({'number': f'{side}.{i}', 'name':label, 'type':typ})
            if expected is not None and sorted(pins, key=lambda x:x['number']) != sorted(expected, key=lambda x:x['number']):
                errors.append(f'Pin baseline differs: {key}')
            ref = p.get('Footprint', '')
            pads = set()
            if ref:
                if ref not in fps:
                    errors.append(f'Unknown footprint: {key}: {ref}')
                else:
                    pads = {str(v[1]) for v in children(fps[ref], 'pad') if v[1]}
                    if pads != set(counts):
                        errors.append(f'Pin/pad mismatch: {key}: pins-only={sorted(set(counts)-pads)}, pads-only={sorted(pads-set(counts))}')
            elif child(s, 'on_board', ['', 'yes'])[1] != 'no':
                errors.append(f'PCB part has no footprint: {key}')
            else:
                warnings.append(f'外接接線介面不指定整個模組的 PCB 封裝：{key}；載板連接器仍需另選。')
            for v in pins:
                pinrows.append({'Symbol':key, **v, 'Footprint':ref, 'Pad exists': 'yes' if v['number'] in pads else 'not applicable' if not ref else 'NO'})
    # Independently check exact carrier coordinates against the nominal OEM facts.
    yd = fps['ESP32_Custom:' + spec['footprint']]
    for pad in children(yd, 'pad'):
        side, number = str(pad[1]).split('.')
        at = child(pad, 'at')
        expected_x = -12.7 if side == 'J1' else 12.7
        expected_y = (int(number)-1)*2.54
        if abs(float(at[1])-expected_x) > 1e-6 or abs(float(at[2])-expected_y) > 1e-6:
            errors.append(f'YD board pad coordinate mismatch: {pad[1]}')
    checks.append(f'Python 已解析 {len(symbols)} 個有效符號、{len(fps)} 個封裝。')
    checks.append('腳位名稱、電氣類型及編號已與來源基準、修訂紀錄、外接端子清單比對；有 PCB 封裝者另核對 Pin/Pad 集合。')
    checks.append('重複焊盤依上游露銅散熱焊盤清單核對；不是一律當成重複錯誤。')
    checks.append('所有保留的模型引用均存在，且使用 MY_KICAD_LIB_DIR；缺少的上游模型已移除引用並明列。')

    with tempfile.TemporaryDirectory(prefix='my-kicad8-config-') as config:
        env = dict(os.environ, KICAD_CONFIG_HOME=config, MY_KICAD_LIB_DIR=str(ROOT))
        def run(argv):
            r = subprocess.run([args.kicad_cli] + argv, env=env, text=True, capture_output=True)
            commands.append({'argv':[args.kicad_cli]+argv, 'returncode':r.returncode, 'stdout':r.stdout, 'stderr':r.stderr})
            if r.returncode:
                errors.append('KiCad CLI failed: ' + ' '.join(argv))
            return r
        try:
            v = run(['version']).stdout.strip()
            if not re.match(r'^8\.', v):
                errors.append(f'Need real KiCad 8 CLI; got {v!r}')
            else:
                # A fresh directory prevents stale SVGs hiding a missing export.
                with tempfile.TemporaryDirectory(prefix='my-kicad8-export-') as temp:
                    temp = Path(temp)
                    for nick, path in libs.items():
                        out = temp / 'Symbols' / nick
                        out.mkdir(parents=True)
                        run(['sym','export','svg','-o',str(out),str(expand(path))])
                        expected_count = len(children(parse(expand(path).read_text()), 'symbol'))
                        if len(list(out.glob('*.svg'))) != expected_count:
                            errors.append(f'SVG count mismatch for {nick}')
                    for nick, path in fplibs.items():
                        out = temp / 'Footprints' / nick
                        out.mkdir(parents=True)
                        run(['fp','export','svg','-o',str(out),'-l','F.Cu,F.SilkS,F.Fab,F.CrtYd,Dwgs.User',str(expand(path))])
                        if len(list(out.glob('*.svg'))) != len(list(expand(path).glob('*.kicad_mod'))):
                            errors.append(f'Footprint SVG count mismatch for {nick}')
                    for svg in temp.rglob('*.svg'):
                        ET.parse(svg)
                    previews=ROOT/'Reports/Previews'
                    if previews.exists():
                        history=ROOT/'.history/validation_previews';history.mkdir(parents=True,exist_ok=True)
                        backup=Path(tempfile.mkdtemp(prefix='before-',dir=history))/'Previews'
                        shutil.move(str(previews),str(backup))
                    shutil.copytree(temp, previews)
                checks.append(f'實際 KiCad CLI {v} 已匯出全部有效符號與封裝 SVG，並解析 SVG XML。')
                fixture = ROOT/'Examples/Library_Loading_Test.kicad_sch'
                if fixture.exists():
                    out=ROOT/'Reports/Fixture';out.mkdir(parents=True,exist_ok=True)
                    run(['sch','export','svg','-e','-o',str(out),str(fixture)])
                    netlist=out/'Library_Loading_Test.xml'
                    run(['sch','export','netlist','--format','kicadxml','-o',str(netlist),str(fixture)])
                    if netlist.exists():
                        net=ET.parse(netlist)
                        refs={x.attrib['ref']:x.findtext('footprint') for x in net.findall('./components/comp')}
                        for ref,name in [('A1',spec['symbol']),('U1','ESP32-S3-WROOM-1-N16R8')]:
                            if refs.get(ref)!=properties(symbols['ESP32_Custom:'+name])['Footprint']:
                                errors.append(f'範例網表封裝對應錯誤：{ref}')
                    erc=out/'erc.rpt'
                    run(['sch','erc','-o',str(erc),str(fixture)])
                    if erc.exists() and not re.search(r'Errors 0\s+Warnings 0', erc.read_text(errors='replace')):
                        errors.append('載入測試專案 ERC 仍有錯誤或警告；詳見 Reports/Fixture/erc.rpt。')
                    step=out/'Library_Loading_Test.step'
                    run(['pcb','export','step','-f','-o',str(step),str(fixture.with_suffix('.kicad_pcb'))])
                    if not step.exists() or 'U1' not in step.read_text(errors='replace'):
                        errors.append('範例 STEP 未找到預期的 U1 模組。')
                    checks.append('載入測試專案的原理圖 SVG、網表、ERC 與 PCB STEP 已實際執行；網表 A1/U1 分別對應開發板與裸模組封裝。僅測到該 WROOM STEP 的讀取，不代表全部 33 個模型已人工核對。')
        except (OSError, subprocess.SubprocessError) as ex:
            errors.append(f'KiCad CLI unavailable: {ex}')
            v = 'unavailable'
    with (ROOT/'Reports/pin_pad_map.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['Symbol','number','name','type','Footprint','Pad exists'])
        w.writeheader();w.writerows(pinrows)
    with (ROOT/'Reports/component_list.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    for row in rows:
        if row['Symbol Name'] and row['Symbol Library']+':'+row['Symbol Name'] not in symbols:
            errors.append('Inventory symbol missing: '+row['Component ID'])
        if row['Verification Status'] not in ('Verified','Partially Verified','Pending','Not Applicable'):
            errors.append('Invalid verification status: '+row['Component ID'])
    if len({x['Component ID'] for x in rows})!=len(rows):
        errors.append('Duplicate Component IDs in inventory')
    missing=json.loads((ROOT/'Reports/missing_models.json').read_text())
    warnings.append(f'{len(missing)} 個上游封裝的指定模型未在固定來源取得；詳見 missing_models.json。')
    warnings.append('YD-ESP32-S3 完整開發板 3D 缺少，使用者已接受；V1.5 逐腳與實際排母尺寸仍待核對。')
    warnings.append('ESP32-WROOM-DA 已保存在 Reports/Quarantine，不註冊供設計使用。')
    warnings.append('尚未驗證 Windows GUI、全部模型的外形與對位、實物裝配或正式電路 ERC/DRC；範例全部腳位未接，不能當成產品電路。')
    inputs={}
    for folder in ['Symbols','Footprints','3D_Models','Config','Sources','Examples','Scripts','LICENSES']:
        for file in sorted((ROOT/folder).rglob('*')):
            if file.is_file() and '__pycache__' not in file.parts and not file.name.endswith(('.lck','.pyc','.bak')):
                inputs[file.relative_to(ROOT).as_posix()]=hashlib.sha256(file.read_bytes()).hexdigest()
    inputs['Reports/component_list.csv']=hashlib.sha256((ROOT/'Reports/component_list.csv').read_bytes()).hexdigest()
    result={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'kicad_cli_version':v,
            'input_sha256':inputs, 'inventory_records':len(rows),'model_files':len(list((ROOT/'3D_Models').rglob('*.STEP')))+len(list((ROOT/'3D_Models').rglob('*.wrl'))),
            'active_symbols':len(symbols),'footprints':len(fps),'errors':errors,'warnings':warnings,'checks':checks,'commands':commands}
    (ROOT/'Reports/validation_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    report='# KiCad 8 初版驗證報告\n\n'+f'CLI：{v}；有效符號 {len(symbols)}、封裝 {len(fps)}、3D 檔案 {result["model_files"]}。自動檢查錯誤 {len(errors)} 項。\n\n'
    report+=f'零件紀錄共 {len(rows)} 筆，包含通用家族、使用者零件、歷史候選與隔離紀錄，不是實物數量。狀態分布：'+str(dict(collections.Counter(x['Verification Status'] for x in rows)))+'。\n\n'
    report+='## 自動檢查\n\n'+'\n'.join('- '+x for x in checks)+'\n\n'
    report+='## 錯誤\n\n'+ ('\n'.join('- '+x for x in errors) or '本次自動檢查未發現錯誤。')+'\n\n'
    report+='## 人工核對與已知缺項\n\n'+'\n'.join('- '+x for x in warnings)+'\n\n'
    report+='自動通過僅證明目前檔案能被 KiCad 8 解析及所列結構一致，不能取代實物、資料表、ERC/DRC 或電氣安全驗收。\n'
    (ROOT/'Reports/validation_report.md').write_text(report,encoding='utf-8')
    print(f'{len(symbols)} symbols / {len(fps)} footprints; {len(errors)} errors / {len(warnings)} review items; KiCad {v}')
    raise SystemExit(1 if errors else 0)


if __name__=='__main__':
    main()
