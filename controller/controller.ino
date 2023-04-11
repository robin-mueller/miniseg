#include <Arduino.h>
#include "src/communication/communication.hpp"

void setup() {
  Serial.begin(9600);
  while (!Serial) {};
}

void loop() {
}

void serialEvent() {
  const DeserializationError err = Communication::receive();
  if (err) return;

  static int i = 0;
  if (i++ % 2 == 0) Communication::put_message("TEST");

  Communication::TX.controller_state = Communication::RX.controller_state;
  Communication::transmit();
  Communication::put_message("");  // Reset message buffer
}
