#include <Arduino.h>
#include <util/atomic.h>
#include "comm.hpp"

Communication comm;  // Define communication instance globally here

Communication::Communication() {
  /*
  Initial values of interface can be defined here.

  By default the following inital values set:
    bool -> false
    int, float, double -> 0
  */
  message_clear();
}

void Communication::setup() {
  /*
  Set up timed interrupt for reading the hardware serial receive buffer (64 bytes) using timer/counter3.
  The buffer is estimated to be full every 64 (Buffer size) * 86.806 µs (Real byte rate at 115200 baud rate) ~= 5 ms (Conservatively floored).
  So the timer must trigger the buffer read interrupt routine faster than that.
  */
  TCCR3A = 0;
  TCCR3B = 0;
  TCCR3B |= (1 << WGM32);               // Set CTC mode and clear counter on match with OCR3A.
  TCCR3B |= (1 << CS32) | (1 << CS30);  // At a clock speed of 16 MHz (Arduino Mega 2560) use prescale factor 1/1024 for counter increment every 64 µs
  enable_rx_serial_buffer_read_interrupt();

  // Output Compare Register A has to be set to a value lower than 5 ms (Hardware buffer full rate) / 64 µs (Counter increment rate) = 78.125.
  // Lower values ensure a higher margin for delays in executing the read buffer routine and promise short interrupt times, since only few bytes have to be shifted from the hardware buffer to the local one.
  // However, high frequency interrupts can cause problematic delays in the actual control loop.
  // OCR3A is a 16 bit register. Accessing it requires to temporarily disable interrupts.
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    OCR3A = (uint16_t)20;  // Choosing e.g. 78 here results in reading the buffer when it is filled with 78 (Output Compare Register value) * 64 µs (Counter increment rate) / 86.806 µs (Real byte rate at 115200 baud rate) ~= 57.5 bytes !< 64 (Buffer size)
  }

  pinMode(LED_BUILTIN, OUTPUT);  // Indicator LED on when packet receive in progress.
}

// Receives data from the local rx buffer.
// This method reads only the available chunk of data and then returns thus leaving the message completion up for the next cycles.
// Filling the local rx buffer is done by a timer interrupt routine.
Communication::ReceiveCode Communication::_async_receive() {
  if (rx_buf_tail == rx_buf_head) return ReceiveCode::NO_DATA_AVAILABLE;
  while (rx_buf_tail < rx_buf_head) {

    // Read buffer at tail
    uint8_t b = RX_BUFFER[rx_buf_tail];

    if (b == PACKET_START_TOKEN) {
      digitalWrite(LED_BUILTIN, HIGH);
      if (rx_state != 0) message_enqueue_for_transmit(F("Warning: PREVIOUS_PACKET_INCOMPLETE"));  // Previous message is corrupted since new start token is found but rx_state is not 0

      rx_buf_tail++;
      rx_state = 1;
      continue;
    }

    switch (rx_state) {
      case 1:
        // Read the message length byte 1 (most significant byte) -> Big endian byte format
        rx_message_length = 0;  // Reset variable since new message starts
        rx_message_length = b << 8;

        rx_buf_tail++;
        rx_state = 2;
        break;
      case 2:
        // Read the message length byte 2 (least significant byte) -> Big endian byte format
        rx_message_length |= b;

        // Verify that the message length doesn't exceed the buffer size
        if (rx_message_length > RX_BUFFER_SIZE) {
          // If it exceeds the buffer size, discard it.
          rx_state = 0;
          rx_buf_tail = 0;
          rx_buf_head = 0;
          return ReceiveCode::MESSAGE_EXCEEDS_RX_BUFFER_SIZE;
        }
        rx_buf_tail++;
        rx_message_start = rx_buf_tail;
        rx_state = 3;
        break;
      case 3:  // Wait for message to be complete
        rx_buf_tail = min(rx_message_length + rx_message_start, rx_buf_head);
        if (rx_message_length - (rx_buf_tail - rx_message_start) > 0) return ReceiveCode::RX_IN_PROGRESS;  // Wait for more data

        // Reset receive state machine.
        rx_state = 0;
        if (rx_buf_tail == rx_buf_head) {
          rx_buf_tail = 0;
          rx_buf_head = 0;
        }

        // Try deserialization now that packet has been fully received. Don't use zero-copy mode since buffer may not be changed inplace as it is needed for the debug message.
        StaticJsonDocument<JSON_DOC_SIZE_RX> rx_doc;
        const DeserializationError err = deserializeJson(rx_doc, (const char *)RX_BUFFER + rx_message_start, rx_message_length);

        if (err) {
          message_append(F("Error: "));
          message_append(err.f_str());
          message_append(F(" when deserializing: "));
          message_enqueue_for_transmit(RX_BUFFER + rx_message_start, rx_message_length);
          return ReceiveCode::DESERIALIZATION_FAILED;
        }

        // Update rx_data when message is valid
        rx_data.from_doc(rx_doc);
        digitalWrite(LED_BUILTIN, LOW);
        return ReceiveCode::PACKET_RECEIVED;

        break;
    }
  }

  return ReceiveCode::RX_IN_PROGRESS;
}

