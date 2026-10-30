"""Render the color reference with one ESP32 and an explicit 5V fan-out.

Only diagram assets are written; firmware is read solely to verify GPIO mappings.
"""
from copy import deepcopy
from html import escape
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'docs/wiring/archive/legacy'
NS = '{http://www.w3.org/2000/svg}'
ET.register_namespace('', NS[1:-1])
RED, ORANGE, BLACK, PURPLE = '#be123c', '#ef8b00', '#111827', '#7c3aed'
S = []


def text(x, y, value, size=20, bold=False, color='#102a43'):
    S.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{escape(value)}</text>')


def rect(x, y, w, h, fill='#fff', stroke='#486581', radius=12):
    S.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')


def wire(path, color=BLACK, width=5):
    S.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round"/>')


def dot(x, y, color=BLACK):
    S.append(f'<circle cx="{x}" cy="{y}" r="6" fill="{color}"/>')


def terminal(x, y, color=BLACK):
    S.append(f'<circle cx="{x}" cy="{y}" r="6" fill="white" stroke="{color}" stroke-width="3"/>')


def bridge(path, color=BLACK, width=4):
    wire(path, '#fff', 11)
    wire(path, color, width)


def asset(name):
    archived = ARCHIVE / name
    return archived if archived.exists() else ROOT / name


# One drawing of the board and its power pin; no repeated ESP32 power block.
rect(40, 610, 1720, 920, '#eff6ff', '#2563eb')
text(65, 650, 'B. 5V 供電集中圖：ESP32 只接一次電源，再從同一接點分接', 29, True)
text(65, 690, '橘色＝5V；黑色＝COM／GND；實心圓點＝相接；拱橋跨線＝不相接。方塊內線段代表同一接點。', 20)
rect(80, 730, 300, 240)
text(100, 770, 'PS1：D-50B 輸出端', 23, True)
text(100, 810, '第 7 端：+5V', 22, True, ORANGE)
text(100, 850, '直接分接三路：', 20)
text(100, 885, 'ESP32、K1、R3', 22, True)
text(100, 940, '第 5／6 端：COM', 21, True)
# Three direct positive feeds, matching the user's physical topology.
wire('M380 810 H650', ORANGE)
wire('M450 810 V1420 H180', ORANGE)
wire('M450 1210 H380', ORANGE)
for x, y in [(450, 810), (450, 1210)]:
    dot(x, y, ORANGE)
terminal(180, 1420, ORANGE)
text(80, 1380, '+5V_R3 → 接 D 區 R3 上端', 19, True, ORANGE)
rect(650, 730, 420, 320)
text(675, 770, 'ESP32-S3（整張圖同一塊板）', 22, True)
wire('M650 810 H1070', ORANGE, 5)
dot(650, 810, ORANGE); dot(1070, 810, ORANGE)
text(735, 800, '同一個 5V 接點', 21, True, ORANGE)
text(675, 865, '← 電源送入       往右分接 →', 21, True)
text(675, 905, '只需一條 5V 供電線進板上接點', 20, True, RED)
text(675, 940, '不是 GPIO5，也不是另一個電源', 19)
wire('M650 990 H1070', BLACK, 5)
dot(650, 990); dot(1070, 990)
text(750, 980, '同一個 GND 接點', 20, True)
text(675, 1027, 'GPIO 接線逐條列在 E 區', 19)
# ESP32 5V fan-out to three existing loads.
wire('M1070 810 H1230 V1350 H1350', ORANGE)
wire('M1230 810 H1350', ORANGE)
wire('M1230 1080 H1350', ORANGE)
for y in [810, 1080, 1350]:
    dot(1230, y, ORANGE)
text(1105, 755, '從 ESP32 接點分出去', 18, True, ORANGE)
for y, title, power, ground, other in [
    (730, 'LCD 顯示器', '5V', 'GND', '資料與控制線：見 E 區'),
    (1000, 'HC-SR04', 'VCC', 'GND', 'TRIG／ECHO：見 E 區'),
    (1270, 'K2：HW-307／5V', 'VCC', 'GND', 'IN：接 D 區 K2_IN')]:
    rect(1350, y, 360, 190)
    text(1375, y+40, title, 22, True)
    text(1375, y+87, power+' ← 5V', 21, True, ORANGE)
    text(1375, y+126, other, 18)
    text(1555, y+163, ground, 19, True)
    wire(f'M1710 {y+140} H1730', BLACK, 4)
