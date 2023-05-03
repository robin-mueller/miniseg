#include "Arduino.h"
#include "sensor.hpp"

uint8_t Sensor::cycle_num = 1;

// Sensor abstract class.
// Parameter 'freq_hz' defines the update frequency. If set to 0 updates every call.
Sensor::Sensor(uint32_t freq_hz)
  : freq_hz(freq_hz) {}

double Sensor::operator()() {
  uint32_t ts = micros();
  if (cycle_num != prev_cycle_num && (freq_hz == 0 || ts - prev_value_ts_us >= 1e6 / freq_hz)) {
    prev_value = value;
    value = get_value();
    prev_value_ts_us = value_ts_us;
    value_ts_us = ts;
    prev_cycle_num = cycle_num;
  }
  return value;
};

double Sensor::derivative() {
  return (operator()() - prev_value) / (value_ts_us - prev_value_ts_us) * 1e6;  // Backwards euler
}

double Sensor::integral() {
  double old_val = value;
  if (operator()() != old_val) integrator += operator()() * (value_ts_us - prev_value_ts_us) * 1e-6;  // Backwards euler
  return integrator;
}
