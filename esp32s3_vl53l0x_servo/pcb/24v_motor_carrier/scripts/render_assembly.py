#!/usr/bin/env python3
"""Readable assembly preview derived from actual KiCad pad/body coordinates."""
from pathlib import Path
from html import escape
import pcbnew as P
R=Path(__file__).resolve().parents[1]
b=P.LoadBoard(str(R/'esp32s3_24v_carrier.kicad_pcb'))
S=[]
def text(x,y,s,size=1,fill='#17324d'):
 S.append(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="middle" fill="{fill}">{escape(s)}</text>')
outline=[(30.48,30.48),(121.92,30.48),(121.92,55.88),(118.11,55.88),(118.11,78.74),(121.92,78.74),(121.92,106.68),(30.48,106.68)]
S.append('<polygon points="'+' '.join(f'{x},{y}' for x,y in outline)+'" fill="#eef7ee" stroke="#2b7355" stroke-width=".25"/>')
labels={'A1':'A1 ESP32-S3 socket','J1':'J1 DC INPUT','J2':'J2 LCD CABLE','J3':'J3 ToF1','J4':'J4 ToF2','J5':'J5 HC-SR04','J6':'J6 K1 CTRL','J7':'J7 K2 CTRL','J8':'J8 K2 COM/NO','J9':'J9 MOTOR','D1':'D1 1N5408','Q2':'Q2 E / B / C','JP1':'JP1 EXT 5V','JP2':'JP2 VIN1','JP3':'JP3 VIN2','R1':'R1 1k5','R2':'R2 47k','R3':'R3 4k7','R4':'R4 10k','R5':'R5 20k'}
for f in b.GetFootprints():
 ref=f.GetReference()
 if ref.startswith('H'):continue
 items=[x for x in f.GraphicalItems() if x.GetLayer()==P.F_CrtYd]
 if not items:continue
 boxes=[x.GetBoundingBox() for x in items]
 x0=min(P.ToMM(x.GetX()) for x in boxes);y0=min(P.ToMM(x.GetY()) for x in boxes)
 x1=max(P.ToMM(x.GetRight()) for x in boxes);y1=max(P.ToMM(x.GetBottom()) for x in boxes)
 S.append(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" rx=".3" fill="{ "#dfeaff" if ref=="A1" else "#fff"}" stroke="#7193a4" stroke-width=".12"/>')
 # Board-side silk references are kept in the real PCB; this explanatory label
 # is placed at the body center, away from its pads where possible.
 if ref=='A1':
  text((x0+x1)/2,(y0+y1)/2,'A1 ESP32-S3 SOCKET',1.6)
  text((x0+x1)/2,(y0+y1)/2+3,'USB LEFT  |  ANTENNA RIGHT',.9)
 elif ref in ['D1','J1','J8','J9']:
  text((x0+x1)/2,y1-1,labels[ref],.8)
 elif ref.startswith('R'):
  text((x0+x1)/2,y0-.6,labels[ref],.8)
 else:
  text((x0+x1)/2,y0-.6,labels.get(ref,ref),.8)
 for p in f.Pads():
  xy=p.GetPosition();sz=p.GetSize();px=P.ToMM(xy.x);py=P.ToMM(xy.y);w=P.ToMM(sz.x);h=P.ToMM(sz.y);dr=P.ToMM(p.GetDrillSize().x)
  if p.GetShape()==P.PAD_SHAPE_RECT:
   S.append(f'<rect x="{px-w/2}" y="{py-h/2}" width="{w}" height="{h}" fill="#e7b74a" stroke="#947025" stroke-width=".1"/>')
  else:S.append(f'<circle cx="{px}" cy="{py}" r="{w/2}" fill="#e7b74a" stroke="#947025" stroke-width=".1"/>')
  S.append(f'<circle cx="{px}" cy="{py}" r="{dr/2}" fill="white"/>')
  if ref!='A1':text(px,py+.2,p.GetNumber(),.65,'#102e3b')
for f in b.GetFootprints():
 if f.GetReference().startswith('H'):
  p=next(iter(f.Pads()));xy=p.GetPosition();x=P.ToMM(xy.x);y=P.ToMM(xy.y)
  S.append(f'<circle cx="{x}" cy="{y}" r="1.35" fill="white" stroke="#678575" stroke-width=".12"/>')
text(75,28,'ACTUAL PCB PLACEMENT / DRAFT - VERIFY HARDWARE',1.3)
text(76,109,'91.44 x 76.20 mm bounding box / connector pin order is project-defined',1)
text(44,66,'USB CLEAR',.9)
text(125,67,'RF',1)
svg='<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="1450" viewBox="26 25 102 86"><style>text{font-family:DejaVu Sans,sans-serif;font-weight:600}</style><rect x="26" y="25" width="102" height="86" fill="#fafcfe"/>'+''.join(S)+'</svg>'
p=R/'preview/placement.svg'
if p.exists() and not (R/'preview/placement_native.svg').exists():p.replace(R/'preview/placement_native.svg')
p.write_text(svg)
print('Assembly view rendered from actual footprint and pad geometry.')
