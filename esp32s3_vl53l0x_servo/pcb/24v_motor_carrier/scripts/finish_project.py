#!/usr/bin/env python3
"""Add the ground reference and readable assembly markings after routing."""
from pathlib import Path
import json,pcbnew as P
ROOT=Path(__file__).resolve().parents[1];NAME='esp32s3_24v_carrier'
def pos(x,y):return P.VECTOR2I(P.FromMM(x),P.FromMM(y))
b=P.LoadBoard(str(ROOT/(NAME+'.kicad_pcb')))
for f in b.GetFootprints():
 ref=f.GetReference()
 if ref in ['H1','H2']:f.Reference().SetPosition(pos(36.5,33.02 if ref=='H1' else 104.14))
 if ref=='H3':f.Reference().SetPosition(pos(115.8,104.14))
 if ref=='D1':f.Reference().SetPosition(pos(53.34,35.56))
 if ref=='R3':f.Reference().SetPosition(pos(113.03,93.98))
 if ref=='Q2':
  for pad in f.Pads():
   if pad.GetNumber()=='E':pad.SetZoneConnection(P.ZONE_CONNECTION_FULL)
# Update text in place; removing loaded SWIG text objects is not safe in this
# extracted pcbnew build. This also makes the finishing step idempotent.
texts={d.GetText():d for d in b.GetDrawings() if isinstance(d,P.PCB_TEXT)}
for value,x,y in [('E',106.68,91.0),('B',109.22,91.0),('C',111.76,91.0),('K',45.72,32.8),('A',60.96,32.8),('ToF VIN: CHECK / JP OPEN',69,86.5)]:
 t=texts.get(value)
 if t is None:t=P.PCB_TEXT(b);b.Add(t)
 t.SetText(value);t.SetLayer(P.F_SilkS);t.SetPosition(pos(x,y));t.SetTextSize(pos(.8,.8));t.SetTextThickness(P.FromMM(.1))
zone=next((b.GetArea(i) for i in range(b.GetAreaCount()) if b.GetArea(i).GetNetname()=='GND'),None)
if zone is None:
 zone=P.ZONE(b);zone.SetLayer(P.B_Cu);zone.SetNet(b.FindNet('GND'))
 poly=zone.Outline();poly.NewOutline()
 outline=json.loads((ROOT/'component_layout.json').read_text())['outline_mm']
 for x,y in outline:poly.Append(P.FromMM(x),P.FromMM(y))
 b.Add(zone)
zone.SetLocalClearance(P.FromMM(.254));zone.SetMinThickness(P.FromMM(.254));zone.SetPadConnection(P.ZONE_CONNECTION_THERMAL);zone.SetThermalReliefGap(P.FromMM(.254));zone.SetThermalReliefSpokeWidth(P.FromMM(.508));zone.SetIslandRemovalMode(P.ISLAND_REMOVAL_MODE_ALWAYS)
P.ZONE_FILLER(b).Fill(b.Zones());b.BuildConnectivity();P.SaveBoard(str(ROOT/(NAME+'.kicad_pcb')),b)
print('Ground filled and assembly markings updated; no DRC rules excluded.')
