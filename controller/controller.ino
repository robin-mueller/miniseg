#include <Arduino.h>
#include "src/interface/interface.hpp"

#define SERIAL_BUF_SIZE_RX 2048

StaticJsonDocument<JSON_DOC_SIZE_RX> rx_doc;
StaticJsonDocument<JSON_DOC_SIZE_TX> tx_doc;

char serial_buf_rx[SERIAL_BUF_SIZE_RX];

void setup() {
  Serial.begin(9600);
  while (!Serial);
}

void loop() {
  if (Serial.available()) {
    // Read from serial
    int bytes_read = Serial.readBytesUntil('\n', serial_buf_rx, SERIAL_BUF_SIZE_RX);
    serial_buf_rx[bytes_read] = '\0';
    if (serial_buf_rx[bytes_read-1] != '}') {
      Serial.println("Serial receive buffer size exceeded!");
      return;
    }
    
    // Deserialize receive buffer
    const DeserializationError err = deserializeJson(rx_doc, serial_buf_rx, SERIAL_BUF_SIZE_RX);
    if (err) {
      Serial.print("Deserialization of received data failed: ");
      Serial.println(err.f_str());
      return;
    }

    serializeJsonPretty(rx_doc, Serial);
  }

  // Serial.println(Serial.read());
  // delay(200);
}
