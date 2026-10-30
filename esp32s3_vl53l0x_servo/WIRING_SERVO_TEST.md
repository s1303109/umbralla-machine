> 歷史版本：目前 24V／7rpm 馬達方案請看 [新版接線圖索引](WIRING_INDEX.md)。本文件保留舊版資料，舊圖片已集中封存。

# 三線伺服辨識測試：GPIO1 訊號，保留 K2 電源控制

本版供之後拿到伺服時，辨識「定位型」與「連續旋轉型」。**不是已校正的 40rpm 控制器，也尚未確認你手上的伺服型號、電流、6V 供電及 3.3V 訊號相容性。** 不因斷電時能手轉 360° 就判定為連續旋轉型。

目前實際供電分接已由使用者補充：**D-50B 的 5V 直接接 K1、ESP32、電晶體介面 R3 上端；LCD 5V、HC-SR04 VCC、K2 VCC 再從 ESP32 的 5V 接點分接，這三個模組的 GND 也從 ESP32 GND 分接。** 最新圖為 [黑白原理圖](./docs/wiring/archive/legacy/wiring_electrical_bw.png) 與 [互動逐線圖](./wiring_connected_current.html)。最新圖省略保護元件符號，僅簡化顯示，不表示建議拆除實物；下列舊版圖片保留作歷史參考。

> **目前狀態：編譯成功、主機控制測試通過、已燒錄並讀到本版開機紀錄。** USB 重新連接後寫入雜湊驗證通過，開機確認 GPIO1 伺服訊號初始化、K1/K2 初始 OFF、LCD 與兩顆 ToF 啟動。下次上電即可使用本辨識測試版；仍需按圖確認實物供電與接線、滿足三顆感測器條件，尚未實測伺服或校正 40rpm。

- [新增伺服接線詳圖 PNG](./docs/wiring/archive/legacy/wiring_servo_test_detail.png)
- [新增伺服接線詳圖 SVG](./docs/wiring/archive/legacy/wiring_servo_test_detail.svg)
- [包含原鼓風機與感測器的完整圖 PNG](./docs/wiring/archive/legacy/wiring_110v_blower_servo_test.png)
- [完整圖 SVG](./docs/wiring/archive/legacy/wiring_110v_blower_servo_test.svg)
- [圖面產生程式](./tools/make_servo_wiring_diagram.py)
- [控制狀態機主機檢查](./tools/test_servo_control.py)

## 1. 舊馬達換成伺服，需要哪些接線

概念上是把原本兩條負載電源線改接到伺服 V+／GND，**另加 GPIO1 → SIG**。施工前必須核對伺服實物線序和額定，不照線色猜測。保留原 K1、K2、Q2、R1/R2/R3、感測器與 LCD；移除原裸馬達 M2 和其外接續流二極體 D1。

| 伺服 SV1 端子 | 接到哪裡 | 說明 |
|---|---|---|
| **V+** | **K2 NO** | U1 OUT+ → K2 COM → NO → SV1 V+；不直接接 24V；圖面省略保護元件 |
| **GND** | **U1 OUT−**，並連低壓共地排 G | 電源回流線直接回模組，不經 ESP32 GND 細線 |
| **SIG** | **ESP32 GPIO1** | 新增 RC 伺服控制訊號；不接 GPIO2、K2 IN 或 Q2 |
| R4 ×1 | **10kΩ／0.25W／±5%，SIG → G** | 開機訊號下拉，靠近伺服訊號介面；3.3V 時負載約 0.33mA、1.09mW |

K2 的 **VCC 從 ESP32 5V 接點分接**，K2 接點切換的則是 U1 提供的伺服電源；兩者不能混淆。LCD 5V、HC-SR04 VCC 亦由 ESP32 5V 接點分接，不是接到 3V3；本處表示 5V 電源分配節點，不是從 ESP32 的 3.3V 穩壓器取得 5V。伺服正負極不可像裸直流馬達那樣反接換方向。

原裸馬達的 D1 在本版移除，不照搬到伺服 V+／GND。伺服是內建驅動電路的完整負載，若需要供電端去耦或浪湧抑制，應依所選伺服與電源規格設計，不把它當成兩線馬達處理。

## 2. 保留的 K2 控制接法

