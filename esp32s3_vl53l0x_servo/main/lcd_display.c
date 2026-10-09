#include "lcd_display.h"

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "driver/gpio.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_rom_sys.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "soc/gpio_struct.h"

static const char *TAG = "LCD_DISPLAY";

#define LCD_RST_PIN GPIO_NUM_4
#define LCD_CS_PIN GPIO_NUM_38
#define LCD_RS_PIN GPIO_NUM_39
#define LCD_WR_PIN GPIO_NUM_40
#define LCD_RD_PIN GPIO_NUM_41

#define LCD_WIDTH 480U
#define LCD_HEIGHT 320U

#define FAN_X 22U
#define FAN_Y 72U
#define FAN_WIDTH 126U
#define FAN_HEIGHT 94U

#define SPRITE_MAX_WIDTH LCD_WIDTH
#define SPRITE_MAX_HEIGHT 130U
#define SPRITE_CAPACITY (SPRITE_MAX_WIDTH * SPRITE_MAX_HEIGHT)

#define COLOR_BACKGROUND 0x020CU
#define COLOR_BACKGROUND_2 0x0841U
#define COLOR_PANEL_TOP 0x10A4U
#define COLOR_PANEL_BOTTOM 0x0822U
#define COLOR_WHITE 0xFFFFU
#define COLOR_MUTED 0x9D76U
#define COLOR_DIM 0x5B0DU
#define COLOR_CYAN 0x07FFU
#define COLOR_CYAN_DARK 0x0350U
#define COLOR_BLUE 0x157EU
#define COLOR_BLUE_DARK 0x082CU
#define COLOR_GREEN 0x2FC7U
#define COLOR_GREEN_DARK 0x02E1U
#define COLOR_RED 0xF2A8U
#define COLOR_RED_DARK 0x6004U
#define COLOR_AMBER 0xFD20U
#define COLOR_BLACK 0x0000U
#define COLOR_REFERENCE_TEXT 0x10E5U
#define COLOR_REFERENCE_MUTED 0x738EU
#define COLOR_REFERENCE_BLUE 0x2D7CU
#define COLOR_REFERENCE_LIGHT_BLUE 0xE73FU

#define FAN_FRAME_MS 45U
#define CARD_REFRESH_MS 500U
#define DISPLAY_POLL_MS 10U

#define LCD_DATA_LOW_MASK ((0x3FU << 13) | (1U << 21))
#define LCD_DATA_HIGH_MASK (1U << (47 - 32))
#define LCD_WR_HIGH_MASK (1U << (40 - 32))

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

typedef struct {
    char character;
    uint8_t rows[7];
} glyph_t;

static const glyph_t FONT[] = {
    {' ', {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00}},
    {'-', {0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00}},
    {'/', {0x01, 0x02, 0x04, 0x08, 0x10, 0x00, 0x00}},
    {'0', {0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E}},
    {'1', {0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E}},
    {'2', {0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F}},
    {'3', {0x1E, 0x01, 0x01, 0x0E, 0x01, 0x01, 0x1E}},
    {'4', {0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02}},
    {'5', {0x1F, 0x10, 0x10, 0x1E, 0x01, 0x01, 0x1E}},
    {'6', {0x0E, 0x10, 0x10, 0x1E, 0x11, 0x11, 0x0E}},
    {'7', {0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08}},
    {'8', {0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E}},
    {'9', {0x0E, 0x11, 0x11, 0x0F, 0x01, 0x01, 0x0E}},
    {'A', {0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11}},
    {'B', {0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E}},
    {'C', {0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E}},
    {'D', {0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E}},
    {'E', {0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F}},
    {'F', {0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10}},
    {'G', {0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F}},
    {'H', {0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11}},
    {'I', {0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E}},
    {'J', {0x07, 0x02, 0x02, 0x02, 0x12, 0x12, 0x0C}},
    {'K', {0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11}},
    {'L', {0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F}},
    {'M', {0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11}},
    {'N', {0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11}},
    {'O', {0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E}},
    {'P', {0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10}},
    {'Q', {0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D}},
    {'R', {0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11}},
    {'S', {0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E}},
    {'T', {0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04}},
    {'U', {0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E}},
    {'V', {0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04}},
    {'W', {0x11, 0x11, 0x11, 0x15, 0x15, 0x15, 0x0A}},
    {'X', {0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11}},
    {'Y', {0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04}},
    {'Z', {0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F}},
};

typedef struct {
    uint16_t *pixels;
    uint16_t width;
    uint16_t height;
} canvas_t;

