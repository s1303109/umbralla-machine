#!/usr/bin/env python3
"""Build a portable, functional KiCad 8 low-voltage carrier DRAFT.

Design contract is the single source for all schematic pin nets and PCB pad nets.
No mains nets or fabrication output. Footprints with unverified hardware remain
explicitly marked as generic candidates in component documentation.
"""
from pathlib import Path
import copy, json, math, shutil, sys, uuid
ROOT=Path(__file__).resolve().parents[1]
FW=ROOT.parents[1]
sys.path.insert(0,str(Path(__file__).resolve().parent))
from sexpr import Quoted as Q, child, children, dumps, parse, properties, walk
import pcbnew as P
NAME='esp32s3_24v_carrier'
CON=json.loads((ROOT/'design_contract.json').read_text())
LIB='CarrierDraft'
FPDIR=ROOT/(LIB+'.pretty');FPDIR.mkdir(exist_ok=True)
ROOT_ID=str(uuid.uuid5(uuid.NAMESPACE_URL,'esp32-carrier-draft/root'))

def uid(v):return str(uuid.uuid5(uuid.NAMESPACE_URL,'esp32-carrier-draft/'+v))
def mm(v):return P.FromMM(float(v))
def point(x,y):return P.VECTOR2I(mm(x),mm(y))
def eff(size=1,hide=False):return ['effects',['font',['size',str(size),str(size)]]]+([['hide','yes']] if hide else [])
def prop(k,v,x=0,y=0,hide=False):return ['property',Q(k),Q(v),['at',str(x),str(y),'0'],eff(1,hide)]
def symbol_graph(name,pins,kind='connector'):
    n=len(pins);length=2.54*(n-1);top=length/2
    sym=['symbol',Q(name),['pin_names',['offset','1.016']],['in_bom','yes'],['on_board','yes'],prop('Reference','J',0,top+5.08),prop('Value',name,0,top+2.54),prop('Footprint','',0,0,True)]
    graphics=['symbol',Q(name+'_0_1')]; unit=['symbol',Q(name+'_1_1')]
    def line(a,b):return ['polyline',['pts',['xy',str(a[0]),str(a[1])],['xy',str(b[0]),str(b[1])]],['stroke',['width','.254'],['type','default']],['fill',['type','none']]]
    if kind=='resistor':
        graphics.append(['rectangle',['start','-3.81','1.27'],['end','3.81','-1.27'],['stroke',['width','.254'],['type','default']],['fill',['type','none']]])
        specs=[('1','1',-7.62,0,0,3.81),('2','2',7.62,0,180,3.81)]
    elif kind=='npn':
        graphics.append(['circle',['center','1.27','0'],['radius','5.08'],['stroke',['width','.254'],['type','default']],['fill',['type','none']]])
        graphics.extend([line((-1.27,-3.81),(-1.27,3.81)),line((-1.27,2.54),(5.08,6.35)),line((-1.27,-2.54),(5.08,-6.35)),line((5.08,-6.35),(2.3,-5.7)),line((5.08,-6.35),(3.8,-3.9))])
        specs=[('B','B',-7.62,0,0,6.35),('C','C',5.08,7.62,270,1.27),('E','E',5.08,-7.62,90,1.27)]
    elif kind=='diode':
        graphics.extend([line((-1.27,-2.54),(-1.27,2.54)),line((-1.27,0),(2.54,2.54)),line((2.54,2.54),(2.54,-2.54)),line((2.54,-2.54),(-1.27,0))])
        specs=[('K','K',-7.62,0,0,6.35),('A','A',7.62,0,180,5.08)]
    elif kind=='mount':
        graphics.append(['circle',['center','0','0'],['radius','2.54'],['stroke',['width','.254'],['type','default']],['fill',['type','none']]])
        specs=[]
    else:
        graphics.append(['rectangle',['start','0',str(top+2.54)],['end','15.24',str(-top-2.54)],['stroke',['width','.254'],['type','default']],['fill',['type','background']]])
        specs=[(str(k),str(v),-5.08,top-2.54*i,0,5.08) for i,(k,v) in enumerate(pins.items())]
    for num,pname,x,y,ang,plen in specs:
        unit.append(['pin','passive','line',['at',str(x),str(y),str(ang)],['length',str(plen)],['name',Q(pname),eff(.9)],['number',Q(num),eff(.9)]])
    sym += [graphics,unit]
    return sym


