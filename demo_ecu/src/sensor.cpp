#include "sensor.h"

static Sensor activeSensor{42, true};

Sensor* readSensor() {
    return activeSensor.connected ? &activeSensor : nullptr;
}

int readSensorValue(const Sensor* sensor) {
    return sensor->value;
}

int safeSensorValue(const Sensor* sensor) {
    return sensor ? sensor->value : 0;
}

bool sensorConnected(const Sensor* sensor) {
    return sensor && sensor->connected;
}
