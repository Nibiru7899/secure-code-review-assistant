#pragma once
#include "sensor.h"
int calculatePressure(const Sensor* sensor);
int safePressure(const Sensor* sensor);
int clampPressure(int value);
