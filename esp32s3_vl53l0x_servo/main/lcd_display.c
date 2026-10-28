#include "lcd_display.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "driver/gpio.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "lvgl.h"
#include "soc/gpio_struct.h"

static const char *TAG = "LCD_DISPLAY";

#define LCD_RST_PIN GPIO_NUM_4
#define LCD_CS_PIN GPIO_NUM_38
#define LCD_RS_PIN GPIO_NUM_39
#define LCD_WR_PIN GPIO_NUM_40
#define LCD_RD_PIN GPIO_NUM_41

#define LCD_WIDTH 480U
#define LCD_HEIGHT 320U

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


#define DRAW_BUFFER_MAX_ROWS 40U
#define DRAW_BUFFER_MIN_ROWS 8U
#define INTERNAL_RESERVE_BYTES (96U * 1024U)
#define DISPLAY_STACK_BYTES 8192U
#define DISPLAY_POLL_MS 10U
#define COLOR_TEXT 0xFAF6F4U
#define COLOR_MUTED 0xBEB0ADU

static QueueHandle_t status_queue;
static lv_color_t *draw_pixels[2];
static uint16_t draw_rows;
static lv_disp_draw_buf_t draw_buffer;
static lv_disp_drv_t display_driver;
static esp_timer_handle_t tick_timer;


LV_FONT_DECLARE(menu_digits_22);
LV_FONT_DECLARE(menu_units_12);
extern const uint8_t background_start[] asm("_binary_lvgl_background_rgb565_start");
extern const uint8_t fan_frames_start[] asm("_binary_lvgl_fan_frames_rgb565_start");
extern const uint8_t states_start[] asm("_binary_lvgl_states_rgb565_start");
#define FAN_FRAME_COUNT 36U
#define FAN_WIDTH 114U
#define FAN_HEIGHT 106U
#define FAN_FRAME_BYTES (FAN_WIDTH * FAN_HEIGHT * 2U)
static const lv_img_dsc_t background_image = {
    .header = {.cf = LV_IMG_CF_TRUE_COLOR, .w = LCD_WIDTH, .h = LCD_HEIGHT},
    .data_size = LCD_WIDTH * LCD_HEIGHT * 2U,
    .data = background_start,
};
static lv_img_dsc_t fan_images[FAN_FRAME_COUNT];
static lv_img_dsc_t state_images[5][2];

typedef struct {
    lv_obj_t *value;
    lv_obj_t *unit;
    lv_obj_t *light;
} sensor_widgets_t;
static sensor_widgets_t sensors[3];
static lv_obj_t *fan;
static lv_obj_t *blower_state;
static lv_obj_t *relay_state;

static uint64_t lcd_data_pin_mask(void)
{
    uint64_t mask = 0;
    for (size_t bit = 0; bit < 8; ++bit) {
        mask |= 1ULL << LCD_DATA_PINS[bit];
    }
    return mask;
}

