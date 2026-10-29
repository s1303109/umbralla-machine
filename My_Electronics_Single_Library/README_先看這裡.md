# 單一符號庫安裝版（KiCad 8）

這一包將原本六個分類庫合併成一個檔案，包含 52 個符號。原完整版 ZIP 保留不變。

## 只加入符號，做這兩步

1. 解壓整個資料夾，放在固定位置，例如 `Documents\KiCad_Libraries\My_Electronics_Single_Library`。
2. KiCad → 偏好設定 → 管理符號庫 → 全域庫 → 加入現有庫，選資料夾根目錄的 **My_Electronics_All.kicad_sym**，按確定。

現在原理圖按 A，搜尋 `YD-ESP32-S3`，或選 `My_Electronics_All`，就能找到這包的全部符號。

**不能直接從 ZIP 內選檔。僅複製到某個資料夾，也不會讓 KiCad 自動註冊；需執行一次上述加入現有庫。** 不要覆蓋原廠庫或整份全域設定。

## 要使用 PCB 封裝／3D，再做這兩步

1. 偏好設定 → 設定路徑，新增 `MY_KICAD_LIB_DIR`，值為這一包解壓後的完整根目錄。
2. 偏好設定 → 管理封裝庫 → 全域庫 → 加入 `Footprints/ESP32_Custom.pretty` 整個資料夾，Nickname 保持 **ESP32_Custom**。

符號庫名稱 My_Electronics_All 和封裝庫名稱 ESP32_Custom 不同，這是刻意保留的有效對應。

## 限制與維護

有 54 個封裝、33 個 3D 檔案。外接模組僅有接線介面，不直接指定整個模組的 PCB 封裝；載板連接器仍需另選。未知型號、待確認尺寸、缺少模型與隔離項目均保留在 Reports，不因合併而變成已驗證。

YD 完整開發板沒有整板 3D，裸 WROOM 模組則有自己的官方模型。S9014、伺服等待確認資料仍未補成猜測的完整料號。

這是方便安裝的合併輸出；新增與維護仍使用原本的完整版資料庫及工具，更新後再重新合併。已用原六庫建立的舊專案可繼續使用原庫，不需要為了這包刪掉原庫或重新指定舊符號。

Config 是參考表，**不是拿來覆蓋你現有的全域庫表**。符號合併後的實際解析與封裝引用檢查見 Reports/single_library_validation.md；上游來源與原始變更歷史見 SOURCE_MANIFEST.md。
