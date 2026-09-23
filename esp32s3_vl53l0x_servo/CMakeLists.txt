cmake_minimum_required(VERSION 3.16)

set(COMPONENTS main vl53l0x_idf)
set(EXCLUDE_COMPONENTS arduino ESP32Servo VL53L0X vl53l0x)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(esp32s3_vl53l0x_servo)
