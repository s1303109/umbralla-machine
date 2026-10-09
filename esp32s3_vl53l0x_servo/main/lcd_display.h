#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "esp_err.h"

typedef struct {
    bool blower_running;
    bool tof_1_active;
    bool tof_2_active;
    bool ultrasonic_active;
    bool tof_1_valid;
    bool tof_2_valid;
    bool ultrasonic_valid;
    uint32_t tof_1_distance_mm;
    uint32_t tof_2_distance_mm;
    uint32_t ultrasonic_distance_mm;
} lcd_display_status_t;

esp_err_t lcd_display_start(void);
void lcd_display_update(const lcd_display_status_t *status);
