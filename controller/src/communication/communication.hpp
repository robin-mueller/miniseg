#ifndef COMMUNICATION_HPP
#define COMMUNICATION_HPP

#include <Arduino.h>
#include "interface.hpp"

namespace Communication {

const char PACKET_START_TOKEN{ '$' };

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
