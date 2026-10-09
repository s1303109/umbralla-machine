#include <stddef.h>
#include <stdint.h>

#include "driver/gpio.h"
#include "esp_check.h"
#include "esp_log.h"
#include "esp_rom_sys.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "LCD_PROBE";

// Keep the high-level-trigger relay OFF throughout LCD diagnosis.
#define RELAY_PIN GPIO_NUM_7

#define LCD_RST_PIN GPIO_NUM_4
#define LCD_CS_PIN GPIO_NUM_38
#define LCD_RS_PIN GPIO_NUM_39
#define LCD_WR_PIN GPIO_NUM_40
#define LCD_RD_PIN GPIO_NUM_41

static const gpio_num_t LCD_DATA_PINS[8] = {
    GPIO_NUM_13,
    GPIO_NUM_14,
    GPIO_NUM_15,
    GPIO_NUM_16,
    GPIO_NUM_17,
    GPIO_NUM_18,
    GPIO_NUM_21,
    GPIO_NUM_47,
};

static uint64_t lcd_data_pin_mask(void)
{
    uint64_t mask = 0;
    for (size_t bit = 0; bit < 8; ++bit) {
        mask |= 1ULL << LCD_DATA_PINS[bit];
    }
    return mask;
}

static void lcd_set_data_direction(gpio_mode_t mode)
{
    const gpio_config_t config = {
        .pin_bit_mask = lcd_data_pin_mask(),
        .mode = mode,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&config));
}

static void lcd_write_bus(uint8_t value)
{
    for (size_t bit = 0; bit < 8; ++bit) {
        gpio_set_level(LCD_DATA_PINS[bit], (value >> bit) & 1U);
    }
}

static uint8_t lcd_read_bus(void)
{
    uint8_t value = 0;
    for (size_t bit = 0; bit < 8; ++bit) {
        value |= (uint8_t)(gpio_get_level(LCD_DATA_PINS[bit]) << bit);
    }
    return value;
}

static void lcd_write_command_selected(uint8_t command)
{
    gpio_set_level(LCD_RS_PIN, 0);
    lcd_write_bus(command);
    gpio_set_level(LCD_WR_PIN, 0);
    esp_rom_delay_us(2);
    gpio_set_level(LCD_WR_PIN, 1);
    esp_rom_delay_us(2);
}

static void lcd_write_data_selected(uint8_t data)
{
    gpio_set_level(LCD_RS_PIN, 1);
    lcd_write_bus(data);
    gpio_set_level(LCD_WR_PIN, 0);
    esp_rom_delay_us(1);
    gpio_set_level(LCD_WR_PIN, 1);
    esp_rom_delay_us(1);
}

static void lcd_write_command(uint8_t command, const uint8_t *data, size_t length)
{
    gpio_set_level(LCD_CS_PIN, 0);
    gpio_set_level(LCD_RD_PIN, 1);
    lcd_write_command_selected(command);
    for (size_t index = 0; index < length; ++index) {
        lcd_write_data_selected(data[index]);
    }
    gpio_set_level(LCD_CS_PIN, 1);
}

static void lcd_read_register(uint8_t command, uint8_t *data, size_t length)
{
    gpio_set_level(LCD_CS_PIN, 0);
    gpio_set_level(LCD_RD_PIN, 1);
    lcd_set_data_direction(GPIO_MODE_OUTPUT);
    lcd_write_command_selected(command);

    gpio_set_level(LCD_RS_PIN, 1);
    lcd_set_data_direction(GPIO_MODE_INPUT);
    esp_rom_delay_us(2);

    for (size_t index = 0; index < length; ++index) {
        gpio_set_level(LCD_RD_PIN, 0);
        esp_rom_delay_us(3);
        data[index] = lcd_read_bus();
        gpio_set_level(LCD_RD_PIN, 1);
        esp_rom_delay_us(3);
    }

    gpio_set_level(LCD_CS_PIN, 1);
    lcd_set_data_direction(GPIO_MODE_OUTPUT);
    lcd_write_bus(0x00);
}

