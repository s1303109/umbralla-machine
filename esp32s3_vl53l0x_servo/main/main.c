#include <stdbool.h>
#include <stdint.h>

#include "driver/gpio.h"
#include "driver/i2c_master.h"
#include "driver/ledc.h"
#include "esp_check.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_rom_sys.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "vl53l0x.h"

static const char *TAG = "TOF_RELAY_SERVO";

// ESP32-S3-WROOM-1 N16R8 pin assignments
#define TOF_1_SDA_PIN GPIO_NUM_8
#define TOF_1_SCL_PIN GPIO_NUM_9
#define TOF_1_XSHUT_PIN GPIO_NUM_10
#define TOF_2_SDA_PIN GPIO_NUM_11
#define TOF_2_SCL_PIN GPIO_NUM_12
#define HC_SR04_TRIG_PIN GPIO_NUM_5
#define HC_SR04_ECHO_PIN GPIO_NUM_6
#define RELAY_PIN GPIO_NUM_7
#define SERVO_PIN GPIO_NUM_4
#define TOF_I2C_ADDRESS 0x29U

// The relay module jumper must be set to H (high-level trigger).
#define RELAY_ON_LEVEL 1
#define RELAY_OFF_LEVEL 0

#define HC_SR04_MEASUREMENT_INTERVAL_MS 100U
#define HC_SR04_ECHO_TIMEOUT_US 30000LL

// Independent trigger distances for the TOF and ultrasonic sensors
#define TOF_TRIGGER_DISTANCE_MM 101U
#define HC_SR04_TRIGGER_DISTANCE_MM 65U
#define REQUIRED_CONSECUTIVE_READINGS 3U
#define MEASUREMENT_INTERVAL_MS 50U

#define SERVO_REST_ANGLE 10U
#define SERVO_ACTION_ANGLE 90U
#define SERVO_POWER_UP_DELAY_MS 200U
#define SERVO_RETURN_TIME_MS 600U
#define SERVO_PWM_FREQUENCY_HZ 50U
#define SERVO_PWM_PERIOD_US 20000U
#define SERVO_MIN_PULSE_US 500U
#define SERVO_MAX_PULSE_US 2400U
#define SERVO_DUTY_BITS 14U
#define SERVO_DUTY_MAX ((1U << SERVO_DUTY_BITS) - 1U)

typedef enum {
    OUTPUT_OFF,
    OUTPUT_SERVO_POWER_UP,
    OUTPUT_ACTIVE,
    OUTPUT_SERVO_RETURNING,
} output_state_t;

typedef struct {
    const char *name;
    uint32_t threshold_mm;
    bool active;
    uint8_t below_threshold_count;
    uint8_t clear_threshold_count;
} distance_trigger_t;

static bool relay_enabled = false;
static output_state_t output_state = OUTPUT_OFF;
static uint32_t output_state_started_ms = 0;
static uint32_t last_hc_sr04_measurement_ms = 0;
static distance_trigger_t tof_1_trigger = {
    .name = "TOF 1",
    .threshold_mm = TOF_TRIGGER_DISTANCE_MM,
};
static distance_trigger_t tof_2_trigger = {
    .name = "TOF 2",
    .threshold_mm = TOF_TRIGGER_DISTANCE_MM,
};
static distance_trigger_t hc_sr04_trigger = {
    .name = "HC-SR04",
    .threshold_mm = HC_SR04_TRIGGER_DISTANCE_MM,
};

static uint32_t now_ms(void)
{
    return (uint32_t)(esp_timer_get_time() / 1000ULL);
}

static esp_err_t relay_set_enabled(bool enabled)
{
    const esp_err_t result = gpio_set_level(
        RELAY_PIN, enabled ? RELAY_ON_LEVEL : RELAY_OFF_LEVEL);
    if (result == ESP_OK && relay_enabled != enabled) {
        relay_enabled = enabled;
        ESP_LOGI(TAG, "Relay %s", enabled ? "ON (COM-NO closed)" : "OFF (COM-NO open)");
    }
    return result;
}

static esp_err_t relay_init(void)
{
    // Set the output latch LOW before changing the pin to output mode so the
    // relay cannot pulse ON during startup.
    ESP_RETURN_ON_ERROR(gpio_set_level(RELAY_PIN, RELAY_OFF_LEVEL), TAG, "Failed to preset relay OFF");
    const gpio_config_t relay_config = {
        .pin_bit_mask = 1ULL << RELAY_PIN,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_ENABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_RETURN_ON_ERROR(gpio_config(&relay_config), TAG, "Failed to configure relay GPIO");
    return relay_set_enabled(false);
}

static uint32_t servo_angle_to_duty(uint8_t angle)
{
    const uint32_t pulse_us = SERVO_MIN_PULSE_US
        + ((SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US) * angle) / 180U;
    return (pulse_us * SERVO_DUTY_MAX) / SERVO_PWM_PERIOD_US;
}

static esp_err_t servo_set_angle(uint8_t angle)
{
    ESP_RETURN_ON_ERROR(
        ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, servo_angle_to_duty(angle)),
        TAG,
        "Failed to set servo PWM duty");
    return ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);
}

