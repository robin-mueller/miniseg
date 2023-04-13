#include <stdint.h>
#ifndef SENSOR_HPP
#define SENSOR_HPP

#include <Arduino.h>

class Sensor {
private:
  double value = 0;
  uint32_t value_ts_ms = 0;
  double prev_value = 0;
  uint32_t prev_value_ts_ms = 0;
  uint64_t prev_cycle_num = 0;
  double transformation;

  virtual double get_value() = 0;

protected:
  const uint32_t freq_hz;

public:
  static uint64_t cycle_num;

  Sensor(double transformation = 1, uint32_t freq_hz = 0);

  double operator()();
  double derivative();
};

#endif