static QueueHandle_t status_queue;
static uint16_t *sprite_pixels;

extern const uint8_t dashboard_rgb565_start[]
    asm("_binary_dashboard_rgb565_start");
extern const uint8_t dashboard_rgb565_end[]
    asm("_binary_dashboard_rgb565_end");

static const int16_t COS_36[36] = {
    1024, 1008, 962, 887, 784, 658, 512, 350, 178,
    0, -178, -350, -512, -658, -784, -887, -962, -1008,
    -1024, -1008, -962, -887, -784, -658, -512, -350, -178,
    0, 178, 350, 512, 658, 784, 887, 962, 1008,
};
static const int16_t SIN_36[36] = {
    0, 178, 350, 512, 658, 784, 887, 962, 1008,
    1024, 1008, 962, 887, 784, 658, 512, 350, 178,
    0, -178, -350, -512, -658, -784, -887, -962, -1008,
    -1024, -1008, -962, -887, -784, -658, -512, -350, -178,
};

static uint64_t lcd_data_pin_mask(void)
{
    uint64_t mask = 0;
    for (size_t bit = 0; bit < 8; ++bit) {
        mask |= 1ULL << LCD_DATA_PINS[bit];
    }
    return mask;
}

static void lcd_write_bus(uint8_t value)
{
    const uint32_t low_value =
        ((uint32_t)(value & 0x3FU) << 13) |
        ((uint32_t)(value & 0x40U) << 15);

    GPIO.out_w1tc = LCD_DATA_LOW_MASK;
    GPIO.out1_w1tc.val = LCD_DATA_HIGH_MASK;
    GPIO.out_w1ts = low_value;
    if ((value & 0x80U) != 0U) {
        GPIO.out1_w1ts.val = LCD_DATA_HIGH_MASK;
    }
}

static inline void lcd_write_byte_selected(uint8_t value)
{
    lcd_write_bus(value);
    GPIO.out1_w1tc.val = LCD_WR_HIGH_MASK;
    esp_rom_delay_us(1);
    GPIO.out1_w1ts.val = LCD_WR_HIGH_MASK;
    __asm__ __volatile__("nop; nop; nop; nop;" ::: "memory");
}

static void lcd_write_command(uint8_t command, const uint8_t *data, size_t length)
{
    gpio_set_level(LCD_CS_PIN, 0);
    gpio_set_level(LCD_RD_PIN, 1);
    gpio_set_level(LCD_RS_PIN, 0);
    lcd_write_byte_selected(command);
    gpio_set_level(LCD_RS_PIN, 1);
    for (size_t index = 0; index < length; ++index) {
        lcd_write_byte_selected(data[index]);
    }
    gpio_set_level(LCD_CS_PIN, 1);
}

static void lcd_gpio_init(void)
{
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

    const gpio_config_t data_config = {
        .pin_bit_mask = lcd_data_pin_mask(),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&data_config));

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
    // Previous landscape setting was 0x28. MX+MY rotates that view by 180°.
    static const uint8_t landscape_rotated_180[] = {0xE8};

    lcd_write_command(0x01, NULL, 0);
    vTaskDelay(pdMS_TO_TICKS(120));
    lcd_write_command(0x11, NULL, 0);
    vTaskDelay(pdMS_TO_TICKS(120));
    lcd_write_command(0x3A, pixel_format, sizeof(pixel_format));
    lcd_write_command(0xC0, power_control_1, sizeof(power_control_1));
    lcd_write_command(0xC1, power_control_2, sizeof(power_control_2));
    lcd_write_command(0xC2, power_control_3, sizeof(power_control_3));
    lcd_write_command(0xC5, vcom_control, sizeof(vcom_control));
    lcd_write_command(0xE0, positive_gamma, sizeof(positive_gamma));
    lcd_write_command(0xE1, negative_gamma, sizeof(negative_gamma));
    lcd_write_command(0x20, NULL, 0);
    lcd_write_command(0x36, landscape_rotated_180, sizeof(landscape_rotated_180));
    lcd_write_command(0x29, NULL, 0);
    vTaskDelay(pdMS_TO_TICKS(150));
}

static void lcd_set_window(uint16_t x, uint16_t y, uint16_t width, uint16_t height)
{
    const uint16_t x_end = x + width - 1U;
    const uint16_t y_end = y + height - 1U;
    const uint8_t columns[] = {
        (uint8_t)(x >> 8), (uint8_t)x, (uint8_t)(x_end >> 8), (uint8_t)x_end,
    };
    const uint8_t rows[] = {
        (uint8_t)(y >> 8), (uint8_t)y, (uint8_t)(y_end >> 8), (uint8_t)y_end,
    };
    lcd_write_command(0x2A, columns, sizeof(columns));
    lcd_write_command(0x2B, rows, sizeof(rows));
}

