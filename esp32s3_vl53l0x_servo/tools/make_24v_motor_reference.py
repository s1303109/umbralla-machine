"""Render the proposed 24V motor circuit in the existing color block style.

Read archived SVGs for layout only; write independent reference artifacts.
Firmware and existing diagrams are not changed.
"""
from copy import deepcopy
from html import escape
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def archived_source(name):
    original = ROOT / name
    return original if original.exists() else ROOT / 'docs/wiring/archive/legacy' / name

NS = '{http://www.w3.org/2000/svg}'
ET.register_namespace('', NS[1:-1])
parts = []
RED, ORANGE, BLACK, PURPLE = '#be123c', '#c27100', '#111827', '#7c3aed'


def text(x, y, value, size=19, bold=False, color='#102a43'):
    parts.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{escape(value)}</text>')


def rect(x, y, w, h, fill='#fff', stroke='#486581', radius=12):
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')


def wire(path, color=BLACK, width=5):
    parts.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round"/>')


def dot(x, y):
    parts.append(f'<circle cx="{x}" cy="{y}" r="6" fill="{BLACK}"/>')


text(60, 48, '24V 減速馬達參考接線｜無降壓器、無伺服訊號；GPIO2 控制 K2', 29, True)
text(60, 82, '依商品表：JGB37-555-2460，空載 7rpm／0.14A，額定負載 5.5rpm／0.65A，堵轉 3A；非實測。', 18, False, RED)
rect(40, 110, 1720, 570, '#f0fdf4', '#15803d')
text(65, 150, 'C. 馬達電源：24V 直接經 K2 COM／NO，供給兩線式直流馬達', 26, True)
text(65, 184, 'D-50B 的 24V 僅額定 1A：尚未證實可可靠啟動此馬達；本圖說明接線關係，不表示容量已足夠。', 19, True, RED)
rect(75, 230, 310, 240)
text(95, 268, 'PS1：D-50B 直流輸出', 21, True)
text(95, 307, '4：+24V（額定 1A）', 20, True, RED)
text(95, 350, '7：+5V（額定 6A）', 19)
text(95, 385, '5V 供電支路見 B、D 區', 18)
text(95, 427, '5／6：COM（0V）', 20, True)
rect(620, 230, 350, 240)
text(640, 268, 'K2：馬達電源接點側', 21, True)
text(640, 340, 'COM', 19, True)
text(880, 340, 'NO', 19, True)
wire('M385 300 H700', RED)
wire('M700 300 L820 275', BLACK, 3)
parts.append('<circle cx="850" cy="300" r="6" fill="white" stroke="#111827" stroke-width="2"/>')
wire('M856 300 H1410', RED)
text(640, 380, 'NC 留空；馬達電流經接點', 18)
text(640, 415, 'K2 的 VCC 仍然使用 5V', 18, True, RED)
text(640, 448, '直流馬達接點能力待核對', 18)
rect(1410, 230, 320, 240)
text(1430, 268, 'M2：JGB37-555-2460', 20, True)
text(1430, 307, '＋ ← K2 NO', 20, True)
text(1430, 350, 'DC 24V／空載 7rpm', 20, True)
text(1430, 385, '兩線式；單方向啟停', 18)
text(1430, 427, '－ → PS1 COM', 20, True)
wire('M385 420 H450 V520 H1360 V420 H1410')
wire('M450 520 V605 H515', BLACK, 4)
dot(450, 520)
text(530, 613, 'G：COM → ESP32 GND／Q2 E／模組低壓 GND', 19, True)
# Cathode bar on switched motor+, anode on negative return.
wire('M1240 300 V355', RED, 4)
wire('M1222 355 H1258', BLACK, 4)
parts.append('<path d="M1240 363 L1222 397 H1258 Z" fill="white" stroke="#111827" stroke-width="3"/>')
wire('M1240 397 V520', BLACK, 4)
dot(1240, 300); dot(1240, 520)
text(1000, 555, 'D1：1N5408；跨馬達兩端', 19, True)
text(1000, 582, '有環 K → 馬達＋；無環 A → 馬達－', 17)
text(75, 555, '馬達負極用獨立線回 COM。', 19, True)
text(75, 582, '馬達電流不經 ESP32 GND 細線。', 18, False, RED)
text(75, 655, 'G＝直流 COM；FG＝保護地 PE。此圖沒有 COM–FG 短接；保護元件符號省略不表示可拆除實物。', 18, True)

