# 接線圖：目前請看這裡

目前方案是 JGB37-555 24V／7rpm，沒有 LM2596 與伺服訊號。

- [完整接線圖 PNG](wiring_110v_blower_24v_no_buck.png)
- [可放大 SVG](wiring_110v_blower_24v_no_buck.svg)
- [PDF](wiring_110v_blower_24v_no_buck.pdf)
- [低壓供電與控制詳圖 PNG](wiring_24v_motor_no_buck_detail.png)
- [新版說明與產圖指令](docs/wiring/24v_motor_reference.md)
- [歷史圖片封存清單](docs/wiring/archive/README.md)

目前已恢復先前彩色分區版型，只修正 5V 畫法。B、D 區是同一塊 ESP32；D 區 K2 VCC 沿用 B 區既有 5V 分接，不另拉線回 ESP32。電源仍直接分接 ESP32、K1、R3；K2、LCD、HC-SR04 由 ESP32 接點分接。

舊 WIRING_SERVO_TEST、WIRING_6V_MOTOR、WIRING_24V_MOTOR 文件及 wiring_connected_current.csv／html 保留歷史資料，並未改成新版接線。程式未更動，仍含伺服測試流程。


## KiCad 實作草稿

- [開啟 KiCad 專案](pcb/24v_motor_carrier/esp32s3_24v_carrier.kicad_pro)
- [PCB 元件擺放預覽](pcb/24v_motor_carrier/preview/placement.png)
- [PCB 雙層銅箔預覽](pcb/24v_motor_carrier/preview/board_layers.png)
- [原理圖 PDF](pcb/24v_motor_carrier/preview/schematic.pdf)
- [專案說明與接頭腳序](pcb/24v_motor_carrier/README.md)
- [完整專案 ZIP](pcb/esp32s3_24v_carrier_draft.zip)

此實作為91.44×76.20mm低壓載板，110V接點保持板外。ERC／DRC與網路一致性檢查已通過；實物封裝、接頭、供電與電流容量仍待確認，不能直接送製板。
