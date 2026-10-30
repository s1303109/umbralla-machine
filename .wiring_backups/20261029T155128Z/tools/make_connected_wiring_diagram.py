"""Draw connected wire paths from the current ESP-IDF GPIO assignments.

Produces SVG, HTML, CSV and Markdown. Existing wiring drawings and firmware
are not modified. Orange dashed paths are unresolved, not wiring instructions.
"""
from pathlib import Path
from html import escape
import csv
import json
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = 'wiring_connected_current'
WIDTH, HEIGHT = 2400, 4130
INK, BLUE, GREEN = '#172b4d', '#1764c0', '#087e67'
RED, VIOLET, GRAY, AMBER = '#be2642', '#7844b3', '#526174', '#a45f00'
items, records = [], []


def text(x, y, value, size=23, color=INK, bold=False, anchor='start'):
    items.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
                 f'font-weight="{700 if bold else 400}" text-anchor="{anchor}">{escape(str(value))}</text>')


def box(x, y, w, h, fill='#fff', stroke='#a8b8c9', radius=12):
    items.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>')


def line(points, color=INK, width=4, dashed=False):
    pts = ' '.join(f'{x},{y}' for x, y in points)
    items.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}" '
                 f'stroke-linejoin="round" stroke-linecap="round"'+(' stroke-dasharray="10 8"' if dashed else '')+'/>')


def dot(x, y, color=INK):
    items.append(f'<circle cx="{x}" cy="{y}" r="6" fill="{color}"/>')


def wire(wid, start, end, points, net, color=BLUE, note='', pending=False, label=None):
    records.append({'wire': wid, 'from': start, 'to': end, 'net': net,
                    'status': '待確認，勿依虛線新增接線' if pending else '程式／既有文件對應，未逐線量測', 'note': note})
    items.append(f'<g class="wire" data-wire="{escape(wid)}"><title>{escape(wid+"："+start+" → "+end+"；"+note)}</title>')
    line(points, AMBER if pending else color, 4, pending)
    if label:
        x, y = label
        text(x, y, wid, 18, AMBER if pending else color, True)
    items.append('</g>')


def resistor(x1, y1, x2, y2, label, color=INK):
    if y1 == y2:
        box(x1, y1-15, x2-x1, 30, '#fff', color, 2)
        text((x1+x2)/2, y1-27, label, 22, color, True, 'middle')
    else:
        box(x1-15, y1, 30, y2-y1, '#fff', color, 2)
        text(x1+28, (y1+y2)/2+7, label, 22, color, True)


def panel(y, h, title, subtitle, fill='#fff', stroke='#bac9d7'):
    box(35, y, 2330, h, fill, stroke, 18)
    text(65, y+42, title, 31, INK, True)
    text(65, y+77, subtitle, 22, GRAY)


def nodebox(x, y, w, h, title, subtitle='', fill='#fff'):
    box(x, y, w, h, fill)
    text(x+w/2, y+37, title, 25, INK, True, 'middle')
    if subtitle:
        text(x+w/2, y+68, subtitle, 20, GRAY, False, 'middle')


def ground(x, y, label='G 共地'):
    line([(x, y), (x, y+12)])
    for dy, half in [(12, 17), (20, 11), (28, 5)]:
        line([(x-half, y+dy), (x+half, y+dy)], width=3)
    text(x+26, y+24, label, 21, GRAY)


def get_pins():
    main = (ROOT/'main/main.c').read_text()
    lcd = (ROOT/'main/lcd_display.c').read_text()
    pinmap = {key: int(value) for key, value in re.findall(r'#define\s+(\w+_PIN)\s+GPIO_NUM_(\d+)', main+'\n'+lcd)}
    data = re.search(r'LCD_DATA_PINS\[8\]\s*=\s*\{(.*?)\}', lcd, re.S)
    data = [int(v) for v in re.findall(r'GPIO_NUM_(\d+)', data[1])]
    assert len(data) == 8
    expected = {'SERVO_SIGNAL_PIN': 1, 'MOTOR_RELAY_PIN': 2, 'RELAY_PIN': 7,
                'LCD_RST_PIN': 4, 'HC_SR04_TRIG_PIN': 5, 'HC_SR04_ECHO_PIN': 6}
    for key, value in expected.items():
        assert pinmap[key] == value, f'Review diagram layout after changing {key}'
    return pinmap, data


