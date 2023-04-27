#ifndef SENSOR_HPP
#define SENSOR_HPP

#include <Arduino.h>

class Sensor {
private:
  double value = 0;
  uint32_t value_ts_ms = 0;
  double prev_value = 0;
  uint32_t prev_value_ts_ms = 0;
  double integrator = 0;
  uint32_t prev_cycle_num = 0;

  virtual double get_value() = 0;

protected:
  const uint32_t freq_hz;

public:
  static uint8_t cycle_num;  // Overflow will happen but this doesn't concern since this number still offers the opportunity to compare cycles

  Sensor(uint32_t freq_hz = 0);

  double operator()();
  double derivative();
  double integral();
};

#endif
