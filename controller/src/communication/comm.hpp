#ifndef COMM_HPP
#define COMM_HPP

#include <Arduino.h>
#include "interface.hpp"

// Comment in/out to change receiving approach. If commented out, data is received by sequential polling inside loop().
#define ENABLE_RX_INTERRUPT_POLLING

class Communication {
public:
  ReceiveInterface rx_data;
  TransmitInterface tx_data;

  struct PacketInfo {
    uint32_t timestamp_us = 0;
    uint16_t message_length = 0;
  };
  PacketInfo rx_packet_info;

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
    TX_BUFFER_TOO_SMALL_TO_FIT_DATA,
    TRANSMIT_RATE_TOO_LOW
  };

private:
  static const size_t TX_STATUS_MSG_BUFFER_SIZE = 128;
  static const size_t TX_BUFFER_SIZE = 1500;
  static const size_t TX_STATUS_MSG_TRUNC_IND_SIZE = 5;
  static const size_t RX_BUFFER_SIZE = 1500;

  size_t tx_buf_tail = 0;  // Counter to indicate the progress of transmitting data from the tx local buffer. Points to the next byte to be written.
  size_t tx_buf_head = 0;  // Counter to indicate the current length of data in the tx local buffer that is scheduled to be transmitted. Points to the last byte in the buffer.

  uint8_t rx_state = 0;             // State variable for state machine that handles asynchronous packet receiving
  volatile size_t rx_buf_tail = 0;  // Counter to indicate the progress of receiving data from the rx local buffer. Points to the next byte to be read.
  volatile size_t rx_buf_head = 0;  // Counter to indicate the current length of data in the rx local buffer that is read later. Points to the last byte in the buffer.
  size_t rx_message_start = 0;      // Points to the beginning of the currently received message.
  uint16_t rx_message_length = 0;

  const char PACKET_START_TOKEN{ '$' };
  const char STATUS_MESSAGE_KEY[4]{ "msg" };

  const char TX_STATUS_MSG_TRUNC_IND[TX_STATUS_MSG_TRUNC_IND_SIZE]{ " ..." };
  char TX_STATUS_MSG_BUFFER[TX_STATUS_MSG_BUFFER_SIZE]{ 0 };
  char TX_BUFFER[TX_BUFFER_SIZE]{ 0 };
  char RX_BUFFER[RX_BUFFER_SIZE]{ 0 };

  size_t build_packet(const JsonDocument &tx_doc, char *dest, size_t dest_size);

#ifdef ENABLE_RX_INTERRUPT_POLLING
  void enable_rx_serial_buffer_read_interrupt();
  void disable_rx_serial_buffer_read_interrupt();
public:
#endif
  void rx_read_from_serial_to_local_buffer();

private:
  ReceiveCode receive_packet();

public:
  Communication();
  void setup();

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