def footprint(name,pads,bounds,body=None,notes=()):
    x0,y0,x1,y1=bounds
    f=['footprint',Q(name),['version','20240108'],['generator','pcbnew'],['layer',Q('F.Cu')],['descr',Q('DRAFT generic candidate; verify actual hardware before fabrication')],['attr','through_hole']]
    f += [['fp_text','reference',Q('REF**'),['at','0',str(y0-1.4)],['layer',Q('F.SilkS')],eff(.8)],['fp_text','value',Q(name),['at','0',str(y1+1.4)],['layer',Q('F.Fab')],eff(.8)]]
    for layer,bb,width in [('F.CrtYd',bounds,.05),('F.Fab',body or bounds,.1)]:
        a,b,c,d=bb
        f.append(['fp_rect',['start',str(a),str(b)],['end',str(c),str(d)],['stroke',['width',str(width)],['type','default']],['fill','none'],['layer',Q(layer)]])
    for num,x,y,size,drill,shape,attr in pads:
        f.append(['pad',Q(num),attr,shape,['at',str(x),str(y)],['size',str(size),str(size)],['drill',str(drill)],['layers',Q('*.Cu'),Q('*.Mask')]])
    for text,x,y in notes:f.append(['fp_text','user',Q(text),['at',str(x),str(y)],['layer',Q('F.Fab')],eff(.7)])
    if name=='NPN_EBC_Wire_Form_VERIFY':
        for p in children(f,'pad'):
            if p[1]=='E':p.append(['zone_connect','2'])
    (FPDIR/(name+'.kicad_mod')).write_text(dumps(f)+'\n')

# Portable local library: original ESP32 socket definition, no global config.
espname=CON['esp32']['symbol']
symbol_source=Path(CON['sources']['esp32_symbol'])
if not symbol_source.exists():symbol_source=ROOT/(LIB+'.kicad_sym')
espsource=parse(symbol_source.read_text())
esp=copy.deepcopy(next(s for s in children(espsource,'symbol') if str(s[1])==espname))
for pr in children(esp,'property'):
    if pr[1]=='Footprint':pr[2]=Q(LIB+':YD-ESP32-S3_2x22_P2.54mm_Row25.40mm')
fp_source=Path(CON['sources']['esp32_footprint'])
fp_target=FPDIR/'YD-ESP32-S3_2x22_P2.54mm_Row25.40mm.kicad_mod'
if fp_source.exists() and fp_source.resolve()!=fp_target.resolve():shutil.copy2(fp_source,fp_target)
# The dev-board antenna extends beyond the carrier notch; keep its body
# drawing off manufacturing silkscreen while retaining the actual socket pads.
esp_fp=parse(fp_target.read_text())
for item in esp_fp:
    if isinstance(item,list) and child(item,'layer') and child(item,'layer')[1]=='F.SilkS':
        if not (item[0]=='fp_text' and item[1]=='reference'):child(item,'layer')[1]=Q('Dwgs.User')
for zone in walk(esp_fp,'zone'):child(zone,'layers')[:]=['layers',Q('F.Cu'),Q('B.Cu')]
fp_target.write_text(dumps(esp_fp)+'\n')
SYMS={espname:esp}
for n in [2,3,4,6,16]:
    pads=[(str(i+1),i*2.54,0,1.8,1.0,'rect' if i==0 else 'circle','thru_hole') for i in range(n)]
    footprint(f'Header_1x{n}_P2.54',pads,(-1.52,-1.52,(n-1)*2.54+1.52,1.52),(-1.27,-1.27,(n-1)*2.54+1.27,1.27))
for n in [2,3]:
    pads=[(str(i+1),i*5.08,0,2.8,1.3,'rect' if i==0 else 'circle','thru_hole') for i in range(n)]
    footprint(f'Terminal_1x{n}_P5.08_GENERIC',pads,(-2.79,-4.25,(n-1)*5.08+2.79,4.25),(-2.54,-4,(n-1)*5.08+2.54,4))
