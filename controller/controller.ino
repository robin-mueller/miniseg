#include <Arduino.h>
#include "src/communication/communication.hpp"
#include "src/encoder.hpp"

static Communication::ReceiveInterface rx_data;
static Communication::TransmitInterface tx_data;
static Encoder wheel_position_rad(ENC_PIN_CHA, ENC_PIN_CHB, encoder_isr, enc_counter); // 2 * (2 * PI / 360)

void setup() {
  Serial.begin(9600);
  while (!Serial) {};

  wheel_position_rad.setup();

  // Initial values of RX Interface
  rx_data.controller_state = false;
}

void loop() {
  // if (Communication::RX.controller_state) {
    tx_data.encoder_pos = wheel_position_rad();
  // }
  Communication::transmit(tx_data);
  delay(100);
}

void serialEvent() {
  const DeserializationError err = Communication::receive(rx_data);
  if (err) return;

  // Communication::TX.controller_state = Communication::RX.controller_state;
  // Communication::transmit();
}
