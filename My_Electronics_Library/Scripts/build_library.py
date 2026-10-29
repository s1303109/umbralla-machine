#!/usr/bin/env python3
"""Build pinned KiCad 8 assets; never touches global tables or creates a ZIP."""
import argparse
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import time
import urllib.request
import zipfile

from sexpr import Quoted as Q, child, children, dumps, parse, properties, set_property, walk
from external_assets import collect

ROOT = Path(__file__).resolve().parents[1]
NICK = 'ESP32_Custom'
DS = 'https://documentation.espressif.com/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def effects(size='1.27'):
    return ['effects', ['font', ['size', size, size]]]


def board_symbol(spec):
    name = spec['symbol']
    n = ['symbol', Q(name), ['pin_names', ['offset', '1.016']],
         ['in_bom', 'yes'], ['on_board', 'yes']]
    for key, val, y in [('Reference', 'A', 33.02), ('Value', name, 30.48)]:
        n.append(['property', Q(key), Q(val), ['at', '0', str(y), '0'], effects()])
    for k, v in {'Footprint': NICK + ':' + spec['footprint'], 'Datasheet': spec['source_repository'],
                 'Description': 'Dual USB-C development board; V1.4 source mapping, V1.5 physical audit pending; N16R8',
                 'Manufacturer': spec['manufacturer'], 'MPN': spec['model'],
                 'Verification': spec['status'], 'ki_keywords': 'ESP32 S3 YD N16R8 development board Type-C 44 pins',
                 'Source': spec['source_repository'], 'Mounting': 'Two 1x22 sockets, 25.40 mm row spacing'}.items():
        set_property(n, k, v)
    graphics = ['symbol', Q(name + '_0_1'), ['rectangle', ['start', '-30.48', '27.94'],
                 ['end', '30.48', '-33.02'], ['stroke', ['width', '0.254'], ['type', 'default']],
                 ['fill', ['type', 'background']]]]
    graphics.append(['text', Q('ANTENNA / TOP'), ['at', '0', '24.13', '0'], effects('1.0')])
    graphics.append(['text', Q('USB-C / BOTTOM'), ['at', '0', '-30.48', '0'], effects('1.0')])
    n.append(graphics)
    pins = ['symbol', Q(name + '_1_1')]
    for side, names in [('left', spec['left']), ('right', spec['right'])]:
        for i, label in enumerate(names, 1):
            pnum = ('J1.' if side == 'left' else 'J2.') + str(i)
            # Carrier connector power can be input or output: passive avoids claiming
            # that any rail is an approved simultaneous supply/backfeed path.
            ptype = 'passive' if label in ('3V3', '5V', 'GND') else 'input' if label == 'EN' else 'no_connect' if 'RESERVED' in label else 'bidirectional'
            pins.append(['pin', ptype, 'line', ['at', '-35.56' if side == 'left' else '35.56',
                       f'{24.13 - (i - 1) * 2.54:.2f}', '0' if side == 'left' else '180'],
                       ['length', '5.08'], ['name', Q(label), effects('1.016')],
                       ['number', Q(pnum), effects('1.016')]])
    n.append(pins)
    return n