static void log_register(uint8_t command, size_t length)
{
    uint8_t data[8] = {0};
    lcd_read_register(command, data, length);

    char output[3 * sizeof(data) + 1] = {0};
    size_t offset = 0;
    for (size_t index = 0; index < length; ++index) {
        offset += (size_t)snprintf(
            output + offset,
            sizeof(output) - offset,
            "%02X%s",
            data[index],
            index + 1U < length ? " " : "");
    }
    ESP_LOGI(TAG, "Register 0x%02X: %s", command, output);
}

static void lcd_gpio_init(void)
{
    // Preset the relay latch LOW before enabling output mode.
    ESP_ERROR_CHECK(gpio_set_level(RELAY_PIN, 0));
    const gpio_config_t relay_config = {
        .pin_bit_mask = 1ULL << RELAY_PIN,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_ENABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&relay_config));
    ESP_ERROR_CHECK(gpio_set_level(RELAY_PIN, 0));

    const gpio_config_t control_config = {
        .pin_bit_mask = (1ULL << LCD_RST_PIN) |
                        (1ULL << LCD_CS_PIN) |
                        (1ULL << LCD_RS_PIN) |
                        (1ULL << LCD_WR_PIN) |
                        (1ULL << LCD_RD_PIN),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&control_config));
    lcd_set_data_direction(GPIO_MODE_OUTPUT);

    gpio_set_level(LCD_CS_PIN, 1);
    gpio_set_level(LCD_RS_PIN, 1);
    gpio_set_level(LCD_WR_PIN, 1);
    gpio_set_level(LCD_RD_PIN, 1);
    gpio_set_level(LCD_RST_PIN, 1);
    lcd_write_bus(0x00);
}

static void lcd_hardware_reset(void)
{
    gpio_set_level(LCD_RST_PIN, 1);
    vTaskDelay(pdMS_TO_TICKS(10));
    gpio_set_level(LCD_RST_PIN, 0);
    vTaskDelay(pdMS_TO_TICKS(20));
    gpio_set_level(LCD_RST_PIN, 1);
    vTaskDelay(pdMS_TO_TICKS(150));
}

static void lcd_init_ili9486(void)
{
    // Full ILI9486 8-bit parallel setup.  The earlier abbreviated ILI948x
    // sequence is not accepted by every 3.5-inch Arduino-style shield.
    static const uint8_t pixel_format[] = {0x55};
    static const uint8_t power_control_1[] = {0x0E, 0x0E};
    static const uint8_t power_control_2[] = {0x41, 0x00};
    static const uint8_t power_control_3[] = {0x55};
    static const uint8_t vcom_control[] = {0x00, 0x00, 0x00, 0x00};
    static const uint8_t positive_gamma[] = {
        0x0F, 0x1F, 0x1C, 0x0C, 0x0F, 0x08, 0x48, 0x98,
        0x37, 0x0A, 0x13, 0x04, 0x11, 0x0D, 0x00,
    };
    static const uint8_t negative_gamma[] = {
        0x0F, 0x32, 0x2E, 0x0B, 0x0D, 0x05, 0x47, 0x75,
        0x37, 0x06, 0x10, 0x03, 0x24, 0x20, 0x00,
    };
    static const uint8_t inversion_off[] = {0x00};
    // MV swaps the native 320x480 axes into a 480x320 landscape window.
    static const uint8_t memory_access_control[] = {0x28};

    lcd_write_command(0x01, NULL, 0);  // Software reset
    vTaskDelay(pdMS_TO_TICKS(120));
    lcd_write_command(0x11, NULL, 0);  // Sleep out
    vTaskDelay(pdMS_TO_TICKS(120));
    lcd_write_command(0x3A, pixel_format, sizeof(pixel_format));
    lcd_write_command(0xC0, power_control_1, sizeof(power_control_1));
    lcd_write_command(0xC1, power_control_2, sizeof(power_control_2));
    lcd_write_command(0xC2, power_control_3, sizeof(power_control_3));
    lcd_write_command(0xC5, vcom_control, sizeof(vcom_control));
    lcd_write_command(0xE0, positive_gamma, sizeof(positive_gamma));
    lcd_write_command(0xE1, negative_gamma, sizeof(negative_gamma));
    lcd_write_command(0x20, inversion_off, 0);  // Display inversion off
    lcd_write_command(0x36, memory_access_control, sizeof(memory_access_control));
    lcd_write_command(0x29, NULL, 0);  // Display on
    vTaskDelay(pdMS_TO_TICKS(150));
}

