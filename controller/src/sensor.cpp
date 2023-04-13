#include "Arduino.h"
#include "sensor.hpp"

uint64_t Sensor::cycle_num = 0;

// Sensor abstract class.
// Parameter 'freq_hz' defines the update frequency. If set to 0 updates every call.
Sensor::Sensor(double transformation, uint32_t freq_hz)
  : transformation(transformation), freq_hz(freq_hz) {}

double Sensor::operator()() {
  uint32_t ts = millis();
  if (cycle_num != prev_cycle_num && (freq_hz == 0 || ts - prev_value_ts_ms >= 1000 / freq_hz)) {
    prev_value = value;
    value = transformation == 1 ? get_value() : transformation * get_value();
    prev_value_ts_ms = value_ts_ms;
    value_ts_ms = ts;
    prev_cycle_num = cycle_num;
  }
  return value;
};

double Sensor::derivative() {
  return (operator()() - prev_value) / (value_ts_ms - prev_value_ts_ms) * 1e3;
}
