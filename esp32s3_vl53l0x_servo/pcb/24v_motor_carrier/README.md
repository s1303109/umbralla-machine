# ESP32-S3／24V 馬達載板：KiCad 實作草稿

**狀態：DRAFT_NOT_FOR_FABRICATION。已實際建立原理圖、元件擺放、雙層銅箔、過孔與背面 GND 填充；未取得實物封裝與電氣驗證前，不可直接送製板。**

開啟 `esp32s3_24v_carrier.kicad_pro`。本專案附有本地符號庫、封裝庫及兩個 lib-table，不需要安裝全域元件庫。沒有操作遠端電腦上的 KiCad 視窗，也沒有修改原韌體或舊接線圖。

## 已完成

- 真正的 KiCad 8 `.kicad_sch`、`.kicad_pcb`、`.kicad_pro`，不是只有圖片。
- 23個封裝（含3個暫定固定孔）、33個功能網路；未使用 GPIO 另保留 KiCad 的單焊盤 NC 網路。
- 板外框包圍尺寸 **91.44 × 76.20 mm**，天線側有退讓切口；這是可檢查的第一版草稿，不宣稱最小尺寸或孔位已核准。
- 22個使用中的 GPIO 對照現有 `main/main.c` 與 `main/lcd_display.c`，GPIO1留空、GPIO35／36／37保留不接。
- R3 為 +5V_IN 到 K2_IN_L 的上拉；Q2 C 直接接 K2_IN_L。
- HC ECHO → R4 10kΩ → GPIO6分壓中點 → R5 20kΩ → GND。
- D1 有環端 K 接馬達切換正極、A 接GND；位於 K2 NO 後，與馬達並聯。
- 24V／馬達切換正極及直接回電源的馬達回流，用 **2.032mm** 預設銅線寬。此數字不構成任意銅厚、溫升、啟動電流下的容量保證。
- KiCad 8.0.9 原生 ERC／DRC、PCB與原理圖一致性檢查及網表逐端點比對。最後結果見 [reports/validation.json](reports/validation.json)。

## 如何看圖

- [原理圖 PDF](preview/schematic.pdf)
- [原理圖 PNG](preview/schematic.png)
- [完整雙層 PCB 預覽](preview/board_layers.png)
- [實際元件擺放與極性標示](preview/placement.png)
- [前面銅箔與絲印](preview/front.png)
- [背面銅箔](preview/back.png)
- [接頭腳位表 CSV](connector_pinout.csv)
- [全元件網路表 CSV](wiring_matrix.csv)
- [BOM／封裝狀態 CSV](bom.csv)

PCB上的 A1 是 ESP32 開發板插座。左側保留 USB 插拔方向，右側為天線退讓區；LCD以外接接頭J2表示，沒有將未確認的整片LCD孔位當成已核准製造尺寸。U5／U11等照片中的參考代號沒有直接沿用為本專案的實物焊盤代號。

擺放預覽依實際PCB封裝與焊盤座標重繪清楚標籤；原生F.Fab輸出另保留在 `preview/placement_native.svg`。銅箔與原理圖預覽均由KiCad原生輸出。

## 接頭與跳帽

**所有外接排針順序都是這份新載板定義的順序，不是宣稱與原LCD／模組原生排針完全相同。必須依下表和實物端子名稱製作接線，不能盲插。** 第1腳以方形焊盤標示。

