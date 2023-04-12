#include <Arduino.h>
#include "src/communication/communication.hpp"
#include "src/encoder.h"

Encoder enc("Wheel Encoder", ENC_PIN_CHA, ENC_PIN_CHB, update_motor_position, motor_pos, 100);

void setup() {
  Serial.begin(9600);
  while (!Serial) {};

  enc.setup();
}

void loop() {
  // if (Communication::RX.controller_state) {
    Communication::TX.encoder_pos = enc();
  // }
  Communication::transmit();
  delay(200);
}

void serialEvent() {
  const DeserializationError err = Communication::receive();
  if (err) return;

  // static int i = 0;
  // if (i++ % 2 == 0) Communication::put_message("TEST");

  // Communication::TX.controller_state = Communication::RX.controller_state;
  // Communication::transmit();
  Communication::put_message("");  // Reset message buffer
}
