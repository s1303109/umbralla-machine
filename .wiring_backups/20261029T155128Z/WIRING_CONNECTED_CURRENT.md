# 逐條接線對照

對應 wiring_connected_current.svg／png／html；未修改韌體或舊接線圖。

每列為同一條線的兩端；R1／R2／R3／R4 與 Echo 分壓的中間接點已在 SVG 畫出圓點。G 與 +5V_F4 是全圖共用的同名節點。

| 線號 | 起點 | 終點 | 網路 | 備註 |
|---|---|---|---|---|
| P01 | +5V BUS | ESP32 5V | +5V | EXT-5V 跳線；USB 供電時拔開 |
| P02 | +5V BUS | K1 DC+ | +5V | 鼓風機繼電器控制側 |
| P03 | +5V BUS | HC-SR04 VCC | +5V | 超音波供電 |
| P04 | +5V BUS | F4 → K2 VCC ＋ R3 上端 | +5V / F4 | F4 後節點命名 +5V_F4，完整分支見 C |
| S14 | ESP32 GPIO7 | K1 IN | K1_IN |  |
| G01 | G 共地排 | ESP32 GND | G |  |
| G02 | G 共地排 | ToF1 GND | G |  |
| G03 | G 共地排 | ToF2 GND | G |  |
| G04 | G 共地排 | HC-SR04 GND | G |  |
| G05 | G 共地排 | LCD GND | G |  |
| G06 | G 共地排 | K1 DC− | G |  |
| G07 | G 共地排 | K2 GND | G |  |
| G08 | G 共地排 | Q2 E | G |  |
| G09 | G 共地排 | LM2596 IN− | G |  |
| G10 | G 共地排 | LM2596 OUT− | G |  |
| G11 | G 共地排 | 伺服 GND | G |  |
| P05 | D-50B +24V | F3 輸入 | +24V |  |
| P06 | F3 輸出 | LM2596 IN+ | +24V_F3 |  |
| P07 | LM2596 OUT+ | F5 輸入 | +6V 暫定 |  |
| P08 | F5 輸出 | K2 COM | +6V_F5 |  |
| P09 | K2 NO | 伺服 V+ | 伺服切換電源 |  |
| P10 | D-50B COM | LM2596 IN− | G |  |
| P11 | 伺服 GND | LM2596 OUT− | G／伺服回流 | 獨立回流線直接回 OUT−，不經 ESP32 的 GND 細線 |
| S01 | ESP32 GPIO1 | 伺服 SIG | SERVO_SIG |  |
| R4a | 伺服 SIG／GPIO1 節點 | R4 10kΩ 一端 | SERVO_SIG |  |
| R4b | R4 10kΩ 另一端 | G 共地排 | G |  |
| P12 | F4 輸出 +5V_F4 | K2 VCC | +5V_F4 |  |
| R3a | +5V_F4 | R3 4.7kΩ 上端 | +5V_F4 |  |
| S02 | ESP32 GPIO2 | R1 1.5kΩ 一端 | K2_DRIVE |  |
| R1b | R1 1.5kΩ 另一端 | Q2 B／R2 上端 | Q2_BASE |  |
| R2a | Q2 B 節點 | R2 47kΩ 上端 | Q2_BASE |  |
| S03 | Q2 C | K2 IN／R3 下端 | K2_IN |  |
| R3b | R3 4.7kΩ 下端 | K2 IN／Q2 C 節點 | K2_IN |  |
| R2b | R2 47kΩ 下端 | G 共地排 | G |  |
| Q2E | Q2 E | G 共地排 | G |  |
| G12 | K2 GND | G 共地排 | G |  |
| S04 | ESP32 GPIO8 | ToF1 SDA | ToF1 SDA |  |
| S05 | ESP32 GPIO9 | ToF1 SCL | ToF1 SCL |  |
| S06 | ESP32 GPIO10 | ToF1 XSHUT | ToF1 XSHUT |  |
| S07 | ESP32 GPIO11 | ToF2 SDA | ToF2 SDA |  |
| S08 | ESP32 GPIO12 | ToF2 SCL | ToF2 SCL |  |
| U01 | ToF1 原有電源（待核實） | ToF1 VIN | TOF1_VIN |  |
| U02 | ToF2 原有電源（待核實） | ToF2 VIN | TOF2_VIN |  |
| S09 | ESP32 GPIO5 | HC-SR04 TRIG | HC_TRIG |  |
| S10 | HC-SR04 ECHO | 10kΩ 分壓上臂 | HC_ECHO_5V |  |
| S11 | 10kΩ 另一端／20kΩ 上端 | ESP32 GPIO6 | HC_ECHO_DIV |  |
| S12 | GPIO6 分壓節點 | 20kΩ 一端 | HC_ECHO_DIV |  |
| S13 | 20kΩ 另一端 | G 共地排 | G |  |
| L01 | ESP32 GPIO4 | LCD LCD_RST | LCD_RST |  |
| L02 | ESP32 GPIO38 | LCD LCD_CS | LCD_CS |  |
| L03 | ESP32 GPIO39 | LCD LCD_RS | LCD_RS |  |
| L04 | ESP32 GPIO40 | LCD LCD_WR | LCD_WR |  |
| L05 | ESP32 GPIO41 | LCD LCD_RD | LCD_RD |  |
| L06 | ESP32 GPIO13 | LCD LCD_D0 | LCD_D0 |  |
| L07 | ESP32 GPIO14 | LCD LCD_D1 | LCD_D1 |  |
| L08 | ESP32 GPIO15 | LCD LCD_D2 | LCD_D2 |  |
| L09 | ESP32 GPIO16 | LCD LCD_D3 | LCD_D3 |  |
| L10 | ESP32 GPIO17 | LCD LCD_D4 | LCD_D4 |  |
| L11 | ESP32 GPIO18 | LCD LCD_D5 | LCD_D5 |  |
| L12 | ESP32 GPIO21 | LCD LCD_D6 | LCD_D6 |  |
| L13 | ESP32 GPIO47 | LCD LCD_D7 | LCD_D7 |  |
| AC01 | 受保護的市電 L | D-50B AC/L（1） | AC_L |  |
| AC02 | 受保護的市電 L | K1 COM | AC_L |  |
| AC03 | K1 NO | 鼓風機 L | AC_SWITCHED_L |  |
| AC04 | 經總開關的 N | D-50B AC/N（2） | AC_N |  |
| AC05 | 經總開關的 N | 鼓風機 N | AC_N |  |
| AC06 | PE | D-50B FG／機殼／鼓風機原有 PE | PE | 鼓風機只有原電纜確有 PE 時才接；PE 不經繼電器 |

## 未確認的部分

ToF1／ToF2 VIN、LCD 供電端、5V 母線實際來源、伺服型號與 6V／3.3V 相容性、S9014 腳序、保險絲與市電實線身分仍待核實。橘虛線不是接線指示。
