#include <stdint.h>
#include <Arduino.h>
#include "encoder.hpp"

volatile int32_t enc_counter = 0;

void encoder_isr() {
  uint8_t curr_ab = 0;
  if (digitalRead(ENC_PIN_CHA)) curr_ab |= (1 << 0);  // Writing channel A bit
  if (digitalRead(ENC_PIN_CHB)) curr_ab |= (1 << 1);  // Writing channel B bit
  static uint8_t prev_ab = curr_ab;  // At initialization prev_ab is equal to curr_ab

  // Rene Sommer algorithm
  // Swap bits A and B according to https://www.codevscolor.com/c-program-swap-two-bits-of-number
  unsigned char a = (prev_ab >> 1) & 1;  // Bit A
  unsigned char b = (prev_ab >> 0) & 1;  // Bit B
  unsigned char xorbit = (a ^ b);
  xorbit = (xorbit << 0) | (xorbit << 1);
  unsigned char prev_ba = prev_ab ^ xorbit;

  // XOR with next value yields direction
  if ((prev_ba ^ curr_ab) == 1) enc_counter++; else enc_counter--;

  prev_ab = curr_ab;
}

Encoder::Encoder(uint8_t cha_pin, uint8_t chb_pin, void (*isr)(), volatile int32_t& counter, double transformation, uint32_t freq_hz)
  : Sensor(freq_hz), cha_pin(cha_pin), chb_pin(chb_pin), isr(isr), counter(counter), transformation(transformation) {}

void Encoder::setup() {
  pinMode(cha_pin, INPUT);
  pinMode(chb_pin, INPUT);
  attachInterrupt(digitalPinToInterrupt(cha_pin), isr, CHANGE);
  attachInterrupt(digitalPinToInterrupt(chb_pin), isr, CHANGE);
  reset();
}

// Reset encoder values
void Encoder::reset() {
  this->counter = 0;
}

double Encoder::get_value() {
  return transformation == 1 ? this->counter : transformation * this->counter;
}