footprint('R_Axial_P7.62', [('1',0,0,1.8,.8,'circle','thru_hole'),('2',7.62,0,1.8,.8,'circle','thru_hole')],(-1.2,-1.5,8.82,1.5),(1.66,-1.15,5.96,1.15))
footprint('NPN_EBC_Wire_Form_VERIFY',[('E',-2.54,0,1.8,1,'circle','thru_hole'),('B',0,0,1.8,1,'circle','thru_hole'),('C',2.54,0,1.8,1,'circle','thru_hole')],(-3.8,-1.52,3.8,1.52),(-3.55,-1.27,3.55,1.27),[('E B C / VERIFY',0,2.5)])
footprint('D_DO201_P15.24',[('K',0,0,3,1.3,'rect','thru_hole'),('A',15.24,0,3,1.3,'circle','thru_hole')],(-1.75,-2.85,16.99,2.85),(2.87,-2.6,12.37,2.6),[('K BAND',0,-4)])
footprint('MountingHole_2.7_GENERIC',[('',0,0,2.7,2.7,'circle','np_thru_hole')],(-1.6,-1.6,1.6,1.6),(-1.35,-1.35,1.35,1.35))

COMP=copy.deepcopy(CON['components'])
for ref,pos in {'H1':(33.02,33.02),'H2':(33.02,104.14),'H3':(119.38,104.14)}.items():COMP[ref]={'kind':'mount','value':'M2.5 clearance - verify case','pins':{}}
for ref,c in COMP.items():
    if ref=='A1':c.update(symbol=espname,fp='YD-ESP32-S3_2x22_P2.54mm_Row25.40mm',value='YD-ESP32-S3 N16R8 SOCKET')
    elif ref.startswith('R'):c.update(symbol='R',fp='R_Axial_P7.62')
    elif ref=='Q2':c.update(symbol='NPN_EBC',fp='NPN_EBC_Wire_Form_VERIFY',value='NPN E/B/C VERIFY PART')
    elif ref=='D1':c.update(symbol='D_KA',fp='D_DO201_P15.24')
    elif ref.startswith('H'):c.update(symbol='MountingHole',fp='MountingHole_2.7_GENERIC')
    else:
        c['symbol']='Connector_'+ref
        c['value']=c.get('kind',ref)
        c['fp']=f'Terminal_1x{len(c["pins"])}_P5.08_GENERIC' if ref in ['J1','J8','J9'] else f'Header_1x{len(c["pins"])}_P2.54'
        labelmap=c.get('pin_labels',{})
        SYMS[c['symbol']]=symbol_graph(c['symbol'],{n:labelmap.get(n,net or 'NC') for n,net in c['pins'].items()})
for name,kind in [('R','resistor'),('NPN_EBC','npn'),('D_KA','diode'),('MountingHole','mount')]:SYMS[name]=symbol_graph(name,{},kind)
for ref,c in COMP.items():
    # Different connector symbols carry distinct values/footprints; R shared.
    if c['symbol'] not in ['R','NPN_EBC','D_KA','MountingHole',espname]:
        for pr in children(SYMS[c['symbol']],'property'):
            if pr[1]=='Footprint':pr[2]=Q(LIB+':'+c['fp'])
lib=['kicad_symbol_lib',['version','20231120'],['generator','kicad_symbol_editor'],*SYMS.values()]
(ROOT/(LIB+'.kicad_sym')).write_text(dumps(lib)+'\n')
for kind in ['sym','fp']:
    path='${KIPRJMOD}/'+(LIB+'.kicad_sym' if kind=='sym' else LIB+'.pretty')
    (ROOT/(kind+'-lib-table')).write_text(f'({kind}_lib_table\n (lib (name "{LIB}")(type "KiCad")(uri "{path}")(options "")(descr "Project-local verified-format draft parts"))\n)\n')

SCH_POS={'A1':(85,108),'J1':(40,35),'JP1':(90,35),'J6':(145,35),'J7':(195,35),'J8':(250,35),'J9':(300,35),'D1':(355,35),'J2':(210,105),'J3':(285,85),'JP2':(340,85),'J4':(285,125),'JP3':(340,125),'J5':(265,165),'R4':(320,165),'R5':(365,165),'Q2':(90,195),'R1':(40,195),'R2':(90,230),'R3':(150,195),'H1':(265,230),'H2':(305,230),'H3':(345,230)}
sch=['kicad_sch',['version','20231120'],['generator','eeschema'],['uuid',ROOT_ID],['paper',Q('A3')],['lib_symbols']]
for name,sym in SYMS.items():
    e=copy.deepcopy(sym);e[1]=Q(LIB+':'+name);sch[-1].append(e)