def main():
    pins, data = get_pins()
    text(60, 60, '目前接線連接圖｜沿每條線看起點與終點', 43, INK, True)
    text(60, 105, '伺服測試版：GPIO1＝伺服訊號；GPIO2＝Q2／K2；GPIO7＝K1；GPIO4＝LCD RESET。', 27)
    text(60, 147, '同名 G／+5V BUS／+5V_F4 是同一電氣節點；有圓點才表示分支相接。框內接點不是實物腳位排列。', 24, GRAY)
    line([(65, 181), (130, 181)], BLUE); text(145, 189, '訊號', 22)
    line([(310, 181), (375, 181)], RED); text(390, 189, '正電源', 22)
    line([(600, 181), (665, 181)], INK); text(680, 189, '共地／回流', 22)
    line([(980, 181), (1045, 181)], AMBER, dashed=True); text(1060, 189, '橘虛線＝尚未核實，不是要你照接', 22, AMBER, True)

    # A: all DC ground terminals are explicitly joined on one drawn bus.
    panel(215, 505, 'A｜5V 分配與全部共地接點', '既有 5V 母線來源待核實：原 S-50-5 或 D-50B 的 5V，只使用一個來源，不將兩者正極並聯。', '#f4f8fe')
    nodebox(95, 320, 535, 95, '既有 +5V BUS', '原供電來源／上游 F2 實裝待核實')
    line([(630, 367), (770, 367)], RED)
    line([(770,345),(770,540)],RED);dot(770,367,RED)
    branches = [(345, 'ESP32 5V', 'EXT-5V 跳線；USB 供電時拔開', 'P01'),
                (405, 'K1 DC+', '鼓風機繼電器控制側', 'P02'),
                (465, 'HC-SR04 VCC', '超音波供電', 'P03'),
                (525, 'F4 → K2 VCC ＋ R3 上端', 'F4 後節點命名 +5V_F4，完整分支見 C', 'P04')]
    for y, title, sub, wid in branches:
        dot(770, y, RED)
        wire(wid, '+5V BUS', title, [(770, y), (1150, y)], '+5V' if wid!='P04' else '+5V / F4', RED, sub, label=(860,y-10))
        text(1180, y+8, title, 27, RED, True); text(1180, y+34, sub, 20, GRAY)
    text(95, 460, 'ESP32：USB 與外部 5V', 24, INK, True)
    text(95, 493, '沿用原 EXT-5V 隔開方式。', 23)
    text(95, 550, 'LCD／ToF 的實際供電待確認，沒有擅自接到這條 5V 母線。', 23, AMBER, True)
    text(95,588,'ESP32 GPIO7',25,INK,True)
    wire('S14','ESP32 GPIO7','K1 IN',[(360,580),(1150,580)],'K1_IN',GREEN,label=(840,568))
    text(1180,588,'K1 IN；H 觸發，原 DC／JD 供電跳帽保持連接',24,GREEN,True)
    line([(115, 620), (2290, 620)], INK, 6)
    text(2303,629,'G',24,INK,True)
    grounds = [('ESP32','GND'),('ToF1','GND'),('ToF2','GND'),('HC-SR04','GND'),('LCD','GND'),
               ('K1','DC−'),('K2','GND'),('Q2','E'),('LM2596','IN−'),('LM2596','OUT−'),('伺服','GND')]
    for i, (device, terminal) in enumerate(grounds):
        x=155+i*203; dot(x,620)
        wire(f'G{i+1:02}', 'G 共地排', device+' '+terminal, [(x,620),(x,651)], 'G', INK)
        text(x,675,device,22,INK,True,'middle');text(x,700,terminal,21,GRAY,False,'middle')

    # B: direct high-current servo return and separate signal/pulldown path.
    panel(745, 595, 'B｜24V → 降壓器 → K2 接點 → 伺服：正極與回流一起看', '輸出暫定 6.0V，僅適用額定允許 6V 的伺服；F3／F5 安培值仍待核定。', '#fff8f4')
    nodebox(95,865,330,245,'D-50B／24V')
    nodebox(690,865,405,245,'LM2596 完整模組')
    nodebox(1370,865,340,245,'K2：同一顆 HW-307')
    nodebox(1940,865,345,245,'三線伺服 SV1')
    text(260,1090,'4＝+24V；5/6＝COM',20,GRAY,False,'middle')
    text(892,1090,'24V 輸入 → 暫定 6.0V',20,GRAY,False,'middle')
    text(2112,985,'型號／相容性待確認',20,GRAY,False,'middle')
    text(400,945,'+24V',23,RED,True,'end');text(710,945,'IN+',23,RED,True)
    text(1070,945,'OUT+',23,RED,True,'end');text(1390,966,'COM',23,RED,True)
    text(1690,966,'NO',23,RED,True,'end');text(1960,945,'V+',23,RED,True)
    wire('P05','D-50B +24V','F3 輸入',[(425,935),(490,935)],'+24V',RED)
    resistor(490,935,595,935,'F3 待定',RED)
    wire('P06','F3 輸出','LM2596 IN+',[(595,935),(690,935)],'+24V_F3',RED,label=(610,921))
    wire('P07','LM2596 OUT+','F5 輸入',[(1095,935),(1170,935)],'+6V 暫定',RED)
    resistor(1170,935,1270,935,'F5 待定',RED)
    wire('P08','F5 輸出','K2 COM',[(1270,935),(1370,935)],'+6V_F5',RED,label=(1280,920))
    # A contact symbol is intentionally not an external COM-NO wire.
    line([(1370,935),(1480,935),(1590,960)], INK, 3)
    items.append('<circle cx="1620" cy="935" r="7" fill="white" stroke="#172b4d" stroke-width="3"/>')
    line([(1627,935),(1710,935)],INK,3)
    text(1540,995,'吸合時內部接通',21,INK,False,'middle')
    text(1540,1027,'勿用外線短接 COM／NO',20,RED,True,'middle')
    text(1540,1077,'NC 留空',22,GRAY,True,'middle')
    wire('P09','K2 NO','伺服 V+',[(1710,935),(1940,935)],'伺服切換電源',RED,label=(1790,921))
    text(400,1050,'COM',23,INK,True,'end');text(710,1050,'IN−',23,INK,True)
    wire('P10','D-50B COM','LM2596 IN−',[(425,1040),(690,1040)],'G',INK,label=(490,1027))
    dot(545,1040);line([(545,1040),(545,1145)])
    ground(545,1145,'→ A 區 G')
    text(1070,1050,'OUT−',23,INK,True,'end');text(1960,1050,'GND',23,INK,True)
    wire('P11','伺服 GND','LM2596 OUT−',[(1940,1040),(1860,1040),(1860,1150),(1150,1150),(1150,1040),(1095,1040)],'G／伺服回流',INK,'獨立回流線直接回 OUT−，不經 ESP32 的 GND 細線',label=(1390,1138))
    dot(1700,1150);ground(1700,1150,'同 A 區 G')
    nodebox(95,1200,340,90,'ESP32 GPIO1','3.3V RC 伺服訊號')
    text(1960,1092,'SIG',23,VIOLET,True)
    wire('S01','ESP32 GPIO1','伺服 SIG',[(435,1245),(1900,1245),(1900,1085),(1940,1085)],'SERVO_SIG',VIOLET,label=(640,1230))
    dot(950,1245,VIOLET)
    wire('R4a','伺服 SIG／GPIO1 節點','R4 10kΩ 一端',[(950,1245),(950,1290),(1050,1290)],'SERVO_SIG',VIOLET)
    resistor(1050,1290,1180,1290,'R4 10kΩ',VIOLET)
    wire('R4b','R4 10kΩ 另一端','G 共地排',[(1180,1290),(1370,1290)],'G',INK)
    ground(1370,1290,'同 A 區 G')

    # C: one complete base/collector/emitter circuit, not a parts list.
    panel(1365,610,'C｜GPIO2、R1／R2／R3、Q2 與 K2 IN 的完整接點','Q2 只拉低 K2 IN，不直接承受伺服電流。S9014 實體腳序未核實；圖中只標 B／C／E。','#f6f3ff')
    nodebox(95,1480,390,90,'A 區 F4 後 +5V_F4','同一節點供 K2 VCC 與 R3')
    nodebox(1810,1480,460,90,'K2 VCC','固定 5V，不接 6V／24V')
    wire('P12','F4 輸出 +5V_F4','K2 VCC',[(485,1525),(1810,1525)],'+5V_F4',RED,label=(800,1512))
    dot(1520,1525,RED)
    wire('R3a','+5V_F4','R3 4.7kΩ 上端',[(1520,1525),(1520,1565)],'+5V_F4',RED)
    resistor(1520,1565,1520,1640,'R3 4.7kΩ',RED)
    nodebox(95,1660,275,90,'ESP32 GPIO2','HIGH＝啟動 K2')
    wire('S02','ESP32 GPIO2','R1 1.5kΩ 一端',[(370,1705),(470,1705)],'K2_DRIVE',VIOLET)
    resistor(470,1705,610,1705,'R1 1.5kΩ',VIOLET)
    wire('R1b','R1 1.5kΩ 另一端','Q2 B／R2 上端',[(610,1705),(900,1705)],'Q2_BASE',VIOLET,label=(640,1690))
    dot(730,1705,VIOLET)
    wire('R2a','Q2 B 節點','R2 47kΩ 上端',[(730,1705),(730,1790)],'Q2_BASE',VIOLET)
    resistor(730,1790,730,1860,'R2 47kΩ',VIOLET)
    # NPN pictogram: base at left, collector up, emitter down with outward arrow.
    items.append('<circle cx="982" cy="1710" r="76" fill="#fff" stroke="#526174" stroke-width="2"/>')
    line([(900,1705),(950,1705),(950,1668),(950,1748)],INK,4)
    line([(950,1685),(1030,1630)],INK,4);line([(950,1730),(1030,1800)],INK,4)
    line([(999,1753),(1013,1784),(981,1775)],INK,3)
    text(935,1620,'Q2：S9014',25,INK,True)
    text(875,1680,'B',24,VIOLET,True);text(1044,1658,'C',24,INK,True);text(1044,1808,'E',24,INK,True)
    nodebox(1810,1660,460,90,'K2 IN','Q2 導通時被拉低')
    wire('S03','Q2 C','K2 IN／R3 下端',[(1030,1630),(1160,1630),(1160,1705),(1810,1705)],'K2_IN',BLUE,label=(1280,1691))
    wire('R3b','R3 4.7kΩ 下端','K2 IN／Q2 C 節點',[(1520,1640),(1520,1705)],'K2_IN',BLUE)
    dot(1520,1705,BLUE)
    line([(650,1910),(1730,1910)],INK,6)
    wire('R2b','R2 47kΩ 下端','G 共地排',[(730,1860),(730,1910)],'G',INK);dot(730,1910)
    wire('Q2E','Q2 E','G 共地排',[(1030,1800),(1030,1910)],'G',INK);dot(1030,1910)
    nodebox(1810,1800,460,90,'K2 GND','同 A 區共地排')
    wire('G12','K2 GND','G 共地排',[(1810,1845),(1700,1845),(1700,1910)],'G',INK);dot(1700,1910)
    ground(1250,1910,'同 A 區 G')

    # D: direct sensor pairs plus the actual echo-divider junction.
    panel(2000,665,'D｜兩顆 ToF 與 HC-SR04：每根訊號直接連到對應端子','ToF 編號依 GPIO 接線辨識；VIN 與未使用腳位保留原接法，待核實。','#f2fbf8')
    box(95,2110,470,300);text(330,2150,'ESP32 感測器接線',27,INK,True,'middle')
    box(1070,2110,440,205);text(1290,2150,'ToF1 模組',27,INK,True,'middle')
    box(1760,2315,500,130);text(2010,2350,'ToF2 模組',27,INK,True,'middle')
    tof=[('TOF_1_SDA_PIN','ToF1 SDA',2190,1070,'S04'),('TOF_1_SCL_PIN','ToF1 SCL',2240,1070,'S05'),
         ('TOF_1_XSHUT_PIN','ToF1 XSHUT',2290,1070,'S06'),('TOF_2_SDA_PIN','ToF2 SDA',2360,1760,'S07'),('TOF_2_SCL_PIN','ToF2 SCL',2410,1760,'S08')]
    for key,dest,y,x,wid in tof:
        text(535,y+8,f'GPIO{pins[key]}',25,INK,True,'end')
        wire(wid,f'ESP32 GPIO{pins[key]}',dest,[(565,y),(x,y)],dest,BLUE,label=(750,y-12))
        text(x+25,y+8,dest.split()[-1],25,BLUE,True)
    nodebox(1640,2140,620,80,'ToF1 VIN：實際供電待確認',fill='#fff4de')
    wire('U01','ToF1 原有電源（待核實）','ToF1 VIN',[(1640,2180),(1510,2180)],'TOF1_VIN',pending=True)
    nodebox(600,2110,420,65,'ToF2 VIN：供電待核實',fill='#fff4de')
    wire('U02','ToF2 原有電源（待核實）','ToF2 VIN',[(1020,2142),(1040,2142),(1040,2090),(2320,2090),(2320,2325),(2260,2325)],'TOF2_VIN',pending=True)
    text(2240,2343,'VIN',18,AMBER,True,'end')
    text(1640,2250,'GND 都已接到 A 區 G；中斷腳未使用。',21,GRAY)
    text(1640,2280,'ToF2 XSHUT 的現有使能方式待核實。',21,AMBER)
    nodebox(95,2460,470,80,'ESP32 GPIO5')
    box(1760,2470,500,175);text(2010,2505,'HC-SR04',27,INK,True,'middle')
    wire('S09','ESP32 GPIO5','HC-SR04 TRIG',[(565,2500),(1760,2500)],'HC_TRIG',GREEN,label=(770,2488));text(1780,2532,'TRIG',23,GREEN,True)
    nodebox(95,2550,470,80,'ESP32 GPIO6')
    text(1780,2583,'ECHO',23,BLUE,True)
    wire('S10','HC-SR04 ECHO','10kΩ 分壓上臂',[(1760,2575),(1440,2575)],'HC_ECHO_5V',BLUE)
    resistor(1280,2575,1440,2575,'10kΩ',BLUE)
    wire('S11','10kΩ 另一端／20kΩ 上端','ESP32 GPIO6',[(1280,2575),(1000,2575),(1000,2590),(565,2590)],'HC_ECHO_DIV',BLUE,label=(660,2576))
    dot(1000,2575,BLUE)
    wire('S12','GPIO6 分壓節點','20kΩ 一端',[(1000,2575),(1000,2630),(1090,2630)],'HC_ECHO_DIV',BLUE)
    resistor(1090,2630,1250,2630,'20kΩ',BLUE)
    wire('S13','20kΩ 另一端','G 共地排',[(1250,2630),(1410,2630)],'G',INK)
    ground(1410,2630,'同 A 區 G')
    text(1780,2620,'VCC → A 區 5V；GND → A 區 G',21,GRAY)

    # E: thirteen direct parallel traces with both endpoints labelled.
    panel(2695,740,'E｜LCD 完整平行訊號：沿同一條橫線接，不按排針序號猜測','GPIO4 是 LCD RESET；LCD_D0～D7 的順序不能交換。SD 卡端子目前程式未配置。','#f4f9ff')
    box(95,2805,475,570);box(1670,2805,590,570)
    text(330,2845,'ESP32',28,INK,True,'middle');text(1965,2845,'3.5 吋 LCD Shield',28,INK,True,'middle')
    lcd=[(pins[k],name) for k,name in [('LCD_RST_PIN','LCD_RST'),('LCD_CS_PIN','LCD_CS'),('LCD_RS_PIN','LCD_RS'),('LCD_WR_PIN','LCD_WR'),('LCD_RD_PIN','LCD_RD')]]
    lcd += [(gpio,f'LCD_D{i}') for i,gpio in enumerate(data)]
    for i,(gpio,name) in enumerate(lcd):
        y=2880+i*38;color=GREEN if i<5 else BLUE;wid=f'L{i+1:02}'
        text(535,y+7,f'GPIO{gpio}',25,INK,True,'end')
        wire(wid,f'ESP32 GPIO{gpio}',f'LCD {name}',[(570,y),(1670,y)],name,color,label=(1070,y-8))
        text(1700,y+7,name,25,color,True)
    text(95,3410,'LCD GND → A 區 G；LCD 實際接 5V 或 3V3 端待確認，不將兩個電源端短接。',24,AMBER,True)

    # F: existing mains topology; no invented wire colours or fuse approval.
    panel(3465,570,'F｜原 110V 鼓風機支路：與低壓 G 分開', '沿用既有文件的端子拓樸，非市電施工驗收；L／N／PE 實線身分與保護額定仍需核對。','#fff8ed','#d8a657')
    nodebox(95,3580,360,85,'受保護的市電 L','原總開關／保護支路後')
    nodebox(1810,3565,450,70,'D-50B AC/L（1）')
    line([(455,3620),(1040,3620)],RED);dot(1040,3620,RED)
    wire('AC01','受保護的市電 L','D-50B AC/L（1）',[(1040,3620),(1040,3600),(1810,3600)],'AC_L',RED,label=(1330,3587))
    box(1240,3655,370,95);text(1425,3690,'K1：COM → 內部接點 → NO',22,INK,True,'middle')
    wire('AC02','受保護的市電 L','K1 COM',[(1040,3620),(1040,3710),(1240,3710)],'AC_L',RED,label=(1080,3697))
    line([(1240,3710),(1270,3710),(1270,3730),(1320,3730),(1490,3703)],INK,3)
    items.append('<circle cx="1540" cy="3730" r="6" fill="white" stroke="#172b4d" stroke-width="2"/>')
    line([(1546,3730),(1580,3730),(1580,3710),(1610,3710)],INK,3)
    nodebox(1810,3670,450,70,'鼓風機 L')
    wire('AC03','K1 NO','鼓風機 L',[(1610,3710),(1760,3710),(1760,3705),(1810,3705)],'AC_SWITCHED_L',RED)
    nodebox(95,3760,360,75,'經雙極總開關的 N')
    line([(455,3798),(1040,3798)],BLUE);dot(1040,3798,BLUE)
    nodebox(1810,3750,450,65,'D-50B AC/N（2）')
    nodebox(1810,3830,450,65,'鼓風機 N')
    wire('AC04','經總開關的 N','D-50B AC/N（2）',[(1040,3798),(1040,3783),(1810,3783)],'AC_N',BLUE)
    wire('AC05','經總開關的 N','鼓風機 N',[(1040,3798),(1040,3863),(1810,3863)],'AC_N',BLUE)
    nodebox(95,3900,360,75,'PE 保護接地')
    nodebox(1510,3915,750,65,'D-50B FG（3）／機殼／鼓風機原有 PE')
    wire('AC06','PE','D-50B FG／機殼／鼓風機原有 PE',[(455,3938),(1510,3938)],'PE',GREEN,'鼓風機只有原電纜確有 PE 時才接；PE 不經繼電器',label=(900,3925))
    text(95,4010,'市電 N 不接低壓 G。K1 NC 留空；原圖 MOV／保險絲是否實裝與額定仍待核對。',23,AMBER,True)
    text(60,4080,'圖面＝目前程式與既有文件的連線參考；橘色未確認項目保留原線，不表示可依猜測上電。',24,GRAY)

    svg=(f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">'
         '<style>text{font-family:"Noto Sans CJK TC","Microsoft JhengHei",sans-serif}.wire:hover polyline{stroke-width:9}</style>'
         f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#eaf0f6"/>'+''.join(items)+'</svg>')
    (ROOT/(OUT+'.svg')).write_text(svg,encoding='utf-8')
    with (ROOT/(OUT+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['wire','from','to','net','status','note']);w.writeheader();w.writerows(records)
    md='# 逐條接線對照\n\n對應 wiring_connected_current.svg／png／html；未修改韌體或舊接線圖。\n\n'
    md+='每列為同一條線的兩端；R1／R2／R3／R4 與 Echo 分壓的中間接點已在 SVG 畫出圓點。G 與 +5V_F4 是全圖共用的同名節點。\n\n'
    md+='| 線號 | 起點 | 終點 | 網路 | 備註 |\n|---|---|---|---|---|\n'
    for r in records:
        md+='| '+' | '.join(str(r[k]).replace('|','／') for k in ['wire','from','to','net','note'])+' |\n'
    md+='\n## 未確認的部分\n\nToF1／ToF2 VIN、LCD 供電端、5V 母線實際來源、伺服型號與 6V／3.3V 相容性、S9014 腳序、保險絲與市電實線身分仍待核實。橘虛線不是接線指示。\n'
    (ROOT/'WIRING_CONNECTED_CURRENT.md').write_text(md,encoding='utf-8')
    rows=''.join('<tr data-wire="'+escape(r['wire'])+'"><td>'+escape(r['wire'])+'</td><td>'+escape(r['from'])+'</td><td>'+escape(r['to'])+'</td><td>'+escape(r['note'])+'</td></tr>' for r in records)
    html='''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>目前逐線連接圖</title>
<style>body{margin:0;background:#eaf0f6;color:#172b4d;font-family:system-ui,"Microsoft JhengHei",sans-serif}header{position:sticky;top:0;padding:12px 20px;background:white;border-bottom:1px solid #bac9d7;z-index:5}button,input{font:inherit;padding:8px;margin:4px}#drawing{overflow:auto;height:75vh}#drawing svg{width:1600px;height:auto;display:block;margin:auto}table{border-collapse:collapse;background:white;width:100%}td,th{border:1px solid #bac9d7;padding:9px;text-align:left}tr[data-wire]{cursor:pointer}tr:hover{background:#e0efff}.selected polyline{stroke:#f08b00!important;stroke-width:11!important}footer{padding:20px} @media print{header{position:static}#drawing{height:auto}#drawing svg{width:100%}}</style>
<header><b>逐線接線圖</b>　<button onclick="zoom(-200)">縮小</button><button onclick="zoom(200)">放大</button><button onclick="window.print()">列印</button><input id="filter" placeholder="搜尋 GPIO、R3、ToF、K2…" oninput="filterRows(this.value)"><span>點選下方線號可在圖中標亮；橘虛線待確認。</span></header><div id="drawing">'''+svg+'''</div><table><thead><tr><th>線號</th><th>起點</th><th>終點</th><th>備註</th></tr></thead><tbody>'''+rows+'''</tbody></table><footer>實線代表目前程式／既有文件的對應，尚未逐線量測。未確認的供電與實物腳序不可依猜測改接。</footer>
<script>let width=1600;function zoom(d){width=Math.max(800,Math.min(3200,width+d));document.querySelector('#drawing svg').style.width=width+'px'}function filterRows(q){q=q.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.innerText.toLowerCase().includes(q))}document.querySelectorAll('tr[data-wire]').forEach(r=>r.onclick=()=>{document.querySelectorAll('.selected').forEach(x=>x.classList.remove('selected'));let g=document.querySelector('g[data-wire="'+r.dataset.wire+'"]');if(g){g.classList.add('selected');g.scrollIntoView({block:'center',behavior:'smooth'})}});</script></html>'''
    (ROOT/(OUT+'.html')).write_text(html,encoding='utf-8')
    # Coverage is a wiring-specific check: all actual firmware-used GPIOs must occur.
    used={str(v) for v in pins.values()} | {str(v) for v in data}
    covered={m for r in records for value in (r['from'],r['to']) for m in re.findall(r'GPIO(\d+)',value)}
    assert used <= covered, ('Missing GPIOs', used-covered)
    assert len({r['wire'] for r in records})==len(records)
    print(json.dumps({'wires':len(records),'gpio_count':len(used),'svg':OUT+'.svg','html':OUT+'.html'},ensure_ascii=False))


if __name__=='__main__':main()