| 元件 | 腳位順序 |
|---|---|
| J1 DC輸入，暫定5.08mm | 1＝外部+5V、2＝COM/GND、3＝+24V |
| JP1 外部5V連接 | 1＝+5V_IN、2＝+5V_ESP；使用外部5V時連接，USB供電前依原方案移除，不宣稱自動切換 |
| J2 LCD，1×16／2.54mm | 1 GND、2 +5V_ESP、3 RST、4 CS、5 RS、6 WR、7 RD、8 D0、9 D1、10 D2、11 D3、12 D4、13 D5、14 D6、15 D7、16 NC |
| J3 ToF1 | 1 VIN、2 GND、3 SCL、4 SDA、5 GPIO1/INT未接、6 XSHUT |
| J4 ToF2 | 1 VIN、2 GND、3 SCL、4 SDA |
| JP2／JP3 ToF供電 | 1 3V3、2 VIN、3 +5V_ESP；**預設不裝跳帽**，先確認模組VIN及I2C上拉電壓 |
| J5 HC-SR04 | 1 VCC、2 TRIG、3 ECHO、4 GND；ECHO經板上分壓後才到GPIO6 |
| J6 K1控制 | 1 DC+／+5V_IN、2 DC−／GND、3 IN／GPIO7；模組設H觸發 |
| J7 K2控制 | 1 VCC／+5V_ESP、2 GND、3 IN／K2_IN_L；由Q2拉低啟動 |
| J8 K2直流接點，暫定5.08mm | 1 → K2 COM（+24V）；2 ← K2 NO（切換正極）；NC不接 |
| J9 馬達，暫定5.08mm | 1 馬達＋、2 馬達－ |

J6只接K1控制側。**110V、L／N／PE與K1市電接點全部留在載板外**；本PCB沒有這些網路。

Q2封裝以 **E、B、C** 功能字母編號，使用暫定2.54mm引線成形／插接排列；它不是已確認的S9014、CS9013或2N3904通用腳序。E／B／C與D1 K／A已加在絲印，裝配前仍須核對實際零件。

## 製板前仍須完成

1. 實際 YD-ESP32-S3 V1.5 每腳、排距、排母、孔徑、USB與天線／機殼淨空確認。
2. 全部接頭的實際料號、腳距、線序、額定電流與線徑；LCD本體與排線接法。
3. ToF1／ToF2 供電與I2C上拉。JP2／JP3目前是開路選擇，未裝跳帽時感測器不會上電。
4. Q2實物型號、廠牌、腳序與封裝；K1輸入相容性、K2 IN電流與觸發門檻。
5. 24V電源啟動能力、馬達實際電流、K2直流馬達接點能力及D1續流／熱條件。
6. 銅厚、導線與端子的電流容量、過流保護、實際模組高度／固定孔及機構。

原D-50B照片為24V／1A，不能因布線完成就認定能啟動表列堵轉3A的馬達。程式仍含伺服測試服務；本PCB將GPIO1留空，未更動控制程式。

## 重產生與檢查

一般使用只需在 KiCad 8 或更新版本開啟 `.kicad_pro`。下列指令用於重建；需要KiCad 8的pcbnew Python綁定及CLI：

```sh
python3 scripts/build_project.py
python3 scripts/route_project.py
python3 scripts/finish_project.py
kicad-cli sch erc --format json --exit-code-violations -o reports/erc.json esp32s3_24v_carrier.kicad_sch
kicad-cli sch export netlist --format kicadxml -o reports/netlist.xml esp32s3_24v_carrier.kicad_sch
kicad-cli pcb drc --format json --schematic-parity --exit-code-violations -o reports/drc.json esp32s3_24v_carrier.kicad_pcb
python3 scripts/check_project.py
```

`build_project.py`會重新產生未完整布線的起始PCB；若要保留手動編輯，先另存副本再執行。腳本不讀寫韌體。

本機工具位於 `/opt/kicad8-validation`；環境設定已收在 `scripts/run_local.sh`。專案本身不依賴該絕對路徑即可在KiCad開啟。最初的檢查報告留在 `reports/history/`，正式結果以 `reports/erc.json`、`reports/drc.json`、`reports/validation.json`為準。

## 參考

- [Espressif：模組在載板上的天線擺放](https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/pcb-layout-design.html#general-principles-of-pcb-layout-for-modules-positioning-a-module-on-a-base-board)
- [Vishay 1N5408資料表](https://www.vishay.com/docs/88516/1n5400.pdf)：額定有熱條件，不能只看3A字樣。
- 本地原始庫來源、44腳對照、GPIO檔案SHA-256與待確認項目保留在 `design_contract.json`、`contract_review.md`。
