#include "HardwareSerial.h"
#include <Arduino.h>
#include "communication.hpp"

Communication::Communication() {
  /*
  Initial values of interface can be defined here.

  By default the following inital values set:
    bool -> false
    int, float, double -> 0
  */
  message_clear();
}

bool Communication::receive() {
  if (!Serial.available()) return false;
  char buffer[RX_SERIAL_BUFFER_SIZE]{ 0 };
  union {
    uint16_t integer = 0;
    byte arr[2];
  } msg_len;

  // When data arrives this function blocks the execution on the microcontroller until the entire message was received or until timeout.
  if (Serial.find(PACKET_START_TOKEN)) {
    // When packet start was found, read message length information from first two bytes
    Serial.readBytes(msg_len.arr, 2);
    Serial.readBytes(buffer, msg_len.integer);

    // Now read message
    StaticJsonDocument<JSON_DOC_SIZE_RX> rx_doc;
    const DeserializationError err = deserializeJson(rx_doc, (const char *)buffer);  // prevent zero-copy mode since buffer should not be changed inplace as it is needed for the debug message.
    if (err) {
      message_clear();
      message_append(F("Deserialization ERROR: Failed with code: "));
      message_transmit(err.f_str());
      message_append(F("Tried to deserialize: "));
      message_transmit(buffer);
      return false;
    }
    rx_data.from_doc(rx_doc);
    return true;
  }
  return false;
}

bool Communication::transmit() {
  StaticJsonDocument<JSON_DOC_SIZE_TX> tx_doc;
  tx_data.to_doc(tx_doc);

  if (tx_doc.overflowed()) {
    message_clear();
    message_transmit(F("Serialization ERROR: Document size for tx_doc too small!"));
    return false;
  } else {
    write_packet(tx_doc);
    return true;
  }
}

// Send a maximum of TX_SERIAL_BUFFER_SIZE bytes plus 3 bytes header (start char (1 byte) + message length information (2 bytes))
void Communication::write_packet(JsonDocument &tx_doc) {
  char buffer[TX_SERIAL_BUFFER_SIZE]{ 0 };
  size_t msg_len = serializeJson(tx_doc, buffer);

  // Write to serial. Be aware that this will block if serial buffer is full.
  Serial.write(PACKET_START_TOKEN);
  Serial.write(lowByte(msg_len));
  Serial.write(highByte(msg_len));
  Serial.write(buffer, msg_len);
}

bool Communication::message_append(const __FlashStringHelper *msg) {
  size_t existing_len = strlen(TX_STATUS_MSG_BUFFER);
  size_t append_len = strlcpy_P(TX_STATUS_MSG_BUFFER + existing_len, (const char *)msg, TX_STATUS_MSG_BUFFER_SIZE - existing_len);
  if (append_len < TX_STATUS_MSG_BUFFER_SIZE - existing_len) {
    return true;  // Return true if every char fitted into the buffer
  } else {
    strlcpy(TX_STATUS_MSG_BUFFER + (TX_STATUS_MSG_BUFFER_SIZE - TX_STATUS_MSG_TRUNC_IND_SIZE), TX_STATUS_MSG_TRUNC_IND, TX_STATUS_MSG_TRUNC_IND_SIZE);  // If truncated append TX_STATUS_MSG_TRUNC_IND to indicate that
    return false;
  }
}

bool Communication::message_append(const char *msg) {
  size_t existing_len = strlen(TX_STATUS_MSG_BUFFER);
  size_t append_len = strlcpy(TX_STATUS_MSG_BUFFER + existing_len, msg, TX_STATUS_MSG_BUFFER_SIZE - existing_len);
  if (append_len < TX_STATUS_MSG_BUFFER_SIZE - existing_len) {
    return true;  // Return true if every char fitted into the buffer
  } else {
    strlcpy(TX_STATUS_MSG_BUFFER + (TX_STATUS_MSG_BUFFER_SIZE - TX_STATUS_MSG_TRUNC_IND_SIZE), TX_STATUS_MSG_TRUNC_IND, TX_STATUS_MSG_TRUNC_IND_SIZE);  // If truncated append TX_STATUS_MSG_TRUNC_IND to indicate that
    return false;
  }
}

bool Communication::message_transmit(const __FlashStringHelper *msg) {
  bool success = message_append(msg);
  StaticJsonDocument<8 + TX_STATUS_MSG_BUFFER_SIZE> tx_doc;
  tx_doc["msg"] = TX_STATUS_MSG_BUFFER;
  write_packet(tx_doc);
  message_clear();
  return success;
}

bool Communication::message_transmit(const char *msg) {
  bool success = message_append(msg);
  StaticJsonDocument<8 + TX_STATUS_MSG_BUFFER_SIZE> tx_doc;
  tx_doc["msg"] = TX_STATUS_MSG_BUFFER;
  write_packet(tx_doc);
  message_clear();
  return success;
}

void Communication::message_clear() {
  strlcpy(TX_STATUS_MSG_BUFFER, "", TX_STATUS_MSG_BUFFER_SIZE);
}
