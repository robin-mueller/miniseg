#include <Arduino.h>
#include "src/communication/comm.hpp"
#include "src/encoder.hpp"
#include "src/mpu.hpp"

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

Encoder wheel_position_rad{ ENC_PIN_CHA, ENC_PIN_CHB, encoder_isr, enc_counter };
MinSegMPU mpu;

void setup() {
  Serial.begin(115200);  // Baud rate has been increased permanently on the HC-06 bluetooth module to allow for bigger messages
  while (!Serial) {};

  // Communication setup
  comm.setup();

  // Sensor setup
  mpu.setup();
  wheel_position_rad.setup();
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

  mpu.update();  // This has to be called as frequent as possible to keep up with the configured MPU FIFO buffer sample rate

  static uint32_t control_cycle_start_us = micros();
  if (millis() > control_cycle_start_us * 1e-3 + comm.rx_data.parameters.General.h_ms) {
    comm.tx_data.control.cycle_us = micros() - control_cycle_start_us;
    control_cycle_start_us = micros();

    // Initialize tx interface with sensor readings
    comm.tx_data.wheel.pos_rad = wheel_position_rad();
    comm.tx_data.wheel.pos_deriv_rad_s = wheel_position_rad.derivative();
    comm.tx_data.tilt.angle_rad.from_acc = mpu.tilt_angle_from_acc_rad();
    comm.tx_data.tilt.angle_rad.from_euler = mpu.tilt_angle_from_euler_rad();
    comm.tx_data.tilt.vel_rad_s = mpu.tilt_vel_rad_s();

    // Reference controller state
    double &alpha_dot = comm.tx_data.tilt.vel_rad_s;
    double alpha = comm.tx_data.tilt.angle_rad.from_euler + comm.rx_data.parameters.General.alpha_off;
    double &theta_dot = comm.tx_data.wheel.pos_deriv_rad_s;
    double &theta = comm.tx_data.wheel.pos_rad;

    double &k1 = comm.rx_data.parameters.K.k1;
    double &k2 = comm.rx_data.parameters.K.k2;
    double &k3 = comm.rx_data.parameters.K.k3;
    double &k4 = comm.rx_data.parameters.K.k4;

    double u = 0;

    if (comm.rx_data.control_state) {
      u = -k1 * alpha_dot - k2 * alpha - k3 * theta_dot - k4 * theta;
    } else {
      u = comm.rx_data.pos_setpoint;
    }
    int16_t motor_val = write_motor_voltage(u, 9, 3);

    comm.tx_data.control.u = u;
    comm.tx_data.control.motor = motor_val;

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
        comm.message_transmit_now(F("Transmit Error: TX_DOC_OVERFLOW"));
        break;
      case Communication::TransmitCode::TX_BUFFER_TOO_SMALL_TO_FIT_DATA:
        comm.message_transmit_now(F("Transmit Error: TX_BUFFER_TOO_SMALL_TO_FIT_DATA"));
        break;
      case Communication::TransmitCode::TRANSMIT_RATE_TOO_LOW:
        comm.message_transmit_now(F("Transmit Error: TRANSMIT_RATE_TOO_LOW"));
        break;
    }
  }

  // Deplete transmit buffer without blocking procedurally
  comm.async_transmit();
}

void calibrate_mpu() {
  comm.tx_data.calibrated = false;
  comm.enqueue_for_transmit(comm.tx_data.to_doc());
  while (comm.async_transmit() > 0) {}

  // Only acc gyro calibration necessary
  comm.message_transmit_now(F("Accel Gyro calibration will start in 3sec."));
  comm.message_transmit_now(F("Please leave the device still on the flat plane."));
  delay(2000);
  comm.message_transmit_now(F("Accel Gyro calibration start!"));
  mpu.calibrateAccelGyro();
  comm.message_transmit_now(F("Accel Gyro calibration finished!"));
  comm.message_transmit_now(F("-------------------------"));
  comm.message_transmit_now(F("    Calibration done!"));

  comm.tx_data.calibrated = true;    // Tell gui that calibration procedure is finished
  comm.rx_data.calibration = false;  // Prevent doing a calibration in the next loop again

  // Adresses issue (https://github.com/hideakitai/MPU9250/issues/88) that biases are not actually forwarded to the sensor after calibration. Do it manually here.
  mpu.setAccBias(mpu.getAccBiasX(), mpu.getAccBiasY(), mpu.getAccBiasZ());
  mpu.setGyroBias(mpu.getGyroBiasX(), mpu.getGyroBiasY(), mpu.getGyroBiasZ());
}

int16_t write_motor_voltage(double volt, double saturation, uint8_t decimals) {
  long volt_int_max = round(saturation * decimals);
  long volt_int = constrain(round(volt * decimals), -volt_int_max, volt_int_max);  // map does integer calculations, so we have to increase the resolution
  int16_t motor_val = map(volt_int, -volt_int_max, volt_int_max, -UINT8_MAX, UINT8_MAX);

  // Motor deadzone compensation
  if (abs(motor_val) < comm.rx_data.parameters.General.r_stop) motor_val = 0;
  else {
    uint8_t abs_deadzone_compensated_motor_val = map(abs(motor_val), 0, UINT8_MAX, comm.rx_data.parameters.General.r_start, UINT8_MAX);
    if (motor_val < 0) motor_val = -(int16_t)abs_deadzone_compensated_motor_val;
    else motor_val = abs_deadzone_compensated_motor_val;
  }

  if (motor_val < 0) {
    analogWrite(PD4, -motor_val);
    analogWrite(PD5, 0);
  } else {
    analogWrite(PD4, 0);
    analogWrite(PD5, motor_val);
  }
  return motor_val;
}
