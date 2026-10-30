"""Generate servo identification diagrams; preserve the existing motor diagrams.

The archived 6V design supplies the unchanged K1/K2 control drawing.
PNG export: rsvg-convert -z 1.5 -o OUTPUT.png INPUT.svg
"""

from html import escape
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'docs/wiring/archive/legacy'
root.mkdir(parents=True, exist_ok=True)
parts = []
red, orange, black, purple = '#be123c', '#c27100', '#111827', '#7c3aed'


def text(x, y, value, size=19, bold=False, color='#102a43'):
    parts.append(f'<text x="{x}" y="{y}" font-size="{size}" '
                 f'font-weight="{700 if bold else 400}" fill="{color}">'
                 f'{escape(value)}</text>')


def rect(x, y, width, height, fill='#fff', stroke='#486581', radius=12):
    parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
                 f'rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')


def wire(path, color=black, width=5):
    parts.append(f'<path d="{path}" fill="none" stroke="{color}" '
                 f'stroke-width="{width}" stroke-linejoin="round"/>')


def dot(x, y, color=black):
    parts.append(f'<circle cx="{x}" cy="{y}" r="6" fill="{color}"/>')


text(60, 48, '伺服辨識測試接線｜GPIO1 訊號、GPIO2 控制 K2 電源、GPIO7 保留', 29, True)
text(60, 82, 'SV1 型號／連續旋轉能力未確認；6V 及 3.3V 訊號相容性、供電容量需依實物核對。非 40rpm 校正版。', 18, False, red)
rect(40, 110, 1720, 570, '#f0fdf4', '#15803d')
text(65, 150, 'C. 將原減速馬達換成三線伺服；K2 保留作電源開關', 26, True)
text(65, 184, '先拆除負載測試；U1 空載量測並調為 6.0V，僅在伺服規格允許 6V 時使用。', 19, True, red)
rect(75, 220, 230, 250)
text(95, 258, 'PS2：既有 24V', 21, True)
text(95, 307, '+24V 輸出', 22, True)
text(95, 350, '額定電流待核對', 18, False, red)
text(95, 383, '原 5V 輸出保留', 18)
text(95, 427, '0V／負極', 22, True)
rect(340, 280, 130, 40, '#fff7ed', orange, 4)
text(354, 307, 'F3 待定', 18, True)
text(332, 265, '24V 輸入保護', 16)
text(332, 352, 'DC ≥32V', 16)
wire('M305 300 H340', red)
wire('M470 300 H510', red)
rect(510, 220, 340, 250)
text(530, 258, 'U1：LM2596 可調模組', 21, True)
text(530, 325, 'IN+', 19, True)
text(765, 325, 'OUT+', 19, True)
text(530, 370, '輸入 24V → 輸出 6.0V', 20, True, red)
text(530, 399, '伺服啟動電流／容量待核對', 17)
text(530, 446, 'IN−', 19, True)
text(765, 446, 'OUT−', 19, True)
wire('M850 300 H890', red)
rect(890, 280, 110, 40, '#fff7ed', orange, 4)
text(903, 307, 'F5 待定', 18, True)
text(879, 265, '6V 輸出保護', 16)
text(894, 352, 'DC ≥32V', 16)
wire('M1000 300 H1050', red)
rect(1050, 220, 250, 250)
text(1070, 258, 'K2：保留接點側', 21, True)
text(1070, 332, 'COM', 19, True)
text(1230, 332, 'NO', 19, True)
wire('M1050 300 H1120', red)
wire('M1120 300 L1200 275', black, 3)
parts.append('<circle cx="1220" cy="300" r="6" fill="white" stroke="#111827" stroke-width="2"/>')
wire('M1226 300 H1300', red)
text(1070, 370, 'NC 留空；只切換 V＋', 17)
text(1070, 402, '不接原 K1 的 110V', 17, True, red)
text(1070, 434, '停止時釋放，伺服斷電', 17)
wire('M1300 300 H1440', red)
rect(1440, 220, 290, 250)
text(1460, 258, 'SV1：待確認伺服', 21, True)
text(1460, 307, 'V＋ ← K2 NO', 19, True)
text(1460, 367, 'SIG ← GPIO1', 19, True, purple)
text(1460, 427, 'GND → OUT−', 19, True)
wire('M1320 360 H1440', purple, 4)
text(1320, 344, '同 E 區 SIG', 14, True, purple)
wire('M305 420 H350 V510 H1400 V420 H1440')
wire('M510 420 H480 V510', black, 4)
wire('M850 420 H875 V510', black, 4)
for x in (350, 480, 875):
    dot(x, 510)
wire('M350 510 V600 H420', black, 4)
text(435, 608, '0V → D 區 G 共地端子排', 18, True)
text(75, 560, '伺服正負極不可反接；方向由訊號決定。', 18, True, red)
text(890, 560, '原馬達端 D1：移除，不跨接到伺服 V＋／GND。', 19, True, red)
text(890, 590, '伺服電流直接回 U1 OUT−，不經 ESP32 GND 細線。', 17)
text(890, 620, '3A 等級伺服不可直接假定此 LM2596 模組供得動。', 17)
text(75, 655, '端子依實物標示辨識，不按線色或圖上左右猜測；5V、6V、24V 正極分開。', 19, True)

