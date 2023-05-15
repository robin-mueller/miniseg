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

const double WHEEL_RAD_TO_MM = 130.0 / (2 * PI);
const double WHEEL_MM_TO_RAD = 1 / WHEEL_RAD_TO_MM;

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
  bool prev_control_state = comm.rx_data.control_state;
  static bool reset_control = true;

  // Receive available data
  switch (comm.async_receive()) {
    case Communication::ReceiveCode::NO_DATA_AVAILABLE:
      break;
    case Communication::ReceiveCode::PACKET_RECEIVED:
      comm.message_append(F("## Packet ["));
      char msg_bytes_num[6];
      itoa(comm.rx_packet_info.message_length, msg_bytes_num, 10);
      comm.message_append(msg_bytes_num, sizeof(msg_bytes_num));
      comm.message_enqueue_for_transmit(F(" Bytes] received!"));
      break;
    case Communication::ReceiveCode::RX_IN_PROGRESS:
      static uint32_t last_rx_timestamp_us = 0;
      if (comm.rx_packet_info.timestamp_us > last_rx_timestamp_us) {  // Only send this message once per rx process
        comm.message_append(F("Receiving Packet ["));
        char msg_bytes_num[6];
        itoa(comm.rx_packet_info.message_length, msg_bytes_num, 10);
        comm.message_append(msg_bytes_num, sizeof(msg_bytes_num));
        comm.message_enqueue_for_transmit(F(" Bytes] ..."));
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

  // Reset positional variables when control state is set to true to be able to restart the control from the inital position
  if (prev_control_state == false && comm.rx_data.control_state == true) {
    reset_control = true;  // This flag will be reset once the asynchronous control cycle became aware of the state change
  }

  if (comm.rx_data.calibration) calibrate_mpu();

  mpu.update();  // This has to be called as frequent as possible to keep up with the configured MPU FIFO buffer sample rate

  static uint32_t control_cycle_start_us = micros();
  if (millis() > control_cycle_start_us * 1e-3 + comm.rx_data.parameters.variable.General.h_ms) {
    comm.tx_data.control.cycle_us = micros() - control_cycle_start_us;
    control_cycle_start_us = micros();

    // System states
    static double x1 = 0, x2 = 0, x3 = 0, x4 = 0;          // Persistent state values that are calculated recursively by the observer's state equation
    static double x_m1 = 0, x_m2 = 0, x_m3 = 0, x_m4 = 0;  // Persistent state values that are calculated recursively by the feedforward model's state equation
    static double xi = 0;                                  // Persistent integral action state for position control
    double x1_corr, x2_corr, x3_corr, x4_corr;             // State values that are corrected to contain the observer's direct term (using the most recent measurement y)

    if (reset_control) {
      wheel_angle_rad.reset();
      xi = 0;
      x_m1 = 0;
      x_m2 = 0;
      x_m3 = 0;
      x_m4 = 0;

      reset_control = false;
    }

    // Sensor readings
    comm.tx_data.sensor.wheel.angle_rad = wheel_angle_rad();
    comm.tx_data.sensor.wheel.angle_deriv_rad_s = wheel_angle_rad.derivative();
    comm.tx_data.sensor.tilt.angle_rad = mpu.tilt_angle_from_acc_rad();
    comm.tx_data.sensor.tilt.vel_rad_s = mpu.tilt_vel_rad_s();

    // System output measurements
    double &y1 = comm.tx_data.sensor.tilt.vel_rad_s;
    double &y2 = comm.tx_data.sensor.tilt.angle_rad;
    double &y3 = comm.tx_data.sensor.wheel.angle_rad;

    // Correct state estimate
    correct_state_estimation(x1_corr, x2_corr, x3_corr, x4_corr, x1, x2, x3, x4, y1, y2, y3);

    // Estimated system state x_hat
    comm.tx_data.observer.tilt.vel_rad_s = x1_corr;
    comm.tx_data.observer.tilt.angle_rad = x2_corr;
    comm.tx_data.observer.wheel.vel_rad_s = x3_corr;
    comm.tx_data.observer.wheel.angle_rad = x4_corr;
    comm.tx_data.observer.position.z_mm = -x4_corr * WHEEL_RAD_TO_MM;

    // Feed Forward Model states
    comm.tx_data.ff_model.tilt.vel_rad_s = x_m1;
    comm.tx_data.ff_model.tilt.angle_rad = x_m2;
    comm.tx_data.ff_model.wheel.vel_rad_s = x_m3;
    comm.tx_data.ff_model.wheel.angle_rad = x_m4;
    comm.tx_data.ff_model.position.z_mm = -x_m4 * WHEEL_RAD_TO_MM;

    double r_rad = -comm.rx_data.pos_setpoint_mm * WHEEL_MM_TO_RAD;  // Wheel angle setpoint

    double u = 0, u_bal, u_pos, u_ff;
    calculate_feedforward_control_signal(u_ff, x_m1, x_m2, x_m3, x_m4, r_rad);
    calculate_feedback_control_signal(u_bal, u_pos, x1_corr, x2_corr, x3_corr, x4_corr, xi, x_m1, x_m2, x_m3, x_m4);
    if (comm.rx_data.control_state) {
      u = u_bal + u_pos + u_ff;
    }
    int16_t motor_val = write_motor_voltage(u, 9, 2);

    comm.tx_data.control.signal.u = u;
    comm.tx_data.control.signal.u_bal = u_bal;
    comm.tx_data.control.signal.u_pos = u_pos;
    comm.tx_data.control.signal.u_ff = u_ff;
    comm.tx_data.control.motor = motor_val;

    // Calculate (predict) next cycle values (k+1)
    predict_state_estimation(x1, x2, x3, x4, u, y1, y2, y3);
    predict_feedforward_model_state(x_m1, x_m2, x_m3, x_m4, u_ff);
    predict_integral_action_state(xi, x4_corr, r_rad);

    // Finish loop
    Sensor::cycle_num++;
  }

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

  // Deplete transmit buffer procedurally without blocking
  comm.async_transmit();
}

void calibrate_mpu() {
  comm.tx_data.calibrated = false;
  comm.enqueue_for_transmit(comm.tx_data.to_doc());
  while (comm.async_transmit() > 0) {}  // Empty transmit buffer

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
  double &l11 = comm.rx_data.parameters.inferred.observer.gain.l11;
  double &l12 = comm.rx_data.parameters.inferred.observer.gain.l12;
  double &l13 = comm.rx_data.parameters.inferred.observer.gain.l13;
  double &l21 = comm.rx_data.parameters.inferred.observer.gain.l21;
  double &l22 = comm.rx_data.parameters.inferred.observer.gain.l22;
  double &l23 = comm.rx_data.parameters.inferred.observer.gain.l23;
  double &l31 = comm.rx_data.parameters.inferred.observer.gain.l31;
  double &l32 = comm.rx_data.parameters.inferred.observer.gain.l32;
  double &l33 = comm.rx_data.parameters.inferred.observer.gain.l33;
  double &l41 = comm.rx_data.parameters.inferred.observer.gain.l41;
  double &l42 = comm.rx_data.parameters.inferred.observer.gain.l42;
  double &l43 = comm.rx_data.parameters.inferred.observer.gain.l43;

  double &o_phi11 = comm.rx_data.parameters.inferred.observer.phi.phi11;
  double &o_phi12 = comm.rx_data.parameters.inferred.observer.phi.phi12;
  double &o_phi13 = comm.rx_data.parameters.inferred.observer.phi.phi13;
  double &o_phi14 = comm.rx_data.parameters.inferred.observer.phi.phi14;
  double &o_phi21 = comm.rx_data.parameters.inferred.observer.phi.phi21;
  double &o_phi22 = comm.rx_data.parameters.inferred.observer.phi.phi22;
  double &o_phi23 = comm.rx_data.parameters.inferred.observer.phi.phi23;
  double &o_phi24 = comm.rx_data.parameters.inferred.observer.phi.phi24;
  double &o_phi31 = comm.rx_data.parameters.inferred.observer.phi.phi31;
  double &o_phi32 = comm.rx_data.parameters.inferred.observer.phi.phi32;
  double &o_phi33 = comm.rx_data.parameters.inferred.observer.phi.phi33;
  double &o_phi34 = comm.rx_data.parameters.inferred.observer.phi.phi34;
  double &o_phi41 = comm.rx_data.parameters.inferred.observer.phi.phi41;
  double &o_phi42 = comm.rx_data.parameters.inferred.observer.phi.phi42;
  double &o_phi43 = comm.rx_data.parameters.inferred.observer.phi.phi43;
  double &o_phi44 = comm.rx_data.parameters.inferred.observer.phi.phi44;

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
  double &mx11 = comm.rx_data.parameters.inferred.observer.innoGain.mx11;
  double &mx12 = comm.rx_data.parameters.inferred.observer.innoGain.mx12;
  double &mx13 = comm.rx_data.parameters.inferred.observer.innoGain.mx13;
  double &mx21 = comm.rx_data.parameters.inferred.observer.innoGain.mx21;
  double &mx22 = comm.rx_data.parameters.inferred.observer.innoGain.mx22;
  double &mx23 = comm.rx_data.parameters.inferred.observer.innoGain.mx23;
  double &mx31 = comm.rx_data.parameters.inferred.observer.innoGain.mx31;
  double &mx32 = comm.rx_data.parameters.inferred.observer.innoGain.mx32;
  double &mx33 = comm.rx_data.parameters.inferred.observer.innoGain.mx33;
  double &mx41 = comm.rx_data.parameters.inferred.observer.innoGain.mx41;
  double &mx42 = comm.rx_data.parameters.inferred.observer.innoGain.mx42;
  double &mx43 = comm.rx_data.parameters.inferred.observer.innoGain.mx43;

  double y1_err = y1 - x1_prev;
  double y2_err = y2 - x2_prev;
  double y3_err = y3 - x4_prev;

  x1 = x1_prev + mx11 * y1_err + mx12 * y2_err + mx13 * y3_err;
  x2 = x2_prev + mx21 * y1_err + mx22 * y2_err + mx23 * y3_err;
  x3 = x3_prev + mx31 * y1_err + mx32 * y2_err + mx33 * y3_err;
  x4 = x4_prev + mx41 * y1_err + mx42 * y2_err + mx43 * y3_err;
}

void predict_feedforward_model_state(double &x1, double &x2, double &x3, double &x4, double &u_ff) {
  double &phi11 = comm.rx_data.parameters.inferred.ff.phi.phi11;
  double &phi12 = comm.rx_data.parameters.inferred.ff.phi.phi12;
  double &phi13 = comm.rx_data.parameters.inferred.ff.phi.phi13;
  double &phi14 = comm.rx_data.parameters.inferred.ff.phi.phi14;
  double &phi21 = comm.rx_data.parameters.inferred.ff.phi.phi21;
  double &phi22 = comm.rx_data.parameters.inferred.ff.phi.phi22;
  double &phi23 = comm.rx_data.parameters.inferred.ff.phi.phi23;
  double &phi24 = comm.rx_data.parameters.inferred.ff.phi.phi24;
  double &phi31 = comm.rx_data.parameters.inferred.ff.phi.phi31;
  double &phi32 = comm.rx_data.parameters.inferred.ff.phi.phi32;
  double &phi33 = comm.rx_data.parameters.inferred.ff.phi.phi33;
  double &phi34 = comm.rx_data.parameters.inferred.ff.phi.phi34;
  double &phi41 = comm.rx_data.parameters.inferred.ff.phi.phi41;
  double &phi42 = comm.rx_data.parameters.inferred.ff.phi.phi42;
  double &phi43 = comm.rx_data.parameters.inferred.ff.phi.phi43;
  double &phi44 = comm.rx_data.parameters.inferred.ff.phi.phi44;

  double &gam1 = comm.rx_data.parameters.inferred.ff.gamma.gam1;
  double &gam2 = comm.rx_data.parameters.inferred.ff.gamma.gam2;
  double &gam3 = comm.rx_data.parameters.inferred.ff.gamma.gam3;
  double &gam4 = comm.rx_data.parameters.inferred.ff.gamma.gam4;

  double x1_prev = x1;
  double x2_prev = x2;
  double x3_prev = x3;
  double x4_prev = x4;

  x1 = phi11 * x1_prev + phi12 * x2_prev + phi13 * x3_prev + phi14 * x4_prev + gam1 * u_ff;
  x2 = phi21 * x1_prev + phi22 * x2_prev + phi23 * x3_prev + phi24 * x4_prev + gam2 * u_ff;
  x3 = phi31 * x1_prev + phi32 * x2_prev + phi33 * x3_prev + phi34 * x4_prev + gam3 * u_ff;
  x4 = phi41 * x1_prev + phi42 * x2_prev + phi43 * x3_prev + phi44 * x4_prev + gam4 * u_ff;
}

void predict_integral_action_state(double &xi, double &x4, double &r_rad) {
  double h = comm.rx_data.parameters.variable.General.h_ms * 1e-3;

  xi += h * (r_rad - x4);
}

void calculate_feedforward_control_signal(double &u_ff, double &x1, double &x2, double &x3, double &x4, double &u_c) {
  double &k_m1 = comm.rx_data.parameters.inferred.ff.Km.k1;
  double &k_m2 = comm.rx_data.parameters.inferred.ff.Km.k2;
  double &k_m3 = comm.rx_data.parameters.inferred.ff.Km.k3;
  double &k_m4 = comm.rx_data.parameters.inferred.ff.Km.k4;

  double &k_c = comm.rx_data.parameters.inferred.ff.Kc;

  u_ff = k_c * u_c - k_m1 * x1 - k_m2 * x2 - k_m3 * x3 - k_m4 * x4;
}

void calculate_feedback_control_signal(double &u_bal, double &u_pos, double &x1, double &x2, double &x3, double &x4, double &xi, double &x_m1, double &x_m2, double &x_m3, double &x_m4) {
  double &k1 = comm.rx_data.parameters.variable.BalanceControl.k1;
  double &k2 = comm.rx_data.parameters.variable.BalanceControl.k2;
  double &k3 = comm.rx_data.parameters.variable.BalanceControl.k3;
  double &k4 = comm.rx_data.parameters.variable.PositionControl.k4;
  double &ki = comm.rx_data.parameters.variable.PositionControl.ki;

  u_bal = k1 * (x_m1 - x1) + k2 * (x_m2 + comm.rx_data.parameters.variable.General.alpha_off - x2) + k3 * (x_m3 - x3);
  u_pos = k4 * (x_m4 - x4) - ki * xi;
}

int16_t write_motor_voltage(double volt, double saturation, uint8_t decimals) {
  const long scale_amp = pow(10, decimals);
  const long volt_int_max = round(saturation * scale_amp);
  const long volt_int = constrain(round(volt * scale_amp), -volt_int_max, volt_int_max);  // map does integer calculations, so we increase the resolution by scaling up the double value by scale_amp
  uint8_t motor_val = map(abs(volt_int), 0, volt_int_max, 0, UINT8_MAX);

  // Motor deadzone compensation
  uint8_t &stop_threshold = comm.rx_data.parameters.variable.General.m_stop;
  uint8_t &start_threshold = comm.rx_data.parameters.variable.General.m_start;
  motor_val = motor_val < stop_threshold ? 0 : map(motor_val, 0, UINT8_MAX, start_threshold, UINT8_MAX);

  // Positive means to rotate in positive direction
  if (volt < 0) {
    analogWrite(PD4, motor_val);
    analogWrite(PD5, 0);
    return -motor_val;
  } else {
    analogWrite(PD4, 0);
    analogWrite(PD5, motor_val);
    return motor_val;
  }
}
