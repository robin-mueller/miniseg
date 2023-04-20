#include <Arduino.h>
#include "src/Communication/comm.hpp"
#include "src/encoder.hpp"
#include "src/mpu.hpp"

// CONTROLLER_UPDATE_INTERVAL_MS determines the frequency of sensor readings and actuation changes.
#define CONTROLLER_UPDATE_INTERVAL_MS 10

/* 
TX_INTERFACE_UPDATE_INTERVAL_MS determines the frequency of appending data from the tx interface to the transmit buffer. This value can not be chosen arbitrarily, due to serial baud rate limitations.
According to this table (https://lucidar.me/en/serialib/most-used-baud-rates-table/) using a baud rate of 115200 serial data can be transmitted at a real byte rate of 86.806 µs per byte.
Depending on the size of the outgoing message and the interval in which data messages are queued up in the buffer, this could overload the transmit buffer in which case data would be lost.
The fastest interval that is theoretically save from causing data loss can be expressed as transmit_buffer_size * real_byte_rate which for example results in 88.89 ms for a buffer size of 1024 bytes and a baud rate of 115200 bauds per second. 
So the transmit pitch interval must not be faster than that. Additionally it should incorporate a margin for transmit buffer depletion delays that are caused by long running code.
These exist since the buffer is only asynchronously emptied (that is in parallel to other executing code) in chunks of 64 bytes at maximum on the Arduino Mega.
Consequently, if those 64 bytes are sent before more bytes are forwarded to the serial transmit hardware buffer, transmit delays occur.
*/
#define TX_INTERFACE_UPDATE_INTERVAL_MS 100

Encoder wheel_position_rad{ ENC_PIN_CHA, ENC_PIN_CHB, encoder_isr, enc_counter, 0.5 * (2 * PI / 360) };
MinSegMPU mpu;

void setup() {
  Serial.begin(115200);  // Baud rate has been increased permanently on the HC-06 bluetooth module to allow for bigger messages
  while (!Serial) {};

  // Sensor setup
  mpu.setup();
  wheel_position_rad.setup();
  comm.setup();
}

void loop() {
  // Receive available data
  switch (comm.async_receive()) {
    case Communication::ReceiveCode::NO_DATA_AVAILABLE:
      break;
    case Communication::ReceiveCode::PACKET_RECEIVED:
      comm.message_enqueue_for_transmit(F("Packet received"));
      break;
    case Communication::ReceiveCode::RX_IN_PROGRESS:
      comm.message_enqueue_for_transmit(F("Receiving ..."));
      break;
    case Communication::ReceiveCode::MESSAGE_EXCEEDS_RX_BUFFER_SIZE:
      comm.message_enqueue_for_transmit(F("Receive Error: MESSAGE_EXCEEDS_RX_BUFFER_SIZE"));
      break;
    case Communication::ReceiveCode::DESERIALIZATION_FAILED:
      comm.message_enqueue_for_transmit(F("Receive Error: DESERIALIZATION_FAILED"));
      break;
  }

  bool new_mpu_data = mpu.update();  // This has to be called as frequent as possible to keep up with the configured sensor sample rate

  static uint32_t control_cycle_start_ms = 0;
  if (new_mpu_data && millis() > control_cycle_start_ms + CONTROLLER_UPDATE_INTERVAL_MS) {
    control_cycle_start_ms = millis();

    // Initialize tx interface with sensor readings
    comm.tx_data.wheel.pos_rad = wheel_position_rad();
    comm.tx_data.wheel.pos_deriv_rad_s = wheel_position_rad.derivative();
    comm.tx_data.tilt.angle_deg.from_acc = mpu.tilt_angle_from_acc_deg();
    comm.tx_data.tilt.angle_deg.from_euler = mpu.tilt_angle_from_euler_deg();
    comm.tx_data.tilt.angle_deriv_deg_s.from_acc = mpu.tilt_angle_from_acc_deg.derivative();
    comm.tx_data.tilt.angle_deriv_deg_s.from_euler = mpu.tilt_angle_from_euler_deg.derivative();
    comm.tx_data.tilt.vel_deg_s = mpu.tilt_vel_deg_s();

    // Reference controller state
    // double &wheel_pos_rad = tx_data.wheel.pos_rad;
    // double &tilt_angle_deg = ;
    // double &tilt_vel_deg_s = ;


    if (comm.rx_data.control_state) {
      // Control loop here
    }

    // Finish loop
    Sensor::cycle_num++;
  }

  if (comm.rx_data.calibration) calibrate_mpu();

  // Move data to the transmit buffer
  static uint32_t last_tx_update_ms = 0;
  if (millis() > last_tx_update_ms + TX_INTERFACE_UPDATE_INTERVAL_MS) {
    last_tx_update_ms = millis();
    switch (comm.enqueue_for_transmit(comm.tx_data.to_doc())) {
      case Communication::TransmitCode::TX_SUCCESS:
        break;
      case Communication::TransmitCode::TX_DOC_OVERFLOW:
        comm.message_enqueue_for_transmit(F("Transmit Error: TX_DOC_OVERFLOW"));
        break;
      case Communication::TransmitCode::INSUFFICIENT_TRANSMIT_RATE:
        comm.message_transmit_now(F("Transmit Error: INSUFFICIENT_TRANSMIT_RATE"));
        break;
      case Communication::TransmitCode::PACKET_EXCEEDS_TX_BUFFER_SIZE:
        comm.message_transmit_now(F("Transmit Error: PACKET_EXCEEDS_TX_BUFFER_SIZE"));
        break;
    }
  }

  // Deplete transmit buffer as possible without blocking
  comm.async_transmit();
}

void calibrate_mpu() {
  comm.message_transmit_now(F("Accel Gyro calibration will start in 3sec."));
  comm.message_transmit_now(F("Please leave the device still on the flat plane."));
  delay(3000);
  comm.message_transmit_now(F("Accel Gyro calibration start!"));
  mpu.calibrateAccelGyro();
  comm.message_transmit_now(F("Accel Gyro calibration finished!"));

  delay(1000);

  comm.message_transmit_now(F("Mag calibration will start in 3sec."));
  comm.message_transmit_now(F("Please Wave device in a figure eight until done."));
  delay(3000);
  comm.message_transmit_now(F("Mag calibration start!"));
  mpu.calibrateMag();
  comm.message_transmit_now(F("Mag calibration finished!"));
  comm.message_transmit_now(F("-------------------------"));
  comm.message_transmit_now(F("    Calibration done!"));

  comm.tx_data.calibrated = true;    // Tell gui that calibration procedure is finished
  comm.rx_data.calibration = false;  // Prevent doing a calibration in the next loop again
}
