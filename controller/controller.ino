#include <Arduino.h>
#include <ArduinoJson.h>
#include "interface.h"

StaticJsonDocument<RX_DOC_SIZE> rx_doc;
StaticJsonDocument<TX_DOC_SIZE> tx_doc;

void setup() {
  Serial.begin(9600);
    
}

void loop() {
  if (Serial.available()) {
    DeserializationError err = deserializeJson(rx_doc, Serial.readString());
    if (err) {
      Serial.print("Deserialization of received data failed: ");
      Serial.println(err.f_str());
      return;
    }
    String out;
    serializeJsonPretty(rx_doc, out);
    Serial.println(out);
  }

  // Serial.println(Serial.read());
  // delay(200);
}
