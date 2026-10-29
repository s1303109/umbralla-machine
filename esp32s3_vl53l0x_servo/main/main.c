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
#include "lcd_display.h"
#include "vl53l0x.h"

static const char *TAG = "TOF_BLOWER_LCD";

#define TOF_1_SDA_PIN GPIO_NUM_8
#define TOF_1_SCL_PIN GPIO_NUM_9
#define TOF_1_XSHUT_PIN GPIO_NUM_10
#define TOF_2_SDA_PIN GPIO_NUM_11
#define TOF_2_SCL_PIN GPIO_NUM_12
#define HC_SR04_TRIG_PIN GPIO_NUM_5
#define HC_SR04_ECHO_PIN GPIO_NUM_6
#define RELAY_PIN GPIO_NUM_7
// HIGH drives the external NPN interface; K2 itself is configured for LOW trigger.
#define MOTOR_RELAY_PIN GPIO_NUM_2
#define SERVO_SIGNAL_PIN GPIO_NUM_1
#define TOF_I2C_ADDRESS 0x29U

#define RELAY_ON_LEVEL 1
#define RELAY_OFF_LEVEL 0

// Preserve the thresholds from the previously flashed blower firmware.
#define TOF_TRIGGER_DISTANCE_MM 101U
#define HC_SR04_TRIGGER_DISTANCE_MM 65U
#define REQUIRED_START_CYCLES 3U
#define MEASUREMENT_INTERVAL_MS 50U
#define HC_SR04_ECHO_TIMEOUT_US 30000LL

// Identification test only: these pulses do not specify an RPM or an angle.
#define SERVO_PWM_FREQUENCY_HZ 50U
#define SERVO_PWM_PERIOD_US 20000U
#define SERVO_PWM_RESOLUTION_BITS 14U
#define SERVO_NEUTRAL_PULSE_US 1500U
#define SERVO_TEST_PULSE_US 1600U
#define SERVO_POWER_SETTLE_US 100000LL
#define SERVO_NEUTRAL_HOLD_US 500000LL

_Static_assert(SERVO_SIGNAL_PIN != MOTOR_RELAY_PIN &&
               SERVO_SIGNAL_PIN != RELAY_PIN,
               "Servo signal and relay GPIOs must be different");
_Static_assert(SERVO_NEUTRAL_PULSE_US >= 1000U &&
               SERVO_NEUTRAL_PULSE_US <= 2000U &&
               SERVO_TEST_PULSE_US >= 1000U &&
               SERVO_TEST_PULSE_US <= 2000U,
               "Keep identification pulses within the initial test range");

typedef struct {
    const char *name;
    uint32_t distance_mm;
    uint32_t threshold_mm;
    bool valid;
    bool active;
} sensor_reading_t;

static bool relay_enabled;
static uint8_t all_active_count;

static sensor_reading_t tof_1_reading = {
    .name = "TOF 1",
    .threshold_mm = TOF_TRIGGER_DISTANCE_MM,
};
static sensor_reading_t tof_2_reading = {
    .name = "TOF 2",
    .threshold_mm = TOF_TRIGGER_DISTANCE_MM,
};
static sensor_reading_t ultrasonic_reading = {
    .name = "HC-SR04",
    .threshold_mm = HC_SR04_TRIGGER_DISTANCE_MM,
};

typedef enum {
    SERVO_TEST_OFF,
    SERVO_TEST_POWER_WAIT,
    SERVO_TEST_NEUTRAL,
    SERVO_TEST_RUNNING,
} servo_test_phase_t;

static bool servo_pwm_ready;
static servo_test_phase_t servo_test_phase;
static int64_t servo_phase_deadline_us;

static esp_err_t servo_signal_off(void)
{
    servo_test_phase = SERVO_TEST_OFF;
    if (!servo_pwm_ready) {
        return ESP_OK;
    }
    // No pulses into the unpowered servo; K2 opens its V+ supply separately.
    return ledc_stop(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, 0);
}

static esp_err_t servo_write_pulse_us(uint32_t pulse_us)
{
    if (pulse_us < 1000U || pulse_us > 2000U) {
        return ESP_ERR_INVALID_ARG;
    }
    const uint32_t duty =
        (pulse_us * (1UL << SERVO_PWM_RESOLUTION_BITS) +
         SERVO_PWM_PERIOD_US / 2U) / SERVO_PWM_PERIOD_US;
    ESP_RETURN_ON_ERROR(
        ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, duty),
        TAG, "Failed to set servo pulse");
    return ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);
}