static void lcd_begin_pixels(uint16_t x, uint16_t y, uint16_t width, uint16_t height)
{
    lcd_set_window(x, y, width, height);
    gpio_set_level(LCD_CS_PIN, 0);
    gpio_set_level(LCD_RS_PIN, 0);
    lcd_write_byte_selected(0x2C);
    gpio_set_level(LCD_RS_PIN, 1);
}

static inline void lcd_write_color(uint16_t color)
{
    lcd_write_byte_selected((uint8_t)(color >> 8));
    lcd_write_byte_selected((uint8_t)color);
}

static void lcd_end_pixels(void)
{
    gpio_set_level(LCD_CS_PIN, 1);
}

static void lcd_fill_rect(
    uint16_t x,
    uint16_t y,
    uint16_t width,
    uint16_t height,
    uint16_t color)
{
    lcd_begin_pixels(x, y, width, height);
    for (uint32_t pixel = 0; pixel < (uint32_t)width * height; ++pixel) {
        lcd_write_color(color);
        if ((pixel & 0x07FFU) == 0x07FFU) {
            vTaskDelay(1);
        }
    }
    lcd_end_pixels();
}

static const uint8_t *font_rows(char character)
{
    for (size_t index = 0; index < sizeof(FONT) / sizeof(FONT[0]); ++index) {
        if (FONT[index].character == character) {
            return FONT[index].rows;
        }
    }
    return FONT[0].rows;
}

static uint16_t text_width(const char *text, uint8_t scale)
{
    return (uint16_t)(strlen(text) * 6U * scale);
}

static canvas_t canvas_begin(uint16_t width, uint16_t height, uint16_t color)
{
    canvas_t canvas = {
        .pixels = sprite_pixels,
        .width = width,
        .height = height,
    };
    if ((uint32_t)width * height > SPRITE_CAPACITY) {
        canvas.width = 0;
        canvas.height = 0;
        return canvas;
    }
    for (uint32_t index = 0; index < (uint32_t)width * height; ++index) {
        canvas.pixels[index] = color;
    }
    return canvas;
}

static uint16_t dashboard_pixel(uint16_t x, uint16_t y)
{
    const uint32_t offset = ((uint32_t)y * LCD_WIDTH + x) * 2U;
    return (uint16_t)(((uint16_t)dashboard_rgb565_start[offset] << 8) |
                      dashboard_rgb565_start[offset + 1U]);
}

static canvas_t canvas_begin_from_dashboard(
    uint16_t screen_x,
    uint16_t screen_y,
    uint16_t width,
    uint16_t height)
{
    canvas_t canvas = canvas_begin(width, height, COLOR_WHITE);
    if (canvas.width == 0U || screen_x + width > LCD_WIDTH ||
        screen_y + height > LCD_HEIGHT) {
        canvas.width = 0;
        canvas.height = 0;
        return canvas;
    }
    for (uint16_t y = 0; y < height; ++y) {
        for (uint16_t x = 0; x < width; ++x) {
            canvas.pixels[(uint32_t)y * width + x] =
                dashboard_pixel(screen_x + x, screen_y + y);
        }
    }
    return canvas;
}

static void canvas_pixel(canvas_t *canvas, int x, int y, uint16_t color)
{
    if (x >= 0 && y >= 0 && x < canvas->width && y < canvas->height) {
        canvas->pixels[(uint32_t)y * canvas->width + (uint32_t)x] = color;
    }
}

static void canvas_fill_rect(
    canvas_t *canvas,
    int x,
    int y,
    int width,
    int height,
    uint16_t color)
{
    if (x < 0) {
        width += x;
        x = 0;
    }
    if (y < 0) {
        height += y;
        y = 0;
    }
    if (x + width > canvas->width) {
        width = canvas->width - x;
    }
    if (y + height > canvas->height) {
        height = canvas->height - y;
    }
    if (width <= 0 || height <= 0) {
        return;
    }
    for (int row = y; row < y + height; ++row) {
        uint16_t *destination = &canvas->pixels[(uint32_t)row * canvas->width + x];
        for (int column = 0; column < width; ++column) {
            destination[column] = color;
        }
    }
}