# Negative return to the board, and separately from board to PS1 COM.
wire('M230 970 V1020 H55 V1490 H610 V990 H650', BLACK, 4)
wire('M1070 990 H1210', BLACK, 4)
bridge('M1210 990 Q1230 960 1250 990 H1730', BLACK, 4)
wire('M1730 870 V1410', BLACK, 4)
for y in [870, 990, 1140, 1410]:
    dot(1730, y)
rect(80, 1110, 300, 220)
text(100, 1150, 'K1：鼓風機控制側', 22, True)
text(100, 1210, 'DC+ ← 電源直接 5V', 20, True, ORANGE)
text(100, 1250, 'IN ← GPIO7；H 觸發', 19)
text(100, 1300, 'DC− → COM', 20, True)
wire('M380 1270 H430', BLACK, 4)
bridge('M430 1270 Q450 1240 470 1270 H570 V1490 H610', BLACK, 4)
dot(570, 1490); dot(610, 1490)
text(695, 1160, 'K2、LCD、HC 的 5V 與 GND', 22, True)
text(695, 1200, '均由同一個 ESP32 接點分接。', 22, True)
text(695, 1250, 'R3 則由電源 +5V 直接分支。', 21)
text(695, 1300, '同名端點（如 K2_IN）跨區相接；', 19)
text(695, 1335, 'D 區只畫訊號介面，不再重畫板子。', 19)
text(695, 1390, '外部 5V 與 USB 依原供電跳線隔開。', 19, False, RED)

# 24V load circuit, kept separate from 5V control supply.
rect(40, 1560, 1720, 570, '#f0fdf4', '#15803d')
text(65, 1600, 'C. 馬達電源：24V → K2 COM／NO → JGB37-555；沒有降壓器', 28, True)
text(65, 1640, 'D-50B 的 24V 額定 1A；商品表堵轉 3A，尚未證實啟動容量足夠。接線關係不代表已實測通過。', 19, True, RED)
rect(75, 1680, 310, 240)
text(95, 1720, 'PS1：同一台 D-50B', 22, True)
text(95, 1770, '第 4 端：+24V', 22, True, RED)
text(95, 1810, '所有 5V 配線已畫在 B 區', 18)
text(95, 1870, '第 5／6 端：COM', 20, True)
rect(620, 1680, 350, 240)
text(640, 1720, 'K2：同一模組的接點側', 21, True)
wire('M385 1750 H700', RED)
wire('M700 1750 L820 1725', BLACK, 3)
terminal(850, 1750)
wire('M856 1750 H1410', RED)
text(640, 1795, 'COM', 20, True); text(875, 1795, 'NO', 20, True)
text(640, 1840, 'NC 留空；VCC 供電見 B 區', 18)
text(640, 1880, '直流馬達接點能力待核對', 18)
rect(1410, 1680, 320, 240)
text(1430, 1720, 'M2：JGB37-555-2460', 20, True)
text(1430, 1770, '＋ ← K2 NO', 21, True)
text(1430, 1820, '24V／空載 7rpm', 22, True)
text(1430, 1870, '－ → PS1 COM', 20, True)
wire('M385 1870 H450 V1970 H1360 V1870 H1410', BLACK)
wire('M1240 1750 V1805', RED, 4)
wire('M1222 1805 H1258', BLACK, 4)
S.append('<path d="M1240 1813 L1222 1847 H1258 Z" fill="white" stroke="#111827" stroke-width="3"/>')
wire('M1240 1847 V1970', BLACK, 4)
dot(1240, 1750, RED); dot(1240, 1970)
text(990, 2010, 'D1：1N5408；跨馬達兩端', 20, True)
text(990, 2045, '有環 K → 馬達＋；無環 A → 馬達－', 18)
text(75, 2010, '馬達負極獨立回 COM，不經 ESP32 的 GND 細線。', 20, True)
text(75, 2088, '商品表：空載 7rpm／0.14A；額定負載 5.5rpm／0.65A；堵轉 3A。這些是商品數據，非實物量測。', 19)

