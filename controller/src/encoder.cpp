#include "Arduino.h"
#include "encoder.h"

volatile uint8_t previous_cha = 0;
volatile int32_t motor_pos = 0;
void update_motor_position() {
  uint8_t current_cha = digitalRead(ENC_PIN_CHA);  // Read the current state of CHA

  // If last and current state of CHA are different, then pulse occurred
  // React to only 1 state change to avoid double count
  if (current_cha != previous_cha && current_cha == 1) {
    if (digitalRead(ENC_PIN_CHB) == current_cha) {
      // Encoder is rotating clockwise
      motor_pos++;
    } else {
      // Encoder is rotating counter clockwise
      motor_pos--;
    }
  }
  previous_cha = current_cha;
}

Encoder::Encoder(String name, uint8_t cha_pin, uint8_t chb_pin, void (*isr)(), volatile int32_t& motor_pos, uint32_t freq_hz)
  : Sensor(name, freq_hz), cha_pin(cha_pin), chb_pin(chb_pin), isr(isr), motor_pos(motor_pos) {}

void Encoder::setup() {
  pinMode(cha_pin, INPUT);
  pinMode(chb_pin, INPUT);
  attachInterrupt(digitalPinToInterrupt(cha_pin), isr, CHANGE);
  attachInterrupt(digitalPinToInterrupt(chb_pin), isr, CHANGE);
  reset();
}

// Reset encoder values
void Encoder::reset() {
  this->motor_pos = 0;
}

int32_t Encoder::get_value() {
  return this->motor_pos;  // A template type cannot be volatile or a reference so this is necessary
}
