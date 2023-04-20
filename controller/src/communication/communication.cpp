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

// Receives data from the serial port and stores it in rx_data in an asynchronous manner.
// So this method reads only the available chunk of data and then returns thus leaving the message completion up for the next cycles.
Communication::ReceiveCode Communication::async_receive() {
  if (Serial.available() == 63) message_queue_for_transmit(F("Warning: INSUFFICIENT_RECEIVE_RATE"));
  while (Serial.available()) {
    uint8_t b = Serial.read();  // Read one byte
    if (b == PACKET_START_TOKEN) {
      if (rx_state != 0) message_queue_for_transmit(F("Warning: PREVIOUS_PACKET_INCOMPLETE"));  // Previous message is corrupted since new start token is found but rx_state is not 0
      rx_message_len = 0;
      rx_message_pos = 0;
      rx_state = 1;
      continue;
    }

    switch (rx_state) {
      case 1:  // Read the message length byte 1 (most significant byte) -> Big endian byte format
        rx_message_len = b << 8;
        rx_state = 2;
        break;
      case 2:  // Read the message length byte 2 (least significant byte) -> Big endian byte format
        rx_message_len |= b;
        if (rx_message_len > RX_SERIAL_BUFFER_SIZE) {  // Check if the message length doesn't exceed the buffer size
          rx_state = 0;
          return ReceiveCode::MESSAGE_EXCEEDS_RX_BUFFER_SIZE;
        } else {
          rx_state = 3;
        }
        break;
      case 3:  // Read the message bytes
        RX_SERIAL_BUFFER[rx_message_pos++] = b;
        if (rx_message_pos == rx_message_len) {  // Check if packet has been fully received
          rx_state = 0;

          // Now read message. Don't use zero-copy mode since buffer may not be changed inplace as it is needed for the debug message.
          StaticJsonDocument<JSON_DOC_SIZE_RX> rx_doc;
          const DeserializationError err = deserializeJson(rx_doc, (const char *)RX_SERIAL_BUFFER, rx_message_len);

          if (err) {
            message_append(F("Error: "));
            message_append(err.f_str());
            message_append(F(" when deserializing: "));
            message_queue_for_transmit(RX_SERIAL_BUFFER);
            return ReceiveCode::DESERIALIZATION_FAILED;
          }

          // Update rx_data when message is valid
          rx_data.from_doc(rx_doc);
          return ReceiveCode::PACKET_RECEIVED;
        }
        break;
    }
  }
  return ReceiveCode::RX_IN_PROGRESS;
}

// Builds a packet from tx_doc with a 3 bytes header (start token (1 byte) + message length (2 bytes)) prepended in dest.
// Returns the length of the packet built by this function.
size_t Communication::build_packet(const JsonDocument &tx_doc, char *dest, size_t dest_size) {
  // There must be space for the three header bytes + json message length
  if (dest_size < 3 + measureJson(tx_doc)) return 0;

  size_t data_len = serializeJson(tx_doc, dest + 3, dest_size - 3);
  dest[0] = PACKET_START_TOKEN;

  // Big endian byte format for length information
  dest[1] = highByte(data_len);
  dest[2] = lowByte(data_len);
  return 3 + data_len;  // 3 bytes header + Json msg length
}

// Appends a data packet inferred from tx_doc to the transmit buffer.
Communication::TransmitCode Communication::queue_for_transmit(const JsonDocument &tx_doc) {
  if (tx_doc.overflowed()) return TransmitCode::TX_DOC_OVERFLOW;

  // Create data packet. If there is no place for it in the buffer this function returns 0.
  size_t packet_size = build_packet(tx_doc, TX_SERIAL_BUFFER + tx_write_end, TX_SERIAL_BUFFER_SIZE - tx_write_end);

  // Append packet to tx serial buffer if it was successfully created
  if (packet_size) {
    tx_write_end += packet_size;
    return TransmitCode::TX_SUCCESS;
  }
  if (tx_write_start < tx_write_end) return TransmitCode::INSUFFICIENT_TRANSMIT_RATE;
  return TransmitCode::PACKET_EXCEEDS_TX_BUFFER_SIZE;  // This occurs if the packet size is too big for the transmit buffer or if it cannot be depleted faster than new data is added
}

// Forwards bytes from the transmit buffer to the hardware buffer that sends out serial data.
// Returns the number of bytes that are left for transmission.
uint16_t Communication::async_transmit() {
  if (tx_write_end > tx_write_start) {
    uint8_t available_bytes = Serial.availableForWrite();  // check how much space is available in the serial buffer
    if (available_bytes > 0) {
      // write as much data as possible without blocking and update start counter to point to the start of the remaining data
      tx_write_start += Serial.write(TX_SERIAL_BUFFER + tx_write_start, min(tx_write_end - tx_write_start, available_bytes));

      // reset counters if tx serial buffer was fully transmitted and is currently empty
      if (tx_write_start == tx_write_end) {
        tx_write_start = 0;
        tx_write_end = 0;
      }
    }
  }
  return tx_write_end - tx_write_start;
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

Communication::TransmitCode Communication::message_queue_for_transmit(const __FlashStringHelper *msg) {
  message_append(msg);
  StaticJsonDocument<8 + TX_STATUS_MSG_BUFFER_SIZE> status_msg_doc;
  status_msg_doc[STATUS_MESSAGE_KEY] = TX_STATUS_MSG_BUFFER;
  TransmitCode tx_error = queue_for_transmit(status_msg_doc);
  message_clear();
  return tx_error;
}

Communication::TransmitCode Communication::message_queue_for_transmit(const char *msg) {
  message_append(msg);
  StaticJsonDocument<8 + TX_STATUS_MSG_BUFFER_SIZE> status_msg_doc;
  status_msg_doc[STATUS_MESSAGE_KEY] = TX_STATUS_MSG_BUFFER;
  TransmitCode tx_error = queue_for_transmit(status_msg_doc);
  message_clear();
  return tx_error;
}

// Transmits a message in a blocking manner. Returns as soon as the message is fully transmitted.
// This should only be used when an alternative to the asynchronous approach of sending data by appending bytes to the transmit buffer and then forwarding them later to the hardware serial buffer is needed.
void Communication::message_transmit_now(const __FlashStringHelper *msg) {
  message_append(msg);
  StaticJsonDocument<8 + TX_STATUS_MSG_BUFFER_SIZE> status_msg_doc;
  status_msg_doc[STATUS_MESSAGE_KEY] = TX_STATUS_MSG_BUFFER;
  const size_t buf_size = 3 + measureJson(status_msg_doc);  // Account for 3 bytes header + json message length
  char buffer[buf_size]{ 0 };
  size_t status_msg_size = build_packet(status_msg_doc, buffer, buf_size);
  while (async_transmit() > 0) {};        // Wait for pending data to be transmitted to not corrupt the stream
  Serial.write(buffer, status_msg_size);  // blocks until all bytes including the null terminal have been written
  message_clear();
}

void Communication::message_clear() {
  strlcpy(TX_STATUS_MSG_BUFFER, "", TX_STATUS_MSG_BUFFER_SIZE);
}
