#include <Arduino.h>
#include "src/communication/communication.hpp"
#include "src/encoder.hpp"
#include "src/mpu.hpp"

// CONTROLLER_UPDATE_INTERVAL_MS determines the frequency of sensor readings and actuation changes.
#define CONTROLLER_UPDATE_INTERVAL_MS 10

/* 
TX_INTERFACE_ENQUEUEMENT_INTERVAL_MS determines the frequency of appending data from the tx interface to the transmit buffer. This value can not be chosen arbitrarily, due to serial baud rate limitations.
According to this table (https://lucidar.me/en/serialib/most-used-baud-rates-table/) using a baud rate of 115200 serial data can be transmitted at a real byte rate of 86.806 µs per byte.
Depending on the size of the outgoing message and the interval in which data messages are queued up in the buffer, this could overload the transmit buffer in which case data would be lost.
The fastest interval that is theoretically save from causing data loss can be expressed as transmit_buffer_size * real_byte_rate which for example results in 88.89 ms for a buffer size of 1024 bytes and a baud rate of 115200 bauds per second. 
So the transmit pitch interval must not be faster than that. Additionally it should incorporate a margin for transmit buffer depletion delays that are caused by long running code.
These exist since the buffer is only asynchronously emptied (that is in parallel to other executing code) in chunks of 64 bytes at maximum on the Arduino Mega.
Consequently, if those 64 bytes are sent before more bytes are forwarded to the serial transmit hardware buffer, transmit delays occur.
*/
#define TX_INTERFACE_ENQUEUEMENT_INTERVAL_MS 100

Communication com;
Encoder wheel_position_rad{ ENC_PIN_CHA, ENC_PIN_CHB, encoder_isr, enc_counter, 0.5 * (2 * PI / 360) };
MinSegMPU mpu;

void setup() {
  Serial.begin(115200);  // Baud rate has been increased permanently on the HC-06 bluetooth module to allow for bigger messages
  Serial.setTimeout(1000);
  while (!Serial) {};

  // Sensor setup
  mpu.setup();
  wheel_position_rad.setup();
}

void loop() {
  com.message_clear();
  bool new_mpu_data = mpu.update();  // This has to be called as frequent as possible since it reads the MPU data from the FIFO buffer and stores it.

  static uint32_t control_cycle_start_ms = 0;
  if (new_mpu_data && millis() > control_cycle_start_ms + CONTROLLER_UPDATE_INTERVAL_MS) {
    control_cycle_start_ms = millis();

    // Initialize tx interface with sensor readings
    com.tx_data.wheel.pos_rad = wheel_position_rad();
    com.tx_data.wheel.pos_deriv_rad_s = wheel_position_rad.derivative();
    com.tx_data.tilt.angle_deg.from_acc = mpu.tilt_angle_from_acc_deg();
    com.tx_data.tilt.angle_deg.from_euler = mpu.tilt_angle_from_euler_deg();
    com.tx_data.tilt.angle_deriv_deg_s.from_acc = mpu.tilt_angle_from_acc_deg.derivative();
    com.tx_data.tilt.angle_deriv_deg_s.from_euler = mpu.tilt_angle_from_euler_deg.derivative();
    com.tx_data.tilt.vel_deg_s = mpu.tilt_vel_deg_s();

    // Reference controller state
    // double &wheel_pos_rad = tx_data.wheel.pos_rad;
    // double &tilt_angle_deg = ;
    // double &tilt_vel_deg_s = ;


    if (com.rx_data.control_state) {
      // Control loop here
    }

    // Finish loop
    Sensor::cycle_num++;
  }

  if (com.rx_data.calibration) calibrate_mpu();

  // Move data to the transmit buffer
  static uint32_t last_transmit_enqueuement_ms = 0;
  if (millis() > last_transmit_enqueuement_ms + TX_INTERFACE_ENQUEUEMENT_INTERVAL_MS) {
    last_transmit_enqueuement_ms = millis();
    switch (com.queue_for_transmit(com.tx_data.to_doc())) {
      case Communication::TransmitError::TX_SUCCESS:
        break;
      case Communication::TransmitError::TX_DOC_OVERFLOW:
        com.message_clear();
        com.message_queue_for_transmit(F("Transmit Error: TX_DOC_OVERFLOW"));
        break;
      case Communication::TransmitError::TRANSMIT_BUFFER_FULL:
        com.message_clear();
        com.message_transmit_now(F("Transmit Error: TRANSMIT_BUFFER_FULL"));
        break;
    }
  }

  // Deplete transmit buffer as possible without blocking
  com.async_transmit();
}

void calibrate_mpu() {
  com.message_transmit_now(F("Accel Gyro calibration will start in 3sec."));
  com.message_transmit_now(F("Please leave the device still on the flat plane."));
  delay(3000);
  com.message_transmit_now(F("Accel Gyro calibration start!"));
  mpu.calibrateAccelGyro();
  com.message_transmit_now(F("Accel Gyro calibration finished!"));

  delay(1000);

  com.message_transmit_now(F("Mag calibration will start in 3sec."));
  com.message_transmit_now(F("Please Wave device in a figure eight until done."));
  delay(3000);
  com.message_transmit_now(F("Mag calibration start!"));
  mpu.calibrateMag();
  com.message_transmit_now(F("Mag calibration finished!"));
  com.message_transmit_now(F("-------------------------"));
  com.message_transmit_now(F("    Calibration done!"));

  com.tx_data.calibrated = true;    // Tell gui that calibration procedure is finished
  com.rx_data.calibration = false;  // Prevent doing a calibration in the next loop again
}

void serialEvent() {
  switch (com.receive()) {
    case Communication::ReceiveError::RX_SUCCESS:
      com.message_queue_for_transmit(F("Packet received"));
      break;
    case Communication::ReceiveError::NO_DATA_AVAILABLE:
      // Should not happen since receive is called inside serialEvent()
      com.message_queue_for_transmit(F("Receive Error: NO_DATA_AVAILABLE"));
      break;
    case Communication::ReceiveError::DESERIALIZATION_FAILED:
      com.message_queue_for_transmit(F("Receive Error: DESERIALIZATION_FAILED"));
      break;
    case Communication::ReceiveError::PACKET_START_NOT_FOUND:
      com.message_queue_for_transmit(F("Receive Error: PACKET_START_NOT_FOUND"));
      break;
  }
}
