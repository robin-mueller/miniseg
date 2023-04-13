#include <Arduino.h>
#include "communication.hpp"

const DeserializationError Communication::read(const char *msg, ReceiveInterface &rx_data) {
  StaticJsonDocument<JSON_DOC_SIZE_RX> rx_doc;
  const DeserializationError err = deserializeJson(rx_doc, msg);
  if (!err) rx_data.from_doc(rx_doc);
  return err;
}

bool Communication::transmit(TransmitInterface &tx_data) {
  StaticJsonDocument<JSON_DOC_SIZE_TX> tx_doc;
  tx_data.to_doc(tx_doc);
  bool success = true;
  if (tx_doc.overflowed()) {
    tx_doc.clear();
    tx_doc["msg"] = "Serialization ERROR: Document size for tx_doc too small!";
    success = false;
  };

  // Send 4096 bytes at maximum including 3 bytes header with start char (1 byte) and message length information (2 bytes unencoded)
  char msg_buffer[4093];
  serializeJson(tx_doc, msg_buffer);
  uint16_t msg_len = strlen(msg_buffer);
  Serial.write('\n');
  Serial.write(lowByte(msg_len));
  Serial.write(highByte(msg_len));
  Serial.write(msg_buffer, msg_len);

  // Reset message
  strlcpy(tx_data.msg, "", sizeof(tx_data.msg)/sizeof(*tx_data.msg));
  return success;
}