// This file is automatically generated. Any changes will be overwritten.

#ifndef INTERFACE_HPP
#define INTERFACE_HPP

#include <ArduinoJson.h>

#define JSON_DOC_SIZE_RX 900
#define JSON_DOC_SIZE_TX 184

struct ReceiveInterface {
bool calibration;
bool control_state;
double pos_setpoint_mm;
bool reset_pos;
struct {
struct {
struct {
uint16_t h_ms;
double alpha_off;
uint8_t r_stop;
uint8_t r_start;
} General;
struct {
double k1;
double k2;
double k3;
} BalanceControl;
struct {
double k4;
double ki;
} PositionControl;
} variable;
struct {
struct {
struct {
double l11;
double l12;
double l13;
double l21;
double l22;
double l23;
double l31;
double l32;
double l33;
double l41;
double l42;
double l43;
} gain;
struct {
double phi11;
double phi12;
double phi13;
double phi14;
double phi21;
double phi22;
double phi23;
double phi24;
double phi31;
double phi32;
double phi33;
double phi34;
double phi41;
double phi42;
double phi43;
double phi44;
} phi;
struct {
double mx11;
double mx12;
double mx13;
double mx21;
double mx22;
double mx23;
double mx31;
double mx32;
double mx33;
double mx41;
double mx42;
double mx43;
} innoGain;
} observer;
} inferred;
} parameters;

void from_doc(StaticJsonDocument<JSON_DOC_SIZE_RX> &doc);
};

struct TransmitInterface {
struct {
struct {
double angle_rad;
double angle_deriv_rad_s;
} wheel;
struct {
double angle_rad;
double vel_rad_s;
} tilt;
} sensor;
struct {
struct {
double angle_rad;
double vel_rad_s;
} wheel;
struct {
double angle_rad;
double vel_rad_s;
} tilt;
struct {
double s_mm;
} position;
} observer;
struct {
uint32_t cycle_us;
double u;
double u_bal;
double u_pos;
int16_t motor;
} control;
bool calibrated;

StaticJsonDocument<JSON_DOC_SIZE_TX> to_doc();
};

#endif
