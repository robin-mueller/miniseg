#ifndef COMMUNICATION_HPP
#define COMMUNICATION_HPP

#include <Arduino.h>
#include "interface.hpp"

class Communication {
public:
  ReceiveInterface rx_data;
  TransmitInterface tx_data;

  static const size_t TX_MSG_BUFFER_SIZE = 256;
  static const char PACKET_START_TOKEN{ '$' };
  static const size_t RX_SERIAL_BUFFER_SIZE = 512;
  static const size_t TX_SERIAL_BUFFER_SIZE = 1024;

private:
  char TX_MSG_BUFFER[TX_MSG_BUFFER_SIZE]{ 0 };

  void write_packet(JsonDocument &tx_doc);

public:
  bool receive();
  bool transmit();
  bool message_append(const __FlashStringHelper *msg);
  bool message_transmit(const __FlashStringHelper *msg);
  void message_clear();
};

#endif
