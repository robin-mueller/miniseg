#ifndef COMMUNICATION_HPP
#define COMMUNICATION_HPP

#include <Arduino.h>
#include "interface.hpp"

class Communication {
public:
  ReceiveInterface rx_data;
  TransmitInterface tx_data;

private:
  const char PACKET_START_TOKEN{ '$' };
  static const size_t TX_STATUS_MSG_BUFFER_SIZE = 256;
  static const size_t RX_SERIAL_BUFFER_SIZE = 512;
  static const size_t TX_SERIAL_BUFFER_SIZE = 1024;
  static const size_t TX_STATUS_MSG_TRUNC_IND_SIZE = 5;
  const char TX_STATUS_MSG_TRUNC_IND[TX_STATUS_MSG_TRUNC_IND_SIZE]{ " ..." };
  char TX_STATUS_MSG_BUFFER[TX_STATUS_MSG_BUFFER_SIZE]{ 0 };
  char RX_SERIAL_BUFFER[RX_SERIAL_BUFFER_SIZE]{ 0 };
  char TX_SERIAL_BUFFER[TX_SERIAL_BUFFER_SIZE]{ 0 };
  uint16_t tx_write_start_idx = 0;
  uint16_t tx_write_end_idx = 0;

  // Build packet from json doc, prepend 3 bytes header (start char (1 byte) + message length information (2 bytes)) in dest.
  // Returns the length of the packet build by this function.
  template<size_t N>
  size_t Communication::build_packet(JsonDocument &tx_doc, char (&dest)[N]) {
    size_t msg_len = serializeJson(tx_doc, dest + 3, N - 3);
    dest[0] = PACKET_START_TOKEN;
    dest[1] = lowByte(msg_len);
    dest[2] = lowByte(msg_len);
    return msg_len + 3;
  }

public:
  Communication();

  bool receive();
  bool transmit();
  bool message_append(const __FlashStringHelper *msg);
  bool message_append(const char *msg);
  bool message_transmit(const __FlashStringHelper *msg);
  bool message_transmit(const char *msg = "");
  void message_clear();
};

#endif
