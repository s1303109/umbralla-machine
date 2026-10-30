> 已建立 [真正的 KiCad 原理圖與已布線 PCB 草稿](../../../pcb/24v_motor_carrier/README.md)。本頁以下仍為前一階段概念圖，實作以新專案為準。

# PCB 擺放概念建議

依使用者提供的 KiCad PCB 截圖與第二張原理圖整理。沒有原始 `.kicad_pcb`、網表、完整模組外形和高度資料，所以這是相對位置概念，沒有已驗證的板尺寸、焊盤座標或製造走線。

- [擺放圖 PNG](pcb_placement_concept.png)
- [可放大 SVG](pcb_placement_concept.svg)
- [PDF](pcb_placement_concept.pdf)
- [重產生工具](make_placement_concept.py)

## 建議採用順序

1. 如果 LCD 仍以線材外接，載板只需要已確認尺寸與腳序的 LCD 插座，無須把整塊 LCD 外框納入板面。這比縮小電阻間距有效。
2. 如果 LCD 直接裝在載板且要求同面：先固定 U11，再把 U5 長排針旋成水平放在 LCD 下方。讓 GPIO13～18 所在排朝向 LCD 的資料排；實際旋轉方向以焊盤名稱與飛線判斷，不能只憑「90度」選方向。
3. 若允許前後堆疊，LCD 正面、ESP32 載板背面可減少平面面積；須先確認插座／螺絲／SD 插槽／金屬背板／零件高度，並讓天線遠離金屬遮蔽、USB 可插拔。不是將兩個同面封裝任意重疊。

## 每組零件

| 零件 | 擺放原則 |
|---|---|
| U11 LCD | 最大外形先固定；資料排朝向 U5；孔位和實物輪廓優先 |
| U5 ESP32 | 橫放到 LCD 下方；天線朝外；USB 插頭與拔插通道留空 |
| HC-SR04 接頭 | 靠 GPIO5／6 的板邊 |
| R4 10kΩ、R5 20kΩ | 靠 GPIO6，縮短分壓中點到 GPIO6 的線；ECHO 不直接接 GPIO6 |
| 兩顆 ToF 接頭 | 靠 GPIO8／9／10 與 GPIO11／12 的板邊 |
| Q2、R1、R2 | 位於 GPIO2 與 K2 IN 之間；R1／R2 靠 Q2 B／E |
| R3 | 靠 K2 IN／Q2 C 的共用節點；另一端仍為 +5V |
| U4／K2 與 U7 馬達接口 | 靠同一板邊，COM／NO 面向電源與負載端 |
| D1 | 靠馬達輸出接口，跨在馬達端正負極；K 接正、A 接負。若馬達線長，需重新評估馬達端抑制 |
| DC 入口 | 靠 K2 電力側，馬達回流直接到電源入口，避免經過 ESP32 GND 細線 |
| U1、U2 的市電部分 | 建議板外接線，只讓 DC／控制接口進載板。若一定要同板，必須另外核對市電連接器、間距、爬電距離、隔離區與保護，不能縮成通用小排針 |

圖中接頭方塊不是完整模組外形，沒有宣稱所有本體可在該區安裝。若使用者要把完整繼電器或感測器模組直接裝到板上，必須代入實體 courtyard／固定孔，重新檢查干涉。

## 布線關係

保持第二張原理圖與現有韌體 GPIO 契約，不為了減少飛線而互換功能腳位。飛線只是未布線網路提示，不要求銅箔照斜線外觀走。

電源仍依原本分支：5V 直接分 ESP32、K1、R3；ESP32 5V 接點分接 LCD、HC-SR04、K2。24V 馬達與其回流走電力區，不經 ESP32 接點。

先處理 LCD 資料與控制群線，再處理感測器、Q2 介面及供電；用兩層板作為試排起點，保留合理接地參考。不能由示意圖宣稱單面可走完、線寬足夠承受馬達3A或已通過 DRC。

## 資料與限制

- [Espressif ESP32-S3：模組在載板上的天線擺放](https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/pcb-layout-design.html#general-principles-of-pcb-layout-for-modules-positioning-a-module-on-a-base-board)：天線朝外與載板邊緣、機殼淨空與金屬影響。
- [KiCad PCB Editor 文件](https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html)：飛線、封裝 courtyard、DRC 與板框。
- 本機 YD 封裝紀錄是兩排22腳、腳距2.54mm、排距25.40mm；不代表使用者照片中全部其他封裝已確認為正確製造尺寸。

沒有修改韌體、原理圖、現行接線圖或 PCB 檔。也沒有製造檔、實際布線、ERC／DRC 或機構驗證結果。