// Receives data from the serial port and stores it in rx_data in an asynchronous manner.
// So this method reads only the available chunk of data and then returns thus leaving the message completion up for the next cycles.
Communication::ReceiveCode Communication::async_receive() {

  // Freeze hardware buffer read routine during evaluation of local buffer.
  disable_rx_serial_buffer_read_interrupt();

  // Call implementation
  ReceiveCode code = _async_receive();

  // Reenable hardware buffer read interrupts during loop
  enable_rx_serial_buffer_read_interrupt();

  return code;
}

// Builds a packet from tx_doc with a 3 bytes header (start token (1 byte) + message length (2 bytes)) prepended in dest.
// Returns the length of the packet built by this function.
size_t Communication::build_packet(const JsonDocument &tx_doc, char *dest, size_t dest_size) {
  // There must be space for the three header bytes + json message length
  if (dest_size < 3 + measureJson(tx_doc)) return 0;

  size_t data_len = serializeJson(tx_doc, dest + 3, dest_size - 3);
  dest[0] = PACKET_START_TOKEN;

  // Big endian byte format for length information
  dest[1] = highByte(data_len);
  dest[2] = lowByte(data_len);
  return 3 + data_len;  // 3 bytes header + Json msg length
}

// Appends a data packet inferred from tx_doc to the transmit buffer.
Communication::TransmitCode Communication::enqueue_for_transmit(const JsonDocument &tx_doc) {
  if (tx_doc.overflowed()) return TransmitCode::TX_DOC_OVERFLOW;

  // Create data packet. If there is no place for it in the buffer this function returns 0.
  size_t packet_size = build_packet(tx_doc, TX_BUFFER + tx_buf_head, TX_BUFFER_SIZE - tx_buf_head);

  // Append packet to tx serial buffer if it was successfully created
  if (packet_size) {
    tx_buf_head += packet_size;
    return TransmitCode::TX_SUCCESS;
  }
  if (tx_buf_tail < tx_buf_head) return TransmitCode::INSUFFICIENT_TRANSMIT_RATE;
  return TransmitCode::PACKET_EXCEEDS_TX_BUFFER_SIZE;  // This occurs if the packet size is too big for the transmit buffer or if it cannot be depleted faster than new data is added
}

// Forwards bytes from the transmit buffer to the hardware buffer that sends out serial data.
// Returns the number of bytes that are left for transmission.
uint16_t Communication::async_transmit() {
  if (tx_buf_head > tx_buf_tail) {
    uint8_t available_bytes = Serial.availableForWrite();  // check how much space is available in the serial buffer
    if (available_bytes > 0) {
      // write as much data as possible without blocking and update start counter to point to the start of the remaining data
      tx_buf_tail += Serial.write(TX_BUFFER + tx_buf_tail, min(tx_buf_head - tx_buf_tail, available_bytes));

      // reset counters if tx serial buffer was fully transmitted and is currently empty
      if (tx_buf_tail == tx_buf_head) {
        tx_buf_tail = 0;
        tx_buf_head = 0;
      }
    }
  }
  return tx_buf_head - tx_buf_tail;
}

bool Communication::message_append(const __FlashStringHelper *msg) {
  size_t existing_len = strlen(TX_STATUS_MSG_BUFFER);
  size_t append_len = strlcpy_P(TX_STATUS_MSG_BUFFER + existing_len, (const char *)msg, TX_STATUS_MSG_BUFFER_SIZE - existing_len);
  if (append_len < TX_STATUS_MSG_BUFFER_SIZE - existing_len) {
    return true;  // Return true if every char fitted into the buffer
  } else {
    strlcpy(TX_STATUS_MSG_BUFFER + (TX_STATUS_MSG_BUFFER_SIZE - TX_STATUS_MSG_TRUNC_IND_SIZE), TX_STATUS_MSG_TRUNC_IND, TX_STATUS_MSG_TRUNC_IND_SIZE);  // If truncated append TX_STATUS_MSG_TRUNC_IND to indicate that
    return false;
  }
}