static void lcd_init_ili9488(void)
{
    static const uint8_t positive_gamma[] = {
        0x00, 0x03, 0x09, 0x08, 0x16, 0x0A, 0x3F, 0x78,
        0x4C, 0x09, 0x0A, 0x08, 0x16, 0x1A, 0x0F,
    };
    static const uint8_t negative_gamma[] = {
        0x00, 0x16, 0x19, 0x03, 0x0F, 0x05, 0x32, 0x45,
        0x46, 0x04, 0x0E, 0x0D, 0x35, 0x37, 0x0F,
    };
    static const uint8_t power_control_1[] = {0x17, 0x15};
    static const uint8_t power_control_2[] = {0x41};
    static const uint8_t vcom_control[] = {0x00, 0x12, 0x80};
    static const uint8_t madctl[] = {0x28};
    static const uint8_t pixel_format[] = {0x55};
    static const uint8_t interface_mode[] = {0x00};
    static const uint8_t frame_rate[] = {0xA0};
    static const uint8_t inversion[] = {0x02};
    static const uint8_t display_function[] = {0x02, 0x02, 0x3B};
    static const uint8_t entry_mode[] = {0xC6};
    static const uint8_t adjust_control[] = {0xA9, 0x51, 0x2C, 0x82};

    lcd_write_command(0x01, NULL, 0);
    vTaskDelay(pdMS_TO_TICKS(120));
    lcd_write_command(0xE0, positive_gamma, sizeof(positive_gamma));
    lcd_write_command(0xE1, negative_gamma, sizeof(negative_gamma));
    lcd_write_command(0xC0, power_control_1, sizeof(power_control_1));
    lcd_write_command(0xC1, power_control_2, sizeof(power_control_2));
    lcd_write_command(0xC5, vcom_control, sizeof(vcom_control));
    lcd_write_command(0x36, madctl, sizeof(madctl));
    lcd_write_command(0x3A, pixel_format, sizeof(pixel_format));
    lcd_write_command(0xB0, interface_mode, sizeof(interface_mode));
    lcd_write_command(0xB1, frame_rate, sizeof(frame_rate));
    lcd_write_command(0xB4, inversion, sizeof(inversion));
    lcd_write_command(0xB6, display_function, sizeof(display_function));
    lcd_write_command(0xB7, entry_mode, sizeof(entry_mode));
    lcd_write_command(0xF7, adjust_control, sizeof(adjust_control));
    lcd_write_command(0x11, NULL, 0);
    vTaskDelay(pdMS_TO_TICKS(120));
    lcd_write_command(0x29, NULL, 0);
    vTaskDelay(pdMS_TO_TICKS(50));
}