static void canvas_fill_circle(
    canvas_t *canvas,
    int center_x,
    int center_y,
    int radius,
    uint16_t color)
{
    const int radius_squared = radius * radius;
    for (int y = -radius; y <= radius; ++y) {
        for (int x = -radius; x <= radius; ++x) {
            if (x * x + y * y <= radius_squared) {
                canvas_pixel(canvas, center_x + x, center_y + y, color);
            }
        }
    }
}

static void canvas_circle(
    canvas_t *canvas,
    int center_x,
    int center_y,
    int radius,
    uint16_t color)
{
    int x = radius;
    int y = 0;
    int error = 1 - radius;
    while (x >= y) {
        canvas_pixel(canvas, center_x + x, center_y + y, color);
        canvas_pixel(canvas, center_x + y, center_y + x, color);
        canvas_pixel(canvas, center_x - y, center_y + x, color);
        canvas_pixel(canvas, center_x - x, center_y + y, color);
        canvas_pixel(canvas, center_x - x, center_y - y, color);
        canvas_pixel(canvas, center_x - y, center_y - x, color);
        canvas_pixel(canvas, center_x + y, center_y - x, color);
        canvas_pixel(canvas, center_x + x, center_y - y, color);
        ++y;
        if (error < 0) {
            error += 2 * y + 1;
        } else {
            --x;
            error += 2 * (y - x) + 1;
        }
    }
}

static void canvas_draw_char(
    canvas_t *canvas,
    int x,
    int y,
    char character,
    uint8_t scale,
    uint16_t foreground)
{
    const uint8_t *rows = font_rows(character);
    for (uint8_t row = 0; row < 7; ++row) {
        for (uint8_t column = 0; column < 5; ++column) {
            if (rows[row] & (1U << (4U - column))) {
                canvas_fill_rect(
                    canvas,
                    x + column * scale,
                    y + row * scale,
                    scale,
                    scale,
                    foreground);
            }
        }
    }
}

static void canvas_draw_text(
    canvas_t *canvas,
    int x,
    int y,
    const char *text,
    uint8_t scale,
    uint16_t foreground)
{
    while (*text != '\0') {
        canvas_draw_char(canvas, x, y, *text, scale, foreground);
        x += 6 * scale;
        ++text;
    }
}

static uint16_t bold_text_width(const char *text, uint8_t scale)
{
    const size_t length = strlen(text);
    if (length == 0U) {
        return 0U;
    }
    return (uint16_t)(length * (6U * scale + 1U) - 1U);
}

static void canvas_draw_text_bold(
    canvas_t *canvas,
    int x,
    int y,
    const char *text,
    uint8_t scale,
    uint16_t foreground)
{
    while (*text != '\0') {
        canvas_draw_char(canvas, x, y, *text, scale, foreground);
        canvas_draw_char(canvas, x + 1, y, *text, scale, foreground);
        x += 6 * scale + 1;
        ++text;
    }
}

static void canvas_draw_centered_bold(
    canvas_t *canvas,
    int y,
    const char *text,
    uint8_t scale,
    uint16_t foreground)
{
    canvas_draw_text_bold(
        canvas,
        ((int)canvas->width - (int)bold_text_width(text, scale)) / 2,
        y,
        text,
        scale,
        foreground);
}

static void lcd_push_canvas(uint16_t x, uint16_t y, const canvas_t *canvas)
{
    if (canvas->width == 0 || canvas->height == 0) {
        return;
    }
    lcd_begin_pixels(x, y, canvas->width, canvas->height);
    const uint32_t pixel_count = (uint32_t)canvas->width * canvas->height;
    for (uint32_t index = 0; index < pixel_count; ++index) {
        lcd_write_color(canvas->pixels[index]);
        if ((index & 0x07FFU) == 0x07FFU) {
            vTaskDelay(1);
        }
    }
    lcd_end_pixels();
}

static void draw_static_screen(void)
{
    const size_t expected_size = (size_t)LCD_WIDTH * LCD_HEIGHT * 2U;
    const size_t asset_size =
        (size_t)(dashboard_rgb565_end - dashboard_rgb565_start);
    if (asset_size != expected_size) {
        ESP_LOGE(
            TAG,
            "Dashboard asset size mismatch: got %u, expected %u",
            (unsigned)asset_size,
            (unsigned)expected_size);
        lcd_fill_rect(0, 0, LCD_WIDTH, LCD_HEIGHT, COLOR_WHITE);
        return;
    }

    lcd_begin_pixels(0, 0, LCD_WIDTH, LCD_HEIGHT);
    for (uint32_t pixel = 0; pixel < (uint32_t)LCD_WIDTH * LCD_HEIGHT; ++pixel) {
        lcd_write_byte_selected(dashboard_rgb565_start[pixel * 2U]);
        lcd_write_byte_selected(dashboard_rgb565_start[pixel * 2U + 1U]);
        if ((pixel & 0x07FFU) == 0x07FFU) {
            vTaskDelay(1);
        }
    }
    lcd_end_pixels();
}

