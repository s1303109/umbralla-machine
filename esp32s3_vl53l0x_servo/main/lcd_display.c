#include "lcd_display.h"

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#include "driver/gpio.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
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

#define FAN_X 56U
#define FAN_Y 75U
#define FAN_WIDTH 110U
#define FAN_HEIGHT 110U
#define FAN_FRAME_COUNT 72U
#define FAN_CENTER_X_Q8 14080
#define FAN_CENTER_Y_Q8 14016
#define FAN_HUB_RADIUS_Q8 3994
#define FAN_ROTATION_RADIUS_Q8 13568
#define FAN_EDGE_MARGIN 1U
#define BLOWER_STATUS_X 176U
#define BLOWER_STATUS_Y 112U
#define BLOWER_STATUS_WIDTH 88U
#define BLOWER_STATUS_HEIGHT 35U
#define RELAY_STATUS_X 189U
#define RELAY_STATUS_Y 214U
#define RELAY_STATUS_WIDTH 70U
#define RELAY_STATUS_HEIGHT 29U
#define SENSOR_LIGHT_X 423U
#define SENSOR_LIGHT_WIDTH 33U
#define SENSOR_LIGHT_HEIGHT 30U
#define DIGIT_ATLAS_WIDTH 276U
#define DIGIT_HEIGHT 31U
#define DIGIT_CELL_WIDTH 23U
#define DIGIT_ADVANCE 17U
#define UNIT_ADVANCE 10U
#define UNIT_GAP 2U

/* The blower-status panel is the largest region redrawn at one time. */
#define SPRITE_CAPACITY (270U * 55U)

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
#define COLOR_MENU_WHITE 0xFF9EU
#define COLOR_MENU_MUTED 0xBD35U

#define FAN_FRAME_MS 20U
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
extern const uint8_t fan_original_rgb565_start[]
    asm("_binary_fan_original_rgb565_start");
extern const uint8_t fan_delta_s8_start[]
    asm("_binary_fan_delta_s8_start");
extern const uint8_t blower_on_rgb565_start[]
    asm("_binary_blower_on_rgb565_start");
extern const uint8_t blower_off_rgb565_start[]
    asm("_binary_blower_off_rgb565_start");
extern const uint8_t relay_on_rgb565_start[]
    asm("_binary_relay_on_rgb565_start");
extern const uint8_t relay_off_rgb565_start[]
    asm("_binary_relay_off_rgb565_start");
extern const uint8_t sensor_lights_on_rgb565_start[]
    asm("_binary_sensor_lights_on_rgb565_start");
extern const uint8_t sensor_lights_off_rgb565_start[]
    asm("_binary_sensor_lights_off_rgb565_start");
extern const uint8_t menu_digits_alpha8_start[]
    asm("_binary_menu_digits_alpha8_start");

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

static int16_t trig_72(const int16_t table[36], uint8_t angle)
{
    const uint8_t base = (uint8_t)((angle / 2U) % 36U);
    if ((angle & 1U) == 0U) {
        return table[base];
    }
    return (int16_t)((table[base] + table[(base + 1U) % 36U]) / 2);
}

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
    /*
     * ILI9486L requires a >=50 ns write cycle and >=15 ns for each WR phase.
     * These explicit delays remain within specification even at 240 MHz and
     * avoid the visible wipe caused by the previous 1 us delay per byte.
     */
    __asm__ __volatile__(
        "nop; nop; nop; nop; nop; nop; nop; nop; "
        "nop; nop; nop; nop;"
        ::: "memory");
    GPIO.out1_w1ts.val = LCD_WR_HIGH_MASK;
    __asm__ __volatile__(
        "nop; nop; nop; nop; nop; nop; nop; nop;"
        ::: "memory");
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
}

static void lcd_enable_display(void)
{
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

static uint16_t blend_rgb565(uint16_t background, uint16_t foreground, uint8_t alpha)
{
    const uint16_t inverse = (uint16_t)(255U - alpha);
    const uint16_t background_red = (background >> 11) & 0x1FU;
    const uint16_t background_green = (background >> 5) & 0x3FU;
    const uint16_t background_blue = background & 0x1FU;
    const uint16_t foreground_red = (foreground >> 11) & 0x1FU;
    const uint16_t foreground_green = (foreground >> 5) & 0x3FU;
    const uint16_t foreground_blue = foreground & 0x1FU;
    const uint16_t red =
        (uint16_t)((background_red * inverse + foreground_red * alpha + 127U) / 255U);
    const uint16_t green =
        (uint16_t)((background_green * inverse + foreground_green * alpha + 127U) / 255U);
    const uint16_t blue =
        (uint16_t)((background_blue * inverse + foreground_blue * alpha + 127U) / 255U);
    return (uint16_t)((red << 11) | (green << 5) | blue);
}

static void canvas_blend_pixel(
    canvas_t *canvas,
    int x,
    int y,
    uint16_t color,
    uint8_t alpha)
{
    if (x >= 0 && y >= 0 && x < canvas->width && y < canvas->height) {
        const uint32_t index = (uint32_t)y * canvas->width + (uint32_t)x;
        canvas->pixels[index] = blend_rgb565(canvas->pixels[index], color, alpha);
    }
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
    }
    lcd_end_pixels();
}

