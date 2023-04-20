#ifndef COMM_HPP
#define COMM_HPP

#include <Arduino.h>
#include "interface.hpp"

class Communication {
public:
  ReceiveInterface rx_data;
  TransmitInterface tx_data;

private:
  static const size_t TX_STATUS_MSG_BUFFER_SIZE = 256;
  static const size_t TX_BUFFER_SIZE = 1024;
  static const size_t TX_STATUS_MSG_TRUNC_IND_SIZE = 5;
  static const size_t RX_BUFFER_SIZE = 512;

  size_t tx_buf_tail = 0;  // Counter to indicate the progress of transmitting data from the tx local buffer. Points to the next byte to be written.
  size_t tx_buf_head = 0;  // Counter to indicate the current length of data in the tx local buffer that is scheduled to be transmitted. Points to the last byte in the buffer.

  uint8_t rx_state = 0;             // State variable for state machine that handles asynchronous packet receiving
  volatile size_t rx_buf_tail = 0;  // Counter to indicate the progress of receiving data from the rx local buffer. Points to the next byte to be read.
  volatile size_t rx_buf_head = 0;  // Counter to indicate the current length of data in the rx local buffer that is read later. Points to the last byte in the buffer. This value is incremented by the hardware buffer read interrupt routine.
  size_t rx_message_start = 0;      // Points to the beginning of the currently received message.
  uint16_t rx_message_length = 0;

  const char PACKET_START_TOKEN{ '$' };
  const char STATUS_MESSAGE_KEY[4]{ "msg" };

  const char TX_STATUS_MSG_TRUNC_IND[TX_STATUS_MSG_TRUNC_IND_SIZE]{ " ..." };
  char TX_STATUS_MSG_BUFFER[TX_STATUS_MSG_BUFFER_SIZE]{ 0 };
  char TX_BUFFER[TX_BUFFER_SIZE]{ 0 };
  char RX_BUFFER[RX_BUFFER_SIZE]{ 0 };

  size_t build_packet(const JsonDocument &tx_doc, char *dest, size_t dest_size);
  void enable_rx_serial_buffer_read_interrupt();
  void disable_rx_serial_buffer_read_interrupt();

public:
  enum ReceiveCode {
    NO_DATA_AVAILABLE,
    PACKET_RECEIVED,
    RX_IN_PROGRESS,
    MESSAGE_EXCEEDS_RX_BUFFER_SIZE,
    DESERIALIZATION_FAILED
  };

  enum TransmitCode {
    TX_SUCCESS,
    TX_DOC_OVERFLOW,
    INSUFFICIENT_TRANSMIT_RATE,
    PACKET_EXCEEDS_TX_BUFFER_SIZE
  };

private:
  ReceiveCode _async_receive();

public:
  Communication();
  void setup();

  void read_from_rx_serial_buffer();
  ReceiveCode async_receive();
  TransmitCode enqueue_for_transmit(const JsonDocument &tx_doc);
  uint16_t async_transmit();
  bool message_append(const __FlashStringHelper *msg);
  bool message_append(const char *msg, size_t msg_len);
  TransmitCode message_enqueue_for_transmit(const __FlashStringHelper *msg);
  TransmitCode message_enqueue_for_transmit(const char *msg, size_t msg_len);
  void message_transmit_now(const __FlashStringHelper *msg);
  void message_clear();
};

extern Communication comm;

#endif