static void draw_readable_static_labels(void)
{
    canvas_t subtitle = canvas_begin_from_dashboard(102, 39, 175, 14);
    canvas_draw_centered_bold(
        &subtitle, 3, "UMBRELLA DRYING SYSTEM", 1, COLOR_REFERENCE_MUTED);
    lcd_push_canvas(102, 39, &subtitle);

    canvas_t system = canvas_begin_from_dashboard(168, 83, 132, 14);
    canvas_draw_centered_bold(&system, 3, "SYSTEM STATUS", 1, COLOR_REFERENCE_TEXT);
    lcd_push_canvas(168, 83, &system);

    static const uint16_t distance_label_x[3] = {17, 175, 331};
    for (uint8_t sensor = 0; sensor < 3; ++sensor) {
        canvas_t label = canvas_begin_from_dashboard(
            distance_label_x[sensor], 196, 62, 14);
        canvas_draw_centered_bold(&label, 3, "DISTANCE", 1, COLOR_REFERENCE_MUTED);
        lcd_push_canvas(distance_label_x[sensor], 196, &label);
    }

    canvas_t relay = canvas_begin_from_dashboard(319, 284, 42, 14);
    canvas_draw_centered_bold(&relay, 3, "RELAY", 1, COLOR_REFERENCE_TEXT);
    lcd_push_canvas(319, 284, &relay);
}

static void draw_live_label(void)
{
    canvas_t label = canvas_begin_from_dashboard(374, 8, 90, 14);
    canvas_draw_centered_bold(&label, 3, "LIVE MONITOR", 1, COLOR_REFERENCE_MUTED);
    lcd_push_canvas(374, 8, &label);
}

static void draw_header_status(bool running)
{
    canvas_t status = canvas_begin_from_dashboard(371, 29, 91, 19);
    canvas_fill_circle(&status, 8, 9, 6, running ? COLOR_GREEN : COLOR_REFERENCE_BLUE);
    canvas_draw_text_bold(
        &status,
        20,
        6,
        running ? "RUNNING" : "STANDBY",
        1,
        COLOR_WHITE);
    lcd_push_canvas(371, 29, &status);
}

static int16_t trig_72(const int16_t table[36], uint8_t angle)
{
    const uint8_t base = (uint8_t)((angle / 2U) % 36U);
    if ((angle & 1U) == 0U) {
        return table[base];
    }
    return (int16_t)((table[base] + table[(base + 1U) % 36U]) / 2);
}

static void draw_fan(bool running, uint8_t frame)
{
    canvas_t fan = canvas_begin_from_dashboard(FAN_X, FAN_Y, FAN_WIDTH, FAN_HEIGHT);
    const int center_x = 48;
    const int center_y = 47;
    const uint16_t blade = running ? COLOR_REFERENCE_BLUE : COLOR_REFERENCE_MUTED;
    canvas_fill_circle(&fan, center_x, center_y, 43, COLOR_REFERENCE_LIGHT_BLUE);
    canvas_circle(&fan, center_x, center_y, 43, 0xBE7FU);

    for (uint8_t blade_index = 0; blade_index < 3; ++blade_index) {
        const uint8_t base = (uint8_t)((frame + blade_index * 24U) % 72U);
        for (int radius = 12; radius <= 35; radius += 2) {
            const uint8_t curve =
                (uint8_t)((base + (radius - 12) / 4) % 72U);
            const int x = center_x + trig_72(COS_36, curve) * radius / 1024;
            const int y = center_y + trig_72(SIN_36, curve) * radius / 1024;
            const int brush = 8 - (radius - 12) / 7;
            canvas_fill_circle(&fan, x, y, brush, blade);
        }
    }
    canvas_fill_circle(&fan, center_x, center_y, 9, COLOR_WHITE);
    canvas_fill_circle(&fan, center_x, center_y, 5, running ? COLOR_GREEN : COLOR_REFERENCE_MUTED);

    for (int line = 0; line < 3; ++line) {
        for (int x = 91; x <= 119; ++x) {
            const uint8_t phase = (uint8_t)(((x - 91) * 2 + line * 8) % 36);
            const int y = 34 + line * 13 + SIN_36[phase] * 3 / 1024;
            canvas_fill_circle(&fan, x, y, 1, blade);
        }
    }
    lcd_push_canvas(FAN_X, FAN_Y, &fan);
}