for ref,c in COMP.items():
    x,y=SCH_POS[ref];x=round(x/1.27)*1.27;y=round(y/1.27)*1.27;sy=SYMS[c['symbol']]
    inst=['symbol',['lib_id',Q(LIB+':'+c['symbol'])],['at',str(x),str(y),'0'],['unit','1'],['in_bom','yes'],['on_board','yes'],['dnp','no'],['uuid',uid('symbol/'+ref)]]
    top=max([float(child(p,'at')[2]) for p in walk(sy,'pin')]+[2.54])
    inst += [prop('Reference',ref,x,y-top-7.62),prop('Value',c.get('value',ref),x,y-top-5.08),prop('Footprint',LIB+':'+c['fp'],x,y,True)]
    for pin in walk(sy,'pin'):
        num=str(child(pin,'number')[1]);a=child(pin,'at');px=x+float(a[1]);py=y-float(a[2]);ang=int(a[3]);net=c['pins'].get(num)
        inst.append(['pin',Q(num),['uuid',uid('pin/'+ref+'/'+num)]])
        if net is None and pin[1]=='no_connect':continue
        if net is None:
            sch.append(['no_connect',['at',str(px),str(py)],['uuid',uid('nc/'+ref+'/'+num)]]);continue
        # Stub runs outward from the symbol; labels provide actual net connectivity.
        dx,dy={0:(-7.62,0),180:(7.62,0),90:(0,7.62),270:(0,-7.62)}[ang]
        ex,ey=px+dx,py+dy
        sch.append(['wire',['pts',['xy',str(px),str(py)],['xy',str(ex),str(ey)]],['stroke',['width','0'],['type','default']],['uuid',uid('wire/'+ref+'/'+num)]])
        effects=eff(.9);effects.append(['justify','right' if dx<0 else 'left'])
        sch.append(['global_label',Q(net),['shape','input'],['at',str(ex),str(ey),'0'],effects,['uuid',uid('label/'+ref+'/'+num)]])
    inst.append(['instances',['project',Q(NAME),['path',Q('/'+ROOT_ID),['reference',Q(ref)],['unit','1']]]])
    sch.append(inst)
for i,(s,x,y,size) in enumerate([
('DRAFT - LOW VOLTAGE DC ONLY - NOT FOR FABRICATION',15,12,2),
('All connector pin orders are PROJECT-DEFINED. Cable by signal names, not by assuming module pin order.',15,17,1.2),
('A1: 2x22 YD socket; V1.5 pad audit and mechanical fit pending. GPIO1 and PSRAM-reserved GPIO35/36/37 NC.',15,153,1.1),
('JP1: remove external 5V link for USB power. JP2/JP3: NO SHUNT until ToF VIN/pull-up voltage verified.',15,260,1.2),
('K1 and K2 modules remain external. J8 is 24V DC relay COM/NO only. NO 110V, N or PE on this PCB.',15,267,1.2),
('Q2: verify E/B/C before assembly. D1 band K to switched motor+. Existing D-50B 24V/1A startup capacity unverified.',15,274,1.1)]):
    sch.append(['text',Q(s),['at',str(x),str(y),'0'],['effects',['font',['size',str(size),str(size)]],['justify','left']],['uuid',uid('note/'+str(i))]])
(ROOT/(NAME+'.kicad_sch')).write_text(dumps(sch)+'\n')

