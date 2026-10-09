idf_component_register(
  SRCS
    "main.c"
    "lcd_display.c"
  INCLUDE_DIRS "."
  REQUIRES
    vl53l0x_idf
    esp_driver_gpio
    esp_driver_i2c
    esp_timer
  EMBED_FILES
    "assets/dashboard.rgb565"
)
