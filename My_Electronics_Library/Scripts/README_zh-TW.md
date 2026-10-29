# 重建、驗證與增量維護

所有工具不修改 KiCad 原廠資料庫或全域庫表。Python 工具僅用標準庫；載入範例的 PCB 重產生才需要 KiCad 8 的 pcbnew 綁定。

## 一般重建

在資料庫根目錄，Windows PowerShell：

```powershell
py .\Scripts\build_library.py
py .\Scripts\validate_library.py --kicad-cli "C:\Program Files\KiCad\8.0\bin\kicad-cli.exe"
```

CLI 安裝路徑以你電腦實際位置為準。版本不是 8.x 時，驗證會報錯。

建置依 `Sources/upstream_lock.json` 下載固定來源並核對 SHA-256。預設快取位於資料庫上一層的 `.kicad_library_cache`，不會下載最新 main。完整快取已存在時可離線：

```powershell
py .\Scripts\build_library.py --offline
```

也可用 `--cache "D:\KiCad_Source_Cache"` 指定自己的快取。下載為必要來源，不是自動安裝 KiCad。重建結果相同時不重寫元件檔。

## 新增與修訂

| 檔案 | 用途 |
|---|---|
| Sources/yd_esp32_s3.json | 開發板端子、幾何事實、工程預選孔徑及待確認事項 |
| Sources/upstream_lock.json | 上游版本、來源與檔案雜湊 |
| Sources/espressif_pin_baseline.json | 原始官方腳位名稱、類型、編號基準 |
| Sources/symbol_corrections.json | 補齊已核對 NC、metadata、展開隱藏電源腳與隔離異常元件 |
| Sources/external_parts.json | 目前外接模組的邏輯端子；不是模組實體焊盤座標 |
| Sources/previous_parts.json | 尚無足夠資料的零件、歷史方案、替代候選 |
| Sources/repeated_pads.json | 官方露銅散熱焊盤的重複編號及數量基準 |

新增零件使用唯一 Component ID、明確 SourceScope、真實狀態。外接設備可增加 external_parts；實體焊接元件需要另外取得官方封裝及腳位，加入生成器與註冊表，不得冒充成外接介面來省略封裝。

重建會保留不屬於本工具管理 ID 的清單列。已管理資料應改 Sources，不能只改 CSV。工具偵測到符號、封裝或已記錄的 CSV 被直接改過會停止，先合併修訂，不會靜默覆蓋。正常更新前的檔案存於 `.history`。

刪除已收錄符號需要使用者先確認；確認後才可使用 `--confirm-removal`。不要因為要讓檢查通過而隨意刪除來源基準或放寬重複焊盤清單。

## 驗證結果

`Reports/validation_report.md` 為摘要；`validation_results.json` 保存實際 CLI 命令、輸出、版本、來源雜湊與錯誤。`pin_pad_map.csv` 是逐腳對應。`Previews` 是 CLI 匯出 SVG；`Fixture` 是範例原理圖／網表／ERC／STEP 證據。

自動解析成功不會把 Partially Verified 改成 Verified。Verified 需要對應版本的電氣、尺寸及裝配人工核對；清單中的未知項目保持 Pending。

## 最終打包

只有使用者明確表示「全部完成」或「開始打包」後才執行：

```powershell
py .\Scripts\package_library.py --confirm-collection-complete
```

輸出位於上一層 `dist\My_Electronics_KiCad8_Library.zip`。腳本會檢查最近一次真正的 KiCad 8 驗證、輸入雜湊與 ZIP 完整性；不包含快取、`.history` 或 Python 快取。Pending 與隔離紀錄會隨報告保留，不會冒充完成元件。

尚未獲得結束收集指示時，不執行打包旗標；一般 build／validate 不會產生 ZIP。
