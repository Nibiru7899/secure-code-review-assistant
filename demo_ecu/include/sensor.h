#pragma once
struct Sensor { int value; bool connected; };
Sensor* readSensor();
int readSensorValue(const Sensor* sensor);
int safeSensorValue(const Sensor* sensor);
