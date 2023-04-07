#include <Arduino.h>
#include "src/interface/interface.hpp"

ComInterface::RX rx_interface;
ComInterface::TX tx_interface;

void setup() {
  Serial.begin(9600);
  while (!Serial);
}

void loop() {
  if (Serial.available()) {
    rx_interface.receive();
    strlcpy(tx_interface.msg, "TEST", sizeof(tx_interface.msg)/sizeof(*tx_interface.msg));
    tx_interface.transmit();
  }
}
