# 24V 馬達直供參考圖

沿用使用者指定的 `wiring_110v_blower_servo_test.png` 彩色分區版型，新增獨立參考圖。

- 完整圖：[PNG](../../wiring_110v_blower_24v_no_buck.png)、[SVG](../../wiring_110v_blower_24v_no_buck.svg)、[PDF](../../wiring_110v_blower_24v_no_buck.pdf)。
- 馬達與控制介面詳圖：[PNG](../../wiring_24v_motor_no_buck_detail.png)、[SVG](../../wiring_24v_motor_no_buck_detail.svg)。
- 產生工具：[make_24v_motor_reference.py](../../tools/make_24v_motor_reference.py)。

## 接線關係

| 起點 | 終點 |
|---|---|
| D-50B 第 4 端 +24V | K2 接點 COM |
| K2 接點 NO | JGB37-555 馬達正極 |
| 馬達負極 | D-50B 第 5／6 端 COM，以獨立適當線徑回流 |
| D1 1N5408 有環 K | 馬達正極，位於 K2 NO 後 |
| D1 無環 A | 馬達負極 |
| D-50B 第 7 端 +5V | 原有 K1、ESP32、R3 三個直接分支 |
| ESP32 5V 接點分接 | K2 VCC、LCD 5V、HC-SR04 VCC |
| ESP32 GND 接點分接 | K2、LCD、HC-SR04 的 GND |
| D-50B 第 5／6 端 COM | 低壓共地 G，包括 ESP32 GND、Q2 E |
| D-50B 第 3 端 FG | PE 保護接地；本圖不畫 COM–FG 短接 |
| GPIO2 | R1 1.5kΩ → Q2 B |
| Q2 C | K2 IN，並接 R3 4.7kΩ 至 D-50B +5V |
| Q2 B | R2 47kΩ → Q2 E／G |

不包含 LM2596、三線伺服、GPIO1 訊號配線或伺服專用 10kΩ 下拉；HC-SR04 的 10kΩ／20kΩ 分壓仍保留。

D 區已用完整橘色線畫出 ESP32 的 5V 分接至 K2 VCC，繞過電晶體電源分支方塊上方；R3 上端仍由 D-50B 的 +5V 直接分支供電。

## 依據與未確認事項

使用者提供的 JGB37-555-2460 商品表：24V、810 減速比，空載 7rpm／0.14A、額定負載 5.5rpm／0.65A、堵轉 3A。這些是商品數據，尚未以實物量測。

[MEAN WELL D-50 原廠規格](https://www.meanwell.com/Upload/PDF/D-50/D-50-spec.pdf)及先前電源銘牌顯示 D-50B 的 24V 額定只有 1A、5V 額定 6A；本圖的供電路徑不代表已證實可啟動馬達。另換電源時需重新核對其端子、啟動能力與共地方式，不能直接套用 D-50B 端子編號。

Q2 僅控制 K2 IN。K2 的直流馬達接點能力、Q2 實物腳序、D1 續流電流與熱條件、配線及保護選型仍待確認。圖面省略保護元件符號不表示可拆除實物；市電區沿用原圖作辨識參考，並未完成重新驗收。

只新增圖面，未修改 `main/main.c`、現有產圖工具、舊圖或現行 CSV／HTML。韌體仍含伺服測試功能；未編譯、未燒錄、未實機通電驗證。

## 重產生

在專案根目錄執行：

```sh
python tools/make_24v_motor_reference.py
rsvg-convert -z 1.5 -o wiring_110v_blower_24v_no_buck.png wiring_110v_blower_24v_no_buck.svg
rsvg-convert -f pdf -o wiring_110v_blower_24v_no_buck.pdf wiring_110v_blower_24v_no_buck.svg
rsvg-convert -z 1.5 -o wiring_24v_motor_no_buck_detail.png wiring_24v_motor_no_buck_detail.svg
```