static inline void lcd_write_bus(uint8_t value)
{
    const uint32_t low_value =
        ((uint32_t)(value & 0x3FU) << 13) |
        ((uint32_t)(value & 0x40U) << 15);

    /*
     * Drive each data pin directly to its next state.  Clearing the complete
     * bus first forced unchanged high bits through a needless 1->0->1 pulse,
     * increasing simultaneous-switching current on the parallel wiring.
     */
    GPIO.out_w1tc = LCD_DATA_LOW_MASK & ~low_value;
    GPIO.out_w1ts = low_value;
    if ((value & 0x80U) != 0U) {
        GPIO.out1_w1ts.val = LCD_DATA_HIGH_MASK;
    } else {
        GPIO.out1_w1tc.val = LCD_DATA_HIGH_MASK;
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
    /*
     * Fix the panel refresh at the ILI9486L reset default of 70 Hz instead of
     * relying on clone/module power-on state.  The second byte keeps the
     * documented 17-clock line period.
     */
    static const uint8_t frame_rate_control[] = {0xB0, 0x11};
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
    lcd_write_command(
        0xB1,
        frame_rate_control,
        sizeof(frame_rate_control));
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

static void lcd_end_pixels(void)
{
    gpio_set_level(LCD_CS_PIN, 1);
}


/* The byte-swapped lv_color_t buffer is already in panel wire order.
 * GPIO transfer is synchronous: do not signal flush_ready until CS goes high.
 * Two draw buffers do not make this bit-banged interface asynchronous/DMA. */
static void display_flush(lv_disp_drv_t *driver, const lv_area_t *area, lv_color_t *pixels)
{
    const uint16_t width = (uint16_t)(area->x2 - area->x1 + 1);
    const uint16_t height = (uint16_t)(area->y2 - area->y1 + 1);
    lcd_begin_pixels((uint16_t)area->x1, (uint16_t)area->y1, width, height);
    const uint8_t *bytes = (const uint8_t *)pixels;
    const size_t length = (size_t)width * height * sizeof(lv_color_t);
    for (size_t i = 0; i < length; ++i) {
        lcd_write_byte_selected(bytes[i]);
    }
    lcd_end_pixels();
    lv_disp_flush_ready(driver);
}

static void display_tick(void *argument)
{
    (void)argument;
    lv_tick_inc(1);
}

static void display_log(const char *message)
{
    ESP_LOGW(TAG, "%s", message);
}


/* The fixed artwork, including the glass, Chinese titles and icons, is sampled
 * directly from /workspace/MENU.png at 480x320 without zoom/rearrangement.
 * Transparent LVGL groups retain the five original card bounds. Only these
 * groups' dynamic child images/labels invalidate regions during operation. */
static lv_obj_t *card_group(lv_obj_t *parent, int x, int y, int width, int height)
{
    lv_obj_t *object = lv_obj_create(parent);
    lv_obj_remove_style_all(object);
    lv_obj_clear_flag(object, LV_OBJ_FLAG_SCROLLABLE | LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_pos(object, x, y);
    lv_obj_set_size(object, width, height);
    return object;
}

static lv_obj_t *image_at(lv_obj_t *parent, int x, int y, const lv_img_dsc_t *image)
{
    lv_obj_t *object = lv_img_create(parent);
    lv_img_set_src(object, image);
    lv_obj_set_pos(object, x, y);
    return object;
}

static lv_obj_t *label_at(lv_obj_t *parent, int x, int y, const char *text,
                          const lv_font_t *font, uint32_t color)
{
    lv_obj_t *label = lv_label_create(parent);
    lv_obj_remove_style_all(label);
    lv_obj_set_style_text_font(label, font, 0);
    lv_obj_set_style_text_color(label, lv_color_hex(color), 0);
    lv_label_set_text(label, text);
    lv_obj_set_pos(label, x, y);
    return label;
}

static void initialize_images(void)
{
    for (unsigned i = 0; i < FAN_FRAME_COUNT; ++i) {
        fan_images[i] = (lv_img_dsc_t){
            .header = {.cf = LV_IMG_CF_TRUE_COLOR, .w = FAN_WIDTH, .h = FAN_HEIGHT},
            .data_size = FAN_FRAME_BYTES,
            .data = fan_frames_start + i * FAN_FRAME_BYTES,
        };
    }
    static const uint16_t widths[] = {80, 50, 22, 22, 22};
    static const uint16_t heights[] = {29, 21, 27, 27, 27};
    size_t offset = 0;
    for (unsigned i = 0; i < 5; ++i) {
        for (unsigned on = 0; on < 2; ++on) {
            const size_t size = (size_t)widths[i] * heights[i] * 2U;
            state_images[i][on] = (lv_img_dsc_t){
                .header = {.cf = LV_IMG_CF_TRUE_COLOR, .w = widths[i], .h = heights[i]},
                .data_size = size,
                .data = states_start + offset,
            };
            offset += size;
        }
    }
}

static void create_sensor(lv_obj_t *screen, unsigned index)
{
    static const int card_y[] = {49, 116, 185};
    static const int value_y[] = {81, 149, 218};
    static const int light_y[] = {57, 124, 193};
    lv_obj_t *card = card_group(screen, 276, card_y[index], 188, 65);
    sensors[index].value = label_at(card, 16, value_y[index] - card_y[index], "---",
                                     &menu_digits_22, COLOR_MUTED);
    sensors[index].unit = label_at(card, 16, value_y[index] - card_y[index] + 10,
                                    "mm", &menu_units_12, COLOR_MUTED);
    lv_obj_add_flag(sensors[index].unit, LV_OBJ_FLAG_HIDDEN);
    sensors[index].light = image_at(card, 145, light_y[index] - card_y[index],
                                     &state_images[index + 2][0]);
}

static void create_dashboard(void)
{
    initialize_images();
    lv_obj_t *screen = lv_scr_act();
    lv_obj_remove_style_all(screen);
    lv_obj_set_style_bg_color(screen, lv_color_hex(0x9C7368), 0);
    lv_obj_set_style_bg_opa(screen, LV_OPA_COVER, 0);
    lv_obj_clear_flag(screen, LV_OBJ_FLAG_SCROLLABLE);
    image_at(screen, 0, 0, &background_image);

    lv_obj_t *blower = card_group(screen, 18, 49, 249, 138);
    fan = image_at(blower, 42, 29, &fan_images[0]);
    blower_state = image_at(blower, 160, 66, &state_images[0][0]);
    lv_obj_t *relay = card_group(screen, 18, 192, 249, 60);
    relay_state = image_at(relay, 174, 18, &state_images[1][0]);
    for (unsigned i = 0; i < 3; ++i) {
        create_sensor(screen, i);
    }
}

static void fan_frame(void *image, int32_t frame)
{
    /* Frames retain MENU's photographic blade shading, fixed hub and background.
     * The read-only flash data is used directly: no PSRAM frame cache is needed. */
    lv_img_set_src(image, &fan_images[(unsigned)frame % FAN_FRAME_COUNT]);
}

static void set_running(bool running)
{
    lv_anim_del(fan, fan_frame);
    if (running) {
        lv_anim_t animation;
        lv_anim_init(&animation);
        lv_anim_set_var(&animation, fan);
        lv_anim_set_exec_cb(&animation, fan_frame);
        lv_anim_set_values(&animation, 0, FAN_FRAME_COUNT - 1U);
        lv_anim_set_time(&animation, 1200);
        lv_anim_set_repeat_count(&animation, LV_ANIM_REPEAT_INFINITE);
        lv_anim_start(&animation);
    } else {
        lv_img_set_src(fan, &fan_images[0]);
    }
    lv_img_set_src(blower_state, &state_images[0][running]);
    /* This interface has one shared relay/blower state, as in main.c. */
    lv_img_set_src(relay_state, &state_images[1][running]);
}

static void update_sensor(unsigned index, bool active, bool valid, uint32_t distance,
                          bool previous_active, bool previous_valid, uint32_t previous_distance)
{
    if ((active && valid) != (previous_active && previous_valid)) {
        lv_img_set_src(sensors[index].light, &state_images[index + 2][active && valid]);
    }
    if (valid != previous_valid || (valid && distance != previous_distance)) {
        char text[12];
        if (!valid) {
            snprintf(text, sizeof(text), "---");
        } else if (distance > 9999U) {
            snprintf(text, sizeof(text), "9999+");
        } else {
            snprintf(text, sizeof(text), "%u", (unsigned)distance);
        }
        lv_label_set_text(sensors[index].value, text);
        lv_obj_set_style_text_color(sensors[index].value,
            lv_color_hex(valid ? COLOR_TEXT : COLOR_MUTED), 0);
        if (valid) {
            lv_obj_clear_flag(sensors[index].unit, LV_OBJ_FLAG_HIDDEN);
            lv_obj_update_layout(sensors[index].value);
            lv_obj_set_x(sensors[index].unit, 16 + lv_obj_get_width(sensors[index].value) + 2);
        } else {
            lv_obj_add_flag(sensors[index].unit, LV_OBJ_FLAG_HIDDEN);
        }
    }
}

/* Called only in the display task. No other task may enter LVGL. */
static void apply_status(const lcd_display_status_t *next, lcd_display_status_t *previous)
{
    if (next->blower_running != previous->blower_running) {
        set_running(next->blower_running);
    }
    update_sensor(0, next->tof_1_active, next->tof_1_valid, next->tof_1_distance_mm,
                  previous->tof_1_active, previous->tof_1_valid, previous->tof_1_distance_mm);
    update_sensor(1, next->tof_2_active, next->tof_2_valid, next->tof_2_distance_mm,
                  previous->tof_2_active, previous->tof_2_valid, previous->tof_2_distance_mm);
    update_sensor(2, next->ultrasonic_active, next->ultrasonic_valid, next->ultrasonic_distance_mm,
                  previous->ultrasonic_active, previous->ultrasonic_valid, previous->ultrasonic_distance_mm);
    *previous = *next;
}

static void lcd_display_task(void *argument)
{
    QueueHandle_t ready_queue = (QueueHandle_t)argument;
    const esp_timer_create_args_t timer_args = {
        .callback = display_tick,
        .name = "lvgl_tick",
    };
    esp_err_t result = esp_timer_create(&timer_args, &tick_timer);
    if (result == ESP_OK) {
        result = esp_timer_start_periodic(tick_timer, 1000);
        if (result != ESP_OK) {
            esp_timer_delete(tick_timer);
            tick_timer = NULL;
        }
    }
    if (result != ESP_OK) {
        xQueueSend(ready_queue, &result, portMAX_DELAY);
        vTaskDelete(NULL);
        return;
    }

    lv_init();
    lv_log_register_print_cb(display_log);
    lv_disp_draw_buf_init(&draw_buffer, draw_pixels[0], draw_pixels[1], LCD_WIDTH * draw_rows);
    lv_disp_drv_init(&display_driver);
    display_driver.hor_res = LCD_WIDTH;
    display_driver.ver_res = LCD_HEIGHT;
    display_driver.draw_buf = &draw_buffer;
    display_driver.flush_cb = display_flush;
    display_driver.full_refresh = 0;
    if (lv_disp_drv_register(&display_driver) == NULL) {
        esp_timer_stop(tick_timer);
        esp_timer_delete(tick_timer);
        tick_timer = NULL;
        result = ESP_ERR_NO_MEM;
        xQueueSend(ready_queue, &result, portMAX_DELAY);
        vTaskDelete(NULL);
        return;
    }

    lcd_gpio_init();
    lcd_hardware_reset();
    lcd_init_ili9486();
    create_dashboard();
    /* Finish the initial picture before enabling the panel, as in the old driver. */
    lv_refr_now(NULL);
    lcd_enable_display();
    ESP_LOGI(TAG, "ILI9486 dashboard ready: 480x320, rotated 180 degrees; LVGL %d.%d.%d; core %d",
             LVGL_VERSION_MAJOR, LVGL_VERSION_MINOR, LVGL_VERSION_PATCH, xPortGetCoreID());
    ESP_LOGI(TAG, "LVGL draw buffers: 2 x %u bytes, %u rows, internal DRAM; free internal: %u; PSRAM: %u",
             (unsigned)(LCD_WIDTH * draw_rows * sizeof(lv_color_t)), (unsigned)draw_rows,
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    xQueueSend(ready_queue, &result, portMAX_DELAY);

    lcd_display_status_t displayed = {0};
    int64_t last_diagnostics = esp_timer_get_time();
    while (true) {
        lcd_display_status_t incoming;
        if (xQueueReceive(status_queue, &incoming, pdMS_TO_TICKS(DISPLAY_POLL_MS)) == pdTRUE) {
            apply_status(&incoming, &displayed);
        }
        lv_timer_handler();
        const int64_t now = esp_timer_get_time();
        if (now - last_diagnostics >= 60000000LL) {
            ESP_LOGI(TAG, "LVGL heap: internal free=%u min=%u; PSRAM free=%u; stack unused=%u bytes",
                     (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
                     (unsigned)heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT),
                     (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT),
                     (unsigned)uxTaskGetStackHighWaterMark(NULL));
            last_diagnostics = now;
        }
    }
}

static void release_draw_buffers(void)
{
    for (unsigned i = 0; i < 2; ++i) {
        heap_caps_free(draw_pixels[i]);
        draw_pixels[i] = NULL;
    }
}

static esp_err_t allocate_draw_buffers(void)
{
    const uint32_t caps = MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT;
    for (uint16_t rows = DRAW_BUFFER_MAX_ROWS; rows >= DRAW_BUFFER_MIN_ROWS; rows -= 8U) {
        const size_t bytes = LCD_WIDTH * rows * sizeof(lv_color_t);
        if (heap_caps_get_free_size(caps) < 2U * bytes + INTERNAL_RESERVE_BYTES) {
            continue;
        }
        draw_pixels[0] = heap_caps_malloc(bytes, caps);
        draw_pixels[1] = heap_caps_malloc(bytes, caps);
        if (draw_pixels[0] != NULL && draw_pixels[1] != NULL) {
            draw_rows = rows;
            return ESP_OK;
        }
        release_draw_buffers();
    }
    return ESP_ERR_NO_MEM;
}

esp_err_t lcd_display_start(void)
{
    if (status_queue != NULL) {
        return ESP_ERR_INVALID_STATE;
    }
    esp_err_t result = allocate_draw_buffers();
    if (result != ESP_OK) {
        return result;
    }
    status_queue = xQueueCreate(1, sizeof(lcd_display_status_t));
    QueueHandle_t ready_queue = xQueueCreate(1, sizeof(esp_err_t));
    if (status_queue == NULL || ready_queue == NULL) {
        result = ESP_ERR_NO_MEM;
    } else if (xTaskCreatePinnedToCore(lcd_display_task, "lcd_lvgl", DISPLAY_STACK_BYTES,
                                     ready_queue, 1, NULL, 1) != pdPASS) {
        result = ESP_ERR_NO_MEM;
    } else {
        /* Report display/timer startup failures through the existing interface. */
        xQueueReceive(ready_queue, &result, portMAX_DELAY);
    }
    if (ready_queue != NULL) {
        vQueueDelete(ready_queue);
    }
    if (result != ESP_OK) {
        if (status_queue != NULL) {
            vQueueDelete(status_queue);
            status_queue = NULL;
        }
        release_draw_buffers();
    }
    return result;
}

void lcd_display_update(const lcd_display_status_t *status)
{
    if (status_queue != NULL && status != NULL) {
        xQueueOverwrite(status_queue, status);
    }
}
