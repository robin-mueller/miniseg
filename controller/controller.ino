#include <Arduino.h>
#include "src/communication/comm.hpp"
#include "src/encoder.hpp"
#include "src/mpu.hpp"

/* 
TX_INTERFACE_UPDATE_INTERVAL_MS determines the frequency of appending data from the tx interface to the transmit buffer. This value can not be chosen arbitrarily, due to serial baud rate limitations.
According to this table (https://lucidar.me/en/serialib/most-used-baud-rates-table/) using a baud rate of 115200 serial data can be transmitted at a real byte rate of 86.806 µs per byte.
Depending on the size of the outgoing message and the interval in which data messages are queued up in the buffer, this could overload the transmit buffer in which case data would be lost.
The fastest interval that is theoretically save from causing data loss can be expressed as transmit_buffer_size * real_byte_rate which for example results in 88.89 ms for a buffer size of 1024 bytes and a baud rate of 115200 bauds per second. 
So the transmit enqueue interval must not be faster than that. Additionally it should incorporate a margin for transmit buffer depletion delays that are caused by long running code.
These exist since the buffer is only asynchronously emptied (that is in parallel to other executing code) in chunks of 64 bytes at maximum on the Arduino Mega.
Consequently, if those 64 bytes are sent before more bytes are forwarded to the serial transmit hardware buffer, transmit delays occur.
*/
#define TX_INTERFACE_UPDATE_INTERVAL_MS 100

Encoder wheel_angle_rad{ ENC_PIN_CHA, ENC_PIN_CHB, encoder_isr, enc_counter };
MinSegMPU mpu;

