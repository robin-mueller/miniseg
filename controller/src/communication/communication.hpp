#ifndef COMMUNICATION_HPP
#define COMMUNICATION_HPP

#include <Arduino.h>
#include "interface.hpp"

namespace Communication {

const DeserializationError read(const char *msg, ReceiveInterface &rx_interface);
bool transmit(TransmitInterface &tx_interface);

class MessageHandler {
  char *buf;
  size_t buf_size;

public:
  MessageHandler(char *message_buffer);

  bool append(const char *msg, bool new_line = true);
  void clear();
};

}

#endif
