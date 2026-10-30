# 低壓載板網路契約核對

狀態：DRAFT_NOT_FOR_FABRICATION。只含低壓 DC／控制接口，不把110V、AC/N、PE或K1市電接點放到載板。

- 韌體 GPIO 已逐一讀取：22個新馬達方案使用的 GPIO；GPIO1仍由韌體輸出伺服脈波，但載板不接。
- A1 使用本地 YD 插接板符號／封裝的 J1.1…J1.22、J2.1…J2.22。J1.21=5V、J1.1／J1.2=3V3、J2.5=GPIO2、J1.7=GPIO7；GPIO35/36/37保留不接。
- R3 必須是 +5V_IN 到 K2_IN_L 的上拉；Q2 C 直接接 K2_IN_L，不經串聯電阻。
- R4 10kΩ為 ECHO 到GPIO6的上臂；R5 20kΩ為GPIO6到GND的下臂。
- D1 K接MOTOR_SW24、A接GND；與馬達並聯且在K2 NO之後。
- +5V_IN供K1、R3及JP1；JP1接到+5V_ESP，再供ESP32、LCD、HC-SR04、K2。JP1在USB供電時需移除，未宣稱有自動電源切換。
- LCD與外接接口的排針順序均為此專案定義，不是原模組實物焊盤順序。LCD16號、ToF1 GPIO1端未接。
- ToF VIN未確認，提出JP2／JP3選3V3或5V的方案，預設不裝跳帽；不能在未確認模組供電與上拉時直接選5V。
- Q2只定義邏輯B/C/E，不能把S9014、2N3904、CS9013的實物腳序當成通用；須核對後再定製造焊盤。

完整44腳對照、每個元件端點、網路列表與待確認項目見 design_contract.json。