static esp_err_t servo_signal_init(void)
{
    ESP_RETURN_ON_ERROR(gpio_set_level(SERVO_SIGNAL_PIN, 0),
                        TAG, "Failed to preset servo signal LOW");
    const gpio_config_t signal_config = {
        .pin_bit_mask = 1ULL << SERVO_SIGNAL_PIN,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_ENABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_RETURN_ON_ERROR(gpio_config(&signal_config),
                        TAG, "Failed to configure servo GPIO");
    const ledc_timer_config_t timer_config = {
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .duty_resolution = LEDC_TIMER_14_BIT,
        .timer_num = LEDC_TIMER_0,
        .freq_hz = SERVO_PWM_FREQUENCY_HZ,
        .clk_cfg = LEDC_AUTO_CLK,
    };
    ESP_RETURN_ON_ERROR(ledc_timer_config(&timer_config),
                        TAG, "Failed to configure servo timer");
    const ledc_channel_config_t channel_config = {
        .gpio_num = SERVO_SIGNAL_PIN,
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .channel = LEDC_CHANNEL_0,
        .intr_type = LEDC_INTR_DISABLE,
        .timer_sel = LEDC_TIMER_0,
        .duty = 0,
        .hpoint = 0,
    };
    ESP_RETURN_ON_ERROR(ledc_channel_config(&channel_config),
                        TAG, "Failed to configure servo channel");
    servo_pwm_ready = true;
    return servo_signal_off();
}

static void servo_schedule_start(void)
{
    if (servo_pwm_ready && servo_test_phase == SERVO_TEST_OFF) {
        // Nonblocking: sensor checks continue while the relay/supply settles.
        servo_test_phase = SERVO_TEST_POWER_WAIT;
        servo_phase_deadline_us = esp_timer_get_time() + SERVO_POWER_SETTLE_US;
    }
}

static esp_err_t servo_service(void)
{
    const int64_t now_us = esp_timer_get_time();
    if (servo_test_phase == SERVO_TEST_POWER_WAIT &&
        now_us >= servo_phase_deadline_us) {
        ESP_RETURN_ON_ERROR(servo_write_pulse_us(SERVO_NEUTRAL_PULSE_US),
                            TAG, "Failed to send initial servo pulse");
        servo_test_phase = SERVO_TEST_NEUTRAL;
        servo_phase_deadline_us = now_us + SERVO_NEUTRAL_HOLD_US;
        ESP_LOGI(TAG, "Servo test: GPIO%d, %u us initial pulse; a positional servo may move",
                 (int)SERVO_SIGNAL_PIN, (unsigned)SERVO_NEUTRAL_PULSE_US);
    } else if (servo_test_phase == SERVO_TEST_NEUTRAL &&
               now_us >= servo_phase_deadline_us) {
        ESP_RETURN_ON_ERROR(servo_write_pulse_us(SERVO_TEST_PULSE_US),
                            TAG, "Failed to send servo identification pulse");
        servo_test_phase = SERVO_TEST_RUNNING;
        ESP_LOGI(TAG, "Servo test: holding %u us; observe position versus continuous rotation; RPM uncalibrated",
                 (unsigned)SERVO_TEST_PULSE_US);
    }
    return ESP_OK;
}

static esp_err_t relay_set_enabled(bool enabled)
{
    // Stop the control signal before removing servo power.
    esp_err_t result = enabled ? ESP_OK : servo_signal_off();
    if (result == ESP_OK) {
        result = gpio_set_level(
            RELAY_PIN, enabled ? RELAY_ON_LEVEL : RELAY_OFF_LEVEL);
    }
    if (result == ESP_OK) {
        result = gpio_set_level(
            MOTOR_RELAY_PIN, enabled ? RELAY_ON_LEVEL : RELAY_OFF_LEVEL);
    }
    if (result != ESP_OK) {
        // Best effort: release both loads if either output cannot be written.
        servo_signal_off();
        gpio_set_level(RELAY_PIN, RELAY_OFF_LEVEL);
        gpio_set_level(MOTOR_RELAY_PIN, RELAY_OFF_LEVEL);
        relay_enabled = false;
        return result;
    }
    if (enabled) {
        servo_schedule_start();
    }
    if (relay_enabled != enabled) {
        relay_enabled = enabled;
        ESP_LOGI(
            TAG,
            "Blower relay %s",
            enabled ? "ON (COM-NO closed)" : "OFF (COM-NO open)");
        ESP_LOGI(TAG, "Auxiliary power relay %s (GPIO%d via NPN, K2 LOW trigger)",
                 enabled ? "ON" : "OFF", (int)MOTOR_RELAY_PIN);
    }
    return result;
}

static esp_err_t relay_init(void)
{
    ESP_RETURN_ON_ERROR(
        gpio_set_level(RELAY_PIN, RELAY_OFF_LEVEL),
        TAG,
        "Failed to preset relay OFF");
    ESP_RETURN_ON_ERROR(
        gpio_set_level(MOTOR_RELAY_PIN, RELAY_OFF_LEVEL),
        TAG,
        "Failed to preset motor relay OFF");
    const gpio_config_t relay_config = {
        .pin_bit_mask = (1ULL << RELAY_PIN) | (1ULL << MOTOR_RELAY_PIN),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_ENABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_RETURN_ON_ERROR(
        gpio_config(&relay_config),
        TAG,
        "Failed to configure relay GPIO");
    return relay_set_enabled(false);
}

static void publish_display_status(void)
{
    const lcd_display_status_t status = {
        .blower_running = relay_enabled,
        .tof_1_active = tof_1_reading.active,
        .tof_2_active = tof_2_reading.active,
        .ultrasonic_active = ultrasonic_reading.active,
        .tof_1_valid = tof_1_reading.valid,
        .tof_2_valid = tof_2_reading.valid,
        .ultrasonic_valid = ultrasonic_reading.valid,
        .tof_1_distance_mm = tof_1_reading.distance_mm,
        .tof_2_distance_mm = tof_2_reading.distance_mm,
        .ultrasonic_distance_mm = ultrasonic_reading.distance_mm,
    };
    lcd_display_update(&status);
}

static void stop_blower_immediately(const char *reason)
{
    all_active_count = 0;
    if (relay_enabled) {
        ESP_LOGW(TAG, "Stopping blower: %s", reason);
    }
    if (relay_set_enabled(false) != ESP_OK) {
        ESP_LOGE(TAG, "Failed to turn blower relay OFF");
    }
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
    ESP_RETURN_ON_ERROR(
        gpio_config(&trigger_config),
        TAG,
        "Failed to configure HC-SR04 TRIG");

    const gpio_config_t echo_config = {
        .pin_bit_mask = 1ULL << HC_SR04_ECHO_PIN,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_RETURN_ON_ERROR(
        gpio_config(&echo_config),
        TAG,
        "Failed to configure HC-SR04 ECHO");
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

    const uint32_t echo_duration_us =
        (uint32_t)(esp_timer_get_time() - echo_started_us);
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
        ESP_LOGI(TAG, "Slow I2C test: register 0xC0 = 0x%02X", model_id);
        return true;
    }
    ESP_LOGW(TAG, "Slow 10 kHz I2C test failed: %s", esp_err_to_name(result));
    return false;
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
            "%s I2C levels: SDA(GPIO%d)=%d SCL(GPIO%d)=%d",
            name,
            (int)sda_pin,
            sda_level,
            (int)scl_pin,
            scl_level);
        if (sda_level == 1 && scl_level == 1) {
            read_sensor_id_slow(bus);
        } else {
            ESP_LOGE(TAG, "%s I2C bus stuck LOW; check power and wiring", name);
        }
        ESP_LOGW(TAG, "%s not found at address 0x29", name);
        stop_blower_immediately("TOF sensor unavailable");
        publish_display_status();
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

static void update_reading(
    sensor_reading_t *reading,
    bool valid,
    uint32_t distance_mm)
{
    reading->valid = valid;
    reading->distance_mm = valid ? distance_mm : 0;
    reading->active = valid && distance_mm < reading->threshold_mm;

    if (!reading->active) {
        stop_blower_immediately(
            valid ? "sensor left threshold" : "invalid sensor reading");
    }
}

static void measure_tof(
    vl53l0x_handle_t sensor,
    sensor_reading_t *reading)
{
    vl53l0x_data_t data = {0};
    const esp_err_t result = vl53l0x_single_measure(sensor, &data);
    const bool valid = result == ESP_OK && data.valid && data.distance_mm != 0;
    update_reading(reading, valid, data.distance_mm);

    if (!valid) {
        ESP_LOGW(
            TAG,
            "%s invalid: error=%s status=%u",
            reading->name,
            esp_err_to_name(result),
            (unsigned)data.range_status);
    }
}

static void evaluate_all_sensors(void)
{
    const bool all_active =
        tof_1_reading.active &&
        tof_2_reading.active &&
        ultrasonic_reading.active;

    if (all_active) {
        if (all_active_count < REQUIRED_START_CYCLES) {
            ++all_active_count;
            ESP_LOGI(
                TAG,
                "All sensors below threshold: cycle %u/%u",
                (unsigned)all_active_count,
                (unsigned)REQUIRED_START_CYCLES);
        }
        if (all_active_count >= REQUIRED_START_CYCLES && !relay_enabled) {
            if (relay_set_enabled(true) != ESP_OK) {
                ESP_LOGE(TAG, "Failed to turn blower relay ON");
            }
        }
    } else {
        stop_blower_immediately("not all three sensors are below threshold");
    }

    if (servo_service() != ESP_OK) {
        stop_blower_immediately("servo PWM error");
    }

    ESP_LOGI(
        TAG,
        "TOF1=%s%u mm TOF2=%s%u mm HC=%s%u mm | Relay=%s",
        tof_1_reading.valid ? "" : "INVALID/",
        (unsigned)tof_1_reading.distance_mm,
        tof_2_reading.valid ? "" : "INVALID/",
        (unsigned)tof_2_reading.distance_mm,
        ultrasonic_reading.valid ? "" : "INVALID/",
        (unsigned)ultrasonic_reading.distance_mm,
        relay_enabled ? "ON" : "OFF");

    publish_display_status();
}

void app_main(void)
{
    ESP_ERROR_CHECK(relay_init());
    ESP_LOGI(TAG, "Relay ready: GPIO7, high-level trigger, initial state OFF");
    ESP_LOGI(TAG, "Motor relay ready: GPIO%d, active-high NPN drive, K2 LOW trigger, initial state OFF",
             (int)MOTOR_RELAY_PIN);
    ESP_ERROR_CHECK(servo_signal_init());
    ESP_LOGI(TAG, "Servo signal ready: GPIO%d, %u Hz, signal LOW until sensors enable K2; identification test only",
             (int)SERVO_SIGNAL_PIN, (unsigned)SERVO_PWM_FREQUENCY_HZ);

    ESP_ERROR_CHECK(lcd_display_start());
    publish_display_status();

    ESP_ERROR_CHECK(hc_sr04_init());
    ESP_LOGI(TAG, "HC-SR04 ready: TRIG GPIO5, ECHO GPIO6");

    vl53l0x_handle_t tof_1 = sensor_init(
        "TOF 1", I2C_NUM_0, TOF_1_SDA_PIN, TOF_1_SCL_PIN, true);
    vl53l0x_handle_t tof_2 = sensor_init(
        "TOF 2", I2C_NUM_1, TOF_2_SDA_PIN, TOF_2_SCL_PIN, false);

    ESP_LOGI(TAG, "TOF thresholds: both less than %u mm", TOF_TRIGGER_DISTANCE_MM);
    ESP_LOGI(TAG, "HC-SR04 threshold: less than %u mm", HC_SR04_TRIGGER_DISTANCE_MM);
    ESP_LOGI(
        TAG,
        "Start requires all three sensors for %u consecutive cycles",
        REQUIRED_START_CYCLES);
    ESP_LOGI(TAG, "Stop is immediate when any sensor clears or becomes invalid");

    while (true) {
        measure_tof(tof_1, &tof_1_reading);
        measure_tof(tof_2, &tof_2_reading);

        uint32_t ultrasonic_distance_mm = 0;
        const bool ultrasonic_valid =
            hc_sr04_read_distance_mm(&ultrasonic_distance_mm);
        update_reading(
            &ultrasonic_reading,
            ultrasonic_valid,
            ultrasonic_distance_mm);
        if (!ultrasonic_valid) {
            ESP_LOGW(TAG, "HC-SR04 echo timeout; check wiring or target range");
        }

        evaluate_all_sensors();
        vTaskDelay(pdMS_TO_TICKS(MEASUREMENT_INTERVAL_MS));
    }
}
