# Windows 11／KiCad 8 全域安裝教學

## 1. 固定保存位置

將完整 `My_Electronics_Library` 資料夾放到：

```text
C:\Users\你的帳號\Documents\KiCad_Libraries\My_Electronics_Library
```

如 Documents 在 OneDrive 內，以實際位置為準。不要只複製 Symbols 或 Footprints，也不要移到 KiCad 的 Program Files 原廠庫內。目前可直接複製工作區資料夾；最終 ZIP 尚需使用者確認結束收集後才會產生。

## 2. 設定路徑變數

在 KiCad 8 主視窗開啟「偏好設定 → 設定路徑」（Preferences → Configure Paths），新增：

| 名稱 | 值 |
|---|---|
| MY_KICAD_LIB_DIR | 完整 `My_Electronics_Library` 資料夾的絕對路徑 |

值的尾端不必加斜線，不要把變數值設到 Symbols 子資料夾。所有模型引用使用 `${MY_KICAD_LIB_DIR}/3D_Models/...`，不要逐一手改成某台電腦的磁碟路徑。

## 3. 加入全域符號庫

「偏好設定 → 管理符號庫 → 全域庫」（Manage Symbol Libraries → Global Libraries），以「加入現有庫」選取 `Symbols` 中所有 `.kicad_sym`：

| Nickname（必須維持） | 檔案 |
|---|---|
| ESP32_Custom | ESP32_Custom.kicad_sym |
| Power_Custom | Power_Custom.kicad_sym |
| Relay_Custom | Relay_Custom.kicad_sym |
| Sensors_Custom | Sensors_Custom.kicad_sym |
| Display_Custom | Display_Custom.kicad_sym |
| Other_Custom | Other_Custom.kicad_sym |

將各路徑設為 `${MY_KICAD_LIB_DIR}/Symbols/檔案名稱`。可參考 `Config/sym-lib-table.example`，但**不要用範例檔覆寫現有全域表格**。如同名庫已存在，先辨識其用途，勿直接覆蓋。

## 4. 加入全域封裝庫

「偏好設定 → 管理封裝庫 → 全域庫」（Manage Footprint Libraries → Global Libraries），加入整個：

```text
${MY_KICAD_LIB_DIR}/Footprints/ESP32_Custom.pretty
```

Nickname 必須為 `ESP32_Custom`，與符號的 Footprint 屬性一致。選取 `.pretty` 資料夾，不是逐一加入 `.kicad_mod`。其他分類目前是外接接線介面，沒有實體封裝庫，不需建立空白 `.pretty`。

## 5. 搜尋並放置

在原理圖編輯器按 A，搜尋 `YD-ESP32-S3_Type-A_V1.5_N16R8`，放置後按 E 檢查：

- Footprint 應是 `ESP32_Custom:YD-ESP32-S3_2x22_P2.54mm_Row25.40mm`。
- `ESP32-S3-WROOM-1-N16R8` 是裸模組，使用貼片封裝；不要選錯。
- GPIO35／36／37 在 N16R8 上標示保留，不作一般 GPIO 接出。
- 原廠通用系列名稱不一定是可直接下單的完整採購料號；先看 Verification、Description 及清單備註。

`Power_Custom` 等外接介面不直接產生模組 PCB 焊盤。應另放載板連接器，讓 PCB 上的端子接至這些外部設備。端子型號、額定與腳距未選定前，不要任意指定一個尺寸相似的封裝。

## 6. 導入 PCB 與查看 3D

原理圖完成註解、網路接線及 ERC 後，使用「工具 → 從原理圖更新 PCB」（F8）。使用者自行確認符號／封裝對應、方向及各 pad 編號，之後才佈局。

在 PCB 編輯器以 Alt+3 開啟 3D Viewer。已有官方 STEP／WRL 的模組應顯示模型；完整 YD 開發板模型尚缺，因此載板上只見焊盤／板框相關內容，不會自動出現整片開發板。不能把裸 WROOM 的 STEP 掛到 YD 封裝上當作完成。

若模型不見，檢查 `MY_KICAD_LIB_DIR` 是否指到正確根目錄，以及 `Reports/missing_models.json` 是否列為原本缺少；不要先任意改縮放、位移或旋轉。

## 7. 範例專案

開啟 `Examples/Library_Loading_Test.kicad_pro`，可看到開發板 A1 與裸模組 U1。範例使用自己的專案庫表，但仍需要設定上述根目錄變數。所有引腳刻意未接；板框與元件位置僅供載入測試，沒有供電、感測器或馬達電路，**不是可製造設計**。

自動 SVG、網表與 STEP 測試證據在 `Reports/Fixture`。這些驗證已由 Linux KiCad 8.0.9 執行；你仍需在 Windows 8.x 親自確認 GUI 搜尋、顯示與裝配。

## 8. 更新、備份與搬移

- 新增資料應修改 `Sources` 的來源紀錄或新增獨立分類庫，再執行建置與驗證；細節見 `Scripts/README_zh-TW.md`。
- 不要直接編輯 `Reports/component_list.csv` 當成唯一來源，重建會重新產生已管理列；應修改對應的 Sources 紀錄。
- 若直接修改已產生的符號／封裝，建置工具會偵測並停止，避免靜默蓋掉。先把修訂整理回生成程式／來源檔後再重建。
- 備份整個資料夾；`.history` 是本機修改前快照，不應用它取代完整備份。
- 搬移到另一台電腦後，只需重新設定 `MY_KICAD_LIB_DIR` 並加入庫表，模型路徑不必逐個修改。
- 新版應先在另一資料夾驗證，再切換根目錄變數；保留舊版，以便舊專案重現。

資料庫註冊不會驗證電源、驅動電流、觸點負載或市電設計。元件規格與最終 PCB 的 ERC／DRC、裝配及安全性分開確認。
