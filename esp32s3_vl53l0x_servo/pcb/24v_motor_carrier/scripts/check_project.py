#!/usr/bin/env python3
"""Check independent native KiCad reports/netlists against the GPIO contract."""
from pathlib import Path
import csv,hashlib,json,sys,xml.etree.ElementTree as E
sys.path.insert(0,str(Path(__file__).resolve().parent))
from sexpr import parse,child,children
ROOT=Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'design_contract.json').read_text());r=ROOT/'reports'
actual={}
for n in E.parse(r/'netlist.xml').getroot().find('nets'):
 if n.get('name').startswith('unconnected-'):continue
 actual[n.get('name')]=sorted((node.get('ref'),node.get('pin')) for node in n)
expected={n:sorted(tuple(t) for t in terms) for n,terms in d['nets'].items()}
assert actual==expected,'Native schematic netlist differs from contract'
b=parse((ROOT/'esp32s3_24v_carrier.kicad_pcb').read_text());pads={}
for fp in children(b,'footprint'):
 ref=next(p[2] for p in children(fp,'property') if p[1]=='Reference')
 for p in children(fp,'pad'):
  net=child(p,'net');pads[(str(ref),str(p[1]))]=str(net[2]) if net else None
for ref,c in d['components'].items():
 for pin,net in c['pins'].items():
  got=pads[(ref,pin)]
  assert got==net if net else (got is None or got.startswith('unconnected-')),(ref,pin,got,net)
assert len(actual)==33
assert all(not any(s in n for s in ['AC_L','AC_N','110V','PE_MAINS']) for n in actual)
assert actual['K2_IN_L']==sorted([('J7','3'),('Q2','C'),('R3','2')])
assert actual['HC_ECHO_DIV']==sorted([('A1','J1.6'),('R4','2'),('R5','1')])
assert actual['MOTOR_SW24']==sorted([('J8','2'),('J9','1'),('D1','K')])
erc=json.loads((r/'erc.json').read_text());ercv=[v for s in erc['sheets'] for v in s['violations']]
drc=json.loads((r/'drc.json').read_text());assert not ercv,ercv
for key in ['violations','unconnected_items','schematic_parity']:assert not drc[key],(key,drc[key])
route=json.loads((r/'routing_result.json').read_text());assert not route['unrouted']
firmware={};fw=ROOT.parents[1]
for path,meta in d['sources'].items():
 if not path.startswith('main/'):continue
 p=fw/path
 if p.exists():
  h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==meta['sha256'],path;firmware[path]=h
with (ROOT/'connector_pinout.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['Reference','Pad','Signal','ModuleLabel','HardwareStatus'])
 for ref,c in d['components'].items():
  if not ref.startswith('J'):continue
  for pin,net in c['pins'].items():w.writerow([ref,pin,net or 'NC',c.get('pin_labels',{}).get(pin,''),c.get('verification',c.get('assembly_default','project-defined; verify actual part'))])
with (ROOT/'wiring_matrix.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['Net','Reference','Pad'])
 for net,pts in sorted(actual.items()):
  for ref,pin in pts:w.writerow([net,ref,pin])
layout=json.loads((ROOT/'component_layout.json').read_text())
with (ROOT/'bom.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['Reference','Value','Kind','Footprint','Verification'])
 for ref,c in layout['components'].items():w.writerow([ref,c['value'],c['kind'],c['footprint'],d['components'].get(ref,{}).get('verification','Generic candidate; verify hardware/mechanics')])
result={'status':'DRAFT_NOT_FOR_FABRICATION','kicad_version':drc['kicad_version'],'functional_nets':len(actual),'firmware_used_gpio':len(d['esp32']['firmware_used_gpio']),'footprints':len(layout['components']),'board_bbox_mm':layout['board_bbox_mm'],'routed_segments':len(children(b,'segment')),'vias':len(children(b,'via')),'ground_zones':len(children(b,'zone')),'erc_violations':len(ercv),'drc_violations':len(drc['violations']),'unconnected_items':len(drc['unconnected_items']),'schematic_parity_issues':len(drc['schematic_parity']),'rules_excluded':0,'netlist_exact_match':True,'pcb_pad_net_match':True,'firmware_unchanged_sha256':firmware,'hardware_verified':False,'manufacturing_files_generated':False,'pending_hardware_checks':d['pending_before_fabrication']}
(r/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['pending_hardware_checks','firmware_unchanged_sha256']},ensure_ascii=False))