# Physical low-voltage carrier placement; 91.44 x 76.20 mm bounding box.
PLAC={'A1':(116.84,67.31,270),'J1':(106.68,35.56,0),'J8':(86.36,35.56,0),'J9':(71.12,35.56,0),'D1':(45.72,35.56,0),'J2':(50.8,43.18,0),'J5':(99.06,43.18,0),'R4':(114.3,49.53,180),'R5':(104.14,49.53,180),'J6':(38.1,43.18,270),'JP1':(45.72,86.36,0),'JP2':(58.42,90.17,0),'JP3':(76.2,90.17,0),'J3':(58.42,97.79,0),'J4':(76.2,97.79,0),'R1':(99.06,85.09,0),'Q2':(109.22,88.9,0),'R2':(99.06,93.98,0),'R3':(109.22,93.98,0),'J7':(109.22,99.06,0),'H1':(33.02,33.02,0),'H2':(33.02,104.14,0),'H3':(119.38,104.14,0)}
b=P.BOARD();b.SetCopperLayerCount(2)
settings=b.GetDesignSettings();settings.m_MinClearance=mm(.2);settings.m_TrackMinWidth=mm(.254);settings.m_CopperEdgeClearance=mm(.25);settings.m_HoleClearance=mm(.25);settings.m_HoleToHoleMin=mm(.25)
nets={}
for name in sorted(CON['nets']):n=P.NETINFO_ITEM(b,name);b.Add(n);nets[name]=n
# Match KiCad's single-pad NC net names, without connecting unused pins.
for ref,c in COMP.items():
    sy=SYMS[c['symbol']]
    for pin in walk(sy,'pin'):
        num=str(child(pin,'number')[1])
        if c['pins'].get(num) is None:
            pname=str(child(pin,'name')[1]).replace('/','{slash}')
            name=f'unconnected-({ref}-{pname}-Pad{num})'
            n=P.NETINFO_ITEM(b,name);b.Add(n);nets[name]=n
fps={}
for ref,c in COMP.items():
    f=P.FootprintLoad(str(FPDIR),c['fp']);assert f,ref
    f.SetReference(ref);f.SetValue(c.get('value',ref));f.SetFPID(P.LIB_ID(LIB,c['fp']))
    pth=P.KIID_PATH();pth.push_back(P.KIID(ROOT_ID));pth.push_back(P.KIID(uid('symbol/'+ref)));f.SetPath(pth)
    b.Add(f);x,y,ang=PLAC[ref];f.SetPosition(point(x,y));f.SetOrientationDegrees(ang)
    for pad in f.Pads():
        net=c['pins'].get(str(pad.GetNumber()))
        if net:pad.SetNet(nets[net])
        elif ref in COMP:
            num=str(pad.GetNumber());sy=SYMS[c['symbol']]
            pin=next((p for p in walk(sy,'pin') if str(child(p,'number')[1])==num),None)
            if pin:
                pname=str(child(pin,'name')[1]).replace('/','{slash}')
                pad.SetNet(nets[f'unconnected-({ref}-{pname}-Pad{num})'])
    f.Value().SetVisible(False)
    f.Reference().SetTextSize(point(.8,.8));f.Reference().SetTextThickness(mm(.12))
    # Short references, on real silkscreen; crowded labels can be moved after DRC.
    f.Reference().SetPosition(point(x,y-2.7));f.Reference().SetTextAngle(P.EDA_ANGLE(0,P.DEGREES_T))
    fps[ref]=f
outline=[(30.48,30.48),(121.92,30.48),(121.92,55.88),(118.11,55.88),(118.11,78.74),(121.92,78.74),(121.92,106.68),(30.48,106.68)]
for a,z in zip(outline,outline[1:]+outline[:1]):
    e=P.PCB_SHAPE();e.SetShape(P.SHAPE_T_SEGMENT);e.SetLayer(P.Edge_Cuts);e.SetStart(point(*a));e.SetEnd(point(*z));e.SetWidth(mm(.05));b.Add(e)
for value,x,y,size,layer in [('DRAFT - NO MAINS - VERIFY PARTS',74,103.5,1.0,P.F_SilkS),('LCD CABLE / VERIFY PIN ORDER',71,46,0.8,P.Dwgs_User),('ToF VIN JUMPERS OPEN',70,102,0.8,P.Dwgs_User),('USB PLUG CLEARANCE',45,67,1,P.Dwgs_User),('ANTENNA OUTSIDE / RF CLEAR',125,67,1,P.Dwgs_User)]:
    t=P.PCB_TEXT(b);t.SetText(value);t.SetPosition(point(x,y));t.SetTextSize(point(size,size));t.SetTextThickness(mm(.15));t.SetLayer(layer);b.Add(t)
