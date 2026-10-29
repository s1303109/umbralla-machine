# 使用者零件證據與資料表範圍

原始照片留在使用者工作區；下列為端子事實及來源索引。未找到明確再散布授權的廠商 PDF 僅提供連結，不將網路可下載視為可任意再散布。

| 實物／文件 | 已觀察到的資料 | 限制 |
|---|---|---|
| `esp32.jpg` | VCC-GND Studio、YD-ESP32-S3、Type-A V1.5 | 官方公開 V1.4 原理圖仍需版本核對；使用者確認排距 25.40 mm |
| `TOF.jpg` 上方小板 | VL53L0X、VIN/GND/SCL/SDA；側邊另有兩個焊盤 | 不假定是與下方相同板型。四線介面不包含尚未確認的側邊功能；VIN 額定未知 |
| `TOF.jpg` 下方長板 | VL53L0/1X V2、V438 字樣；VIN/GND/SCL/SDA/GPIO1/XSHUT | 共用 PCB 字樣不能證明實際裝了 L0X 或 L1X。供電／上拉／電平轉換未核對 |
| `RELAY SMALL 05VDC.jpg` | HW-307、JQC3F-05VDC-C；IN/GND/VCC、常開／公共／常閉 | 照片接點印字不能當成整板馬達負載驗證 |
| `pin of lcd.jpg` | 3.5 吋 TFT LCD Shield；LCD_D0…D7、RST/CS/RS/WR/RD、SD_SS/DI/DO/SCK、5V/3V3/GND；74HC245×2、AMS1117-3.3 | 完整 PCB 板號、未標示針腳及電源方向仍待確認；未編造 Arduino shield 座標 |
| `transformer ammp.jpg` | MEAN WELL D-50B；5V 6A、24V 1A | 端子編號另依原廠文件；不沿用舊 S-50-5 的排列 |
| `WIRING_6V_MOTOR.md` | 完整 LM2596 模組四端：IN+、IN−、OUT+、OUT− | TI IC 資料表只涵蓋晶片；不能證明未知模組可持續 3A |
| `WIRING_SERVO_TEST.md` | K1/K2、Q2 與電阻值；三線伺服 V+/GND/SIG | 伺服完整型號、6V／3.3V 相容性與連續旋轉能力仍未確認 |

使用者已確認：ESP32 插在載板排母，其他現有模組均以線材外接。外接介面符號不主張模組實際焊盤編號，載板連接器需另選。

## 廠商資料索引

- [Espressif ESP32-S3-WROOM-1／1U](https://documentation.espressif.com/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf)：N16R8 記憶體與 IO35/36/37 保留。
- [YD 原廠資料固定版本](https://github.com/vcc-gnd/YD-ESP32-S3/tree/b4ac4d60d1845a554bbbc7c97806ccb97cf08941)：機構圖、V1.4 原理圖與腳位表。
- [MEAN WELL D-50 規格](https://www.meanwell.com/Upload/PDF/D-50/D-50-SPEC.PDF)：D-50B，1=L、2=N、3=FG、4=+V2、5/6=COM、7=+V1；V2=24V、V1=5V。
- [TI LM2596](https://www.ti.com/lit/ds/symlink/lm2596.pdf)：晶片規格，非未知整板模組保證。
- [ST VL53L0X](https://www.st.com/resource/en/datasheet/vl53l0x.pdf)：晶片功能；非紫色轉接板的完整供電規格。
- [30A relay module 介面指南](https://www.handsontec.com/dataspecs/module/30A-RelayMod.pdf)：同類型模組參考，不能作為實物板型完全一致的證據。

S9014 C331、2N3904、1N5408／1N5822、舊馬達及舊電源的區分詳見零件清單；沒有把曾討論的所有候選都當成目前已安裝元件。
