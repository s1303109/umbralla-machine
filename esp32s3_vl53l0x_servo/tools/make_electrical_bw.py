"""Black-and-white electrical schematic of the current project, not a redesign."""
from pathlib import Path
from html import escape
import json
import re

ROOT=Path(__file__).resolve().parents[1]
W,H=3000,2250
S=[]
GPIO=set()


def t(x,y,value,size=23,bold=False,anchor='start'):
    S.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{700 if bold else 400}" text-anchor="{anchor}">{escape(str(value))}</text>')


def wire(*points,dash=False,width=2.7):
    pts=' '.join(f'{x},{y}' for x,y in points)
    S.append(f'<polyline points="{pts}" fill="none" stroke="#111" stroke-width="{width}" stroke-linejoin="round"'+(' stroke-dasharray="9 7"' if dash else '')+'/>')


def dot(x,y):
    S.append(f'<circle cx="{x}" cy="{y}" r="5.5" fill="#111"/>')


def frame(x,y,w,h,name,sub=None,dash=False):
    S.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="white" stroke="#111" stroke-width="2"'+(' stroke-dasharray="8 6"' if dash else '')+'/>')
    t(x,y-13,name,27,True)
    if sub:t(x+w/2,y+35,sub,20,False,'middle')


def terminal(x,y,label='',side='right'):
    S.append(f'<circle cx="{x}" cy="{y}" r="5" fill="white" stroke="#111" stroke-width="2"/>')
    if label:t(x+14 if side=='right' else x-14,y-10,label,21,False,'start' if side=='right' else 'end')


def resistor(x,y,label,vertical=True,length=70):
    if vertical:
        S.append(f'<rect x="{x-12}" y="{y}" width="24" height="{length}" fill="white" stroke="#111" stroke-width="2.5"/>')
        t(x+23,y+length/2+7,label,22)
    else:
        S.append(f'<rect x="{x}" y="{y-12}" width="{length}" height="24" fill="white" stroke="#111" stroke-width="2.5"/>')
        t(x+length/2,y-25,label,21,False,'middle')


def contact(x1,x2,y,label):
    wire((x1,y),(x1+30,y),(x2-25,y-27))
    terminal(x2,y)
    t((x1+x2)/2,y-48,label,24,True,'middle')


def logic_ground(x,y):
    wire((x,y),(x,y+12))
    S.append(f'<path d="M{x-15},{y+12} L{x+15},{y+12} L{x},{y+33} Z" fill="white" stroke="#111" stroke-width="2"/>')
    t(x+23,y+28,'G',21)


def pe(x,y):
    wire((x,y),(x,y+15))
    for off,half in [(15,22),(24,14),(33,6)]:wire((x-half,y+off),(x+half,y+off),width=2)
    t(x+32,y+30,'PE',22)


def gp(x,y,number):
    GPIO.add(number);terminal(x,y)
    t(x,y-18,f'U0.GPIO{number}',22)


