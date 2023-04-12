#ifndef SENSOR_H
#define SENSOR_H

#include <Arduino.h>

template<class T>
class Sensor {
private:
  const String name;
  uint32_t last_update_ms = 0;
  T last_value = 0;

  virtual T get_value() = 0;

public:
  const uint32_t freq_hz;

  Sensor(String name, uint32_t freq_hz);

  T operator()();
  double derivative() const {
    return derivative;
  }
  const String get_name() const {
    return name;
  }
  virtual void reset(){};
};

template<class T>
Sensor<T>::Sensor(String name, uint32_t freq_hz)
  : name(name), freq_hz(freq_hz) {}

template<class T>
T Sensor<T>::operator()() {
  if (millis() - last_update_ms >= 1000 / freq_hz) {
    last_value = get_value();
    last_update_ms = millis();
  }
  return last_value;
};

#endif