bool Communication::message_append(const char *msg, size_t msg_len) {
  size_t existing_len = strlen(TX_STATUS_MSG_BUFFER);
  size_t append_len = strlcpy(TX_STATUS_MSG_BUFFER + existing_len, msg, min(msg_len + 1, TX_STATUS_MSG_BUFFER_SIZE - existing_len));
  if (append_len < TX_STATUS_MSG_BUFFER_SIZE - existing_len) {
    return true;  // Return true if every char fitted into the buffer
  } else {
    strlcpy(TX_STATUS_MSG_BUFFER + (TX_STATUS_MSG_BUFFER_SIZE - TX_STATUS_MSG_TRUNC_IND_SIZE), TX_STATUS_MSG_TRUNC_IND, TX_STATUS_MSG_TRUNC_IND_SIZE);  // If truncated append TX_STATUS_MSG_TRUNC_IND to indicate that
    return false;
  }
}

Communication::TransmitCode Communication::message_enqueue_for_transmit(const __FlashStringHelper *msg) {
  message_append(msg);
  StaticJsonDocument<8 + TX_STATUS_MSG_BUFFER_SIZE> status_msg_doc;
  status_msg_doc[STATUS_MESSAGE_KEY] = TX_STATUS_MSG_BUFFER;
  TransmitCode tx_error = enqueue_for_transmit(status_msg_doc);
  message_clear();
  return tx_error;
}

Communication::TransmitCode Communication::message_enqueue_for_transmit(const char *msg, size_t msg_len) {
  message_append(msg, msg_len);
  StaticJsonDocument<8 + TX_STATUS_MSG_BUFFER_SIZE> status_msg_doc;
  status_msg_doc[STATUS_MESSAGE_KEY] = TX_STATUS_MSG_BUFFER;
  TransmitCode tx_error = enqueue_for_transmit(status_msg_doc);
  message_clear();
  return tx_error;
}

// Transmits a message in a blocking manner. Returns as soon as the message is fully transmitted.
// This should only be used when an alternative to the asynchronous approach of sending data by appending bytes to the transmit buffer and then forwarding them later to the hardware serial buffer is needed.
void Communication::message_transmit_now(const __FlashStringHelper *msg) {
  message_append(msg);
  StaticJsonDocument<8 + TX_STATUS_MSG_BUFFER_SIZE> status_msg_doc;
  status_msg_doc[STATUS_MESSAGE_KEY] = TX_STATUS_MSG_BUFFER;
  const size_t buf_size = 3 + measureJson(status_msg_doc);  // Account for 3 bytes header + json message length
  char buffer[buf_size]{ 0 };
  size_t status_msg_size = build_packet(status_msg_doc, buffer, buf_size);
  while (async_transmit() > 0) {};        // Wait for pending data to be transmitted to not corrupt the stream
  Serial.write(buffer, status_msg_size);  // blocks until all bytes including the null terminal have been written
  message_clear();
}

void Communication::message_clear() {
  strlcpy(TX_STATUS_MSG_BUFFER, "", TX_STATUS_MSG_BUFFER_SIZE);
}

// ----------------------- RX Serial Buffer Read Interrupt Handling ------------------------

void Communication::enable_rx_serial_buffer_read_interrupt() {
  TIMSK3 = 0;
  TIMSK3 |= (1 << OCIE3A);  // Enable compare match interrupt for OCR3A.
}

void Communication::disable_rx_serial_buffer_read_interrupt() {
  TIMSK3 = 0;  // Clear timer interrupt mask
}

void Communication::read_from_rx_serial_buffer() {
  if (Serial.available() == 63) message_enqueue_for_transmit(F("Receive Warning: INSUFFICIENT_RECEIVE_RATE"));  // Buffer full
  while (Serial.available()) {
    if (rx_buf_head < RX_BUFFER_SIZE) {
      RX_BUFFER[rx_buf_head++] = Serial.read();  // Transfer bytes from hardware buffer to extended local buffer.
    } else {
      message_enqueue_for_transmit(F("Receive Error: INCOMING_DATA_RATE_TOO_FAST"));  // When the buffer is filled, it means that messages come in faster that they can be deserialized.
      rx_buf_tail = 0;
      rx_buf_head = 0;
      break;
    }
  }
}

ISR(TIMER3_COMPA_vect) {
  comm.read_from_rx_serial_buffer();
}
