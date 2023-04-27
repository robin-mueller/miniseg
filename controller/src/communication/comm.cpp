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
#ifdef ENABLE_RX_INTERRUPT_POLLING
  /*
  Set up timed interrupt for reading the hardware serial receive buffer (64 bytes) using timer/counter4 which is free to use on the MinSeg board.
  The buffer is estimated to be full every 64 (Buffer size) * 86.806 µs (Real byte rate at 115200 baud rate) ~= 5 ms (Conservatively floored).
  So the timer must trigger the buffer read interrupt routine faster than that.
  */
  TCCR4A = 0;
  TCCR4B = 0;
  TCCR4B |= (1 << WGM42);               // Set CTC mode and clear counter on match with OCR4A.
  TCCR4B |= (1 << CS42) | (1 << CS40);  // At a clock speed of 16 MHz (Arduino Mega 2560) use prescale factor 1024 for counter increment every 64 µs
  enable_rx_serial_buffer_read_interrupt();

  /* Output Compare Register A has to be set to a value lower than 5 ms (Hardware buffer full rate) / 64 µs (Counter increment rate) = 78.125.
  Lower values ensure a higher margin for delays in executing the read buffer routine and promise short interrupt times, since only few bytes have to be shifted from the hardware buffer to the local one.
  However, high frequency interrupts can cause problematic delays in the actual control loop.
  OCR3A is a 16 bit register. Accessing it requires to temporarily disable interrupts.
  Choosing e.g. 78 here results in reading the buffer when it is filled with 78 (Output Compare Register value) * 64 µs (Counter increment rate) / 86.806 µs (Real byte rate at 115200 baud rate) ~= 57.5 bytes !< 64 (Buffer size)
  Experiments suggest, that more frequent interrupting results in a higher receive success rate.
  */
  ATOMIC_BLOCK(ATOMIC_RESTORESTATE) {
    OCR4A = (uint16_t)10;  // This value should be bewteen 1 and 78 when using prescale factor 1024
  }
#endif

  pinMode(LED_BUILTIN, OUTPUT);  // Indicator LED on when packet receive in progress.
}

void Communication::rx_read_from_serial_to_local_buffer() {
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

Communication::ReceiveCode Communication::receive_packet() {
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
      case 3:
        // Wait for message to be complete
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

/* 
If ENABLE_RX_INTERRUPT_POLLING is defined:
  Receives data from the local rx buffer which is filled by interrupt polling from the smaller buffer of the Serial class.
  The size of this buffer is not changable without modding the Arduino implementation, so this approach was developed.
  It is unclear if the resulting overhead when polling at a fixed rate by interrupt additioanlly to the interrupts caused when actually receiving data is affecting the runtime negatively.
Otherwise:
  Receives data from the serial port buffer directly by polling when called in loop().

Both methods read only the available chunk of data and then return thus leaving the message completion up for the next cycles.
*/
Communication::ReceiveCode Communication::async_receive() {
#ifdef ENABLE_RX_INTERRUPT_POLLING
  // Freeze hardware buffer read routine during evaluation of local buffer.
  disable_rx_serial_buffer_read_interrupt();
#else
  // Introduce same routine as what is used in an ISR when ENABLE_RX_INTERRUPT_POLLING is set.
  rx_read_from_serial_to_local_buffer();
#endif

  // Call implementation
  ReceiveCode code = receive_packet();

#ifdef ENABLE_RX_INTERRUPT_POLLING
  // Reenable hardware buffer read interrupts during loop
  enable_rx_serial_buffer_read_interrupt();
#endif

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
  if (packet_size > 0) {
    tx_buf_head += packet_size;
    return TransmitCode::TX_SUCCESS;
  }
  if (3 + measureJson(tx_doc) > TX_BUFFER_SIZE) return TransmitCode::TX_BUFFER_TOO_SMALL_TO_FIT_DATA;  // This occurs if the data is too big to fit in the transmit buffer
  return TransmitCode::TRANSMIT_RATE_TOO_LOW;                                                          // This occurs if the buffer cannot be depleted faster than new data is added. The buffer would overflow if the recent packet would be added, so it is discarded.
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

#ifdef ENABLE_RX_INTERRUPT_POLLING
// ----------------------- RX Serial Buffer Read Interrupt Handling ------------------------

void Communication::enable_rx_serial_buffer_read_interrupt() {
  TIMSK4 = 0;
  TIMSK4 |= (1 << OCIE4A);  // Enable compare match interrupt for OCR4A.
}

void Communication::disable_rx_serial_buffer_read_interrupt() {
  TIMSK4 = 0;  // Clear timer interrupt mask
}

ISR(TIMER4_COMPA_vect) {
  comm.rx_read_from_serial_to_local_buffer();
}
#endif
