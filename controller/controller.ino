#include <Arduino.h>
#include "src/communication/communication.hpp"
#include "src/encoder.hpp"
#include "src/mpu.hpp"

/* 
CONTROLLER_UPDATE_INTERVAL_MS determines the frequency of sensor readings and actuation changes.
SERIAL_TRANSMIT_INTERVAL_MS determines the frequency of serial data transmit. This value can not be chosen arbitrarily, due to serial baud rate limitations.
According to this table (https://lucidar.me/en/serialib/most-used-baud-rates-table/) using a baud rate of 115200 serial data can be transmitted at a real byte rate of 86.806 µs per byte.
Depending on the size of the outgoing message and the value of UPDATE_INTERVAL_MS, this could overload the serial buffer and the GUI will most likely not be able to interprete the data sent.
The minimum update interval to not cause the serial buffer to accumulate data due to baud rate limitations can be expressed as message_size_bytes * real_byte_rate 
which for example results in 177,78 ms for a buffer size of 2048 bytes and a baud rate of 115200 bauds. So the update interval must be slower than that.
*/
#define CONTROLLER_UPDATE_INTERVAL_MS 10
#define SERIAL_TRANSMIT_INTERVAL_MS 100

Communication com;
Encoder wheel_position_rad{ ENC_PIN_CHA, ENC_PIN_CHB, encoder_isr, enc_counter, 0.5 * (2 * PI / 360) };
MinSegMPU mpu;

void setup() {
  Serial.begin(115200);  // Baud rate has been increased permanently on the HC-06 bluetooth module to allow for bigger messages
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

  static uint32_t last_transmit_ms = 0;
  if (millis() > last_transmit_ms + SERIAL_TRANSMIT_INTERVAL_MS) {
    last_transmit_ms = millis();
    com.transmit();
  }
}

void calibrate_mpu() {
  com.message_transmit(F("Accel Gyro calibration will start in 3sec."));
  com.message_transmit(F("Please leave the device still on the flat plane."));
  delay(3000);
  com.message_transmit(F("Accel Gyro calibration start!"));
  mpu.calibrateAccelGyro();
  com.message_transmit(F("Accel Gyro calibration finished!"));

  delay(1000);

  com.message_transmit(F("Mag calibration will start in 3sec."));
  com.message_transmit(F("Please Wave device in a figure eight until done."));
  delay(3000);
  com.message_transmit(F("Mag calibration start!"));
  mpu.calibrateMag();
  com.message_transmit(F("Mag calibration finished!"));
  com.message_transmit(F("-------------------------"));
  com.message_transmit(F("    Calibration done!"));

  com.tx_data.calibrated = true;  // Tell gui that calibration procedure is finished
  com.rx_data.calibration = false;  // Prevent doing a calibration in the next loop again
}

void serialEvent() {
  if (com.receive()) {
    com.message_transmit(F("Packet received!"));
  } else {
    com.message_transmit(F("Packet receive ERROR!"));
  }
}
