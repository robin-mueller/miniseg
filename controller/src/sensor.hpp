#ifndef SENSOR_HPP
#define SENSOR_HPP

#include <Arduino.h>

template<class T>
class Sensor {
private:
  uint32_t last_update_ms = 0;
  T last_value = 0;

  virtual T get_value() = 0;

protected:
  const uint32_t freq_hz;

public:
  Sensor(uint32_t freq_hz = 0);

  T operator()();
  double derivative() const;
};

// Sensor abstract class.
// Parameter 'freq_hz' defines the update frequency. If set to 0 updates every call.
template<class T>
Sensor<T>::Sensor(uint32_t freq_hz)
  : freq_hz(freq_hz) {}

template<class T>
T Sensor<T>::operator()() {
  if (freq_hz == 0 || millis() - last_update_ms >= 1000 / freq_hz) {
    last_value = get_value();
    last_update_ms = millis();
  }
  return last_value;
};

template<class T>
double Sensor<T>::derivative() const {
  return ((double)get_value() - last_value) / (millis() - last_update_ms);
}

#endif