static esp_err_t servo_stop_pwm(void)
{
    ESP_RETURN_ON_ERROR(
        ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, 0),
        TAG,
        "Failed to stop servo PWM");
    return ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);
}

static esp_err_t servo_init(void)
{
    const ledc_timer_config_t timer_config = {
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .duty_resolution = LEDC_TIMER_14_BIT,
        .timer_num = LEDC_TIMER_0,
        .freq_hz = SERVO_PWM_FREQUENCY_HZ,
        .clk_cfg = LEDC_AUTO_CLK,
    };
    ESP_RETURN_ON_ERROR(ledc_timer_config(&timer_config), TAG, "Failed to configure servo timer");

    const ledc_channel_config_t channel_config = {
        .gpio_num = SERVO_PIN,
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .channel = LEDC_CHANNEL_0,
        .intr_type = LEDC_INTR_DISABLE,
        .timer_sel = LEDC_TIMER_0,
        .duty = 0,
        .hpoint = 0,
    };
    return ledc_channel_config(&channel_config);
}

static esp_err_t hc_sr04_init(void)
{
    const gpio_config_t trigger_config = {
        .pin_bit_mask = 1ULL << HC_SR04_TRIG_PIN,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_RETURN_ON_ERROR(gpio_config(&trigger_config), TAG, "Failed to configure HC-SR04 TRIG");

    const gpio_config_t echo_config = {
        .pin_bit_mask = 1ULL << HC_SR04_ECHO_PIN,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_RETURN_ON_ERROR(gpio_config(&echo_config), TAG, "Failed to configure HC-SR04 ECHO");

    return gpio_set_level(HC_SR04_TRIG_PIN, 0);
}

static bool hc_sr04_read_distance_mm(uint32_t *distance_mm)
{
    gpio_set_level(HC_SR04_TRIG_PIN, 0);
    esp_rom_delay_us(2);
    gpio_set_level(HC_SR04_TRIG_PIN, 1);
    esp_rom_delay_us(10);
    gpio_set_level(HC_SR04_TRIG_PIN, 0);

    int64_t wait_started_us = esp_timer_get_time();
    while (gpio_get_level(HC_SR04_ECHO_PIN) == 0) {
        if (esp_timer_get_time() - wait_started_us >= HC_SR04_ECHO_TIMEOUT_US) {
            return false;
        }
    }

    const int64_t echo_started_us = esp_timer_get_time();
    while (gpio_get_level(HC_SR04_ECHO_PIN) == 1) {
        if (esp_timer_get_time() - echo_started_us >= HC_SR04_ECHO_TIMEOUT_US) {
            return false;
        }
    }

    const uint32_t echo_duration_us = (uint32_t)(esp_timer_get_time() - echo_started_us);
    *distance_mm = (echo_duration_us * 10U) / 58U;
    return true;
}

static void sensor_hard_reset(void)
{
    gpio_set_direction(TOF_1_XSHUT_PIN, GPIO_MODE_OUTPUT);
    gpio_set_level(TOF_1_XSHUT_PIN, 0);
    vTaskDelay(pdMS_TO_TICKS(10));
    gpio_set_level(TOF_1_XSHUT_PIN, 1);
    vTaskDelay(pdMS_TO_TICKS(10));
}

static bool read_sensor_id_slow(i2c_master_bus_handle_t bus)
{
    const i2c_device_config_t device_config = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address = TOF_I2C_ADDRESS,
        .scl_speed_hz = 10000,
    };
    i2c_master_dev_handle_t device = NULL;
    if (i2c_master_bus_add_device(bus, &device_config, &device) != ESP_OK) {
        return false;
    }

    const uint8_t model_id_register = 0xC0;
    uint8_t model_id = 0;
    const esp_err_t result = i2c_master_transmit_receive(
        device, &model_id_register, 1, &model_id, 1, 100);
    i2c_master_bus_rm_device(device);

    if (result == ESP_OK) {
        ESP_LOGI(TAG, "Slow I2C test succeeded: register 0xC0 = 0x%02X", model_id);
        return true;
    }

    ESP_LOGW(TAG, "Slow 10 kHz I2C test failed: %s", esp_err_to_name(result));
    return false;
}

static void force_outputs_off(void)
{
    if (servo_stop_pwm() != ESP_OK) {
        ESP_LOGE(TAG, "Failed to stop servo PWM during shutdown");
    }
    if (relay_set_enabled(false) != ESP_OK) {
        ESP_LOGE(TAG, "Failed to turn relay OFF during shutdown");
    }
    output_state = OUTPUT_OFF;
}

static void update_output_sequence(uint32_t current_ms)
{
    const bool trigger_requested =
        tof_1_trigger.active && tof_2_trigger.active && hc_sr04_trigger.active;

    switch (output_state) {
        case OUTPUT_OFF:
            if (trigger_requested) {
                if (relay_set_enabled(true) == ESP_OK) {
                    output_state = OUTPUT_SERVO_POWER_UP;
                    output_state_started_ms = current_ms;
                    ESP_LOGI(TAG, "Servo power ON; waiting before PWM command");
                }
            }
            break;

        case OUTPUT_SERVO_POWER_UP:
            if (!trigger_requested) {
                force_outputs_off();
            } else if (current_ms - output_state_started_ms >= SERVO_POWER_UP_DELAY_MS) {
                if (servo_set_angle(SERVO_ACTION_ANGLE) == ESP_OK) {
                    output_state = OUTPUT_ACTIVE;
                    ESP_LOGI(TAG, "Servo commanded to 90 degrees");
                }
            }
            break;

        case OUTPUT_ACTIVE:
            if (!trigger_requested) {
                if (servo_set_angle(SERVO_REST_ANGLE) == ESP_OK) {
                    output_state = OUTPUT_SERVO_RETURNING;
                    output_state_started_ms = current_ms;
                    ESP_LOGI(TAG, "Hand removed; servo returning to 10 degrees");
                }
            }
            break;

        case OUTPUT_SERVO_RETURNING:
            if (trigger_requested) {
                if (servo_set_angle(SERVO_ACTION_ANGLE) == ESP_OK) {
                    output_state = OUTPUT_ACTIVE;
                    ESP_LOGI(TAG, "Trigger returned; servo commanded to 90 degrees");
                }
            } else if (current_ms - output_state_started_ms >= SERVO_RETURN_TIME_MS) {
                force_outputs_off();
                ESP_LOGI(TAG, "Servo PWM stopped; relay power OFF");
            }
            break;
    }
}

static void process_distance(
    distance_trigger_t *trigger,
    uint32_t distance_mm)
{
    if (distance_mm < trigger->threshold_mm) {
        trigger->clear_threshold_count = 0;
        if (!trigger->active &&
            trigger->below_threshold_count < REQUIRED_CONSECUTIVE_READINGS) {
            ++trigger->below_threshold_count;
        }
        if (!trigger->active &&
            trigger->below_threshold_count >= REQUIRED_CONSECUTIVE_READINGS) {
            trigger->active = true;
            ESP_LOGI(
                TAG,
                "%s trigger active: %u mm < %u mm",
                trigger->name,
                (unsigned)distance_mm,
                (unsigned)trigger->threshold_mm);
        }
    } else {
        trigger->below_threshold_count = 0;
        if (trigger->active &&
            trigger->clear_threshold_count < REQUIRED_CONSECUTIVE_READINGS) {
            ++trigger->clear_threshold_count;
        }
        if (trigger->active &&
            trigger->clear_threshold_count >= REQUIRED_CONSECUTIVE_READINGS) {
            trigger->active = false;
            trigger->clear_threshold_count = 0;
            ESP_LOGI(TAG, "%s trigger clear", trigger->name);
        }
    }

    update_output_sequence(now_ms());
}

static void invalidate_trigger(distance_trigger_t *trigger)
{
    trigger->active = false;
    trigger->below_threshold_count = 0;
    trigger->clear_threshold_count = 0;
    // A missing or invalid sensor reading is a fault, so cut power immediately
    // instead of waiting for the normal servo return sequence.
    force_outputs_off();
}

static vl53l0x_handle_t sensor_init(
    const char *name,
    i2c_port_num_t i2c_port,
    gpio_num_t sda_pin,
    gpio_num_t scl_pin,
    bool use_hard_reset)
{
    if (use_hard_reset) {
        sensor_hard_reset();
    }

    i2c_master_bus_handle_t bus = NULL;
    const i2c_master_bus_config_t bus_config = {
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .i2c_port = i2c_port,
        .sda_io_num = sda_pin,
        .scl_io_num = scl_pin,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true,
    };
    ESP_ERROR_CHECK(i2c_new_master_bus(&bus_config, &bus));

    while (i2c_master_probe(bus, TOF_I2C_ADDRESS, 100) != ESP_OK) {
        const int sda_level = gpio_get_level(sda_pin);
        const int scl_level = gpio_get_level(scl_pin);

        ESP_LOGW(
            TAG,
            "%s I2C line levels: SDA(GPIO%d)=%d, SCL(GPIO%d)=%d",
            name,
            (int)sda_pin,
            sda_level,
            (int)scl_pin,
            scl_level);

        // A low line means the bus is electrically stuck, so scanning every
        // address only produces repetitive timeouts. Scan only when both lines
        // have returned to their normal idle-high state.
        if (sda_level == 1 && scl_level == 1) {
            read_sensor_id_slow(bus);
        } else {
            ESP_LOGE(TAG, "%s I2C bus is stuck LOW; check sensor power and wiring", name);
        }
        ESP_LOGW(
            TAG,
            "%s not found at I2C 0x29; check VIN/GND/SDA GPIO%d/SCL GPIO%d",
            name,
            (int)sda_pin,
            (int)scl_pin);
        force_outputs_off();
        vTaskDelay(pdMS_TO_TICKS(1000));
        if (use_hard_reset) {
            sensor_hard_reset();
        }
    }

    ESP_LOGI(TAG, "%s detected at I2C address 0x29", name);

    vl53l0x_handle_t sensor = NULL;
    ESP_ERROR_CHECK(vl53l0x_create(&sensor, bus));
    ESP_ERROR_CHECK(vl53l0x_init(sensor));

    vl53l0x_ref_spad_calibration_t spad_calibration = {0};
    ESP_ERROR_CHECK(vl53l0x_perform_ref_spad_management(sensor, &spad_calibration));

    vl53l0x_ref_calibration_t ref_calibration = {0};
    ESP_ERROR_CHECK(vl53l0x_perform_ref_calibration(sensor, &ref_calibration));
    ESP_ERROR_CHECK(vl53l0x_set_profile(sensor, VL53L0X_PROFILE_DEFAULT));

    return sensor;
}

static void measure_tof(
    vl53l0x_handle_t sensor,
    distance_trigger_t *trigger)
{
    vl53l0x_data_t data = {0};
    const esp_err_t result = vl53l0x_single_measure(sensor, &data);

    if (result != ESP_OK || !data.valid || data.distance_mm == 0) {
        invalidate_trigger(trigger);
        ESP_LOGW(
            TAG,
            "%s invalid reading: error=%s, status=%u",
            trigger->name,
            esp_err_to_name(result),
            (unsigned)data.range_status);
        return;
    }

    ESP_LOGI(
        TAG,
        "%s distance: %u mm | Relay: %s",
        trigger->name,
        (unsigned)data.distance_mm,
        relay_enabled ? "ON" : "OFF");
    process_distance(trigger, data.distance_mm);
}

void app_main(void)
{
    ESP_ERROR_CHECK(relay_init());
    ESP_LOGI(TAG, "Relay ready: GPIO7, high-level trigger, initial state OFF");

    ESP_ERROR_CHECK(servo_init());
    ESP_ERROR_CHECK(servo_stop_pwm());
    ESP_LOGI(TAG, "Servo ready: GPIO4, PWM stopped until relay power is ON");

    ESP_ERROR_CHECK(hc_sr04_init());
    ESP_LOGI(TAG, "HC-SR04 ready: TRIG GPIO5, ECHO GPIO6");

    vl53l0x_handle_t tof_1 = sensor_init(
        "TOF 1", I2C_NUM_0, TOF_1_SDA_PIN, TOF_1_SCL_PIN, true);
    vl53l0x_handle_t tof_2 = sensor_init(
        "TOF 2", I2C_NUM_1, TOF_2_SDA_PIN, TOF_2_SCL_PIN, false);
    ESP_LOGI(TAG, "Both TOF sensors ready; trigger distance is less than 101 mm");
    ESP_LOGI(TAG, "HC-SR04 trigger distance is less than 65 mm");
    ESP_LOGI(TAG, "Relay and servo sequence starts only when all three sensors are active");

    while (true) {
        const uint32_t current_ms = now_ms();
        update_output_sequence(current_ms);

        if (current_ms - last_hc_sr04_measurement_ms >= HC_SR04_MEASUREMENT_INTERVAL_MS) {
            last_hc_sr04_measurement_ms = current_ms;
            uint32_t distance_mm = 0;
            if (hc_sr04_read_distance_mm(&distance_mm)) {
                ESP_LOGI(TAG, "HC-SR04 distance: %u mm", (unsigned)distance_mm);
                process_distance(&hc_sr04_trigger, distance_mm);
            } else {
                invalidate_trigger(&hc_sr04_trigger);
                ESP_LOGW(TAG, "HC-SR04 echo timeout; check wiring or target range");
            }
        }

        measure_tof(tof_1, &tof_1_trigger);
        measure_tof(tof_2, &tof_2_trigger);

        vTaskDelay(pdMS_TO_TICKS(MEASUREMENT_INTERVAL_MS));
    }
}