def board_footprint(spec):
    g = spec['geometry_mm']
    n = ['footprint', Q(spec['footprint']), ['version', '20240108'],
         ['generator', Q('pcbnew')], ['layer', Q('F.Cu')],
         ['descr', Q('YD-ESP32-S3 carrier sockets; OEM nominal dimensions; verify V1.5 and socket before fabrication')],
         ['tags', Q('YD ESP32 S3 2x22 2.54 25.40 socket prototype')], ['attr', 'through_hole']]
    n.append(['fp_text', 'reference', Q('REF**'), ['at', '0', '-10'], ['layer', Q('F.SilkS')], effects('1')])
    n.append(['fp_text', 'value', Q(spec['footprint']), ['at', '0', '58'], ['layer', Q('F.Fab')], effects('1')])
    for layer, x1, y1, x2, y2, width in [('F.Fab', -13.97, -1.91, 13.97, 55.24, .1),
                                        ('F.SilkS', -14.22, -2.16, 14.22, 55.49, .12),
                                        ('F.CrtYd', -14.47, -8.65, 14.47, 55.74, .05),
                                        ('Dwgs.User', -9, -8.15, 9, -1.91, .1)]:
        n.append(['fp_rect', ['start', str(x1), str(y1)], ['end', str(x2), str(y2)],
                  ['stroke', ['width', str(width)], ['type', 'default']], ['fill', 'none'], ['layer', Q(layer)]])
    for text, x, y, layer in [('ANTENNA: FACE BOARD EDGE', 0, -5.08, 'Dwgs.User'),
                               ('USB-C: CHECK PLUG CLEARANCE', 0, 53, 'Dwgs.User'),
                               ('J1.1 / 3V3', -8, -1.2, 'F.SilkS'),
                               ('J2.1 / GND', 8, -1.2, 'F.SilkS')]:
        n.append(['fp_text', 'user', Q(text), ['at', str(x), str(y)], ['layer', Q(layer)], effects('.8')])
    for connector, x in [('J1', -g['row_spacing'] / 2), ('J2', g['row_spacing'] / 2)]:
        for i in range(1, 23):
            n.append(['pad', Q(f'{connector}.{i}'), 'thru_hole', 'rect' if i == 1 else 'circle',
                      ['at', str(x), f'{(i-1)*g["pitch"]:.2f}'],
                      ['size', str(g['carrier_pad_diameter']), str(g['carrier_pad_diameter'])],
                      ['drill', str(g['carrier_finished_hole'])], ['layers', Q('*.Cu'), Q('*.Mask')]])
    # Physical antenna projection only; the final product needs the additional
    # RF clearance prescribed in the module hardware design guide.
    n.append(['zone', ['net', '0'], ['net_name', Q('')], ['layers', Q('*.Cu')],
              ['hatch', 'edge', '.5'], ['connect_pads', ['clearance', '0']], ['min_thickness', '.25'],
              ['keepout', ['tracks', 'not_allowed'], ['vias', 'not_allowed'], ['pads', 'not_allowed'],
               ['copperpour', 'not_allowed'], ['footprints', 'allowed']],
              ['fill', ['thermal_gap', '.3'], ['thermal_bridge_width', '.3']],
              ['polygon', ['pts', ['xy', '-9', '-8.15'], ['xy', '9', '-8.15'],
                           ['xy', '9', '-1.91'], ['xy', '-9', '-1.91']]]])
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cache', type=Path, default=ROOT.parent / '.kicad_library_cache')
    ap.add_argument('--offline', action='store_true')
    ap.add_argument('--confirm-removal', action='store_true', help='Use only after the user explicitly confirms removing existing symbols')
    args = ap.parse_args()
    lock = json.loads((ROOT / 'Sources/upstream_lock.json').read_text(encoding='utf-8'))
    for item in lock['files']:
        path = args.cache / item['cache_path']
        if not path.exists():
            if args.offline:
                raise SystemExit(f'Missing cached source: {path}')
            data = urllib.request.urlopen(item['url'], timeout=120).read()
            if sha(data) != item['sha256']:
                raise SystemExit(f'Download hash mismatch: {item["url"]}')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        if sha(path.read_bytes()) != item['sha256']:
            raise SystemExit(f'Cached source changed: {path}')

    outputs = {}
    source_by_path = {i['cache_path']: i for i in lock['files']}
    z = zipfile.ZipFile(args.cache / 'espressif/3.0.2/espressif-kicad-addon.zip')
    symbols = parse(z.read('symbols/Espressif.kicad_sym').decode())
    fps, fp_sources, missing_models = {}, {}, []
    for name in z.namelist():
        if name.startswith('3dmodels/'):
            outputs['3D_Models/ESP32/' + Path(name).name] = z.read(name)
        elif name.endswith('.kicad_mod'):
            f = parse(z.read(name).decode())
            fps[str(f[1])] = f
            fp_sources[str(f[1])] = 'Espressif 3.0.2'
    for item in lock['files']:
        path = args.cache / item['cache_path']
        if path.suffix == '.kicad_mod':
            f = parse(path.read_text(encoding='utf-8'))
            if f[1] in fps:
                raise SystemExit(f'Footprint collision: {f[1]}')
            fps[str(f[1])] = f
            fp_sources[str(f[1])] = item['url']
        elif path.suffix.lower() in ('.step', '.wrl'):
            outputs['3D_Models/ESP32/' + path.name] = path.read_bytes()
    for f in fps.values():
        for model in list(children(f, 'model')):
            basename = Path(str(model[1])).name
            out = '3D_Models/ESP32/' + basename
            if out not in outputs:
                missing_models.append({'footprint': str(f[1]), 'original_reference': str(model[1])})
                f.remove(model)  # report the missing asset instead of shipping a broken link
            else:
                model[1] = Q('${MY_KICAD_LIB_DIR}/' + out)

    corrections = json.loads((ROOT / 'Sources/symbol_corrections.json').read_text(encoding='utf-8'))
    quarantined = []
    for name, reason in corrections['quarantine'].items():
        s = next(s for s in children(symbols, 'symbol') if s[1] == name)
        fpname = properties(s)['Footprint'].rsplit(':', 1)[-1]
        outputs[f'Reports/Quarantine/{name}.kicad_sym'] = (dumps(['kicad_symbol_lib', ['version', '20231120'], ['generator', Q('kicad_symbol_editor')], s]) + '\n').encode()
        outputs[f'Reports/Quarantine/{fpname}.kicad_mod'] = (dumps(fps[fpname]) + '\n').encode()
        quarantined.append({'name': name, 'reason': reason, 'datasheet': properties(s).get('Datasheet', '')})
        symbols.remove(s)
        del fps[fpname]
        del fp_sources[fpname]
    outputs['Reports/Quarantine/README.md'] = ('# 隔離的上游元件\n\n不註冊供設計使用。\n\n' + '\n'.join('- ' + x['name'] + '：' + x['reason'] for x in quarantined) + '\n').encode()
    for s in children(symbols, 'symbol'):
        for key, value in corrections.get('metadata', {}).get(str(s[1]), {}).items():
            set_property(s, key, value)
        all_pins = list(walk(s, 'pin'))
        hidden = [p for p in all_pins if 'hide' in p[1:]]
        if hidden:
            visible_x = max(float(child(p, 'at')[1]) for p in all_pins) + 15.24
            visible_y = max(float(child(p, 'at')[2]) for p in all_pins)
            for i, pin in enumerate(hidden):
                pin.remove('hide')
                child(pin, 'at')[1:] = [f'{visible_x:.2f}', f'{visible_y-i*2.54:.2f}', '180']
                child(pin, 'length')[1] = '2.54'
        additions = corrections['additions'].get(str(s[1]), {})
        if additions:
            pins = list(walk(s, 'pin'))
            x = max(float(child(p, 'at')[1]) for p in pins) + 15.24
            top = max(float(child(p, 'at')[2]) for p in pins)
            bank = next(sub for sub in children(s, 'symbol') if list(walk(sub, 'pin')))
            for i, (number, label) in enumerate(additions.items()):
                bank.append(['pin', 'no_connect', 'line', ['at', f'{x:.2f}', f'{top-i*2.54:.2f}', '180'],
                             ['length', '2.54'], ['name', Q(label), effects('.762')],
                             ['number', Q(number), effects('.762')]])
    upstream_names = []
    for s in children(symbols, 'symbol'):
        upstream_names.append(str(s[1]))
        ref = properties(s).get('Footprint', '')
        fpname = ref.rsplit(':', 1)[-1]
        if fpname not in fps:
            raise SystemExit(f'Unresolved footprint {ref} in {s[1]}')
        set_property(s, 'Footprint', NICK + ':' + fpname)
        set_property(s, 'Manufacturer', 'Espressif Systems')
        set_property(s, 'MPN', str(s[1]))
        set_property(s, 'Verification', 'Partially Verified')
        set_property(s, 'Source', 'https://github.com/espressif/kicad-libraries/releases/tag/3.0.2')
    # Exact module variant, physically distinct from the user's complete board.
    variant = copy.deepcopy(next(s for s in children(symbols, 'symbol') if s[1] == 'ESP32-S3-WROOM-1'))
    variant[1] = Q('ESP32-S3-WROOM-1-N16R8')
    for sub in children(variant, 'symbol'):
        sub[1] = Q(str(sub[1]).replace('ESP32-S3-WROOM-1_', 'ESP32-S3-WROOM-1-N16R8_'))
    for p in walk(variant, 'pin'):
        if str(child(p, 'number')[1]) in ('28', '29', '30'):
            p[1] = 'no_connect'
            child(p, 'name')[1] = Q('RESERVED_PSRAM/IO' + {'28': '35', '29': '36', '30': '37'}[str(child(p, 'number')[1])])
    for key, value in {'Value': 'ESP32-S3-WROOM-1-N16R8', 'MPN': 'ESP32-S3-WROOM-1-N16R8',
                       'Datasheet': DS, 'Description': 'Bare WROOM module: 16 MB Quad flash / 8 MB Octal PSRAM; IO35/36/37 reserved; not the YD development board',
                       'Source': DS}.items():
        set_property(variant, key, value)
    symbols.append(variant)
    spec = json.loads((ROOT / 'Sources/yd_esp32_s3.json').read_text(encoding='utf-8'))
    symbols.append(board_symbol(spec))
    fps[spec['footprint']] = board_footprint(spec)
    fp_sources[spec['footprint']] = 'Original carrier footprint from OEM mechanical facts; see Sources/yd_esp32_s3.json'
    outputs['Symbols/ESP32_Custom.kicad_sym'] = (dumps(symbols) + '\n').encode()
    for name, f in fps.items():
        outputs['Footprints/ESP32_Custom.pretty/' + name + '.kicad_mod'] = (dumps(f) + '\n').encode()
    outputs['Reports/missing_models.json'] = (json.dumps(missing_models, ensure_ascii=False, indent=2) + '\n').encode()
    outputs['Reports/footprint_sources.json'] = (json.dumps(fp_sources, ensure_ascii=False, indent=2) + '\n').encode()
    outputs['Config/sym-lib-table.example'] = b'(sym_lib_table\n  (lib (name "ESP32_Custom")(type "KiCad")(uri "${MY_KICAD_LIB_DIR}/Symbols/ESP32_Custom.kicad_sym")(options "")(descr "Personal ESP32 library, KiCad 8"))\n)\n'
    outputs['Config/fp-lib-table.example'] = b'(fp_lib_table\n  (lib (name "ESP32_Custom")(type "KiCad")(uri "${MY_KICAD_LIB_DIR}/Footprints/ESP32_Custom.pretty")(options "")(descr "Personal ESP32 footprints, KiCad 8"))\n)\n'
    assets, external_parts, external_nicks = collect(ROOT)
    outputs.update(assets)
    table = parse(outputs['Config/sym-lib-table.example'].decode())
    for nick in sorted(external_nicks):
        table.append(['lib', ['name', Q(nick)], ['type', Q('KiCad')],
                      ['uri', Q('${MY_KICAD_LIB_DIR}/Symbols/' + nick + '.kicad_sym')],
                      ['options', Q('')], ['descr', Q('External functional devices; read verification status')]])
    outputs['Config/sym-lib-table.example'] = (dumps(table) + '\n').encode()
    for src, dst in [('espressif/3.0.2/LICENSE.md', 'Espressif-LICENSE.md'),
                     ('kicad/8.0.9/LICENSE.md', 'KiCad-footprints-LICENSE.md')]:
        outputs['LICENSES/' + dst] = (args.cache / src).read_bytes()
    if 'kicad/8.0.9/models/LICENSE.md' in source_by_path:
        outputs['LICENSES/KiCad-models-LICENSE.md'] = (args.cache / 'kicad/8.0.9/models/LICENSE.md').read_bytes()

    # Preflight ALL writes before mutation; edits to a generated asset are never
    # silently overwritten. A snapshot also records the previous generated version.
    state_path = ROOT / 'Reports/build_state.json'
    old = json.loads(state_path.read_text()) if state_path.exists() else {'files': {}}
    inventory = ROOT / 'Reports/component_list.csv'
    if old.get('inventory_sha256') and sha(inventory.read_bytes()) != old['inventory_sha256']:
        raise SystemExit('Local inventory edit detected; reconcile it with Sources before rebuilding.')
    retired = [f'Footprints/ESP32_Custom.pretty/{name}.kicad_mod' for name in corrections['quarantine']]
    for rel in retired:
        dest = ROOT / rel
        if dest.exists() and sha(dest.read_bytes()) != old['files'].get(rel):
            raise SystemExit(f'Local edit detected in asset to quarantine: {rel}')
    for rel, data in outputs.items():
        dest = ROOT / rel
        if rel.startswith('Symbols/') and rel.endswith('.kicad_sym') and dest.exists():
            before = {str(s[1]) for s in children(parse(dest.read_text()), 'symbol')}
            after = {str(s[1]) for s in children(parse(data.decode()), 'symbol')}
            removed = before-after-set(corrections['quarantine'])
            if removed and not args.confirm_removal:
                raise SystemExit(f'User confirmation required before removing symbols: {sorted(removed)}')
        if dest.exists() and dest.read_bytes() != data:
            expected = old['files'].get(rel)
            if expected is None or sha(dest.read_bytes()) != expected:
                raise SystemExit(f'Local edit detected, merge before rebuilding: {rel}')
    changed = []
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    for rel, data in outputs.items():
        dest = ROOT / rel
        if dest.exists() and dest.read_bytes() == data:
            continue
        if dest.exists():
            backup = ROOT / '.history' / stamp / rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, backup)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        changed.append(rel)
    for rel in retired:
        dest = ROOT / rel
        if dest.exists():
            backup = ROOT / '.history' / stamp / rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dest), str(backup))
    state_path.write_text(json.dumps({'schema_version': 1, 'files': {k: sha(v) for k, v in outputs.items()}}, indent=2) + '\n')

    with inventory.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames, existing = reader.fieldnames, list(reader)
    rows = []
    for i, s in enumerate(children(symbols, 'symbol'), 1):
        p = properties(s)
        board = s[1] == spec['symbol']
        rows.append(dict(zip(fieldnames, [
            'USER-ESP32-001' if board else 'ESP32-' + str(s[1]), 'ESP32 / Development Board' if board else 'ESP32 / Module' if 'WROOM' in s[1] or 'MINI' in s[1] or 'WROVER' in s[1] else 'ESP32 / Development Board' if 'DevKit' in s[1] or 'Saola' in s[1] else 'ESP32 / SoC',
            p.get('Manufacturer', ''), p.get('MPN', str(s[1])), p.get('Description', ''), NICK, str(s[1]), NICK,
            p['Footprint'].split(':')[-1], ';'.join(str(m[1]) for m in children(fps[p['Footprint'].split(':')[-1]], 'model')) or 'Missing',
            p.get('Datasheet', ''), p.get('Source', ''), 'Partially Verified',
            '; '.join(spec['pending']) if board else '官方來源已固定；CLI 與 pin/pad 自動檢查見報告。尚未逐款人工核對 datasheet、3D 外形與裝配；通用系列名不代表完整採購料號。'
        ])))
    for item in quarantined:
        row = {key: '' for key in fieldnames}
        row.update({'Component ID': 'ESP32-' + item['name'], 'Category': 'ESP32 / Quarantined',
                    'Manufacturer': 'Espressif Systems', 'Model': item['name'],
                    'Datasheet URL': item['datasheet'], 'Source URL': 'https://github.com/espressif/kicad-libraries/releases/tag/3.0.2',
                    'Verification Status': 'Pending', 'Notes': item['reason']})
        rows.append(row)
    for item in external_parts:
        row = {key: '' for key in fieldnames}
        row.update({'Component ID':item['id'], 'Category':item['category'], 'Manufacturer':item['manufacturer'],
                    'Model':item['model'], 'Description':item['description'], 'Symbol Library':item['category']+'_Custom',
                    'Symbol Name':item['symbol'], '3D Model':'Not Applicable (external representation)',
                    'Datasheet URL':item['datasheet'], 'Source URL':item['source'], 'Verification Status':item['status'],
                    'Notes':item['source_scope']+' '+item['footprint_status']+' '+item['notes']})
        rows.append(row)
    for item in json.loads((ROOT/'Sources/previous_parts.json').read_text(encoding='utf-8')):
        if item['id'] in {v['id'] for v in external_parts}:
            continue  # a previous pending record is now represented by the same ID
        row = {key: '' for key in fieldnames}
        row.update({'Component ID':item['id'],'Category':item['category'],'Model':item['model'],
                    'Description':item['scope'],'Source URL':item['source'],'Verification Status':item.get('status','Pending'),
                    'Notes':item['pending']})
        rows.append(row)
    managed_ids = {row['Component ID'] for row in rows}
    if len(managed_ids) != len(rows):
        raise SystemExit('Duplicate managed Component IDs; resolve Sources before rebuilding.')
    rows = [row for row in existing if row['Component ID'] not in managed_ids] + rows
    previous_inventory = inventory.read_bytes()
    buf = io.StringIO(newline='')
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader(); writer.writerows(rows)
    next_inventory = ('\ufeff'+buf.getvalue()).encode('utf-8')
    if previous_inventory != next_inventory:
        backup = ROOT/'.history'/stamp/'Reports/component_list.csv'
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(previous_inventory)
    with inventory.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    state = json.loads(state_path.read_text())
    state['inventory_sha256'] = sha(inventory.read_bytes())
    state_path.write_text(json.dumps(state,indent=2)+'\n')
    count = sum(len(children(parse(data.decode()),'symbol')) for rel,data in outputs.items() if rel.startswith('Symbols/') and rel.endswith('.kicad_sym'))
    print(f'Built {count} active symbols, {len(fps)} footprints; {len(changed)} changed assets. No ZIP created.')


if __name__ == '__main__':
    main()
