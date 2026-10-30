#!/usr/bin/env python3
from pathlib import Path
import json,sys,time
import pcbnew as P
from grid_router import route_board
ROOT=Path(__file__).resolve().parents[1]
NAME='esp32s3_24v_carrier'
spec=json.loads((ROOT/'routing_spec.json').read_text())
print('Routing functional low-voltage nets on two copper layers...',flush=True)
start=time.monotonic();res=route_board(spec)
(ROOT/'reports/routing_result.json').write_text(json.dumps(res,indent=2)+'\n')
b=P.LoadBoard(str(ROOT/(NAME+'.kicad_pcb')))
nets={str(n.GetNetname()):n for n in b.GetNetsByNetcode().values()}
def pos(x,y):return P.VECTOR2I(P.FromMM(x),P.FromMM(y))
for tr in res['tracks']:
 t=P.PCB_TRACK(b);t.SetStart(pos(tr['x1'],tr['y1']));t.SetEnd(pos(tr['x2'],tr['y2']));t.SetWidth(P.FromMM(tr['width']));t.SetLayer(P.F_Cu if tr['layer']==0 else P.B_Cu);t.SetNet(nets[tr['net']]);b.Add(t)
for via in res['vias']:
 v=P.PCB_VIA(b);v.SetPosition(pos(via['x'],via['y']));v.SetWidth(P.FromMM(via['diameter']));v.SetDrill(P.FromMM(via['drill']));v.SetViaType(P.VIATYPE_THROUGH);v.SetLayerPair(P.F_Cu,P.B_Cu);v.SetNet(nets[via['net']]);b.Add(v)
b.BuildConnectivity();P.SaveBoard(str(ROOT/(NAME+'.kicad_pcb')),b)
print(json.dumps({'elapsed_s':round(time.monotonic()-start,2),'segments':len(res['tracks']),'vias':len(res['vias']),'unrouted':res['unrouted'],'stats':res['stats']}),flush=True)
