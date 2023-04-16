void setup() {
  Serial.begin(9600);  // Change to current HC-06 baud rate
  delay(10);
  while (Serial.available()) { Serial.read(); }

  Serial.print("AT");
  while (!Serial.available()) {}

  String response = Serial.readString();
  if (response == "OK") {
    Serial.print("AT+BAUD8");  // Enter baud rate alial here. Datasheet: https://www.olimex.com/Products/Components/RF/BLUETOOTH-SERIAL-HC-06/resources/hc06.pdf
    delay(10);
    while (!Serial.available()) {}
    while (Serial.available()) { Serial.println(Serial.readString()); }
  } else {
    Serial.println(response);
  }
}

void loop() {}
