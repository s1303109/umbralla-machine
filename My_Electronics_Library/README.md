# My_Electronics_Library：KiCad 8 個人元件庫

這是實際可由 KiCad 8 載入的增量元件庫初版。**檔案格式與自動結構驗證，不等於所有零件已核准製板。** 最新數量及實際結果以 [驗證報告](Reports/validation_report.md) 為準。

## 已建立內容

| 註冊名稱 | 內容 |
|---|---|
| ESP32_Custom | Espressif 3.0.2 相容元件、明確的 N16R8 模組變體、YD-ESP32-S3 開發板載板封裝 |
| Power_Custom | LM2596 完整外接模組、MEAN WELL D-50B 外接電源 |
| Relay_Custom | HW-307 與 SLA-05VDC-SL-C 模組的接線介面 |
| Sensors_Custom | 兩種不同 ToF 板型與 HC-SR04 的接線介面 |
| Display_Custom | 照片中 3.5 吋 TFT LCD Shield 的具名接線介面 |
| Other_Custom | 型號待確認的三線 RC 伺服接線介面 |

完整開發板、WROOM 模組與裸晶片分開建檔。不要將 `ESP32-S3-WROOM-1-N16R8` 的貼片封裝套用在完整開發板上。

你的開發板符號：`ESP32_Custom:YD-ESP32-S3_Type-A_V1.5_N16R8`。

載板封裝：`ESP32_Custom:YD-ESP32-S3_2x22_P2.54mm_Row25.40mm`。兩排各 22 腳、腳距 2.54 mm、排距 25.40 mm；排距經使用者確認。封裝使用 `J1.1…J1.22`、`J2.1…J2.22`，均由天線端向 USB 端編號，**不是 GPIO 編號**。

載板焊盤直徑 1.8 mm、孔徑 1.1 mm 是排母預選設計值，仍須依實際排母圖面核對。原廠公開原理圖為 V1.4，實物是 V1.5，仍需逐腳實物核對。完整開發板 3D 缺少，使用者已同意先收錄。

## 外接介面與待確認零件

使用者確認：ESP32 插在兩排排母上；其他現有模組保留原板，以線材外接。因此這些模組的符號設定 `on_board=no`，不會冒出一個猜測的整板 PCB 封裝。載板端子是另一顆元件，型號、線徑及腳距尚待選定。

外接符號的端子編號是穩定的**邏輯介面名稱**；不是聲稱模組焊盤實際刻有這些編號。部分符號僅表示現用接線介面，例如上方小 ToF 的四線 I2C 介面，其他側邊焊盤尚未辨識。完整模組規格、供電範圍及所有實體引腳仍可能待確認。

S9014 C331 的廠牌／腳序、電阻電容的實體封裝、保險絲、載板端子及確切伺服型號尚未完整取得，保留在清單中，不使用猜測封裝代替。舊方案及替代候選也有記錄，不當成目前已安裝零件。

## 開始使用

1. 依 [Windows 11 安裝教學](INSTALL_GUIDE_zh-TW.md) 設定 `MY_KICAD_LIB_DIR`，加入全域符號庫與封裝庫。
2. 查看 [零件清單](Reports/component_list.csv)、[待辦進度](Reports/progress.json)、[人工核對清單](Reports/manual_review.md)。
3. 開啟 [載入測試專案](Examples/Library_Loading_Test.kicad_pro)。它區分開發板與裸模組；沒有功能接線，不能拿去製板。
4. 透過 `Scripts/build_library.py` 重建，透過 `Scripts/validate_library.py` 驗證；詳見 [維護說明](Scripts/README_zh-TW.md)。

來源與修改見 [SOURCE_MANIFEST.md](SOURCE_MANIFEST.md)，授權見 [LICENSES/README.md](LICENSES/README.md)。未修改 KiCad 原廠庫或既有全域設定。驗證使用 Linux 的真正 KiCad 8.0.9 CLI；沒有假稱已在 Windows GUI 實測。

目前仍依既有型號與照片持續收錄，沒有自行認定零件收集已結束。只有使用者明確表示「全部完成」或「開始打包」後，才產生最終 ZIP。下次工作先讀進度檔；每次只問一個尚未解決的問題，優先利用已提供的資料。
