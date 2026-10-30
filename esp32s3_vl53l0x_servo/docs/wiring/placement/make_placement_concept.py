"""Concept placement only: no KiCad netlist, pad geometry, or fabrication data."""
from pathlib import Path
from html import escape
OUT = Path(__file__).resolve().parent
S = []

def text(x,y,value,size=22,bold=False,color='#17324d'):
    S.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{escape(value)}</text>')

def box(x,y,w,h,fill='#fff',stroke='#54758c',dash=False,r=10):
    S.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="2"'+(' stroke-dasharray="10 7"' if dash else '')+'/>')

def path(d,color='#2584c5',width=3,dash=False,arrow=False):
    S.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"'+(' stroke-dasharray="8 6"' if dash else '')+(' marker-end="url(#arrow)"' if arrow else '')+'/>')

def pads(x,y,count,step=28):
    for i in range(count):
        S.append(f'<circle cx="{x+step*i}" cy="{y}" r="6" fill="#e4af38" stroke="#8a691a" stroke-width="2"/>')

text(60,58,'PCB 元件擺放建議｜依第一張零件、第二張接線功能',34,True)
text(60,99,'相對位置示意，不按比例；未取得原始 PCB、完整模組外形與固定孔，不能作製板尺寸或銅箔圖。',20,color='#a64819')
text(60,148,'A. LCD 與 ESP32 維持同面：先把 ESP32 橫放在 LCD 下方',28,True)
box(80,195,1000,1120,'#f0f8f4','#3d8b6f',True)
text(105,229,'載板區域示意（外形最後再定，不是正式 Edge.Cuts）',21,True)
# The real display outline determines the upper part of a direct-mounted board.
box(140,270,880,440,'#e7edf5','#536b88')
text(350,355,'U11：3.5 吋 LCD',32,True)
text(320,407,'先固定實際位置、方向、孔位',25)
text(302,449,'若線材外接，載板只需保留對應插座',22,color='#9d5520')
pads(420,291,10,29); pads(420,688,10,29)
text(170,659,'資料腳排朝向 ESP32；實際腳序按網表核對',21,True)
# A horizontal development-board body, with antenna edge and plug corridor.
box(65,790,650,190,'#edf0ff','#7165a5')
box(65,790,108,190,'#f4ddf9','#a65aaf',True)
text(80,835,'天線',24,True,color='#8e3d96')
text(80,872,'朝板外',20,color='#8e3d96')
path('M80 922 H22','#a65aaf',3,arrow=True)
text(250,865,'U5：ESP32-S3 橫放',27,True)
text(205,909,'含 GPIO13～18 的排針朝向 LCD',22,True)
text(205,947,'依飛線選轉向，不預設 R90／R270',20)
pads(205,808,22,23); pads(205,962,22,23)
box(715,843,345,91,'#fff8df','#cb9a33',True)
text(735,880,'USB 插頭／拔插通道',22,True)
text(735,914,'此區不擺接頭或高零件',19)
for i in range(5):
    path(f'M{455+i*27} 710 L{420+i*27} 790','#2584c5',2,True)
text(410,755,'優先布 LCD 資料與控制線',20,True)
# Functional local groups rather than a row of unrelated resistors.
box(130,1035,175,80,'#e6f8ff','#3096ae')
text(145,1066,'HC-SR04 接頭',20,True)
text(145,1098,'靠 GPIO5／6 側',18)
box(330,1028,205,90,'#fff2de','#c18c35')
text(345,1063,'R4 10k／R5 20k',20,True)
text(345,1096,'靠 GPIO6 分壓中點',18)
box(580,1020,180,115,'#fff2de','#c18c35')
text(595,1053,'Q2＋R1／R2',20,True)
text(595,1083,'R3 靠 IN／C',19)
text(595,1113,'靠 GPIO2 側',18)
box(800,1010,240,100,'#ffecdf','#c97736')
text(815,1044,'U4／K2 馬達支路',21,True)
text(815,1077,'接點朝電源／馬達端',18)
box(130,1185,175,80,'#e6f8ff','#3096ae')
text(145,1217,'K1 控制接口',20,True)
text(145,1246,'5V／GND／IN7',18)
box(330,1185,180,80,'#e6f8ff','#3096ae')
text(345,1218,'ToF1 接頭',21,True)
text(345,1247,'靠 GPIO8／9／10',17)
box(535,1185,185,80,'#e6f8ff','#3096ae')
text(550,1218,'ToF2 接頭',21,True)
text(550,1247,'靠 GPIO11／12',18)
box(850,1140,190,57,'#ffe4df','#be573e')
text(865,1176,'DC 電源入口',21,True)
box(850,1220,190,57,'#ffe4df','#be573e')
text(865,1256,'U7 馬達接口',21,True)
box(755,1217,78,64,'#fff2de','#c18c35')
text(767,1256,'D1',23,True)
path('M945 1197 V1220','#be573e',3,True)
text(1115,227,'擺放時保留的限制',25,True)
box(1110,250,340,1065,'#fff','#b8c5d2')
notes=[
('LCD 大外框不能任意縮小', '直插才需要預留整塊模組；', '外接時改用已確認的接頭。'),
('ESP32 天線及 USB 要留空', '天線避開 LCD 金屬背板；', 'USB 線要能插入與拔出。'),
('電阻按功能分組', 'R1／R2 靠 Q2；R3 靠 IN。', 'R4／R5 靠 GPIO6。'),
('馬達支路靠板邊', '電源、K2、D1、輸出靠近；', '回流直接回電源入口。'),
('U1／U2 的市電側另置', '此圖載板只放 DC 與控制口；', 'AC 接線功能仍依第二張圖。'),
('虛線不代表實際銅箔', '沒有指定焊盤座標或走線；', '不能由這張圖產生 Gerber。')]
for i,(head,a,b) in enumerate(notes):
    y=298+i*165
    text(1130,y,head,21,True)
    text(1130,y+37,a,18)
    text(1130,y+69,b,18)
text(85,1362,'實際封裝若為整塊繼電器模組，須以模組本體外形取代小接頭圖框；同面零件不可因只看焊盤而互相重疊。',19,color='#a64819')
text(60,1430,'B. 機構允許時更省面積：LCD 在正面，ESP32 與小零件在背面',28,True)
box(80,1460,1370,285,'#f7f5fe','#8b78ac')
box(140,1512,620,65,'#e7edf5','#536b88')
text(312,1555,'LCD／金屬背板',25,True)
path('M205 1577 V1620 M690 1577 V1620','#54758c',8)
box(160,1620,580,36,'#edf0ff','#7165a5',r=3)
text(240,1696,'背面 ESP32／載板；高度與孔位必須核對',21,True)
text(820,1518,'這是省平面面積的候選方案，',22,True)
text(820,1561,'不是把兩個同面封裝直接重疊。',21)
text(820,1604,'天線須避開 LCD 金屬投影與 RF 淨空區；',20)
text(820,1647,'需保留插座高度、螺絲、絕緣與 USB 空間。',20)
text(60,1800,'布線保持第二張圖與程式的 GPIO 對應；先修正原理圖／網表，再做 ERC、佈局、DRC。',21,True)
text(60,1840,'若 LCD、繼電器及感測器均線材外接，最省面積的載板只需 ESP32 插座、小零件與板邊接頭。',20,color='#276c53')
svg='<svg xmlns="http://www.w3.org/2000/svg" width="1500" height="1880" viewBox="0 0 1500 1880"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill="#a65aaf"/></marker></defs><style>text{font-family:"Noto Sans CJK TC",sans-serif}</style><rect width="1500" height="1880" fill="#fafcfe"/>'+''.join(S)+'</svg>'
(OUT/'pcb_placement_concept.svg').write_text(svg,encoding='utf-8')
print(OUT/'pcb_placement_concept.svg')
