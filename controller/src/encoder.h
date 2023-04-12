#ifndef ENCODER_H
#define ENCODER_H

#include <Arduino.h>
#include "sensor.h"

#define ENC_PIN_CHA PD2
#define ENC_PIN_CHB PD3

extern volatile int32_t motor_pos;   // Temporary value for position control
void update_motor_position();

class Encoder : public Sensor<int32_t> {
private:
  uint8_t cha_pin, chb_pin;
  void (*isr)();
  volatile int32_t& motor_pos;

  virtual int32_t get_value() override;

public:
  Encoder(String name, uint8_t cha_pin, uint8_t chb_pin, void (*isr)(), volatile int32_t& motor_pos, uint32_t freq_hz);

  void setup();
  virtual void reset() override;
};

#endif