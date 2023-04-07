// This file is automatically generated

#ifndef INTERFACE_HPP
#define INTERFACE_HPP

#include <ArduinoJson.h>

#define JSON_DOC_SIZE_RX 80
#define JSON_DOC_SIZE_TX 80

namespace Interface {
struct RX {

bool controller_state;
struct {
float B1;
float B2;
} A1;
struct {
struct {
bool C1;
bool C2;
} B3;
float B4;
} A2;
float A3;

RX(const StaticJsonDocument doc) : controller_state(doc["controller_state"], A1({doc["A1"]["B1"], doc["A1"]["B2"]}, A2({{doc["A2"]["B3"]["C1"], doc["A2"]["B3"]["C2"]}, doc["A2"]["B4"]}, A3(doc["A3"] {}

}

struct TX {
char[10] msg;
struct {
float B1;
float B2;
} A1;
struct {
struct {
bool C1;
bool C2;
} B3;
float B4;
} A2;
float A3;

void to_doc(StaticJsonDocument* doc) {
doc["msg"] = this.msg;
JsonObject A1 = doc.createNestedObject("A1");
A1["B1"] = this.A1.B1;
A1["B2"] = this.A1.B2;
JsonObject A2 = doc.createNestedObject("A2");
JsonObject B3 = A2.createNestedObject("B3");
B3["C1"] = this.A2.B3.C1;
B3["C2"] = this.A2.B3.C2;
A2["B4"] = this.A2.B4;
doc["A3"] = this.A3;
}

}
}

#endif
