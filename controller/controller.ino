#include <Arduino.h>
#include <ArduinoJson.h>
#include "interface.h"

// StaticJsonDocument<512> interface_doc;
// deserializeJson(interface_doc, interface_json);
// const int RX_BUF_SIZE = required_serial_buffer_size(interface_doc["to_device"].as<JsonArray>());

StaticJsonDocument<256> rx_buf;

void setup() {
  Serial.begin(9600);
    
}

void loop() {
  if (Serial.available()) {
    DeserializationError err = deserializeJson(rx_buf, Serial.readString());
    if (err) {
      Serial.print("Deserialization of received data failed: ");
      Serial.println(err.f_str());
      return;
    }
    String out;
    serializeJsonPretty(rx_buf, out);
    Serial.println(out);
  }

  // Serial.println(Serial.read());
  // delay(200);
}
