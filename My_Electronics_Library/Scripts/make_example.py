#!/usr/bin/env python3
"""Generate a KiCad 8 loading fixture; it is deliberately not a circuit design."""
import copy
import json
from pathlib import Path
import uuid
from sexpr import Quoted as Q, child, children, dumps, parse, properties, walk

ROOT=Path(__file__).resolve().parents[1]


def uid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL,'My_Electronics_Library/loading-fixture/'+name))


def main():
    folder=ROOT/'Examples';folder.mkdir(exist_ok=True)
    source=parse((ROOT/'Symbols/ESP32_Custom.kicad_sym').read_text())
    board_name=json.loads((ROOT/'Sources/yd_esp32_s3.json').read_text())['symbol']
    fixture=[(board_name,'A1',81.28,86.36,65,45),('ESP32-S3-WROOM-1-N16R8','U1',195.58,86.36,115,75)]
    root_id=uid('root')
    sch=['kicad_sch',['version','20231120'],['generator','eeschema'],['uuid',root_id],['paper',Q('A3')]]
    embedded=['lib_symbols']
    for name,*_ in fixture:
        symbol=copy.deepcopy(next(x for x in children(source,'symbol') if x[1]==name))
        symbol[1]=Q('ESP32_Custom:'+name);embedded.append(symbol)
    sch.append(embedded)
    for name,ref,x,y,_,_ in fixture:
        original=next(x for x in children(source,'symbol') if x[1]==name)
        symbol=['symbol',['lib_id',Q('ESP32_Custom:'+name)],['at',str(x),str(y),'0'],['unit','1'],
                ['in_bom','yes'],['on_board','yes'],['dnp','no'],['uuid',uid(ref)]]
        for key,value,py in [('Reference',ref,y-38),('Value',name,y-35),('Footprint',properties(original)['Footprint'],y)]:
            eff=['effects',['font',['size','1.27','1.27']]]
            if key=='Footprint':eff.append(['hide','yes'])
            symbol.append(['property',Q(key),Q(value),['at',str(x),str(py),'0'],eff])
        for pin in walk(original,'pin'):
            num=str(child(pin,'number')[1]);pos=child(pin,'at')
            symbol.append(['pin',Q(num),['uuid',uid(ref+'/pin/'+num)]])
            if pin[1] != 'no_connect':
                sch.append(['no_connect',['at',f'{x+float(pos[1]):.4f}',f'{y-float(pos[2]):.4f}'],['uuid',uid(ref+'/nc/'+num)]])
        symbol.append(['instances',['project',Q('Library_Loading_Test'),['path',Q('/'+root_id),['reference',Q(ref)],['unit','1']]]])
        sch.append(symbol)
    sch.append(['text',Q('LIBRARY LOADING TEST ONLY - ALL PINS UNCONNECTED - NOT FOR FABRICATION'),['at','25','20','0'],
                ['effects',['font',['size','2','2']],['justify','left']],['uuid',uid('warning')]])
    (folder/'Library_Loading_Test.kicad_sch').write_text(dumps(sch)+'\n')

    # pcbnew is optional; the current fixture was produced with the real 8.0.9
    # Python binding. Normal library rebuilds do not depend on this binding.
    try:
        import pcbnew
    except ImportError:
        print('Schematic generated. PCB fixture regeneration needs the KiCad 8 pcbnew Python binding.')
        return
    if not pcbnew.Version().startswith('8.'):
        raise SystemExit('PCB fixture generation requires pcbnew 8.x')
    b=pcbnew.BOARD()
    for name,ref,_,_,x,y in fixture:
        original=next(x for x in children(source,'symbol') if x[1]==name)
        fpname=properties(original)['Footprint'].split(':')[1]
        f=pcbnew.FootprintLoad(str(ROOT/'Footprints/ESP32_Custom.pretty'),fpname)
        if not f:raise RuntimeError('Footprint load failed: '+fpname)
        f.SetFPID(pcbnew.LIB_ID('ESP32_Custom',fpname));f.SetReference(ref);f.SetValue(name)
        b.Add(f);f.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y)))
    for x1,y1,x2,y2 in [(45,25,145,25),(145,25,145,120),(145,120,45,120),(45,120,45,25)]:
        edge=pcbnew.PCB_SHAPE();edge.SetShape(pcbnew.SHAPE_T_SEGMENT);edge.SetLayer(pcbnew.Edge_Cuts)
        edge.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(x1),pcbnew.FromMM(y1)))
        edge.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(x2),pcbnew.FromMM(y2)))
        edge.SetWidth(pcbnew.FromMM(.05));b.Add(edge)
    text=pcbnew.PCB_TEXT(b);text.SetText('LIBRARY TEST ONLY / NOT FOR FABRICATION')
    text.SetLayer(pcbnew.Dwgs_User);text.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(95),pcbnew.FromMM(112)))
    b.Add(text)
    pcbnew.SaveBoard(str(folder/'Library_Loading_Test.kicad_pcb'),b)
    # Project-local tables only: no global configuration is read or written.
    for kind in ['sym','fp']:
        (folder/(kind+'-lib-table')).write_bytes((ROOT/'Config'/(kind+'-lib-table.example')).read_bytes())
    (folder/'Library_Loading_Test.kicad_pro').write_text(json.dumps({'meta':{'filename':'Library_Loading_Test.kicad_pro','version':1}},indent=2)+'\n')
    print('Generated schematic and board with two distinct physical forms; no functional nets.')


if __name__=='__main__':main()
