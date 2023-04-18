#ifndef COMMUNICATION_HPP
#define COMMUNICATION_HPP

#include <Arduino.h>
#include "interface.hpp"

class Communication {
public:
  ReceiveInterface rx_data;
  TransmitInterface tx_data;

  static const size_t TX_STATUS_MSG_BUFFER_SIZE = 256;
  static const char PACKET_START_TOKEN{ '$' };
  static const size_t RX_SERIAL_BUFFER_SIZE = 512;
  static const size_t TX_SERIAL_BUFFER_SIZE = 1024;

private:
  char TX_STATUS_MSG_BUFFER[TX_STATUS_MSG_BUFFER_SIZE]{ 0 };

  void write_packet(JsonDocument &tx_doc);

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