void setup() {
  Serial.begin(115200);  // Baud rate has been increased permanently on the HC-06 bluetooth module to allow for bigger messages
  while (!Serial) {};

  // Communication setup
  comm.setup();

  // Sensor setup
  mpu.setup();
  wheel_angle_rad.setup();
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
      static uint32_t last_rx_timestamp_us = 0;
      if (comm.rx_packet_info.timestamp_us > last_rx_timestamp_us) {
        comm.message_append(F("Receiving Packet of "));
        char msg_bytes_num[6];
        itoa(comm.rx_packet_info.message_length, msg_bytes_num, 10);
        comm.message_append(msg_bytes_num, sizeof(msg_bytes_num));
        comm.message_enqueue_for_transmit(F(" Bytes ..."));
        last_rx_timestamp_us = comm.rx_packet_info.timestamp_us;
      }
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
  if (millis() > control_cycle_start_us * 1e-3 + comm.rx_data.parameters.variable.General.h_ms) {
    comm.tx_data.control.cycle_us = micros() - control_cycle_start_us;
    control_cycle_start_us = micros();

    // Sensor readings
    comm.tx_data.sensor.wheel.angle_rad = wheel_angle_rad();
    comm.tx_data.sensor.wheel.angle_deriv_rad_s = wheel_angle_rad.derivative();
    comm.tx_data.sensor.tilt.angle_rad.from_acc = mpu.tilt_angle_from_acc_rad();
    comm.tx_data.sensor.tilt.angle_rad.from_euler = mpu.tilt_angle_from_euler_rad();
    comm.tx_data.sensor.tilt.vel_rad_s = mpu.tilt_vel_rad_s();

    // System output
    double &y1 = comm.tx_data.sensor.tilt.vel_rad_s;
    double &y2 = comm.tx_data.sensor.tilt.angle_rad.from_acc;
    double &y3 = comm.tx_data.sensor.wheel.angle_rad;

    static double u = 0;
    static double x1 = 0, x2 = 0, x3 = 0, x4 = 0;  // persistent state values that are calculated recursively by the observer's state equation
    double x1_corr, x2_corr, x3_corr, x4_corr;     // state values that are corrected to contain the observer's direct term (using the most recent measurement y)

    // Correct state estimate
    correct_state_estimation(x1_corr, x2_corr, x3_corr, x4_corr, x1, x2, x3, x4, y1, y2, y3);

    comm.tx_data.observer.tilt.vel_rad_s = x1_corr;
    comm.tx_data.observer.tilt.angle_rad = x2_corr;
    comm.tx_data.observer.wheel.vel_rad_s = x3_corr;
    comm.tx_data.observer.wheel.angle_rad = x4_corr;

    if (comm.rx_data.control_state) {
      calculate_control_signal(u, x1_corr, x2_corr, x3_corr, x4_corr);
    } else {
      u = comm.rx_data.pos_setpoint;
    }
    int16_t motor_val = write_motor_voltage(u, 9, 2);

    comm.tx_data.control.u = u;
    comm.tx_data.control.motor = motor_val;

    // Generate state estimate for next cycle
    predict_state_estimation(x1, x2, x3, x4, u, y1, y2, y3);

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

void predict_state_estimation(double &x1, double &x2, double &x3, double &x4, double &u, double &y1, double &y2, double &y3) {
  double &l11 = comm.rx_data.parameters.inferred.ObserverGain.l11;
  double &l12 = comm.rx_data.parameters.inferred.ObserverGain.l12;
  double &l13 = comm.rx_data.parameters.inferred.ObserverGain.l13;
  double &l21 = comm.rx_data.parameters.inferred.ObserverGain.l21;
  double &l22 = comm.rx_data.parameters.inferred.ObserverGain.l22;
  double &l23 = comm.rx_data.parameters.inferred.ObserverGain.l23;
  double &l31 = comm.rx_data.parameters.inferred.ObserverGain.l31;
  double &l32 = comm.rx_data.parameters.inferred.ObserverGain.l32;
  double &l33 = comm.rx_data.parameters.inferred.ObserverGain.l33;
  double &l41 = comm.rx_data.parameters.inferred.ObserverGain.l41;
  double &l42 = comm.rx_data.parameters.inferred.ObserverGain.l42;
  double &l43 = comm.rx_data.parameters.inferred.ObserverGain.l43;

  double &o_phi11 = comm.rx_data.parameters.inferred.ObserverPhi.phi11;
  double &o_phi12 = comm.rx_data.parameters.inferred.ObserverPhi.phi12;
  double &o_phi13 = comm.rx_data.parameters.inferred.ObserverPhi.phi13;
  double &o_phi14 = comm.rx_data.parameters.inferred.ObserverPhi.phi14;
  double &o_phi21 = comm.rx_data.parameters.inferred.ObserverPhi.phi21;
  double &o_phi22 = comm.rx_data.parameters.inferred.ObserverPhi.phi22;
  double &o_phi23 = comm.rx_data.parameters.inferred.ObserverPhi.phi23;
  double &o_phi24 = comm.rx_data.parameters.inferred.ObserverPhi.phi24;
  double &o_phi31 = comm.rx_data.parameters.inferred.ObserverPhi.phi31;
  double &o_phi32 = comm.rx_data.parameters.inferred.ObserverPhi.phi32;
  double &o_phi33 = comm.rx_data.parameters.inferred.ObserverPhi.phi33;
  double &o_phi34 = comm.rx_data.parameters.inferred.ObserverPhi.phi34;
  double &o_phi41 = comm.rx_data.parameters.inferred.ObserverPhi.phi41;
  double &o_phi42 = comm.rx_data.parameters.inferred.ObserverPhi.phi42;
  double &o_phi43 = comm.rx_data.parameters.inferred.ObserverPhi.phi43;
  double &o_phi44 = comm.rx_data.parameters.inferred.ObserverPhi.phi44;

  double x1_prev = x1;
  double x2_prev = x2;
  double x3_prev = x3;
  double x4_prev = x4;

  x1 = o_phi11 * x1_prev + o_phi12 * x2_prev + o_phi13 * x3_prev + o_phi14 * x4_prev + l11 * y1 + l12 * y2 + l13 * y3;
  x2 = o_phi21 * x1_prev + o_phi22 * x2_prev + o_phi23 * x3_prev + o_phi24 * x4_prev + l21 * y1 + l22 * y2 + l23 * y3;
  x3 = o_phi31 * x1_prev + o_phi32 * x2_prev + o_phi33 * x3_prev + o_phi34 * x4_prev + l31 * y1 + l32 * y2 + l33 * y3;
  x4 = o_phi41 * x1_prev + o_phi42 * x2_prev + o_phi43 * x3_prev + o_phi44 * x4_prev + l41 * y1 + l42 * y2 + l43 * y3;
}

void correct_state_estimation(double &x1, double &x2, double &x3, double &x4, double &x1_prev, double &x2_prev, double &x3_prev, double &x4_prev, double &y1, double &y2, double &y3) {
  double &mx11 = comm.rx_data.parameters.inferred.ObserverInnoGain.mx11;
  double &mx12 = comm.rx_data.parameters.inferred.ObserverInnoGain.mx12;
  double &mx13 = comm.rx_data.parameters.inferred.ObserverInnoGain.mx13;
  double &mx21 = comm.rx_data.parameters.inferred.ObserverInnoGain.mx21;
  double &mx22 = comm.rx_data.parameters.inferred.ObserverInnoGain.mx22;
  double &mx23 = comm.rx_data.parameters.inferred.ObserverInnoGain.mx23;
  double &mx31 = comm.rx_data.parameters.inferred.ObserverInnoGain.mx31;
  double &mx32 = comm.rx_data.parameters.inferred.ObserverInnoGain.mx32;
  double &mx33 = comm.rx_data.parameters.inferred.ObserverInnoGain.mx33;
  double &mx41 = comm.rx_data.parameters.inferred.ObserverInnoGain.mx41;
  double &mx42 = comm.rx_data.parameters.inferred.ObserverInnoGain.mx42;
  double &mx43 = comm.rx_data.parameters.inferred.ObserverInnoGain.mx43;

  double y1_err = y1 - x1_prev;
  double y2_err = y2 - x2_prev;
  double y3_err = y3 - x4_prev;

  x1 = x1_prev + mx11 * y1_err + mx12 * y2_err + mx13 * y3_err;
  x2 = x2_prev + mx21 * y1_err + mx22 * y2_err + mx23 * y3_err;
  x3 = x3_prev + mx31 * y1_err + mx32 * y2_err + mx33 * y3_err;
  x4 = x4_prev + mx41 * y1_err + mx42 * y2_err + mx43 * y3_err;
}

void calculate_control_signal(double &u, double &x1, double &x2, double &x3, double &x4) {
  double &k1 = comm.rx_data.parameters.variable.ControlGain.k1;
  double &k2 = comm.rx_data.parameters.variable.ControlGain.k2;
  double &k3 = comm.rx_data.parameters.variable.ControlGain.k3;
  double &k4 = comm.rx_data.parameters.variable.ControlGain.k4;

  u = -k1 * x1 - k2 * (x2 + comm.rx_data.parameters.variable.General.alpha_off) - k3 * x3 - k4 * x4;
}

int16_t write_motor_voltage(double volt, double saturation, uint8_t decimals) {
  long scale_amp = pow(10, decimals);
  long volt_int_max = round(saturation * scale_amp);
  long volt_int = constrain(round(volt * scale_amp), -volt_int_max, volt_int_max);  // map does integer calculations, so we increase the resolution by scaling up the double value by scale_amp
  int16_t motor_val = map(volt_int, -volt_int_max, volt_int_max, -UINT8_MAX, UINT8_MAX);

  // Motor deadzone compensation
  if (abs(motor_val) < comm.rx_data.parameters.variable.General.r_stop) motor_val = 0;
  else {
    uint8_t abs_deadzone_compensated_motor_val = map(abs(motor_val), 0, UINT8_MAX, comm.rx_data.parameters.variable.General.r_start, UINT8_MAX);
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