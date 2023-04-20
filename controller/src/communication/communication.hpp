#include <stdint.h>
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
  const char STATUS_MESSAGE_KEY[4]{ "msg" };

  static const size_t TX_STATUS_MSG_BUFFER_SIZE = 256;
  static const size_t TX_SERIAL_BUFFER_SIZE = 1024;
  static const size_t TX_STATUS_MSG_TRUNC_IND_SIZE = 5;
  const char TX_STATUS_MSG_TRUNC_IND[TX_STATUS_MSG_TRUNC_IND_SIZE]{ " ..." };
  char TX_STATUS_MSG_BUFFER[TX_STATUS_MSG_BUFFER_SIZE]{ 0 };
  char TX_SERIAL_BUFFER[TX_SERIAL_BUFFER_SIZE]{ 0 };
  uint16_t tx_write_start = 0;  // Counter to indicate the progress of transmitting data from the tx serial buffer. Points to the next byte to be written.
  uint16_t tx_write_end = 0;    // Counter to indicate the current length of data in the tx serial buffer that is scheduled to be transmitted. Points to the last byte in the buffer.

  static const size_t RX_SERIAL_BUFFER_SIZE = 512;
  char RX_SERIAL_BUFFER[RX_SERIAL_BUFFER_SIZE]{ 0 };
  uint8_t rx_state = 0;  // State variable for state machine that handles asynchronous packet receiving
  uint16_t rx_message_len = 0;
  uint16_t rx_message_pos = 0;  // Counter to indicate the progress of writing the message that is currently being received to the buffer

  size_t build_packet(const JsonDocument &tx_doc, char *dest, size_t dest_size);

public:
  enum ReceiveCode {
    PACKET_RECEIVED,
    RX_IN_PROGRESS,
    MESSAGE_EXCEEDS_RX_BUFFER_SIZE,
    DESERIALIZATION_FAILED
  };

  enum TransmitCode {
    TX_SUCCESS,
    TX_DOC_OVERFLOW,
    INSUFFICIENT_TRANSMIT_RATE,
    PACKET_EXCEEDS_TX_BUFFER_SIZE,
  };

  Communication();

  ReceiveCode async_receive();
  TransmitCode queue_for_transmit(const JsonDocument &tx_doc);
  uint16_t async_transmit();
  bool message_append(const __FlashStringHelper *msg);
  bool message_append(const char *msg);
  TransmitCode message_queue_for_transmit(const __FlashStringHelper *msg);
  TransmitCode message_queue_for_transmit(const char *msg = "");
  void message_transmit_now(const __FlashStringHelper *msg);
  void message_clear();
};

#endif
