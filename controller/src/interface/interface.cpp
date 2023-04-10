#include <Arduino.h>
#include "interface.hpp"

const DeserializationError ComInterface::RX::receive() {
  StaticJsonDocument<JSON_DOC_SIZE_RX> rx_doc;
  const DeserializationError err = deserializeJson(rx_doc, Serial);
  if (err) {
    Serial.print("Deserialization ERROR: Failed with code: ");
    Serial.println(err.f_str());
  } else {
    // Write to struct
    from_doc(rx_doc);
    // Serial.println("Deserialization SUCCESS! RX_DOCSIZE: " + String(rx_doc.memoryUsage()));    
  }
  return err;
}

bool ComInterface::TX::transmit() {
  StaticJsonDocument<JSON_DOC_SIZE_TX> tx_doc;
  to_doc(tx_doc);
  if (tx_doc.overflowed()) {
    Serial.println("Serialization ERROR: Document size for tx_doc too small!");
    return false;
  };
  // serializeJsonPretty(tx_doc, Serial);
  // Serial.println("Serialization SUCCESS! TX_DOCSIZE: " + String(tx_doc.memoryUsage()));
  serializeJson(tx_doc, Serial); 
  return true;
}
