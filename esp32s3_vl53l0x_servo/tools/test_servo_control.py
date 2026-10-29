"""Host checks of the actual main.c servo/relay state machine with fake I/O.

Run: python tools/test_servo_control.py
No hardware is opened. Sensor and controller functions are compiled from main.c;
the mock provides GPIO, LEDC, and a controllable clock, not a second controller.
"""

from pathlib import Path
import re
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'main/main.c').read_text()


def function(name):
    match = re.search(r'^static (?:void|esp_err_t) ' + name + r'\(', source, re.M)
    if match is None:
        raise ValueError(name)
    opening = source.index('{', match.start())
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[match.start():end]


prefix = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef int esp_err_t;
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_INVALID_ARG 1
#define GPIO_NUM_1 1
#define GPIO_NUM_2 2
#define GPIO_NUM_5 5
#define GPIO_NUM_6 6
#define GPIO_NUM_7 7
#define GPIO_NUM_8 8
#define GPIO_NUM_9 9
#define GPIO_NUM_10 10
#define GPIO_NUM_11 11
#define GPIO_NUM_12 12
#define GPIO_MODE_OUTPUT 1
#define GPIO_PULLUP_DISABLE 0
#define GPIO_PULLDOWN_ENABLE 1
#define GPIO_INTR_DISABLE 0
#define LEDC_LOW_SPEED_MODE 0
#define LEDC_CHANNEL_0 0
#define LEDC_TIMER_0 0
#define LEDC_TIMER_14_BIT 14
#define LEDC_AUTO_CLK 0
#define LEDC_INTR_DISABLE 0
static const char *TAG = "test";
static void discard_log(const char *tag, const char *fmt, ...) {(void)tag;(void)fmt;}
#define ESP_LOGI(...) discard_log(__VA_ARGS__)
#define ESP_LOGW(...) discard_log(__VA_ARGS__)
#define ESP_LOGE(...) discard_log(__VA_ARGS__)
#define ESP_RETURN_ON_ERROR(call, ...) do {int e=(call);if(e!=ESP_OK)return e;}while(0)
typedef struct {uint64_t pin_bit_mask;int mode,pull_up_en,pull_down_en,intr_type;} gpio_config_t;
typedef struct {int speed_mode,duty_resolution,timer_num;uint32_t freq_hz;int clk_cfg;} ledc_timer_config_t;
typedef struct {int gpio_num,speed_mode,channel,intr_type,timer_sel;uint32_t duty;int hpoint;} ledc_channel_config_t;
static int pins[49],fail_power,fail_set,fail_update,pulse_writes;
static bool pwm_active;
static uint32_t staged_duty,active_duty;
static int64_t clock_us;
static char events[256];
static unsigned event_count;
static void event(char value) {assert(event_count<sizeof(events)-1);events[event_count++]=value;events[event_count]=0;}
static esp_err_t gpio_set_level(int pin,int level) {
    if(pin==2 && level && fail_power){fail_power=0;return ESP_FAIL;}
    pins[pin]=level;if(pin==2 && !level)event('P');return ESP_OK;
}
static esp_err_t gpio_config(const gpio_config_t *c) {(void)c;return ESP_OK;}
static esp_err_t ledc_timer_config(const ledc_timer_config_t *c) {
    assert(c->freq_hz==50 && c->duty_resolution==14);return ESP_OK;
}
static esp_err_t ledc_channel_config(const ledc_channel_config_t *c) {
    assert(c->gpio_num==1 && c->duty==0);pwm_active=false;return ESP_OK;
}
static esp_err_t ledc_stop(int mode,int channel,int idle) {
    (void)mode;(void)channel;assert(idle==0);pwm_active=false;pins[1]=0;event('S');return ESP_OK;
}
static esp_err_t ledc_set_duty(int mode,int channel,uint32_t duty) {
    (void)mode;(void)channel;if(fail_set){fail_set=0;return ESP_FAIL;}
    staged_duty=duty;return ESP_OK;
}
static esp_err_t ledc_update_duty(int mode,int channel) {
    (void)mode;(void)channel;if(fail_update){fail_update=0;return ESP_FAIL;}
    active_duty=staged_duty;pwm_active=true;++pulse_writes;return ESP_OK;
}
static int64_t esp_timer_get_time(void) {return clock_us;}
static void publish_display_status(void) {}
'''

checks = r'''
static void initialize(void) {
    memset(pins,0,sizeof(pins));fail_power=fail_set=fail_update=pulse_writes=0;
    event_count=0;events[0]=0;clock_us=0;pwm_active=false;
    relay_enabled=false;all_active_count=0;servo_pwm_ready=false;
    servo_test_phase=SERVO_TEST_OFF;servo_phase_deadline_us=0;
    assert(relay_init()==ESP_OK);assert(servo_signal_init()==ESP_OK);
    assert(!pins[7] && !pins[2] && !pwm_active && !pins[1]);
    update_reading(&tof_1_reading,true,50);
    update_reading(&tof_2_reading,true,50);
    update_reading(&ultrasonic_reading,true,30);
}
static void off(void) {
    assert(!relay_enabled && !pins[7] && !pins[2] && !pwm_active);
    assert(servo_test_phase==SERVO_TEST_OFF && all_active_count==0);
}
static void activate(void) {
    evaluate_all_sensors();assert(!relay_enabled);
    evaluate_all_sensors();assert(!relay_enabled);
    evaluate_all_sensors();assert(relay_enabled && pins[7] && pins[2]);
}
static void running(void) {
    activate();clock_us=100000;evaluate_all_sensors();
    clock_us=600000;evaluate_all_sensors();
    assert(pwm_active && active_duty==1311 && servo_test_phase==SERVO_TEST_RUNNING);
}
int main(void) {
    initialize();activate();assert(!pwm_active);
    clock_us=99999;evaluate_all_sensors();assert(!pwm_active);
    clock_us=100000;evaluate_all_sensors();assert(pwm_active && active_duty==1229);
    clock_us=599999;evaluate_all_sensors();assert(active_duty==1229);
    clock_us=600000;evaluate_all_sensors();assert(active_duty==1311);
    clock_us=900000;assert(relay_set_enabled(true)==ESP_OK);
    evaluate_all_sensors();assert(pulse_writes==2);
    event_count=0;events[0]=0;update_reading(&tof_1_reading,false,0);off();
    assert(events[0]=='S' && strchr(events,'P')>events);
    puts("PASS: boot OFF, three-cycle start, power settling, initial/run pulses, stop before power-off");

    sensor_reading_t *readings[]={&tof_1_reading,&tof_2_reading,&ultrasonic_reading};
    for(unsigned i=0;i<3;++i){
        initialize();running();update_reading(readings[i],true,readings[i]->threshold_mm);off();
        initialize();running();update_reading(readings[i],false,50);off();
        initialize();update_reading(readings[i],true,readings[i]->threshold_mm);
        for(int k=0;k<4;++k) {
            evaluate_all_sensors();
        }
        off();
    }
    puts("PASS: each sensor stops immediately on invalid data or threshold equality and cannot start there");

    initialize();activate();update_reading(&ultrasonic_reading,false,0);off();
    clock_us=1000000;evaluate_all_sensors();off();assert(pulse_writes==0);
    initialize();activate();clock_us=100000;evaluate_all_sensors();
    update_reading(&tof_2_reading,false,0);off();
    clock_us=1000000;evaluate_all_sensors();off();assert(pulse_writes==1);
    puts("PASS: cancellation during power settling and initial pulse prevents a later run pulse");

    initialize();fail_power=1;
    evaluate_all_sensors();evaluate_all_sensors();evaluate_all_sensors();
    assert(!relay_enabled && !pins[7] && !pins[2] && !pwm_active);
    assert(servo_test_phase==SERVO_TEST_OFF);
    initialize();activate();clock_us=100000;fail_set=1;evaluate_all_sensors();off();
    initialize();activate();clock_us=100000;evaluate_all_sensors();
    clock_us=600000;fail_update=1;evaluate_all_sensors();off();
    puts("PASS: relay write, PWM duty, and PWM update failures release both relays and stop signal");

    initialize();assert(servo_write_pulse_us(999)==ESP_ERR_INVALID_ARG);
    assert(servo_write_pulse_us(2001)==ESP_ERR_INVALID_ARG);assert(!pwm_active);
    puts("PASS: out-of-range test pulses rejected");
    return 0;
}
'''

controller = source[source.index('#define TOF_1_SDA_PIN'):
                    source.index('static void publish_display_status')]
with tempfile.TemporaryDirectory(prefix='servo-control-check-') as directory:
    path = Path(directory)
    c_file = path / 'servo_check.c'
    c_file.write_text(prefix + controller + '\n' +
                      '\n'.join(function(name) for name in
                                ['stop_blower_immediately', 'update_reading',
                                 'evaluate_all_sensors']) + checks)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    str(c_file), '-o', str(path / 'servo_check')], check=True)
    subprocess.run([str(path / 'servo_check')], check=True)