| 元件／端點 | 接線 |
|---|---|
| K2 VCC | D-50B 5V → ESP32 5V 接點 → K2 VCC |
| K2 GND | ESP32 GND 分接點，與 G 同網路 |
| GPIO2 | R1 **1.5kΩ／¼W／±5%** → Q2 B |
| Q2 E | G |
| Q2 C | K2 IN |
| R2 | **47kΩ／¼W／±5%**，Q2 B → E/G |
| R3 | **4.7kΩ／¼W／±5%**，D-50B 5V 的電晶體分支 → R3 → IN/C；與 ESP32 的 5V 屬同一電源，但實體分支分開畫 |
| Q2 | 手上 S9014 或原 2N3904；B/C/E 依實物廠牌核對 |

Q2 只處理 K2 IN，不承受伺服電流。原介面設計 IC≤10mA、IN 低電位及釋放條件仍需實測；原計算見 [6V 馬達文件](./WIRING_6V_MOTOR.md)。

## 3. 腳位配置

按開發板上 GPIO／IO 絲印找腳，不是排針的第幾根。

本版實際編譯來源是 **`main/main.c` 的 ESP-IDF 專案**。根目錄的 `esp32s3_vl53l0x_servo.ino` 是早期單顆 ToF／GPIO4 伺服範例，不參與這次建置；不要依那份舊範例接 GPIO4 或將它另行上傳覆蓋本版。

| GPIO | 用途 | 本版處理 |
|---|---|---|
| **GPIO1** | **新增 SV1 SIG，3.3V RC 伺服脈波** | LEDC 低速模式、Timer0／Channel0、50Hz、14bit |
| GPIO2 | Q2 → K2 IN | 保留，高電位啟動 K2 |
| GPIO7 | 原 K1 IN | 保留，高電位啟動 K1 |
| **GPIO4** | **LCD RESET** | 保留，不能接伺服 |
| GPIO5、6 | HC-SR04 TRIG、ECHO 分壓節點 | 保留原分壓 |
| GPIO8、9、10 | ToF1 SDA、SCL、XSHUT | 保留 |
| GPIO11、12 | ToF2 SDA、SCL | 保留 |
| GPIO38、39、40、41 | LCD CS、RS、WR、RD | 保留 |
| GPIO13、14、15、16、17、18、21、47 | LCD D0–D7，依序 | 保留 |
| GND | G 共地排 | 與伺服負極、U1、K2、Q2 及既有低壓系統共地，先確認電源可共地 |

本版按直接接受 3.3V 訊號的伺服規劃；若實物需要更高訊號電位，須另設合適介面，不能將 5V 訊號反接至 ESP32。**目前尚未驗證任何特定 YF／DS／FT 伺服的訊號相容性。**

## 4. 供電條件

本圖沿用 **24V → LM2596 → 暫定 6.0V**，只適用額定範圍允許 6V 的伺服。先不接伺服，用電表量 OUT+／OUT− 並調整；不以降低供電來指定 40rpm。

伺服啟動、堵轉及動態電流要重新核對，**原 JGB37-520 的 1.5A 不能沿用**。未知 LM2596 模組不能只看晶片標稱 3A 就當成足夠。若所選伺服在 6V 下需要約 3A 峰值，需確認模組的實際輸出、掉壓、溫升及啟動裕量，不足時另換供電。

最新圖依使用者要求省略保護元件符號，並未將省略圖符視為拆除實體保護元件的建議；實際保護設計仍須另行驗證。5V、6V、24V 正極分開，市電 N 不接低壓 G。完整圖原 110V 區只是沿用拓樸，本次沒有重新驗收。

## 5. 編譯版的動作流程

原條件不變：ToF1<101mm、ToF2<101mm、HC-SR04<65mm，讀值有效且連續三次符合才啟動。

| 階段 | K1／K2 | GPIO1 |
|---|---|---|
| 開機、未觸發、停止 | 皆 OFF | LOW，沒有伺服脈波 |
| 三次符合 | 皆 ON | 暫維持 LOW，至少等待約 100ms 讓 K2／電源建立 |
| 初始訊號 | 皆 ON | **50Hz、1500µs**，維持至少約 500ms |
| 辨識訊號 | 皆 ON | 固定 **50Hz、1600µs**，直到感測器解除 |
| 任一讀值無效或超出門檻 | 嘗試關閉兩路 | **先停脈波、保持 LOW，再切 K2 電源** |
| PWM／GPIO 寫入錯誤 | 嘗試關閉兩路 | 嘗試停脈波，不宣稱硬體故障時一定斷電 |