static void draw_blower_status(bool running)
{
    canvas_t status = canvas_begin_from_dashboard(169, 99, 270, 55);
    canvas_draw_centered_bold(
        &status,
        2,
        running ? "BLOWER RUNNING" : "BLOWER STOPPED",
        3,
        running ? COLOR_REFERENCE_TEXT : COLOR_REFERENCE_MUTED);
    canvas_draw_centered_bold(
        &status,
        39,
        running ? "KEEP UMBRELLA IN PLACE" : "WAITING FOR ALL SENSORS",
        1,
        COLOR_REFERENCE_MUTED);
    lcd_push_canvas(169, 99, &status);
}

static void draw_sensor_state(
    uint8_t sensor_index,
    bool active,
    bool valid)
{
    static const uint16_t state_x[3] = {130, 286, 442};
    const uint16_t x = state_x[sensor_index];
    canvas_t state = canvas_begin_from_dashboard(x, 181, 23, 22);
    const uint16_t color = !valid ? COLOR_AMBER : (active ? COLOR_GREEN : COLOR_REFERENCE_BLUE);
    canvas_fill_circle(&state, 11, 11, 9, color);
    if (active && valid) {
        for (int step = 0; step < 5; ++step) {
            canvas_fill_circle(&state, 6 + step, 11 + step, 1, COLOR_WHITE);
        }
        for (int step = 0; step < 7; ++step) {
            canvas_fill_circle(&state, 10 + step, 15 - step, 1, COLOR_WHITE);
        }
    } else {
        canvas_draw_text(&state, valid ? 9 : 8, 8, valid ? "-" : "X", 1, COLOR_WHITE);
    }
    lcd_push_canvas(x, 181, &state);
}

static void draw_sensor_value(
    uint8_t sensor_index,
    bool active,
    bool valid,
    uint32_t distance_mm)
{
    static const uint16_t value_x[3] = {65, 221, 377};
    static const uint16_t value_width[3] = {82, 83, 87};
    const uint16_t x = value_x[sensor_index];
    const uint16_t width = value_width[sensor_index];
    const uint16_t accent = !valid ? COLOR_AMBER :
        (active ? COLOR_GREEN : COLOR_REFERENCE_TEXT);
    char distance_text[8];
    if (valid) {
        snprintf(distance_text, sizeof(distance_text), "%u", (unsigned)distance_mm);
    } else {
        snprintf(distance_text, sizeof(distance_text), "----");
    }

    const uint8_t scale = valid && distance_mm >= 1000U ? 2U : 3U;
    canvas_t value = canvas_begin_from_dashboard(x, 210, width, 31);
    canvas_draw_text(&value, 0, scale == 3U ? 4 : 9, distance_text, scale, accent);
    const uint16_t number_width = text_width(distance_text, scale);
    if (valid) {
        canvas_draw_text_bold(
            &value,
            number_width + 3,
            18,
            "MM",
            1,
            COLOR_REFERENCE_MUTED);
    }
    lcd_push_canvas(x, 210, &value);
}

static void draw_sensor_progress(
    uint8_t sensor_index,
    bool active,
    bool valid,
    uint32_t distance_mm,
    uint32_t threshold_mm)
{
    static const uint16_t progress_x[3] = {18, 176, 332};
    static const uint16_t progress_width[3] = {130, 130, 132};
    const uint16_t x = progress_x[sensor_index];
    const uint16_t width = progress_width[sensor_index];
    canvas_t progress = canvas_begin_from_dashboard(x, 244, width, 9);
    canvas_fill_rect(&progress, 0, 2, width, 5, 0xDEDBU);
    uint16_t filled = 0;
    if (valid && distance_mm < threshold_mm) {
        filled = (uint16_t)(
            (uint32_t)(threshold_mm - distance_mm) * width / threshold_mm);
        if (filled < 5U) {
            filled = 5U;
        }
    }
    if (filled > width) {
        filled = width;
    }
    canvas_fill_rect(
        &progress,
        0,
        2,
        filled,
        5,
        active ? COLOR_GREEN : COLOR_REFERENCE_BLUE);
    lcd_push_canvas(x, 244, &progress);
}

static uint8_t active_sensor_count(const lcd_display_status_t *status)
{
    return (uint8_t)status->tof_1_active +
           (uint8_t)status->tof_2_active +
           (uint8_t)status->ultrasonic_active;
}

