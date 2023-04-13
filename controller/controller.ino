#include <Arduino.h>
#include "src/communication/communication.hpp"
#include "src/encoder.hpp"

static Communication::ReceiveInterface rx_data;
static Communication::TransmitInterface tx_data;
static Encoder wheel_position_rad(ENC_PIN_CHA, ENC_PIN_CHB, encoder_isr, enc_counter, 0.5 * (2 * PI / 360));

void setup() {
  Serial.begin(9600);
  while (!Serial) {};

  wheel_position_rad.setup();

  // Initial values of RX Interface
  rx_data.control_state = false;
}

void loop() {
  Communication::transmit(tx_data);

  if (rx_data.control_state) {
    tx_data.wheel.pos_rad = wheel_position_rad();
    tx_data.wheel.vel_rad_s = wheel_position_rad.derivative();
  }

  delay(100);
  Sensor::cycle_num++;
}

void serialEvent() {
  char buffer[4096]{ 0 };
  union {
    uint16_t integer = 0;
    byte arr[2];
  } msg_len;

  // When data arrives this function blocks the execution on the microcontroller until the entire message was received or until timeout.
  Serial.setTimeout(100);
  if (Serial.find('\n')) {
    // When message start was found, read message size information from first two bytes and then read message
    Serial.readBytes(msg_len.arr, 2);
    Serial.readBytes(buffer, msg_len.integer);
    const DeserializationError err = Communication::read(buffer, rx_data);
    if (err) {
      String msg("Deserialization ERROR: Failed with code: " + String(err.f_str()));
      msg.toCharArray(tx_data.msg, Communication::TX_MSG_BUF_SIZE);
      return;
    }

    // React to received data
    if (rx_data.control_state) {
      String("Control enabled!").toCharArray(tx_data.msg, Communication::TX_MSG_BUF_SIZE);
    } else {
      String("Control disabled!").toCharArray(tx_data.msg, Communication::TX_MSG_BUF_SIZE);
    }
  }
}