等待採非阻塞狀態機，不額外暫停感測器判斷；100ms、500ms 由感測循環服務，因此實際時間可略長。50Hz 脈波由 LEDC 硬體產生；14bit 下每格約 1.221µs，實際標稱脈寬約 1500.24µs、1600.34µs。改脈寬生效仍有 PWM 週期延遲，不是機械即時停止保證。

**1500µs 是常見中點參考，不保證每款伺服都停止；定位型可能直接移到中間角度。1600µs 也不是固定角度、方向或 40rpm。** 本版不自動掃描端點，不自動反轉，不新增轉速回授。

停止使用 K2 切斷 V+，因此斷電後不提供位置保持力；初次測試需移除舵盤／連桿／負載，避免機構動作。這是辨識測試韌體，之後確認型號與實測速度後再校正 40rpm。

## 6. 之後拿到伺服時的辨識方式

1. 先隔離原鼓風機的 110V **負載支路**。本程式保留 K1 與 K2 同步啟動，三感測器觸發時仍會命令 K1 吸合；這次不做市電操作驗證。
2. 核對伺服型號、線序、供電範圍、啟動電流與訊號電位，再按圖接線。本測試版已燒入板上，下次上電後符合感測器條件，GPIO1 就會執行本頁的測試流程，不需再上傳舊 `.ino`。
3. 伺服空載，先保持感測器未全數觸發，確認 K2 釋放、GPIO1 無脈波。
4. 放好三個目標，滿足三次條件後，觀察 1500µs 階段及 1600µs 階段。若固定 1600µs 後轉到某角度停住，符合定位型反應；若能持續多圈且訊號變化能調整速度／停止，才符合正常連續旋轉控制特徵。
5. 不轉不能直接判成定位型，也可能是死區、訊號不相容、供電或接線問題。失控連續轉動也不能單憑此判定為正常連續型，仍需核對型號與停止／方向反應。
6. 移開任一目標，應撤除脈波並釋放 K2；若動作異常，直接切斷伺服供電。不要用手強行阻擋輸出軸測堵轉。

## 7. 本次驗證與重產生

已完成 ESP-IDF 編譯，以及對實際 `main/main.c` 控制函式的主機 GPIO／LEDC mock 檢查：開機 OFF、三次門檻、脈波時序、取消等待、三顆感測器各自無效／門檻等值時關閉、GPIO／PWM 故障時嘗試關閉、拒絕超出初始測試範圍的脈寬。這些是軟體驗證，不是電氣量測。

已燒入 `/dev/ttyACM0`，資料雜湊驗證通過並自動重啟；另以序列監看確認：

- `Relay ready: GPIO7 ... initial state OFF`
- `Motor relay ready: GPIO2 ... initial state OFF`
- `Servo signal ready: GPIO1, 50 Hz, signal LOW until sensors enable K2; identification test only`
- `ILI9486 dashboard ready: 480x320 ... LVGL 8.4.0`
- ToF1、ToF2 均在 I2C 0x29 偵測到；觀察期間 ToF1 無效、超音波約 642–646mm，輸出維持 OFF。

紀錄：[燒錄紀錄](./build/log/servo_test_flash.log)、[開機與感測器紀錄](./build/log/servo_test_boot.log)。本次二進位大小 **1,575,920 bytes**，SHA-256：`91f1c4e81689a6bfda2e696c78e96b25e5f7b39f37ca5ccef00aa25158941fb3`。

**尚未量測 GPIO1 實體波形、尚未接伺服或確認 360°／40rpm。** 原 LCD、感測器讀取、原鼓風機接線圖及 6V 減速馬達圖保留。開機紀錄不代表實體繼電器或伺服已動作。

```sh
python tools/test_servo_control.py
python tools/make_servo_wiring_diagram.py
rsvg-convert -z 1.5 -o docs/wiring/archive/legacy/wiring_servo_test_detail.png docs/wiring/archive/legacy/wiring_servo_test_detail.svg
rsvg-convert -z 1.5 -o docs/wiring/archive/legacy/wiring_110v_blower_servo_test.png docs/wiring/archive/legacy/wiring_110v_blower_servo_test.svg
. /opt/esp/idf/export.sh
idf.py build
```

產物：`build/esp32s3_vl53l0x_servo.bin`。

參考：[ESP-IDF 5.5.1 LEDC](https://docs.espressif.com/projects/esp-idf/en/v5.5.1/esp32s3/api-reference/peripherals/ledc.html)、[連續旋轉伺服控制特徵](https://www.pololu.com/category/143/continuous-rotation-servos)。以上介面描述不能代替所選伺服的原廠規格。