static void lcd_push_rgb565_asset(
    uint16_t x,
    uint16_t y,
    uint16_t width,
    uint16_t height,
    const uint8_t *asset)
{
    lcd_begin_pixels(x, y, width, height);
    const uint32_t pixel_count = (uint32_t)width * height;
    for (uint32_t index = 0; index < pixel_count; ++index) {
        lcd_write_byte_selected(asset[index * 2U]);
        lcd_write_byte_selected(asset[index * 2U + 1U]);
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

static int16_t sample_fan_delta(
    int source_x_q8,
    int source_y_q8,
    uint8_t channel)
{
    const int x0 = source_x_q8 / 256;
    const int y0 = source_y_q8 / 256;
    const int fraction_x = source_x_q8 & 0xFF;
    const int fraction_y = source_y_q8 & 0xFF;
    const int8_t *delta = (const int8_t *)fan_delta_s8_start;
    const size_t top_left = ((size_t)y0 * FAN_WIDTH + x0) * 3U + channel;
    const size_t top_right = top_left + 3U;
    const size_t bottom_left = top_left + FAN_WIDTH * 3U;
    const size_t bottom_right = bottom_left + 3U;
    const int32_t top =
        delta[top_left] * (256 - fraction_x) +
        delta[top_right] * fraction_x;
    const int32_t bottom =
        delta[bottom_left] * (256 - fraction_x) +
        delta[bottom_right] * fraction_x;
    const int32_t value =
        top * (256 - fraction_y) + bottom * fraction_y;
    return (int16_t)(
        value >= 0 ? (value + 32768) / 65536 :
                     -((-value + 32768) / 65536));
}

static uint16_t clamp_fan_component(int value, int maximum)
{
    if (value < 0) {
        return 0;
    }
    if (value > maximum) {
        return (uint16_t)maximum;
    }
    return (uint16_t)value;
}

static void draw_fan_rotor(bool running, uint8_t frame)
{
    if (!running) {
        lcd_push_rgb565_asset(
            FAN_X,
            FAN_Y,
            FAN_WIDTH,
            FAN_HEIGHT,
            fan_original_rgb565_start);
        return;
    }

    canvas_t fan = canvas_begin_from_dashboard(
        FAN_X,
        FAN_Y,
        FAN_WIDTH,
        FAN_HEIGHT);
    const uint8_t angle = (uint8_t)(frame % FAN_FRAME_COUNT);
    const int32_t cosine = trig_72(COS_36, angle);
    const int32_t sine = trig_72(SIN_36, angle);
    const int32_t rotation_radius_squared =
        FAN_ROTATION_RADIUS_Q8 * FAN_ROTATION_RADIUS_Q8;
    const int32_t hub_radius_squared =
        FAN_HUB_RADIUS_Q8 * FAN_HUB_RADIUS_Q8;

    for (uint16_t y = 0; y < FAN_HEIGHT; ++y) {
        for (uint16_t x = 0; x < FAN_WIDTH; ++x) {
            const int32_t dx_q8 = (int32_t)x * 256 - FAN_CENTER_X_Q8;
            const int32_t dy_q8 = (int32_t)y * 256 - FAN_CENTER_Y_Q8;
            const int32_t distance_squared =
                dx_q8 * dx_q8 + dy_q8 * dy_q8;
            const size_t pixel_index = (size_t)y * FAN_WIDTH + x;

            if (distance_squared <= hub_radius_squared) {
                fan.pixels[pixel_index] =
                    ((uint16_t)fan_original_rgb565_start[pixel_index * 2U] << 8) |
                    fan_original_rgb565_start[pixel_index * 2U + 1U];
                continue;
            }
            if (
                distance_squared > rotation_radius_squared ||
                x < FAN_EDGE_MARGIN ||
                x >= FAN_WIDTH - FAN_EDGE_MARGIN ||
                y < FAN_EDGE_MARGIN ||
                y >= FAN_HEIGHT - FAN_EDGE_MARGIN) {
                continue;
            }

            const int32_t source_x_q8 = FAN_CENTER_X_Q8 +
                (cosine * dx_q8 + sine * dy_q8) / 1024;
            const int32_t source_y_q8 = FAN_CENTER_Y_Q8 +
                (-sine * dx_q8 + cosine * dy_q8) / 1024;
            const int source_x = source_x_q8 / 256;
            const int source_y = source_y_q8 / 256;
            if (
                source_x < (int)FAN_EDGE_MARGIN ||
                source_y < (int)FAN_EDGE_MARGIN ||
                source_x + 1 >= (int)(FAN_WIDTH - FAN_EDGE_MARGIN) ||
                source_y + 1 >= (int)(FAN_HEIGHT - FAN_EDGE_MARGIN)) {
                continue;
            }

            const uint16_t background = fan.pixels[pixel_index];
            const uint16_t red = clamp_fan_component(
                ((background >> 11) & 0x1FU) +
                    sample_fan_delta(source_x_q8, source_y_q8, 0),
                0x1F);
            const uint16_t green = clamp_fan_component(
                ((background >> 5) & 0x3FU) +
                    sample_fan_delta(source_x_q8, source_y_q8, 1),
                0x3F);
            const uint16_t blue = clamp_fan_component(
                (background & 0x1FU) +
                    sample_fan_delta(source_x_q8, source_y_q8, 2),
                0x1F);
            fan.pixels[pixel_index] =
                (uint16_t)((red << 11) | (green << 5) | blue);
        }
    }
    lcd_push_canvas(FAN_X, FAN_Y, &fan);
}

static void draw_blower_status(bool running)
{
    lcd_push_rgb565_asset(
        BLOWER_STATUS_X,
        BLOWER_STATUS_Y,
        BLOWER_STATUS_WIDTH,
        BLOWER_STATUS_HEIGHT,
        running ? blower_on_rgb565_start : blower_off_rgb565_start);
}

static void draw_sensor_state(
    uint8_t sensor_index,
    bool active,
    bool valid)
{
    static const uint16_t state_y[3] = {52, 123, 194};
    const uint16_t y = state_y[sensor_index];
    const size_t patch_size =
        (size_t)SENSOR_LIGHT_WIDTH * SENSOR_LIGHT_HEIGHT * 2U;
    const uint8_t *asset = active && valid
        ? sensor_lights_on_rgb565_start
        : sensor_lights_off_rgb565_start;
    lcd_push_rgb565_asset(
        SENSOR_LIGHT_X,
        y,
        SENSOR_LIGHT_WIDTH,
        SENSOR_LIGHT_HEIGHT,
        asset + sensor_index * patch_size);
}

static int menu_glyph_index(char character)
{
    if (character >= '0' && character <= '9') {
        return character - '0';
    }
    if (character == 'm') {
        return 10;
    }
    if (character == '-') {
        return 11;
    }
    return -1;
}

static void canvas_draw_menu_glyph(
    canvas_t *canvas,
    int x,
    char character,
    uint16_t color)
{
    const int glyph_index = menu_glyph_index(character);
    if (glyph_index < 0) {
        return;
    }
    const uint32_t glyph_x = (uint32_t)glyph_index * DIGIT_CELL_WIDTH;
    for (uint16_t row = 0; row < DIGIT_HEIGHT; ++row) {
        for (uint16_t column = 0; column < DIGIT_CELL_WIDTH; ++column) {
            const uint8_t alpha = menu_digits_alpha8_start[
                (uint32_t)row * DIGIT_ATLAS_WIDTH + glyph_x + column];
            if (alpha != 0U) {
                canvas_blend_pixel(canvas, x + column, row, color, alpha);
            }
        }
    }
}

static void canvas_draw_menu_text(
    canvas_t *canvas,
    int x,
    const char *text,
    bool valid)
{
    char previous_character = '\0';
    while (*text != '\0') {
        if (*text == 'm' && previous_character != 'm') {
            x += UNIT_GAP;
        }
        const uint16_t color =
            (!valid || *text == 'm') ? COLOR_MENU_MUTED : COLOR_MENU_WHITE;
        canvas_draw_menu_glyph(canvas, x, *text, color);
        x += *text == 'm' ? UNIT_ADVANCE : DIGIT_ADVANCE;
        previous_character = *text;
        ++text;
    }
}

static void draw_sensor_value(
    uint8_t sensor_index,
    bool active,
    bool valid,
    uint32_t distance_mm)
{
    (void)active;
    static const uint16_t value_y[3] = {80, 151, 222};
    const uint16_t y = value_y[sensor_index];
    char distance_text[12];
    if (valid) {
        snprintf(distance_text, sizeof(distance_text), "%umm", (unsigned)distance_mm);
    } else {
        snprintf(distance_text, sizeof(distance_text), "---");
    }

    canvas_t value = canvas_begin_from_dashboard(289, y, 118, 31);
    canvas_draw_menu_text(&value, 2, distance_text, valid);
    lcd_push_canvas(289, y, &value);
}

static void draw_relay_status(bool running)
{
    lcd_push_rgb565_asset(
        RELAY_STATUS_X,
        RELAY_STATUS_Y,
        RELAY_STATUS_WIDTH,
        RELAY_STATUS_HEIGHT,
        running ? relay_on_rgb565_start : relay_off_rgb565_start);
}

static void draw_sensor_dynamic(
    uint8_t sensor_index,
    bool active,
    bool valid,
    uint32_t distance_mm)
{
    draw_sensor_state(sensor_index, active, valid);
    draw_sensor_value(sensor_index, active, valid, distance_mm);
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

    lcd_display_status_t displayed = {0};
    lcd_display_status_t latest = {0};
    draw_fan_rotor(false, 0);
    draw_blower_status(false);
    draw_sensor_dynamic(0, false, false, 0);
    draw_sensor_dynamic(1, false, false, 0);
    draw_sensor_dynamic(2, false, false, 0);
    draw_relay_status(false);
    lcd_enable_display();

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
            draw_blower_status(latest.blower_running);
            fan_frame = 0;
            draw_fan_rotor(latest.blower_running, fan_frame);
            draw_relay_status(latest.blower_running);
            displayed.blower_running = latest.blower_running;
            last_fan_frame = now;
        }

        if (tof_1_state_changed) {
            draw_sensor_dynamic(
                0,
                latest.tof_1_active,
                latest.tof_1_valid,
                latest.tof_1_distance_mm);
            displayed.tof_1_active = latest.tof_1_active;
            displayed.tof_1_valid = latest.tof_1_valid;
            displayed.tof_1_distance_mm = latest.tof_1_distance_mm;
        }
        if (tof_2_state_changed) {
            draw_sensor_dynamic(
                1,
                latest.tof_2_active,
                latest.tof_2_valid,
                latest.tof_2_distance_mm);
            displayed.tof_2_active = latest.tof_2_active;
            displayed.tof_2_valid = latest.tof_2_valid;
            displayed.tof_2_distance_mm = latest.tof_2_distance_mm;
        }
        if (ultrasonic_state_changed) {
            draw_sensor_dynamic(
                2,
                latest.ultrasonic_active,
                latest.ultrasonic_valid,
                latest.ultrasonic_distance_mm);
            displayed.ultrasonic_active = latest.ultrasonic_active;
            displayed.ultrasonic_valid = latest.ultrasonic_valid;
            displayed.ultrasonic_distance_mm = latest.ultrasonic_distance_mm;
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
                displayed.ultrasonic_distance_mm = latest.ultrasonic_distance_mm;
            }
            last_card_refresh = now;
        }

        if (latest.blower_running &&
            now - last_fan_frame >= pdMS_TO_TICKS(FAN_FRAME_MS)) {
            fan_frame = (uint8_t)((fan_frame + 1U) % FAN_FRAME_COUNT);
            draw_fan_rotor(true, fan_frame);
            last_fan_frame = now;
        }
    }
}

esp_err_t lcd_display_start(void)
{
    bool sprite_uses_psram = true;
    sprite_pixels = heap_caps_malloc(
        SPRITE_CAPACITY * sizeof(uint16_t),
        MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (sprite_pixels == NULL) {
        sprite_uses_psram = false;
        sprite_pixels = heap_caps_malloc(
            SPRITE_CAPACITY * sizeof(uint16_t),
            MALLOC_CAP_8BIT);
    }
    if (sprite_pixels == NULL) {
        return ESP_ERR_NO_MEM;
    }
    ESP_LOGI(
        TAG,
        "Display buffer: %u bytes in %s; free internal RAM: %u bytes",
        (unsigned)(SPRITE_CAPACITY * sizeof(uint16_t)),
        sprite_uses_psram ? "PSRAM" : "internal RAM",
        (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT));

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