# Signal-only detail, intentionally without a second ESP32 or second 5V input.
rect(40, 2180, 1720, 540, '#eff6ff', '#2563eb')
text(65, 2220, 'D. 電晶體訊號介面：R3 是 5V 上拉，K2 IN 與 Q2 C 直接相接', 28, True)
text(65, 2260, 'K2 的 VCC／GND 已完整畫在 B 區；本區只畫 GPIO2、R1／R2／R3、Q2 與 IN 的連線。', 19)
terminal(1100, 2310, ORANGE)
text(1140, 2320, '+5V_R3（接 B 區電源直接分支）', 19, True, ORANGE)
wire('M1100 2316 V2340', ORANGE, 4)
rect(1088, 2340, 24, 50, '#fff', '#486581', 2)
wire('M1100 2390 V2430', BLACK, 4)
text(1140, 2375, 'R3：4.7kΩ', 21, True)
wire('M810 2430 H1450', BLACK, 4)
dot(1100, 2430)
terminal(1450, 2430)
text(1475, 2437, 'K2_IN → K2 IN', 21, True)
terminal(100, 2510, PURPLE)
text(90, 2460, 'GPIO2', 23, True, PURPLE)
wire('M106 2510 H350', PURPLE, 4)
rect(350, 2498, 140, 24, '#fff', PURPLE, 2)
text(345, 2470, 'R1：1.5kΩ', 21, True)
wire('M490 2510 H700', PURPLE, 4)
dot(620, 2510, PURPLE)
S.append('<circle cx="755" cy="2510" r="65" fill="none" stroke="#486581" stroke-width="2"/>')
wire('M700 2475 V2545', BLACK, 4)
wire('M700 2490 L810 2430', BLACK, 4)
wire('M700 2530 L810 2590 V2660', BLACK, 4)
S.append('<path d="M787 2562 L808 2587 L778 2579 Z" fill="#111827"/>')
text(670, 2500, 'B', 20, True); text(830, 2420, 'C', 20, True); text(830, 2605, 'E', 20, True)
text(900, 2540, 'Q2：S9014 或原 2N3904', 21, True)
text(900, 2575, 'B／C／E 依實物廠牌資料辨識', 19)
wire('M620 2510 V2550', BLACK, 4)
rect(608, 2550, 24, 60, '#fff', '#486581', 2)
text(350, 2590, 'R2：47kΩ', 21)
wire('M620 2610 V2660', BLACK, 4)
wire('M500 2660 H1450', BLACK, 4)
dot(620, 2660); dot(810, 2660)
terminal(1450, 2660)
text(1475, 2667, 'GND（同 B 區）', 20, True)
text(75, 2698, 'GPIO2 HIGH → Q2 導通 → K2 IN 拉低 → 啟動；LOW → 停止。電阻皆 1/4W、±5%；IN 電位仍需實測。', 18)

# GPIO contract read from the actual source. Tables are wire endpoints, not pad numbers.
main = (ROOT / 'main/main.c').read_text()
lcd = (ROOT / 'main/lcd_display.c').read_text()
pins = {k:int(v) for k,v in re.findall(r'#define\s+(\w+_PIN)\s+GPIO_NUM_(\d+)', main+'\n'+lcd)}
data = [int(x) for x in re.findall(r'GPIO_NUM_(\d+)', re.search(r'LCD_DATA_PINS\[8\]\s*=\s*\{(.*?)\}', lcd, re.S)[1])]
assert pins['RELAY_PIN']==7 and pins['MOTOR_RELAY_PIN']==2 and pins['SERVO_SIGNAL_PIN']==1
rect(40, 2770, 1720, 580, '#faf5ff', PURPLE)
text(65, 2810, 'E. GPIO 起訖對照：依現有程式；圖中板上腳號一律以 GPIO 名稱為準', 27, True)
rect(75, 2840, 780, 460)
rect(885, 2840, 835, 460)
text(95, 2875, '繼電器與感測器', 23, True)
rows = [('GPIO7','K1 IN（H 觸發）'), ('GPIO2','R1 → Q2 B → K2 IN（L 觸發）'),
        (f"GPIO{pins['TOF_1_SDA_PIN']}",'ToF1 SDA'),(f"GPIO{pins['TOF_1_SCL_PIN']}",'ToF1 SCL'),
        (f"GPIO{pins['TOF_1_XSHUT_PIN']}",'ToF1 XSHUT'),(f"GPIO{pins['TOF_2_SDA_PIN']}",'ToF2 SDA'),
        (f"GPIO{pins['TOF_2_SCL_PIN']}",'ToF2 SCL'),(f"GPIO{pins['HC_SR04_TRIG_PIN']}",'HC-SR04 TRIG'),
        (f"GPIO{pins['HC_SR04_ECHO_PIN']}",'HC ECHO 的 10kΩ／20kΩ 分壓中點')]
