#include <Arduino.h>
#include "communication.hpp"

const DeserializationError Communication::receive(ReceiveInterface &rx_interface) {
  StaticJsonDocument<JSON_DOC_SIZE_RX> rx_doc;
  // Serial.println(Serial.readString());
  const DeserializationError err = deserializeJson(rx_doc, Serial);
  if (err) {
    Serial.print("Deserialization ERROR: Failed with code: ");
    Serial.println(err.f_str());
  } else {
    // Write to struct
    rx_interface.from_doc(rx_doc);
    // Serial.println("Deserialization SUCCESS! RX_DOCSIZE: " + String(rx_doc.memoryUsage()));
  }
  return err;
}

bool Communication::transmit(TransmitInterface &tx_interface) {
  StaticJsonDocument<JSON_DOC_SIZE_TX> tx_doc;
  tx_interface.to_doc(tx_doc);
  if (tx_doc.overflowed()) {
    Serial.println("Serialization ERROR: Document size for tx_doc too small!");
    return false;
  };
  // serializeJsonPretty(tx_doc, Serial);
  // Serial.println("Serialization SUCCESS! TX_DOCSIZE: " + String(tx_doc.memoryUsage()));

  // Send 4096 bytes at maximum including 3 bytes header with start char (1 byte) and message length information (2 bytes unencoded)
  char msg_buffer[4093];
  serializeJson(tx_doc, msg_buffer);
  uint16_t msg_len = strlen(msg_buffer);
  Serial.write('\n');
  Serial.write(highByte(msg_len));
  Serial.write(lowByte(msg_len));
  Serial.write(msg_buffer, msg_len);

  // Reset message
  strlcpy(tx_interface.msg, "", sizeof(tx_interface.msg)/sizeof(*tx_interface.msg));
  return true;
}