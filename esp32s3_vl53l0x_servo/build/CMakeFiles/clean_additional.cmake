# Additional clean files
cmake_minimum_required(VERSION 3.16)

if("${CONFIG}" STREQUAL "" OR "${CONFIG}" STREQUAL "")
  file(REMOVE_RECURSE
  "blower_off.rgb565.S"
  "blower_on.rgb565.S"
  "bootloader/bootloader.bin"
  "bootloader/bootloader.elf"
  "bootloader/bootloader.map"
  "config/sdkconfig.cmake"
  "config/sdkconfig.h"
  "dashboard.rgb565.S"
  "esp-idf/esptool_py/flasher_args.json.in"
  "esp-idf/mbedtls/x509_crt_bundle"
  "esp32s3_vl53l0x_servo.bin"
  "esp32s3_vl53l0x_servo.map"
  "fan_delta.s8.S"
  "fan_original.rgb565.S"
  "flash_app_args"
  "flash_bootloader_args"
  "flash_project_args"
  "flasher_args.json"
  "ldgen_libraries"
  "ldgen_libraries.in"
  "menu_digits.alpha8.S"
  "project_elf_src_esp32s3.c"
  "relay_off.rgb565.S"
  "relay_on.rgb565.S"
  "sensor_lights_off.rgb565.S"
  "sensor_lights_on.rgb565.S"
  "x509_crt_bundle.S"
  )
endif()