def main():
    main_c=(ROOT/'main/main.c').read_text();lcd=(ROOT/'main/lcd_display.c').read_text()
    pins={k:int(v) for k,v in re.findall(r'#define\s+(\w+_PIN)\s+GPIO_NUM_(\d+)',main_c+'\n'+lcd)}
    data=[int(x) for x in re.findall(r'GPIO_NUM_(\d+)',re.search(r'LCD_DATA_PINS\[8\]\s*=\s*\{(.*?)\}',lcd,re.S)[1])]
    assert pins['SERVO_SIGNAL_PIN']==1 and pins['MOTOR_RELAY_PIN']==2 and pins['RELAY_PIN']==7
    t(55,65,'ESP32 感測器／鼓風機／伺服　電氣原理接線圖',43,True)
    t(55,105,'黑白原理圖｜實心圓點＝相接；跨線無圓點＝不接；?＝未核實。模組框內不代表實物腳序。',25)
    t(55,140,'參照目前 main/main.c、main/lcd_display.c 與伺服版接線；沒有新增正反轉、互鎖或接觸器控制。',23)
    wire((40,160),(2960,160),width=2)
    wire((1050,180),(1050,2070),dash=True,width=1)
    wire((2010,180),(2010,2070),dash=True,width=1)
    t(65,205,'Ⅰ　主電路／負載電源',30,True)
    t(1110,205,'Ⅱ　低壓控制電路',30,True)
    t(2070,205,'Ⅲ　感測器／LCD 介面',30,True)

    # Mains: separate single-phase L/N rails. No invented three-phase motor.
    t(85,250,'受原保護／總開關後',21)
    t(150,290,'L',27,True,'middle');t(980,290,'N',27,True,'middle')
    wire((150,305),(150,650));wire((980,305),(980,650))
    frame(420,325,320,130,'PS1　D-50B','AC → DC 電源')
    terminal(420,380,'L(1)');terminal(740,380,'N(2)','left')
    wire((150,380),(420,380));dot(150,380)
    wire((740,380),(980,380));dot(980,380)
    terminal(580,455);wire((580,455),(580,480));pe(580,480)
    t(620,480,'FG(3)，不得接成低壓 G',20)
    wire((150,590),(350,590));dot(150,590)
    contact(350,510,590,'K1 / NO')
    t(335,630,'COM',20);t(515,630,'NO',20)
    wire((510,590),(690,590))
    S.append('<circle cx="750" cy="590" r="60" fill="white" stroke="#111" stroke-width="2.5"/>')
    t(750,588,'M1',30,True,'middle');t(750,620,'~',28,False,'middle')
    wire((810,590),(980,590));dot(980,590)
    t(535,700,'150FLJ7-1W2　110V 鼓風機',24)
    t(65,744,'K1 NC 留空；原 MOV／保護額定與實裝待核實。',22)
    wire((65,775),(1005,775),width=1)

    # DC output: actual four-terminal buck converter and powered servo.
    t(65,820,'PS1 的 24V 輸出 → 降壓器 → 伺服',26,True)
    terminal(335,855,'PS1:4　+24V')
    wire((335,855),(335,1030))
    frame(230,1030,300,235,'U1　LM2596 模組')
    t(350,1080,'IN+',24,False,'middle')
    terminal(335,1030)
    terminal(335,1265);t(350,1235,'IN−',24,False,'middle')
    terminal(530,1100,'OUT+','left');terminal(530,1210,'OUT−','left')
    wire((335,1265),(335,1440))
    wire((530,1100),(700,1100));contact(700,805,1100,'K2 / NO')
    t(690,1150,'COM',18);t(800,1150,'NO',18)
    wire((805,1100),(840,1100))
    frame(840,1020,155,245,'SV1　伺服')
    terminal(840,1100);t(857,1127,'V+',22)
    terminal(925,1265);t(925,1235,'GND',21,False,'middle')
    terminal(900,1020);t(915,1070,'SIG',21)
    wire((530,1210),(600,1210),(600,1340),(925,1340),(925,1265))
    dot(600,1340);wire((600,1340),(600,1440))
    wire((220,1440),(1000,1440));dot(335,1440);dot(600,1440)
    terminal(220,1440,'PS1:5/6 COM','left')
    logic_ground(700,1440)
    t(65,1510,'OUT 暫定 6.0V；須符合伺服額定與電流需求。',22)
    t(65,1545,'伺服回流直接回 OUT−，不經 ESP32 GND 細線。',22)
    t(65,1580,'K2 NC 留空；K1 與 K2 是不同繼電器模組。',22)
    t(65,1615,'原裸馬達續流二極體 D1 不照搬至三線伺服。',22)

    # Supply branches are being corrected from the user's physical wiring report.
    t(1115,240,'D-50B:7　+5V（直接分支：K1、ESP32、電晶體介面）',22)
    # Exactly three direct D-50B 5V feeds: R3 interface, K1, ESP32.
    wire((1130,270),(2190,270))
    frame(1660,390,280,245,'K1')
    t(1680,455,'SLA-05VDC-SL-C',20)
    terminal(1800,390);t(1815,420,'DC+',21)
    wire((1800,270),(1800,390));dot(1800,270)
    gp(1140,505,7)
    # Conventional bridge at the transistor interface feed: not a junction.
    wire((1140,505),(1460,505))
    terminal(1660,505,'IN')
    terminal(1800,635);wire((1800,635),(1960,635),(1960,1780))
    t(1830,610,'DC−',21)
    t(1125,590,'K1 設 H 觸發；DC／JD',22)
    t(1125,625,'保持原供電跳帽。',22)
    t(1680,565,'內含驅動電路',20)
    t(1680,597,'不是 GPIO 直接推線圈',18)
    wire((1480,270),(1480,790));dot(1480,270)
    t(1510,780,'D-50B → R3',20)
    frame(1660,870,280,280,'K2')
    t(1680,960,'HW-307 / 5V',20)
    terminal(1800,870);t(1815,905,'VCC',21)
    terminal(1660,1060,'IN')
    terminal(1800,1150);t(1815,1127,'GND',21)
    # K2 power and ground are physically distributed from ESP32, per user.
    wire((1800,1150),(1800,1250),(1945,1250))
    wire((1975,1250),(1975,2015),(2190,2015),(2190,1990))
    dot(2190,2015)
    wire((1480,790),(1480,900));resistor(1480,900,'R3 4.7kΩ')
    wire((1480,970),(1480,1060),(1660,1060));dot(1480,1060)
    GPIO.add(2);terminal(1125,1160);t(1125,1100,'U0.GPIO2',22)
    wire((1125,1160),(1170,1160));resistor(1170,1160,'R1 1.5kΩ',False,75)
    wire((1245,1160),(1280,1160));dot(1260,1160)
    S.append('<circle cx="1340" cy="1160" r="65" fill="none" stroke="#111" stroke-width="2"/>')
    wire((1280,1122),(1280,1198))
    wire((1280,1135),(1400,1060),(1480,1060))
    wire((1280,1180),(1400,1270),(1400,1440))
    wire((1368,1220),(1384,1254),(1350,1246),width=2.7)
    t(1305,1030,'Q2 S9014',24,True)
    t(1285,1208,'B',21);t(1408,1093,'C',21);t(1412,1270,'E',21)
    wire((1260,1160),(1260,1280));resistor(1260,1280,'R2 47kΩ')
    wire((1260,1350),(1260,1440))
    wire((1130,1440),(1960,1440));dot(1260,1440);dot(1400,1440);dot(1960,1440)
    logic_ground(1700,1440)
    # Real continuous SIG lead crosses the column gap and reaches SV1.
    gp(1140,1600,1)
    wire((900,1020),(900,850),(1080,850),(1080,1600),(1500,1600))
    dot(1140,1600);dot(1500,1600)
    t(1160,1650,'SV1.SIG（同一條線）',22)
    wire((1500,1600),(1500,1650));resistor(1500,1650,'R4 10kΩ')
    wire((1500,1720),(1500,1780))
    wire((1130,1780),(1960,1780));dot(1500,1780);dot(1960,1780)
    logic_ground(1700,1780)
    t(1110,1850,'Q2 只吸入 K2 IN 的訊號電流。',22)
    t(1110,1885,'B／C／E 是功能，不表示實物腳序。',22)
    t(1110,1920,'GPIO1 為 3.3V、50Hz 伺服測試脈波，',22)
    t(1110,1955,'不是已校正的 40rpm 設定。',22)

    # Controller and all remaining firmware GPIOs.
    frame(2070,340,255,1650,'')
    t(2190,380,'U0 ESP32-S3',24,True,'middle')
    t(2190,410,'其餘 I/O',20,False,'middle')
    t(2100,445,'GPIO1/2/7',22);t(2100,478,'見控制區',22)
    terminal(2190,340);wire((2190,270),(2190,350));dot(2190,270);dot(2190,350)
    # The 5V pin is a distribution junction, not the ESP32 3.3V regulator.
    wire((2190,350),(2325,350),(2390,350),(2390,315),(2980,315),(2980,1320))
    terminal(2325,350);t(2335,340,'5V 分接',18)
    wire((2190,350),(2070,350),(2040,350),(2040,840),(1975,840))
    wire((1945,840),(1800,840),(1800,870))
    t(2050,325,'5V → K2',18,False,'end')
    t(2205,325,'5V*',21)
    wire((2960,580),(2960,2040),(2190,2040),(2190,1990))
    terminal(2190,1990);t(2200,1965,'GND',21)
    wire((2190,2040),(2000,2040),(2000,1780),(1960,1780));logic_ground(2500,2040)
    t(2045,2100,'* 外部 5V／USB 依原 EXT-5V 跳線隔開。',22)
    for name,y,h in [('B1　ToF1',365,265),('B2　ToF2',725,210),('B3　HC-SR04',1040,240),('DS1　LCD',1410,580)]:
        frame(2630,y,290,h,name)
    connections=[('TOF_1_SDA_PIN','SDA',425),('TOF_1_SCL_PIN','SCL',490),('TOF_1_XSHUT_PIN','XSHUT',555),
                 ('TOF_2_SDA_PIN','SDA',785),('TOF_2_SCL_PIN','SCL',850),('HC_SR04_TRIG_PIN','TRIG',1100)]
    for key,name,y in connections:
        n=pins[key];GPIO.add(n);t(2307,y-10,f'IO{n}',22,False,'end')
        terminal(2325,y);wire((2325,y),(2630,y));terminal(2630,y,name)
    for y in [600,900,1240,1960]:
        terminal(2920,y,'GND','left');wire((2920,y),(2960,y));dot(2960,y)
    for y in [365,725]:
        terminal(2880,y);wire((2880,y),(2880,y-30),dash=True)
        t(2895,y-20,'VIN ?',19)
    t(2630,980,'INT／XSHUT2 未配置；保留原使能。',18)
    terminal(2880,1040)
    wire((2980,1010),(2975,1010))
    wire((2945,1010),(2880,1010),(2880,1040))
    t(2894,1078,'5V',18)
    n=pins['HC_SR04_ECHO_PIN'];GPIO.add(n)
    t(2307,1170,f'IO{n}',22,False,'end');terminal(2325,1180)
    wire((2325,1180),(2450,1180),(2500,1180))
    resistor(2500,1180,'10kΩ',False,70)
    wire((2570,1180),(2630,1180));terminal(2630,1180,'ECHO')
    dot(2450,1180);wire((2450,1180),(2450,1250));resistor(2450,1250,'20kΩ')
    wire((2450,1320),(2450,1360),(2960,1360));dot(2960,1360)
    lcdpins=[(pins[key],name) for key,name in [('LCD_RST_PIN','RST'),('LCD_CS_PIN','CS'),('LCD_RS_PIN','RS'),('LCD_WR_PIN','WR'),('LCD_RD_PIN','RD')]]
    lcdpins += [(n,f'D{i}') for i,n in enumerate(data)]
    for i,(n,label) in enumerate(lcdpins):
        y=1450+40*i;GPIO.add(n)
        t(2307,y-9,f'IO{n}',22,False,'end');terminal(2325,y)
        wire((2325,y),(2630,y));terminal(2630,y,label)
    terminal(2800,1410);terminal(2890,1410)
    wire((2980,1320),(2975,1320))
    wire((2945,1320),(2800,1320),(2800,1410))
    t(2787,1434,'5V',18,False,'end');t(2900,1434,'3V3',18)
    t(2900,1458,'未接',16)
    t(2330,2010,'LCD／HC／K2：5V、GND 由 ESP32 分接',18)

    # Complete DC reference bus ties: no connection to mains N or protective PE.
    wire((1000,1440),(1030,1440),(1030,1485),(1065,1485))
    for path in ['M1460,505 Q1480,476 1500,505 L1660,505',
                 'M1065,1485 Q1080,1460 1095,1485 L1130,1485 L1130,1440',
                 'M1945,840 Q1960,815 1975,840',
                 'M1945,1250 Q1960,1225 1975,1250',
                 'M2945,1320 Q2960,1295 2975,1320',
                 'M2945,1010 Q2960,985 2975,1010']:
        S.append(f'<path d="{path}" fill="none" stroke="white" stroke-width="8"/>')
        S.append(f'<path d="{path}" fill="none" stroke="#111" stroke-width="2.7"/>')
    t(65,1695,'符號與未確認事項',25,True)
    t(65,1735,'K1／K2：畫出模組外接端，不猜測板內驅動。',22)
    t(65,1770,'同編號接點與控制模組是同一顆繼電器。',22)
    t(65,1805,'圖中沒有三相電源、正反轉或互鎖功能。',22)
    t(65,1860,'LCD／HC／K2 的 5V、GND 由 ESP32 分接。',22)
    t(65,1895,'本版省略保護元件符號，不表示可拆除實物。',22)
    t(65,1930,'線芯身分與 PE 實裝尚未驗收。',22)
    t(65,1965,'? 端子不表示要你依猜測接上電源。',22)
    wire((40,2140),(2960,2140),width=2)
    t(55,2185,'圖名：目前伺服測試版黑白電氣原理圖　｜　G＝低壓共地；PE＝保護接地；兩者不以本圖推定可短接。',24)
    t(55,2220,'資料依程式與既有接線文件整理，非實物逐線量測或市電施工核准；舊圖與韌體保留。',22)
    expected=set(pins.values())|set(data)
    assert GPIO==expected,(GPIO,expected)
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><style>text{{font-family:"Noto Sans CJK TC","Microsoft JhengHei",sans-serif;fill:#111}}</style><rect width="{W}" height="{H}" fill="white"/>'+''.join(S)+'</svg>'
    (ROOT/'wiring_electrical_bw.svg').write_text(svg,encoding='utf-8')
    print(json.dumps({'svg':'wiring_electrical_bw.svg','gpio_count':len(GPIO),'monochrome':True}))


if __name__=='__main__':main()
