#ifndef MESSAGE_HPP
#define MESSAGE_HPP

#include <Arduino.h>
#include "interface.hpp"

namespace Communication {

const DeserializationError receive(ReceiveInterface &rx_interface);
bool transmit(TransmitInterface &tx_interface);

}

#endif
