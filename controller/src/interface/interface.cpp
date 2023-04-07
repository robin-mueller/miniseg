#include <Arduino.h>
#include "interface.hpp"

#define SERIAL_BUF_SIZE_RX 2048

bool ComInterface::RX::receive() {
  // Read from serial
  char serial_buf_rx[SERIAL_BUF_SIZE_RX];
  int bytes_read = Serial.readBytesUntil('\n', serial_buf_rx, SERIAL_BUF_SIZE_RX);
  serial_buf_rx[bytes_read] = '\0';
  if (serial_buf_rx[bytes_read - 1] != '}') {
    Serial.println("Serial receive buffer size exceeded!");
    return false;
  }

  // Deserialize receive buffer
  StaticJsonDocument<JSON_DOC_SIZE_RX> rx_doc;
  const DeserializationError err = deserializeJson(rx_doc, serial_buf_rx, SERIAL_BUF_SIZE_RX);
  if (err) {
    Serial.print("Deserialization of received data failed: ");
    Serial.println(err.f_str());
    return false;
  }

  // Write to struct
  from_doc(rx_doc);
  return true;
}

bool ComInterface::TX::transmit() {
  StaticJsonDocument<JSON_DOC_SIZE_TX> tx_doc;
  to_doc(tx_doc);
  serializeJsonPretty(tx_doc, Serial);
  return true;
}