static void lcd_init_st7796(void)
{
    static const uint8_t ext_part_1[] = {0xC3};
    static const uint8_t ext_part_2[] = {0x96};
    static const uint8_t madctl[] = {0x28};
    static const uint8_t pixel_format[] = {0x55};
    static const uint8_t inversion[] = {0x01};
    static const uint8_t display_function[] = {0x80, 0x02, 0x3B};
    static const uint8_t display_adjust[] = {
        0x40, 0x8A, 0x00, 0x00, 0x29, 0x19, 0xA5, 0x33,
    };
    static const uint8_t power_control_2[] = {0x06};
    static const uint8_t power_control_3[] = {0xA7};
    static const uint8_t vcom_control[] = {0x18};
    static const uint8_t positive_gamma[] = {
        0xF0, 0x09, 0x0B, 0x06, 0x04, 0x15, 0x2F,
        0x54, 0x42, 0x3C, 0x17, 0x14, 0x18, 0x1B,
    };
    static const uint8_t negative_gamma[] = {
        0xE0, 0x09, 0x0B, 0x06, 0x04, 0x03, 0x2B,
        0x43, 0x42, 0x3B, 0x16, 0x14, 0x17, 0x1B,
    };
    static const uint8_t ext_disable_1[] = {0x3C};
    static const uint8_t ext_disable_2[] = {0x69};

    lcd_write_command(0x01, NULL, 0);
    vTaskDelay(pdMS_TO_TICKS(120));
    lcd_write_command(0x11, NULL, 0);
    vTaskDelay(pdMS_TO_TICKS(120));
    lcd_write_command(0xF0, ext_part_1, sizeof(ext_part_1));
    lcd_write_command(0xF0, ext_part_2, sizeof(ext_part_2));
    lcd_write_command(0x36, madctl, sizeof(madctl));
    lcd_write_command(0x3A, pixel_format, sizeof(pixel_format));
    lcd_write_command(0xB4, inversion, sizeof(inversion));
    lcd_write_command(0xB6, display_function, sizeof(display_function));
    lcd_write_command(0xE8, display_adjust, sizeof(display_adjust));
    lcd_write_command(0xC1, power_control_2, sizeof(power_control_2));
    lcd_write_command(0xC2, power_control_3, sizeof(power_control_3));
    lcd_write_command(0xC5, vcom_control, sizeof(vcom_control));
    vTaskDelay(pdMS_TO_TICKS(120));
    lcd_write_command(0xE0, positive_gamma, sizeof(positive_gamma));
    lcd_write_command(0xE1, negative_gamma, sizeof(negative_gamma));
    vTaskDelay(pdMS_TO_TICKS(120));
    lcd_write_command(0xF0, ext_disable_1, sizeof(ext_disable_1));
    lcd_write_command(0xF0, ext_disable_2, sizeof(ext_disable_2));
    vTaskDelay(pdMS_TO_TICKS(120));
    lcd_write_command(0x29, NULL, 0);
}

static void lcd_init_hx8357d(void)
{
    static const uint8_t ext_command[] = {0xFF, 0x83, 0x57};
    static const uint8_t rgb_control[] = {0x80, 0x00, 0x06, 0x06};
    static const uint8_t com_control[] = {0x25};
    static const uint8_t oscillator[] = {0x68};
    static const uint8_t panel_control[] = {0x05};
    static const uint8_t power_control[] = {0x00, 0x15, 0x1C, 0x1C, 0x83, 0xAA};
    static const uint8_t source_option[] = {0x50, 0x50, 0x01, 0x3C, 0x1E, 0x08};
    static const uint8_t cycle_control[] = {0x02, 0x40, 0x00, 0x2A, 0x2A, 0x0D, 0x78};
    static const uint8_t gamma[] = {
        0x02, 0x0A, 0x11, 0x1D, 0x23, 0x35, 0x41, 0x4B,
        0x4B, 0x42, 0x3A, 0x27, 0x1B, 0x08, 0x09, 0x03,
        0x02, 0x0A, 0x11, 0x1D, 0x23, 0x35, 0x41, 0x4B,
        0x4B, 0x42, 0x3A, 0x27, 0x1B, 0x08, 0x09, 0x03,
        0x00, 0x01,
    };
    static const uint8_t pixel_format[] = {0x55};
    static const uint8_t madctl[] = {0x28};
    static const uint8_t tear_control[] = {0x00};
    static const uint8_t tear_line[] = {0x00, 0x02};

    lcd_write_command(0x01, NULL, 0);
    vTaskDelay(pdMS_TO_TICKS(120));
    lcd_write_command(0xB9, ext_command, sizeof(ext_command));
    vTaskDelay(pdMS_TO_TICKS(300));
    lcd_write_command(0xB3, rgb_control, sizeof(rgb_control));
    lcd_write_command(0xB6, com_control, sizeof(com_control));
    lcd_write_command(0xB0, oscillator, sizeof(oscillator));
    lcd_write_command(0xCC, panel_control, sizeof(panel_control));
    lcd_write_command(0xB1, power_control, sizeof(power_control));
    lcd_write_command(0xC0, source_option, sizeof(source_option));
    lcd_write_command(0xB4, cycle_control, sizeof(cycle_control));
    lcd_write_command(0xE0, gamma, sizeof(gamma));
    lcd_write_command(0x3A, pixel_format, sizeof(pixel_format));
    lcd_write_command(0x36, madctl, sizeof(madctl));
    lcd_write_command(0x35, tear_control, sizeof(tear_control));
    lcd_write_command(0x44, tear_line, sizeof(tear_line));
    lcd_write_command(0x11, NULL, 0);
    vTaskDelay(pdMS_TO_TICKS(150));
    lcd_write_command(0x29, NULL, 0);
    vTaskDelay(pdMS_TO_TICKS(50));
}

