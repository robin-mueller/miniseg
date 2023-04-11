#include <Arduino.h>
#include "communication.hpp"

const DeserializationError Communication::receive() {
  StaticJsonDocument<JSON_DOC_SIZE_RX> rx_doc;
  // Serial.println(Serial.readString());
  const DeserializationError err = deserializeJson(rx_doc, Serial);
  if (err) {
    Serial.print("Deserialization ERROR: Failed with code: ");
    Serial.println(err.f_str());
  } else {
    // Write to struct
    RX.from_doc(rx_doc);
    // Serial.println("Deserialization SUCCESS! RX_DOCSIZE: " + String(rx_doc.memoryUsage()));
  }
  return err;
}

bool Communication::transmit() {
  StaticJsonDocument<JSON_DOC_SIZE_TX> tx_doc;
  TX.to_doc(tx_doc);
  if (tx_doc.overflowed()) {
    Serial.println("Serialization ERROR: Document size for tx_doc too small!");
    return false;
  };
  // serializeJsonPretty(tx_doc, Serial);
  // Serial.println("Serialization SUCCESS! TX_DOCSIZE: " + String(tx_doc.memoryUsage()));
  serializeJson(tx_doc, Serial);
  return true;
}

void Communication::put_message(const char* msg) {
  strlcpy(Communication::TX.msg, msg, sizeof(Communication::TX.msg) / sizeof(*Communication::TX.msg));
}