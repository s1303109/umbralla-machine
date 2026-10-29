# KiCad 8 載入測試專案

開啟 `Library_Loading_Test.kicad_pro`；先依安裝教學設定 MY_KICAD_LIB_DIR。

- A1：YD-ESP32-S3 開發板的 44 腳載板封裝，沒有整板 3D。
- U1：ESP32-S3-WROOM-1-N16R8 裸模組及其官方 STEP。
- 兩者分開放置，不能互換封裝。
- 所有引腳刻意未接；無功能電路、無配線。載板板框、安裝位置只是檔案載入測試，不是 RF 或可製造設計。

`Reports/Fixture` 保存自動匯出證據。原理圖載入及測試專案 ERC，不能代替實際產品電路 ERC／DRC。

重新產生範例使用 `Scripts/make_example.py`；PCB 重產生需要 KiCad 8 的 pcbnew Python 綁定。一般元件庫重建及驗證不需要該綁定，只需 Python 3 與真正的 KiCad 8 CLI。