static void draw_footer_sensors(const lcd_display_status_t *status)
{
    char sensor_text[24];
    snprintf(
        sensor_text,
        sizeof(sensor_text),
        "SENSORS %u/3",
        (unsigned)active_sensor_count(status));

    canvas_t sensors = canvas_begin_from_dashboard(61, 277, 180, 27);
    const uint16_t accent =
        active_sensor_count(status) == 3U ? COLOR_GREEN : COLOR_REFERENCE_BLUE;
    canvas_fill_circle(&sensors, 12, 13, 10, accent);
    canvas_draw_text(&sensors, 29, 2, sensor_text, 2, COLOR_REFERENCE_TEXT);
    canvas_draw_text_bold(
        &sensors,
        29,
        18,
        active_sensor_count(status) == 3U ? "ALL READY" : "WAITING",
        1,
        COLOR_REFERENCE_MUTED);
    lcd_push_canvas(61, 277, &sensors);
}

static void draw_footer_relay(bool running)
{
    canvas_t relay = canvas_begin_from_dashboard(364, 279, 48, 23);
    canvas_fill_rect(&relay, 0, 1, 48, 21, running ? COLOR_GREEN : COLOR_REFERENCE_MUTED);
    canvas_draw_centered_bold(&relay, 5, running ? "ON" : "OFF", 2, COLOR_WHITE);
    lcd_push_canvas(364, 279, &relay);
}

static void draw_sensor_dynamic(
    uint8_t sensor_index,
    bool active,
    bool valid,
    uint32_t distance_mm,
    uint32_t threshold_mm)
{
    draw_sensor_state(sensor_index, active, valid);
    draw_sensor_value(sensor_index, active, valid, distance_mm);
    draw_sensor_progress(
        sensor_index,
        active,
        valid,
        distance_mm,
        threshold_mm);
}

static bool sensor_state_changed(
    bool previous_active,
    bool previous_valid,
    bool next_active,
    bool next_valid)
{
    return previous_active != next_active || previous_valid != next_valid;
}

static uint32_t distance_difference(uint32_t left, uint32_t right)
{
    return left > right ? left - right : right - left;
}

