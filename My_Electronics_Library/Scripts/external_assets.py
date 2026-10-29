"""Functional symbols for evidenced external devices, no guessed PCB land patterns."""
import json
from sexpr import Quoted as Q, dumps, set_property


def collect(root):
    parts=json.loads((root/'Sources/external_parts.json').read_text(encoding='utf-8'))
    libraries={}
    for item in parts:
        name=item['symbol'];nick=item['category']+'_Custom'
        per_side={side:sum(p[3]==side for p in item['pins']) for side in ('left','right')}
        top=max(12.7, (max(per_side.values())-1)*2.54+5.08)
        lib=libraries.setdefault(nick,['kicad_symbol_lib',['version','20231120'],['generator',Q('kicad_symbol_editor')]])
        n=['symbol',Q(name),['in_bom','yes'],['on_board','no'],['pin_names',['offset','1.016']]]
        for key,value,y in [('Reference','A',top+5.08),('Value',name,top+2.54)]:
            n.append(['property',Q(key),Q(value),['at','0',str(y),'0'],['effects',['font',['size','1.27','1.27']]]])
        for k,v in {'Footprint':'','Datasheet':item['datasheet'],'Description':item['description'],
                    'Manufacturer':item['manufacturer'],'MPN':item['model'],'Source':item['source'],
                    'SourceScope':item['source_scope'],'Verification':item['status'],
                    'FootprintStatus':item['footprint_status'],'ki_keywords':item['category']+' external module terminal functional'}.items():
            set_property(n,k,v)
        graphics=['symbol',Q(name+'_0_1'),['rectangle',['start','-17.78',str(top)],['end','17.78',str(-top)],
                   ['stroke',['width','.254'],['type','default']],['fill',['type','background']]]]
        graphics.append(['text',Q('WIRE INTERFACE'),['at','0',str(-top+2.54),'0'],['effects',['font',['size','.762','.762']]]])
        n.append(graphics)
        pins=['symbol',Q(name+'_1_1')];counts={'left':0,'right':0}
        for num,label,typ,side in item['pins']:
            i=counts[side];counts[side]+=1
            pins.append(['pin',typ,'line',['at','-22.86' if side=='left' else '22.86',str(top-5.08-i*5.08),'0' if side=='left' else '180'],
                         ['length','5.08'],['name',Q(label),['effects',['font',['size','1.016','1.016']]]],
                         ['number',Q(num),['effects',['font',['size','.762','.762']]]]])
        n.append(pins);lib.append(n)
    return {f'Symbols/{nick}.kicad_sym':(dumps(lib)+'\n').encode() for nick,lib in libraries.items()},parts,libraries.keys()
