# 來源與版本紀錄

| 資料 | 來源／固定版本 | 目前用途與限制 |
|---|---|---|
| Espressif 官方元件庫 | https://github.com/espressif/kicad-libraries/releases/tag/3.0.2 | 套件 metadata 最低 KiCad 8.0.0；來源 commit `4f6c7a65f161b0df77955b49a1398f77dfdb255e` |
| Espressif 套件 | https://github.com/espressif/kicad-libraries/releases/download/3.0.2/espressif-kicad-addon.zip | SHA-256 `2df44ed8a41246c5de9f40803a9329a22a7bd465c8a222dea8f36bffcbb79b6b`；42 個符號、46 個封裝、25 個 STEP、8 個 WRL 為下載內容盤點，非驗證完成數 |
| YD 開發板原廠資料 | https://github.com/vcc-gnd/YD-ESP32-S3/tree/b4ac4d60d1845a554bbbc7c97806ccb97cf08941 | 公開尺寸 PDF、Altium PCB 與 V1.4 原理圖；實物標示 Type-A V1.5，差異仍需核對；未找到明確再散布授權時只保留連結及事實擷取紀錄 |
| YD 第三方 KiCad 資料 | https://github.com/shkuznetsov/YD-ESP32-S3/tree/bb410449c3d5ee20096ff273d6c1081c5dd6228f | 作者稱 MIT，但符號／封裝為 KiCad 9 格式；不能直接交付 KiCad 8；3D 另出自 GrabCAD，不能宣稱原廠模型 |
| 實物識別照片 | 使用者提供 `/workspace/esp32.jpg` | 可辨識 VCC-GND Studio、YD-ESP32-S3、Type-A V1.5；照片不能單獨作為焊盤精密座標依據 |

下載快取置於工作區 `.kicad_library_cache`，不視為最終交付內容；最終包將保留必要授權、可追溯來源與實際驗證報告。

## 本次實際引入與修改

- 官方 3.0.2 的 42 個符號中，41 個放入有效庫；ESP32-WROOM-DA 因來源符號／封裝不一致保存在 `Reports/Quarantine`。不是刪掉原始資料後假稱全部通過。
- 原附 46 個封裝中，一個同樣隔離；另加入下列八個 KiCad 官方 QFN 封裝及原始授權。再加入自行建立的 YD 載板封裝，共 54 個有效封裝。
- KiCad footprint tag **8.0.9**，固定 commit `f6da1c7ab465ca8a77eadf30e9f7f9b8e2829f35`，來源：[官方 GitLab](https://gitlab.com/kicad/libraries/kicad-footprints/-/tree/8.0.9/Package_DFN_QFN.pretty)。逐檔下載 URL 與 SHA-256 在 `Sources/upstream_lock.json`。
- 八個尺寸：QFN24 4×4/P0.5/EP2.8、QFN28 4×4/P0.4/EP2.6、QFN32 5×5/P0.5/EP3.45、QFN32 5×5/P0.5/EP3.6、QFN40 5×5/P0.4/EP3.6、QFN48 6×6/P0.4/EP4.3、QFN48 7×7/P0.5/EP5.15、QFN56 7×7/P0.4/EP5.6；完整檔名保留於 footprint_sources.json。
- 原 25 個 STEP、8 個 WRL 直接保留內容。模型路徑改為 MY_KICAD_LIB_DIR，原有 scale／offset／rotate 不變；未捏造缺少的完整板模型。
- 9 個指定 QFN 模型在固定來源未取得；已移除失效引用並列在 missing_models.json。沒有拿相近 EP 尺寸模型替代。
- 重新指向實際註冊的 ESP32_Custom，並修正上游 ESP32-P4 的雙重 nickname 引用；補齊五個缺漏 metadata。
- 將上游隱藏、堆疊的供電腳展開為右側可見引腳，保持原電氣類型、名稱及編號。補充四款資料表已確認的 NC／內部保留腳，詳見 symbol_corrections.json；原基準另存 espressif_pin_baseline.json。
- 新增精確 N16R8 模組變體與獨立 YD 開發板符號。N16R8 的模組腳 28／29／30 是 IO35／36／37，依官方資料表禁止另作 GPIO 使用。
- YD 自製符號／封裝來自原廠尺寸與端子事實，非將第三方 KiCad 9 格式的版本字串改成 8。使用者實測確認排距；載板孔徑及焊盤是另行註記的工程預選值。
- 外接模組介面根據使用者照片、既有接線及確認的安裝方式建立；資料表只涵蓋 IC 或相似模組時，明確註明範圍。詳細資料見 external_parts.json 與 Datasheets/USER_PARTS_EVIDENCE.md。

## 實際驗證工具

使用真正的 KiCad 8.0.9 Ubuntu 建置，沒有以 KiCad 9／10 成功載入冒充 KiCad 8：

- [KiCad 官方 8.0 PPA 套件](https://ppa.launchpadcontent.net/kicad/kicad-8.0-releases/ubuntu/pool/main/k/kicad/kicad_8.0.9-0~ubuntu24.04.1_amd64.deb)
- 套件 SHA-256：`bf6b587c1ed596d4d19d671004fa7931ba649c60b60b93a55be3392dd76bf567`，與 PPA Packages 索引一致。
- 在 Linux 隔離的驗證設定目錄執行；沒有存取或修改使用者 Windows 全域元件庫設定。驗證環境使用額外的系統執行期套件；這些不是交付元件庫的一部分。
- 所有有效符號、封裝 SVG 與範例專案的實際執行結果、命令及 stderr 保存在 validation_results.json；沒做過的 GUI／實物驗證明確列為人工項目。

## 增量紀錄

使用者後續確認：LM2596 與其他現有模組均線材外接；TOF.jpg 顯示兩款不同板型，故分開收錄具名接線介面。GPIO／連接器符號的邏輯編號，不冒充未知實體焊盤位置。

最終打包尚需使用者明確結束收集；未確認型號及候選項目仍保留在 CSV 與人工核對清單。
