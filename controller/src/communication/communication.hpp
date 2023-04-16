#include <stdint.h>
#ifndef COMMUNICATION_HPP
#define COMMUNICATION_HPP

#include <Arduino.h>
#include "interface.hpp"

namespace Communication {

const char PACKET_START_TOKEN{ '$' };
const uint16_t RX_SERIAL_BUFFER_SIZE = 1024;
const uint16_t TX_SERIAL_BUFFER_SIZE = 2048;

const DeserializationError read(const char *msg, ReceiveInterface &rx_interface);
bool transmit(TransmitInterface &tx_interface);

class MessageHandler {
  char *buf;
  size_t buf_size;

public:
  template<size_t N>
  MessageHandler(char (&message_buffer)[N])
    : buf(message_buffer), buf_size(N) {
    clear();
  }

  bool append(const char *msg);
  void clear();
};

}

#endif