static void lcd_fill_color(uint16_t color);

static void lcd_try_profile(const char *name, void (*init)(void), uint16_t color)
{
    gpio_set_level(RELAY_PIN, 0);
    ESP_LOGI(TAG, "Trying controller profile: %s", name);
    lcd_hardware_reset();
    init();
    lcd_fill_color(color);
    vTaskDelay(pdMS_TO_TICKS(6000));
}

static void lcd_set_window(uint16_t x_start, uint16_t y_start, uint16_t x_end, uint16_t y_end)
{
    const uint8_t columns[] = {
        (uint8_t)(x_start >> 8),
        (uint8_t)x_start,
        (uint8_t)(x_end >> 8),
        (uint8_t)x_end,
    };
    const uint8_t rows[] = {
        (uint8_t)(y_start >> 8),
        (uint8_t)y_start,
        (uint8_t)(y_end >> 8),
        (uint8_t)y_end,
    };
    lcd_write_command(0x2A, columns, sizeof(columns));
    lcd_write_command(0x2B, rows, sizeof(rows));
}

static void lcd_fill_color(uint16_t color)
{
    lcd_set_window(0, 0, 479, 319);
    gpio_set_level(LCD_CS_PIN, 0);
    lcd_write_command_selected(0x2C);
    for (uint32_t pixel = 0; pixel < 480U * 320U; ++pixel) {
        lcd_write_data_selected((uint8_t)(color >> 8));
        lcd_write_data_selected((uint8_t)color);
    }
    gpio_set_level(LCD_CS_PIN, 1);
}

void app_main(void)
{
    lcd_gpio_init();
    ESP_LOGI(TAG, "Relay locked OFF on GPIO7");
    ESP_LOGI(
        TAG,
        "LCD pins: RST=4 CS=38 RS=39 WR=40 RD=41 D0..D7=13,14,15,16,17,18,21,47");

    lcd_hardware_reset();
    ESP_LOGI(TAG, "LCD reset complete; reading controller registers");

    log_register(0x00, 4);
    log_register(0x04, 4);
    log_register(0x09, 5);
    log_register(0xBF, 6);
    log_register(0xD0, 4);
    log_register(0xD3, 5);
    log_register(0xEF, 6);

    ESP_LOGI(TAG, "Controller ID confirms ILI9486; starting landscape RGB color test");
    lcd_hardware_reset();
    lcd_init_ili9486();

    while (true) {
        gpio_set_level(RELAY_PIN, 0);
        ESP_LOGI(TAG, "ILI9486 landscape test: RED");
        lcd_fill_color(0xF800);
        vTaskDelay(pdMS_TO_TICKS(3000));

        ESP_LOGI(TAG, "ILI9486 landscape test: GREEN");
        lcd_fill_color(0x07E0);
        vTaskDelay(pdMS_TO_TICKS(3000));

        ESP_LOGI(TAG, "ILI9486 landscape test: BLUE");
        lcd_fill_color(0x001F);
        vTaskDelay(pdMS_TO_TICKS(3000));

        ESP_LOGI(TAG, "ILI9486 landscape test: BLACK");
        lcd_fill_color(0x0000);
        vTaskDelay(pdMS_TO_TICKS(3000));
    }
}
