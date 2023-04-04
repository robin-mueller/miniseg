#include <Arduino.h>
#include <ArduinoJson.h>

StaticJsonDocument<256> json_doc;

void setup() {
  Serial.begin(9600);
    
}

void loop() {
  if (Serial.available()) {
    DeserializationError err = deserializeJson(json_doc, Serial.readString());
    if (err) {
      Serial.print("Deserialization of received data failed: ");
      Serial.println(err.f_str());
      return;
    }
    String out;
    serializeJsonPretty(json_doc, out);
    Serial.println(out);
  }

  // Serial.println(Serial.read());
  // delay(200);
}