# Reuse the same module and transistor layout, correcting the physical feeds.
old = archived_source('wiring_6v_motor_detail.svg').read_text()
stage = '<rect x="40" y="710"' + old.split('<rect x="40" y="710"', 1)[1]
stage = stage.split('<rect x="40" y="1495"', 1)[0]
group = ET.fromstring(f'<g xmlns="{NS[1:-1]}">{stage}</g>')
changes = {
    'D. 新增 5V 繼電器供電與訊號介面（HW-307／JQC3F-05VDC-C）': 'D. 5V 控制介面：GPIO2 → Q2 → K2 IN；Q2 不承受馬達電流',
    '原 K1：GPIO7／H 觸發；新 K2：GPIO2 經 Q2 拉低 IN 啟動。模組供電 5V；馬達由 U1 供 6V。': 'K2 低電位觸發、VCC 使用 5V；馬達的 24V 只接 K2 COM／NO。Q2 與 R1／R2／R3 沿用。',
    '來自 B 區 +5V BUS': 'PS1:7 +5V 直接分支',
    '既有 5V 電源分配': 'D-50B：電晶體 5V 分支',
    '接 K2 前先量測為 5.0V': '此分支只接 R3 上端',
    '由既有 5V 母線分支；可用電流待核對': 'K2 VCC 由 ESP32 的 5V 接點分接',
    '+5V → K2 VCC 與 R3；不接 6V／24V': '+5V → R3；不能上拉到 24V',
    'VCC ← +5V（經 F4）': 'VCC ← ESP32 5V 分接',
    'ESP32：新增 GPIO2': 'ESP32：GPIO2（同 B 區）',
    'G：24V 負極、U1 IN−／OUT−、5V 負極、ESP32 GND、Q2 E、K2 GND 共地（確認輸出可共地）': 'G：PS1 COM、ESP32 GND、Q2 E 共地；K2／LCD／HC 的 GND 由 ESP32 接點分接。',
    '同名端點視為相接；交叉處有圓點才相接。保險絲、線徑、D1 與 K2 馬達負載能力尚待核對，這不是已驗收施工圖。': '同 B 區＝沿用既有接點，不另拉 5V 回 ESP32；R3 仍由電源直接分支。其他容量與接點條件仍待確認。',
}
for child in list(group):
    if child.tag == NS + 'text':
        if child.text in ('F4：待定',):
            group.remove(child); continue
        if child.text in changes:
            child.text = changes[child.text]
    if child.tag == NS + 'rect' and child.get('x') == '90' and child.get('y') == '883':
        group.remove(child); continue
    if child.tag == NS + 'path':
        if child.get('d') == 'M75 900 H90':
            child.set('d', 'M75 900 H350')
        elif child.get('d') == 'M220 900 H350':
            group.remove(child); continue
        elif child.get('d') == 'M700 900 H1320':
            child.set('d', 'M700 900 H1160')
    if child.tag == NS + 'text' and child.get('x') == '770' and child.get('y') == '879':
        child.set('font-size', '17')
parts.append(ET.tostring(group, encoding='unicode'))
# Keep the previous layout. The source label refers to the existing B-area
# 5V tap, not an additional supply wire back into the ESP32 GPIO2 illustration.
rect(1100, 800, 200, 85, '#fff7ed', ORANGE, 8)
text(1115, 827, '沿用 B 區同一接點', 17, True, ORANGE)
text(1115, 857, 'ESP32 5V 分接', 18, True, ORANGE)
wire('M1225 885 V900 H1320', ORANGE, 4)

