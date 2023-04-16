#include "mpu.hpp"

float get_tilt_angle_from_pitch(MPU9250 *mpu) {
  return mpu->getPitch();
}

float get_tilt_angle_from_acc(MPU9250 *mpu) {
  return atan2(mpu->getAccZ(), -mpu->getAccY());
}

float get_tilt_vel(MPU9250 *mpu) {
  return mpu->getGyroX();
}

MPUMeasurement::MPUMeasurement(MPU9250 *mpu, float (*getter)(MPU9250 *), double transformation, uint32_t freq_hz)
  : Sensor(transformation, freq_hz), mpu(mpu), getter(getter) {}

double MPUMeasurement::get_value() {
  return getter(mpu);
}

MinSegMPU::MinSegMPU()
  : MPU9250(), tilt_angle_from_pitch_deg{ this, &get_tilt_angle_from_pitch }, tilt_angle_from_acc_deg{ this, &get_tilt_angle_from_acc }, tilt_vel_deg_s{ this, &get_tilt_vel } {}

void MinSegMPU::setup() {
  Wire.begin();
  
  MPU9250Setting mpu_setting;
  mpu_setting.accel_fs_sel = ACCEL_FS_SEL::A16G;           // Accelerometer range in +/- g (gravitational force on earth)
  mpu_setting.gyro_fs_sel = GYRO_FS_SEL::G2000DPS;         // Gyro range in +/- dps (degrees per second)
  mpu_setting.accel_dlpf_cfg = ACCEL_DLPF_CFG::DLPF_45HZ;  // Accelerometer digital low pass filter bandwith
  mpu_setting.gyro_dlpf_cfg = GYRO_DLPF_CFG::DLPF_41HZ;    // Gyro digital low pass filter bandwith
  MPU9250::setup(0x68, mpu_setting);

  // Filter for removing yaw angle drift using 9-DOF sensor fusion
  selectFilter(QuatFilterSel::NONE);

  // Calibration values
  setAccBias(18, 49, 3);
  setGyroBias(-2.1, 0.12, 0.98);
  setMagBias(57.54, 44.81, 264.36);
  setMagScale(1.4, 1.02, 0.75);
  setMagneticDeclination(5.016667);  // Magnetic declination in Lund on 16th of April 2022 from https://www.magnetic-declination.com/
}