# Fixed 2.032mm motor copper, not a thermal/current-rating certification.
fixed=[]
def add_path(net,layer,pts,width):
    for a,z in zip(pts,pts[1:]):fixed.append(dict(net=net,layer=layer,x1=a[0],y1=a[1],x2=z[0],y2=z[1],width=width))
add_path('+24V',0,[(116.84,35.56),(116.84,32.258),(86.36,32.258),(86.36,35.56)],2.032)
add_path('MOTOR_SW24',1,[(91.44,35.56),(91.44,39.116),(45.72,39.116),(45.72,35.56)],2.032)
add_path('MOTOR_SW24',1,[(71.12,35.56),(71.12,39.116)],2.032)
add_path('GND',0,[(60.96,35.56),(60.96,39.624),(111.76,39.624),(111.76,35.56)],2.032)
add_path('GND',0,[(76.2,35.56),(76.2,39.624)],2.032)
for tr in fixed:
    t=P.PCB_TRACK(b);t.SetStart(point(tr['x1'],tr['y1']));t.SetEnd(point(tr['x2'],tr['y2']));t.SetWidth(mm(tr['width']));t.SetLayer(P.F_Cu if tr['layer']==0 else P.B_Cu);t.SetNet(nets[tr['net']]);b.Add(t)
pads=[]
for ref,f in fps.items():
    for pad in f.Pads():
        pos=pad.GetPosition();size=pad.GetSize();net=str(pad.GetNetname()) or None
        if net and net.startswith('unconnected-'):net=None
        pads.append(dict(id=ref+'.'+str(pad.GetNumber()),net=net,x=P.ToMM(pos.x),y=P.ToMM(pos.y),diameter=P.ToMM(max(size.x,size.y)),width=P.ToMM(size.x),height=P.ToMM(size.y),shape='rect' if pad.GetShape()==P.PAD_SHAPE_RECT else 'circle'))
spec=dict(bounds=[30.48,30.48,121.92,106.68],grid=.254,pads=pads,fixed_tracks=fixed,net_widths={'+24V':2.032,'MOTOR_SW24':2.032,'GND':.508,'+5V_IN':.508,'+5V_ESP':.508,'3V3':.254},clearance=.2,via_diameter=.7,via_drill=.3,edge_clearance=.25,keepouts=[dict(xmin=118.11,ymin=55.88,xmax=122.5,ymax=78.74,layers=[0,1])],net_order=['+24V','MOTOR_SW24','GND','+5V_IN','+5V_ESP','3V3'],time_limit_s=240,max_expansions=700000)
(ROOT/'routing_spec.json').write_text(json.dumps(spec,indent=2)+'\n')
b.BuildConnectivity();P.SaveBoard(str(ROOT/(NAME+'.kicad_pcb')),b)
project={'meta':{'filename':NAME+'.kicad_pro','version':1},'net_settings':{'classes':[{'name':'Default','clearance':.2,'track_width':.254,'via_diameter':.7,'via_drill':.3,'microvia_diameter':.3,'microvia_drill':.1,'diff_pair_width':.254,'diff_pair_gap':.254,'diff_pair_via_gap':.254}],'netclass_assignments':{},'netclass_patterns':[]},'board':{'design_settings':{'rules':{'min_clearance':.2,'min_track_width':.254,'min_copper_edge_clearance':.25,'min_through_hole_diameter':.3,'min_via_diameter':.6,'min_hole_clearance':.25,'min_hole_to_hole':.25}}}}
(ROOT/(NAME+'.kicad_pro')).write_text(json.dumps(project,indent=2)+'\n')
(ROOT/'component_layout.json').write_text(json.dumps({'board_bbox_mm':[91.44,76.2],'outline_mm':outline,'components':{ref:dict(position_mm=PLAC[ref][:2],rotation=PLAC[ref][2],footprint=LIB+':'+c['fp'],pins=c['pins'],kind=c['kind'],value=c.get('value','')) for ref,c in COMP.items()}},indent=2)+'\n')
print(json.dumps({'project':NAME,'components':len(COMP),'nets':len(nets),'pads':len(pads),'fixed_motor_segments':len(fixed),'draft':True}))