rect(40, 1495, 1720, 360, '#fff7ed', ORANGE)
text(65, 1535, 'E. 接地與規劃狀態', 26, True)
text(75, 1580, 'PS1 COM（5／6）→ ESP32 GND；PS1 FG（3）→ PE 保護地。市電 N 不接低壓 G。', 22, True)
text(75, 1625, '移除伺服、其 SIG 線與專用 10kΩ 下拉；GPIO1 留空。GPIO4 仍是 LCD RESET。', 21)
text(75, 1670, 'D1 為續流候選，依 3A 斷電電流、啟停頻率與溫升再核對；不能單靠「3A」標示定案。', 20)
text(75, 1715, '24V 電源需有足夠啟動能力；若改用另一台電源，其端子與共地方式須依新型號確認。', 20)
text(75, 1760, '本次只新增參考圖：原 main/main.c 仍含伺服測試流程，未改程式、未燒錄、未實機驗證。', 20, True, RED)
text(75, 1810, '原市電區沿用原圖作辨識參考；線色代表網路功能，不代表現場電纜。保護額定仍須依實物核對。', 18)

style = '<style>text{font-family:"Noto Sans CJK TC",sans-serif}</style>'
body = '\n'.join(parts)
detail_height = 1890
detail = f'<svg xmlns="{NS[1:-1]}" width="1800" height="{detail_height}" viewBox="0 0 1800 {detail_height}"><title>24V JGB37-555 馬達無降壓器參考圖</title>{style}<rect width="1800" height="{detail_height}" fill="#f8fafc"/>{body}</svg>'
(ROOT / 'wiring_24v_motor_no_buck_detail.svg').write_text(detail)

# Keep the requested A/B color-block presentation while correcting D-50B labels.
original = ET.parse(archived_source('wiring_110v_blower_servo_test.svg')).getroot()
base = ET.Element(NS + 'svg', {'width': '1800', 'height': str(1320 + detail_height), 'viewBox': f'0 0 1800 {1320 + detail_height}'})
base_changes = {
    'ESP32-S3：原 110V 鼓風機＋新增伺服辨識測試': 'ESP32-S3：原 110V 鼓風機＋24V／7rpm 減速馬達',
    'A、B 沿用原圖拓樸，僅校正文案；C、D 為新增設計。原市電區本次未重新驗收；各電壓正極不可相接。': '無降壓器參考版｜D-50B 端子依原廠標示校正；24V 啟動容量尚待確認。程式未修改。',
    'PS1：S-50-5': 'PS1：D-50B',
    'L　 N　 ⏚　 -V -V　 +V +V': '1 L｜2 N｜3 FG｜4 +24V',
    '輸出先空載調整為 5.0 ± 0.1V': '5／6 COM（0V）｜7 +5V',
    '⏚ 接 PE 與 PSU 金屬外殼': 'FG 接 PE；COM 接低壓 GND',
    '兩個 -V 互通；兩個 +V 互通': 'COM 共用；5V／24V 正極分開',
    '+V 往低壓區前串 F2 2A': '5V：6A；24V：1A',
    '伺服供電使用獨立 K2；6V／24V 不得併入 K1 端子排。': '24V 馬達使用獨立 K2；不得接入 K1 市電端。',
    'PS1 +V → F2 2A → +5V BUS': 'PS1:7 +5V → ESP32／K1／R3',
    'PS1 -V → 0V/GND BUS': 'PS1:5／6 COM → GND 共地',
    'GPIO1 → 伺服 SIG；GPIO2 → Q2 → K2；GPIO7 保留。': 'GPIO1 不接；GPIO2 → Q2 → K2。',
    '新增 K2 電源：本區 +5V BUS → F4 → K2 VCC（詳 D 區）。': 'K2／LCD／HC 的 5V 與 GND，由 ESP32 接點分接。',
    'L 串 T5A/250V 慢熔': '過流保護額定依實物核對',
}
for element in list(original):
    if element.tag == NS + 'g' and element.get('transform') == 'translate(0,1320)':
        break
    e = deepcopy(element)
    if e.tag == NS + 'rect' and e.get('width') == '1800':
        e.set('height', str(1320 + detail_height))
    if e.tag == NS + 'text' and e.text in base_changes:
        e.text = base_changes[e.text]
    base.append(e)
base.append(ET.fromstring(f'<g xmlns="{NS[1:-1]}" transform="translate(0,1320)">{style}{body}</g>'))
full = ET.tostring(base, encoding='unicode')
assert 'LM2596' not in full and 'S-50-5' not in full and 'U1 IN' not in full
(ROOT / 'wiring_110v_blower_24v_no_buck.svg').write_text(full)
print('Generated full and detail color-block reference SVGs.')