# Reuse only the existing 5V relay control stage, without regenerating old files.
old = (root / 'wiring_6v_motor_detail.svg').read_text()
stage = '<rect x="40" y="710"' + old.split('<rect x="40" y="710"', 1)[1]
stage = stage.split('<rect x="40" y="1495"', 1)[0]
stage = stage.replace('馬達由 U1 供 6V。', '伺服 V＋由 U1 經 K2 供電。')
stage = stage.replace('保險絲、線徑、D1 與 K2 馬達負載能力尚待核對',
                      '保險絲、線徑及 K2 接點對伺服電源的適用性尚待核對')
parts.append(stage)

rect(40, 1495, 1720, 280, '#faf5ff', purple)
text(65, 1535, 'E. 新增一根伺服控制線：GPIO1 → SV1 SIG（不經 Q2、不接 K2 IN）', 25, True)
rect(75, 1560, 400, 150)
text(100, 1607, 'ESP32-S3：GPIO1', 23, True, purple)
text(100, 1645, '3.3V 邏輯，50Hz RC 伺服脈波', 19)
text(100, 1683, 'GND → 共地排 G', 19)
rect(1200, 1560, 500, 150)
text(1225, 1607, 'SV1：SIG 控制輸入', 23, True, purple)
text(1225, 1645, '須確認支援 3.3V 訊號', 20, True, red)
text(1225, 1683, '不支援時須另設介面，不能直接', 18)
wire('M475 1600 H1200', purple, 4)
dot(850, 1600, purple)
wire('M850 1600 V1640', purple, 3)
rect(839, 1640, 22, 45, '#fff', '#486581', 2)
wire('M850 1685 V1730', black, 3)
wire('M475 1730 H1600', black, 4)
dot(850, 1730)
text(1620, 1737, 'G', 19, True)
text(890, 1660, 'R4：10kΩ', 18, True)
text(890, 1690, '¼W／±5%，SIG → G', 16)
text(75, 1755, 'R4 為開機訊號下拉；K2 斷電時 GPIO1 維持 LOW。GPIO4 是 LCD RESET，禁止改接伺服。', 18, True)

rect(40, 1800, 1720, 420, '#fff7ed', orange)
text(65, 1840, 'F. 本次測試流程與元件（非 40rpm 校正版；不掃描機械端點）', 25, True)
rect(75, 1865, 800, 300)
rect(900, 1865, 820, 300)
text(100, 1900, '保留與新增零件', 22, True)
text(100, 1938, 'GPIO7 → K1；GPIO2 → Q2 → K2；新增 GPIO1 → SIG', 18, True)
text(100, 1976, 'Q2：S9014 或原 2N3904；B/C/E 依實物辨識', 18)
text(100, 2014, 'R1=1.5kΩ、R2=47kΩ、R3=4.7kΩ，原接法保留', 18)
text(100, 2052, 'R4=10kΩ 新增；四顆電阻皆 ¼W／±5%', 18, True)
text(100, 2090, 'K2 VCC 仍用既有 5V；F3／F4／F5 安培值待定', 18)
text(100, 2128, 'SV1 型號／電流未確認；原 JGB37-520 數據不沿用', 18, True, red)
text(925, 1900, '所有感測器連續三次符合後', 22, True)
text(925, 1938, '① K1、K2 啟動；GPIO1 暫維持 LOW 約 100ms', 18)
text(925, 1976, '② 送 1500µs 約 500ms；定位型此時可能移動', 18, True, red)
text(925, 2014, '③ 固定送 1600µs，觀察停在角度或持續旋轉', 18, True)
text(925, 2052, '④ 任一感測器解除：停止脈波、K2 斷電、K1 關閉', 18)
text(925, 2090, '延遲由感測循環服務，實際時間可能略長；無轉速回授', 17)
text(925, 2128, '先空載、移除舵盤／連桿；原 110V 鼓風機保持斷電', 18, True, red)
text(75, 2198, '同名端點相接；線路交叉僅有圓點才相接。圖面未經實機驗收；1500µs 不保證每款伺服停止。', 18)

style = '<style>text{font-family:"Noto Sans CJK TC",sans-serif}</style>'
body = '\n'.join(parts)
height = 2260
standalone = (
    f'<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="{height}" '
    f'viewBox="0 0 1800 {height}"><title>伺服辨識測試接線圖</title>'
    '<desc>保留GPIO7原繼電器與GPIO2的K2電源控制，新增GPIO1伺服訊號。'
    'LM2596暫按6V規劃但實物額定及供電容量待確認。移除原馬達續流二極體，'
    '新增SIG至GND的10k下拉。50Hz，1500微秒後1600微秒，非40rpm校正。</desc>'
    f'{style}<rect width="1800" height="{height}" fill="#f8fafc"/>{body}</svg>'
)
(root / 'wiring_servo_test_detail.svg').write_text(standalone)

base = (root / 'wiring_110v_blower_6v_motor.svg').read_text()
base = base.split('<g transform="translate(0,1320)">', 1)[0]
combined_height = 1320 + height
base = base.replace('height="3320"', f'height="{combined_height}"')
base = base.replace('viewBox="0 0 1800 3320"', f'viewBox="0 0 1800 {combined_height}"')
base = base.replace('原 110V 鼓風機＋LM2596 24V 轉 6V 減速馬達', '原 110V 鼓風機＋新增伺服辨識測試')
base = base.replace('新增 GPIO2 → Q2 → K2 IN（詳見 D 區）；原 GPIO7 保留。',
                    'GPIO1 → 伺服 SIG；GPIO2 → Q2 → K2；GPIO7 保留。')
base = base.replace('新增馬達使用獨立 K2', '伺服供電使用獨立 K2')
(root / 'wiring_110v_blower_servo_test.svg').write_text(
    base + f'<g transform="translate(0,1320)">{body}</g></svg>'
)
