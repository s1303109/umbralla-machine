# 接線圖：目前請看這裡

目前方案是 JGB37-555 24V／7rpm，沒有 LM2596 與伺服訊號。

- [完整接線圖 PNG](wiring_110v_blower_24v_no_buck.png)
- [可放大 SVG](wiring_110v_blower_24v_no_buck.svg)
- [PDF](wiring_110v_blower_24v_no_buck.pdf)
- [低壓供電與控制詳圖 PNG](wiring_24v_motor_no_buck_detail.png)
- [新版說明與產圖指令](docs/wiring/24v_motor_reference.md)
- [歷史圖片封存清單](docs/wiring/archive/README.md)

新版只有一個 ESP32 方塊：電源 5V 直接分接 ESP32、K1、R3；ESP32 的同一個 5V 接點再分接 K2、LCD、HC-SR04。

舊 WIRING_SERVO_TEST、WIRING_6V_MOTOR、WIRING_24V_MOTOR 文件及 wiring_connected_current.csv／html 保留歷史資料，並未改成新版接線。程式未更動，仍含伺服測試流程。
