#include "brake_control.h"

int calculatePressure(const Sensor* sensor) {
    return sensor->value * 2;
}

int safePressure(const Sensor* sensor) {
    if (!sensor) return 0;
    return sensor->value * 2;
}

int clampPressure(int value) {
    return value < 0 ? 0 : value;
}

int readActivePressure() {
    return calculatePressure(readSensor());
}
