#include "Arduino.h"
#include "mpu.hpp"

float get_tilt_angle_from_euler(MPU9250 *mpu) {
  return mpu->getEulerX() * DEG_TO_RAD + HALF_PI;
}

float get_tilt_angle_from_acc(MPU9250 *mpu) {
  return atan2(mpu->getAccZ(), -mpu->getAccY());
}

float get_tilt_vel(MPU9250 *mpu) {
  return mpu->getGyroX() * DEG_TO_RAD;
}

MPUMeasurement::MPUMeasurement(MPU9250 *mpu, float (*getter)(MPU9250 *), uint32_t freq_hz)
  : Sensor(freq_hz), mpu(mpu), getter(getter) {}

double MPUMeasurement::get_value() {
  return getter(mpu);
}

MinSegMPU::MinSegMPU()
  : MPU9250(),
    tilt_angle_from_euler_rad{ this, &get_tilt_angle_from_euler },
    tilt_angle_from_acc_rad{ this, &get_tilt_angle_from_acc },
    tilt_vel_rad_s{ this, &get_tilt_vel } {}

void MinSegMPU::setup() {
  Wire.begin();
  Wire.setClock(400000);

  MPU9250Setting mpu_setting;
  mpu_setting.accel_fs_sel = ACCEL_FS_SEL::A4G;            // Accelerometer range in +/- g (gravitational force on earth)
  mpu_setting.gyro_fs_sel = GYRO_FS_SEL::G500DPS;          // Gyro range in +/- dps (degrees per second)
  mpu_setting.accel_dlpf_cfg = ACCEL_DLPF_CFG::DLPF_45HZ;  // Accelerometer digital low pass filter bandwith
  mpu_setting.gyro_dlpf_cfg = GYRO_DLPF_CFG::DLPF_41HZ;    // Gyro digital low pass filter bandwith
  mpu_setting.fifo_sample_rate = FIFO_SAMPLE_RATE::SMPL_200HZ;
  MPU9250::setup(0x68, mpu_setting);

  // Filter for removing yaw angle drift using 9-DOF sensor fusion
  selectFilter(QuatFilterSel::MAHONY);
  setFilterIterations(10);

  // Magnetic declination in Lund on 16th of April 2022 from https://www.magnetic-declination.com/
  setMagneticDeclination(5.016667);
}