static void lcd_display_task(void *argument)
{
    (void)argument;
    lcd_gpio_init();
    lcd_hardware_reset();
    lcd_init_ili9486();
    draw_static_screen();
    draw_readable_static_labels();

    lcd_display_status_t displayed = {0};
    lcd_display_status_t latest = {0};
    draw_live_label();
    draw_header_status(false);
    draw_fan(false, 0);
    draw_blower_status(false);
    draw_sensor_dynamic(0, false, false, 0, 101);
    draw_sensor_dynamic(1, false, false, 0, 101);
    draw_sensor_dynamic(2, false, false, 0, 65);
    draw_footer_sensors(&displayed);
    draw_footer_relay(false);

    TickType_t last_card_refresh = xTaskGetTickCount();
    TickType_t last_fan_frame = last_card_refresh;
    uint8_t fan_frame = 0;
    ESP_LOGI(TAG, "ILI9486 dashboard ready: 480x320, rotated 180 degrees");

    while (true) {
        lcd_display_status_t incoming = {0};
        if (xQueueReceive(
                status_queue,
                &incoming,
                pdMS_TO_TICKS(DISPLAY_POLL_MS)) == pdTRUE) {
            latest = incoming;
            while (xQueueReceive(status_queue, &incoming, 0) == pdTRUE) {
                latest = incoming;
            }
        }

        const TickType_t now = xTaskGetTickCount();
        const bool blower_changed = displayed.blower_running != latest.blower_running;
        const bool tof_1_state_changed = sensor_state_changed(
            displayed.tof_1_active,
            displayed.tof_1_valid,
            latest.tof_1_active,
            latest.tof_1_valid);
        const bool tof_2_state_changed = sensor_state_changed(
            displayed.tof_2_active,
            displayed.tof_2_valid,
            latest.tof_2_active,
            latest.tof_2_valid);
        const bool ultrasonic_state_changed = sensor_state_changed(
            displayed.ultrasonic_active,
            displayed.ultrasonic_valid,
            latest.ultrasonic_active,
            latest.ultrasonic_valid);

        if (blower_changed) {
            draw_header_status(latest.blower_running);
            draw_blower_status(latest.blower_running);
            fan_frame = 0;
            draw_fan(latest.blower_running, fan_frame);
            draw_footer_relay(latest.blower_running);
            displayed.blower_running = latest.blower_running;
        }

        if (tof_1_state_changed) {
            draw_sensor_dynamic(
                0,
                latest.tof_1_active,
                latest.tof_1_valid,
                latest.tof_1_distance_mm,
                101);
            displayed.tof_1_active = latest.tof_1_active;
            displayed.tof_1_valid = latest.tof_1_valid;
            displayed.tof_1_distance_mm = latest.tof_1_distance_mm;
        }
        if (tof_2_state_changed) {
            draw_sensor_dynamic(
                1,
                latest.tof_2_active,
                latest.tof_2_valid,
                latest.tof_2_distance_mm,
                101);
            displayed.tof_2_active = latest.tof_2_active;
            displayed.tof_2_valid = latest.tof_2_valid;
            displayed.tof_2_distance_mm = latest.tof_2_distance_mm;
        }
        if (ultrasonic_state_changed) {
            draw_sensor_dynamic(
                2,
                latest.ultrasonic_active,
                latest.ultrasonic_valid,
                latest.ultrasonic_distance_mm,
                65);
            displayed.ultrasonic_active = latest.ultrasonic_active;
            displayed.ultrasonic_valid = latest.ultrasonic_valid;
            displayed.ultrasonic_distance_mm = latest.ultrasonic_distance_mm;
        }

        if (tof_1_state_changed || tof_2_state_changed ||
            ultrasonic_state_changed) {
            draw_footer_sensors(&latest);
        }

        if (now - last_card_refresh >= pdMS_TO_TICKS(CARD_REFRESH_MS)) {
            if (!tof_1_state_changed && latest.tof_1_valid &&
                distance_difference(
                    displayed.tof_1_distance_mm,
                    latest.tof_1_distance_mm) >= 2U) {
                draw_sensor_value(
                    0,
                    latest.tof_1_active,
                    true,
                    latest.tof_1_distance_mm);
                draw_sensor_progress(
                    0,
                    latest.tof_1_active,
                    true,
                    latest.tof_1_distance_mm,
                    101);
                displayed.tof_1_distance_mm = latest.tof_1_distance_mm;
            }
            if (!tof_2_state_changed && latest.tof_2_valid &&
                distance_difference(
                    displayed.tof_2_distance_mm,
                    latest.tof_2_distance_mm) >= 2U) {
                draw_sensor_value(
                    1,
                    latest.tof_2_active,
                    true,
                    latest.tof_2_distance_mm);
                draw_sensor_progress(
                    1,
                    latest.tof_2_active,
                    true,
                    latest.tof_2_distance_mm,
                    101);
                displayed.tof_2_distance_mm = latest.tof_2_distance_mm;
            }
            if (!ultrasonic_state_changed && latest.ultrasonic_valid &&
                distance_difference(
                    displayed.ultrasonic_distance_mm,
                    latest.ultrasonic_distance_mm) >= 2U) {
                draw_sensor_value(
                    2,
                    latest.ultrasonic_active,
                    true,
                    latest.ultrasonic_distance_mm);
                draw_sensor_progress(
                    2,
                    latest.ultrasonic_active,
                    true,
                    latest.ultrasonic_distance_mm,
                    65);
                displayed.ultrasonic_distance_mm = latest.ultrasonic_distance_mm;
            }
            last_card_refresh = now;
        }

        if (latest.blower_running &&
            now - last_fan_frame >= pdMS_TO_TICKS(FAN_FRAME_MS)) {
            fan_frame = (uint8_t)((fan_frame + 1U) % 72U);
            draw_fan(true, fan_frame);
            last_fan_frame = now;
        }
    }
}

esp_err_t lcd_display_start(void)
{
    sprite_pixels = heap_caps_malloc(
        SPRITE_CAPACITY * sizeof(uint16_t),
        MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (sprite_pixels == NULL) {
        sprite_pixels = heap_caps_malloc(
            SPRITE_CAPACITY * sizeof(uint16_t),
            MALLOC_CAP_8BIT);
    }
    if (sprite_pixels == NULL) {
        return ESP_ERR_NO_MEM;
    }

    status_queue = xQueueCreate(1, sizeof(lcd_display_status_t));
    if (status_queue == NULL) {
        heap_caps_free(sprite_pixels);
        sprite_pixels = NULL;
        return ESP_ERR_NO_MEM;
    }

    if (xTaskCreatePinnedToCore(
            lcd_display_task,
            "lcd_display",
            6144,
            NULL,
            1,
            NULL,
            1) != pdPASS) {
        vQueueDelete(status_queue);
        status_queue = NULL;
        heap_caps_free(sprite_pixels);
        sprite_pixels = NULL;
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}

void lcd_display_update(const lcd_display_status_t *status)
{
    if (status_queue != NULL && status != NULL) {
        xQueueOverwrite(status_queue, status);
    }
}
