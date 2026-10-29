# KiCad 8 初版驗證報告

CLI：8.0.9；有效符號 52、封裝 54、3D 檔案 33。自動檢查錯誤 0 項。

零件紀錄共 71 筆，包含通用家族、使用者零件、歷史候選與隔離紀錄，不是實物數量。狀態分布：{'Partially Verified': 47, 'Pending': 23, 'Not Applicable': 1}。

## 自動檢查

- Python 已解析 52 個有效符號、54 個封裝。
- 腳位名稱、電氣類型及編號已與來源基準、修訂紀錄、外接端子清單比對；有 PCB 封裝者另核對 Pin/Pad 集合。
- 重複焊盤依上游露銅散熱焊盤清單核對；不是一律當成重複錯誤。
- 所有保留的模型引用均存在，且使用 MY_KICAD_LIB_DIR；缺少的上游模型已移除引用並明列。
- 實際 KiCad CLI 8.0.9 已匯出全部有效符號與封裝 SVG，並解析 SVG XML。
- 載入測試專案的原理圖 SVG、網表、ERC 與 PCB STEP 已實際執行；網表 A1/U1 分別對應開發板與裸模組封裝。僅測到該 WROOM STEP 的讀取，不代表全部 33 個模型已人工核對。

## 錯誤

本次自動檢查未發現錯誤。

## 人工核對與已知缺項

- 尚無完整模組原廠資料表：Display_Custom:TFT_3p5_Shield_Wire_Interface；僅依所列照片／接線資料建介面。
- 外接接線介面不指定整個模組的 PCB 封裝：Display_Custom:TFT_3p5_Shield_Wire_Interface；載板連接器仍需另選。
- 尚無完整模組原廠資料表：Other_Custom:RC_Servo_3Wire_Interface；僅依所列照片／接線資料建介面。
- 外接接線介面不指定整個模組的 PCB 封裝：Other_Custom:RC_Servo_3Wire_Interface；載板連接器仍需另選。
- 外接接線介面不指定整個模組的 PCB 封裝：Power_Custom:LM2596_Module_External；載板連接器仍需另選。
- 外接接線介面不指定整個模組的 PCB 封裝：Power_Custom:D-50B_External；載板連接器仍需另選。
- 外接接線介面不指定整個模組的 PCB 封裝：Relay_Custom:HW-307_5V_External；載板連接器仍需另選。
- 外接接線介面不指定整個模組的 PCB 封裝：Relay_Custom:SLA05_Relay_Module_Wire_Interface；載板連接器仍需另選。
- 外接接線介面不指定整個模組的 PCB 封裝：Sensors_Custom:VL53L0X_Module_I2C_4Wire_Interface；載板連接器仍需另選。
- 外接接線介面不指定整個模組的 PCB 封裝：Sensors_Custom:VL53L0_1X_V2_6Wire_Interface；載板連接器仍需另選。
- 尚無完整模組原廠資料表：Sensors_Custom:HC-SR04_4Wire_Interface；僅依所列照片／接線資料建介面。
- 外接接線介面不指定整個模組的 PCB 封裝：Sensors_Custom:HC-SR04_4Wire_Interface；載板連接器仍需另選。
- 9 個上游封裝的指定模型未在固定來源取得；詳見 missing_models.json。
- YD-ESP32-S3 完整開發板 3D 缺少，使用者已接受；V1.5 逐腳與實際排母尺寸仍待核對。
- ESP32-WROOM-DA 已保存在 Reports/Quarantine，不註冊供設計使用。
- 尚未驗證 Windows GUI、全部模型的外形與對位、實物裝配或正式電路 ERC/DRC；範例全部腳位未接，不能當成產品電路。

自動通過僅證明目前檔案能被 KiCad 8 解析及所列結構一致，不能取代實物、資料表、ERC/DRC 或電氣安全驗收。