for i,(start,end) in enumerate(rows): text(100,2915+31*i,f'{start} → {end}',18)
text(100, 3220, 'ToF VIN 依實際模組額定；GND 共地。', 18)
text(100, 3252, 'GPIO1 留空；伺服與其專用訊號下拉移除。', 18, True)
text(100, 3282, 'ECHO → 10kΩ → GPIO6；GPIO6 → 20kΩ → GND', 17)
text(905, 2875, 'LCD：5V／GND 已畫在 B 區', 23, True)
ctrl=[(pins[k],label) for k,label in [('LCD_RST_PIN','RST'),('LCD_CS_PIN','CS'),('LCD_RS_PIN','RS'),('LCD_WR_PIN','WR'),('LCD_RD_PIN','RD')]]
for i,(n,label) in enumerate(ctrl): text(910,2915+31*i,f'GPIO{n} → LCD_{label}',19)
for i,n in enumerate(data):
    col=i//4;row=i%4
    text(910+385*col,3090+36*row,f'GPIO{n} → LCD_D{i}',19)
text(75, 3330, '感測條件：ToF1、ToF2 均 <101mm，HC <65mm，讀值有效且連續三次符合後啟動；任一解除即關閉。', 18)
text(60, 3400, 'COM＝低壓 GND；FG＝PE 保護地。本圖不畫 COM–FG 短接；市電 N 不接 ESP32 GND。', 21, True)
text(60, 3435, '參考圖，非實機驗收；保護符號省略不表示可拆除。電源啟動能力、K2 馬達接點與 D1 熱條件仍待確認。', 18)
text(60, 3470, '僅更新圖面：程式仍保留伺服測試流程；未改程式、未燒錄、未進行實體接線或 110V 通電測試。', 18, False, RED)

# Keep the requested mains reference style; read archived assets after cleanup.
original = ET.parse(asset('wiring_110v_blower_servo_test.svg')).getroot()
base = ET.Element(NS+'svg', {'width':'1800','height':'3500','viewBox':'0 0 1800 3500'})
changes={
'ESP32-S3：原 110V 鼓風機＋新增伺服辨識測試':'ESP32-S3：110V 鼓風機＋24V 馬達｜5V 配線清楚版',
'A、B 沿用原圖拓樸，僅校正文案；C、D 為新增設計。原市電區本次未重新驗收；各電壓正極不可相接。':'ESP32 只畫一次；B 區集中呈現全部 5V 分支。沒有降壓器或伺服配線，GPIO1 留空。',
'PS1：S-50-5':'PS1：D-50B',
'L　 N　 ⏚　 -V -V　 +V +V':'1 L｜2 N｜3 FG｜4 +24V',
'輸出先空載調整為 5.0 ± 0.1V':'5／6 COM（0V）｜7 +5V',
'⏚ 接 PE 與 PSU 金屬外殼':'FG 接 PE；COM 接低壓 GND',
'兩個 -V 互通；兩個 +V 互通':'COM 共用；5V／24V 正極分開',
'+V 往低壓區前串 F2 2A':'5V：6A；24V：1A',
'伺服供電使用獨立 K2；6V／24V 不得併入 K1 端子排。':'24V 馬達使用獨立 K2，不接 K1 市電端。',
'L 串 T5A/250V 慢熔':'過流保護額定依實物核對'}
for e0 in original:
    if e0.tag==NS+'rect' and e0.get('y')=='605': break
    e=deepcopy(e0)
    if e.tag==NS+'rect' and e.get('width')=='1800': e.set('height','3500')
    if e.tag==NS+'text' and e.text in changes: e.text=changes[e.text]
    base.append(e)
style='<style>text{font-family:"Noto Sans CJK TC",sans-serif}</style>'
body='\n'.join(S)
base.append(ET.fromstring(f'<g xmlns="{NS[1:-1]}">{style}{body}</g>'))
full=ET.tostring(base,encoding='unicode')
assert 'LM2596' not in full and 'S-50-5' not in full
assert full.count('整張圖同一塊板')==1
(ROOT/'wiring_110v_blower_24v_no_buck.svg').write_text(full)
detail=f'<svg xmlns="{NS[1:-1]}" width="1800" height="3060" viewBox="0 0 1800 3060">{style}<rect width="1800" height="3060" fill="#f8fafc"/><g transform="translate(0,-460)">{body}</g></svg>'
(ROOT/'wiring_24v_motor_no_buck_detail.svg').write_text(detail)
print('Generated single-ESP32 5V fan-out full and detail diagrams.')
