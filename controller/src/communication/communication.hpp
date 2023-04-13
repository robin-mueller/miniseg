#ifndef COMMUNICATION_HPP
#define COMMUNICATION_HPP

#include <Arduino.h>
#include "interface.hpp"

namespace Communication {

constexpr unsigned int TX_MSG_BUF_SIZE = sizeof(TransmitInterface::msg);

const DeserializationError read(const char *msg, ReceiveInterface &rx_interface);
bool transmit(TransmitInterface &tx_interface);

}

#endif
