#include <Arduino.h>
#include <Wire.h>
#include <VL53L0X.h>
#include <ESP32Servo.h>

// ESP32-S3 pin assignments
constexpr uint8_t TOF_SDA_PIN = 8;
constexpr uint8_t TOF_SCL_PIN = 9;
constexpr uint8_t TOF_XSHUT_PIN = 10;
constexpr uint8_t SERVO_PIN = 4;

// VL53L0X GPIO1 is not used and should remain unconnected.

// Distance decision settings: 10.1 cm = 101 mm
constexpr uint16_t TRIGGER_DISTANCE_MM = 101;
constexpr uint8_t REQUIRED_CONSECUTIVE_READINGS = 3;
constexpr uint32_t MEASUREMENT_INTERVAL_MS = 50;
constexpr uint16_t SENSOR_TIMEOUT_MS = 100;

// Servo motion settings
constexpr uint8_t SERVO_REST_ANGLE = 10;
constexpr uint8_t SERVO_ACTION_ANGLE = 90;
constexpr uint32_t SERVO_TRAVEL_TIME_MS = 500;

VL53L0X tofSensor;
Servo servoMotor;

enum class MotionState : uint8_t {
  Armed,
  MovingToAction,
  Holding,
  Returning
};

MotionState motionState = MotionState::Armed;

bool sensorReady = false;
uint8_t belowThresholdCount = 0;
uint8_t clearThresholdCount = 0;
uint32_t stateStartedAtMs = 0;
uint32_t lastMeasurementAtMs = 0;
uint32_t lastSensorInitAttemptAtMs = 0;

const char* motionStateName(MotionState state) {
  switch (state) {
    case MotionState::Armed:
      return "ARMED";
    case MotionState::MovingToAction:
      return "MOVING_TO_90";
    case MotionState::Holding:
      return "HOLDING_90";
    case MotionState::Returning:
      return "RETURNING_TO_10";
  }

  return "UNKNOWN";
}

void resetSensorHardware() {
  digitalWrite(TOF_XSHUT_PIN, LOW);
  delay(10);
  digitalWrite(TOF_XSHUT_PIN, HIGH);
  delay(10);
}

bool initializeSensor() {
  resetSensorHardware();
  tofSensor.setTimeout(SENSOR_TIMEOUT_MS);

  if (!tofSensor.init()) {
    return false;
  }

  // A 33 ms timing budget is suitable for measurements every 50 ms.
  tofSensor.setMeasurementTimingBudget(33000);
  tofSensor.startContinuous(MEASUREMENT_INTERVAL_MS);
  return true;
}

void triggerServo(uint32_t nowMs) {
  belowThresholdCount = 0;
  clearThresholdCount = 0;
  servoMotor.write(SERVO_ACTION_ANGLE);
  motionState = MotionState::MovingToAction;
  stateStartedAtMs = nowMs;
  Serial.println("Trigger: servo moving from 10 to 90 degrees");
}

void updateServoMotion(uint32_t nowMs) {
  switch (motionState) {
    case MotionState::Armed:
      break;

    case MotionState::MovingToAction:
      if (nowMs - stateStartedAtMs >= SERVO_TRAVEL_TIME_MS) {
        motionState = MotionState::Holding;
        stateStartedAtMs = nowMs;
        Serial.println("Servo at 90 degrees; holding until the hand moves away");
      }
      break;

    case MotionState::Holding:
      break;

    case MotionState::Returning:
      if (nowMs - stateStartedAtMs >= SERVO_TRAVEL_TIME_MS) {
        motionState = MotionState::Armed;
        stateStartedAtMs = nowMs;
        belowThresholdCount = 0;
        clearThresholdCount = 0;
        Serial.println("Servo at 10 degrees; system armed again");
      }
      break;
  }
}

void processDistance(uint16_t distanceMm, uint32_t nowMs) {
  if (motionState == MotionState::Armed) {
    clearThresholdCount = 0;

    if (distanceMm < TRIGGER_DISTANCE_MM) {
      if (belowThresholdCount < REQUIRED_CONSECUTIVE_READINGS) {
        ++belowThresholdCount;
      }

      if (belowThresholdCount >= REQUIRED_CONSECUTIVE_READINGS) {
        triggerServo(nowMs);
      }
    } else {
      belowThresholdCount = 0;
    }
  } else if (
    motionState == MotionState::MovingToAction ||
    motionState == MotionState::Holding
  ) {
    belowThresholdCount = 0;

    if (distanceMm >= TRIGGER_DISTANCE_MM) {
      if (clearThresholdCount < REQUIRED_CONSECUTIVE_READINGS) {
        ++clearThresholdCount;
      }

      if (clearThresholdCount >= REQUIRED_CONSECUTIVE_READINGS) {
        clearThresholdCount = 0;
        servoMotor.write(SERVO_REST_ANGLE);
        motionState = MotionState::Returning;
        stateStartedAtMs = nowMs;
        Serial.println("Hand moved away; servo returning to 10 degrees");
      }
    } else {
      clearThresholdCount = 0;
    }
  } else {
    belowThresholdCount = 0;
    clearThresholdCount = 0;
  }
}

void readAndProcessDistance(uint32_t nowMs) {
  const uint16_t distanceMm = tofSensor.readRangeContinuousMillimeters();

  if (tofSensor.timeoutOccurred() || distanceMm == 0) {
    belowThresholdCount = 0;
    clearThresholdCount = 0;
    Serial.println("VL53L0X reading invalid; servo will not be triggered");
    return;
  }

  Serial.printf(
    "Distance: %u mm | State: %s\n",
    distanceMm,
    motionStateName(motionState)
  );

  processDistance(distanceMm, nowMs);
}

void setup() {
  Serial.begin(115200);

  pinMode(TOF_XSHUT_PIN, OUTPUT);
  digitalWrite(TOF_XSHUT_PIN, HIGH);

  Wire.begin(TOF_SDA_PIN, TOF_SCL_PIN);

  servoMotor.setPeriodHertz(50);
  servoMotor.attach(SERVO_PIN, 500, 2400);
  servoMotor.write(SERVO_REST_ANGLE);

  sensorReady = initializeSensor();
  lastSensorInitAttemptAtMs = millis();

  if (sensorReady) {
    Serial.println("VL53L0X ready; servo resting at 10 degrees");
  } else {
    Serial.println("VL53L0X initialization failed; servo remains at 10 degrees");
  }
}

void loop() {
  const uint32_t nowMs = millis();

  updateServoMotion(nowMs);

  if (!sensorReady) {
    if (nowMs - lastSensorInitAttemptAtMs >= 1000) {
      lastSensorInitAttemptAtMs = nowMs;
      sensorReady = initializeSensor();

      if (sensorReady) {
        Serial.println("VL53L0X connected; measurement started");
      } else {
        Serial.println("Retrying VL53L0X connection...");
      }
    }
    return;
  }

  if (nowMs - lastMeasurementAtMs >= MEASUREMENT_INTERVAL_MS) {
    lastMeasurementAtMs = nowMs;
    readAndProcessDistance(nowMs);
  }
}
