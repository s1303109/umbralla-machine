cmake_minimum_required(VERSION 3.18)

# Keep the pinned graphics dependency in the build tree, outside components/.
include(FetchContent)
if(POLICY CMP0135)
  cmake_policy(SET CMP0135 NEW)
endif()
FetchContent_Declare(lvgl
  URL https://codeload.github.com/lvgl/lvgl/tar.gz/refs/tags/v8.4.0
  URL_HASH SHA256=3b454d602e1667b9bd2c434f5e8156753d92cf3e71fc40a0cb0d99fca9a605be
  SOURCE_DIR "${CMAKE_BINARY_DIR}/_deps/lvgl"
  # Population only; ESP-IDF registers this component after project().
  SOURCE_SUBDIR idf-component-only
)
FetchContent_MakeAvailable(lvgl)
list(APPEND EXTRA_COMPONENT_DIRS "${lvgl_SOURCE_DIR}")

set(COMPONENTS main vl53l0x_idf)
set(EXCLUDE_COMPONENTS arduino ESP32Servo VL53L0X vl53l0x)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(esp32s3_vl53l0x_servo)
