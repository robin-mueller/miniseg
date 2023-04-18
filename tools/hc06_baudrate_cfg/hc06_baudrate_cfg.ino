/* 
See datasheet: https://www.olimex.com/Products/Components/RF/BLUETOOTH-SERIAL-HC-06/resources/hc06.pdf

There is also a website that generates assembly code for sending exactly one message: https://tools.krum.com.ar/save_your_hc-06/
which is based on this blog entry: https://www.instructables.com/Recover-Misconfigured-HC-06-Bluetooth-Module/
Unfortunately, the assembly code is designed for the Atmel AtMega328P microchip.
The Arduino Mega 2560 has a Atmel AtMega 2560 chip built into it. 
To make the assembly code work with the Arduino Mega one has to replace every 0x0B with 0x08 and 0x0A with 0x07.
Further you have to connect Pin 34 of the Arduino and RXD of the HC-06. 
Then just upload the sketch that contains the assembly code while everything is wired up and let it execute once.
This is great, if you have to recover from a high baud rate, because the serial port has trouble sending at higher rates than 115200.
*/
enum class HC06_BAUD_RATE_CFG {
  B_1200,
  B_2400,
  B_4800,
  B_9600,
  B_19200,
  B_38400,
  B_57600,
  B_115200
};

const unsigned long long CURRENT_BAUD_RATE = 9600;
const HC06_BAUD_RATE_CFG baud_cfg = HC06_BAUD_RATE_CFG::B_9600;  // Choose the baud rate to change to

// #define ONLY_TEST_COMMUNICATION  // Comment out if you want to set the baud rate

bool test_communication() {
  Serial.print("AT");
  delay(1500);  // Response should come in within a second
  if (Serial.available() && Serial.readString() == "OK") return true;
  return false;
}

bool set_baud_rate(HC06_BAUD_RATE_CFG cfg) {
  String cmd;
  switch (cfg) {
    case HC06_BAUD_RATE_CFG::B_1200:
      cmd = String("AT+BAUD1");
      break;
    case HC06_BAUD_RATE_CFG::B_2400:
      cmd = String("AT+BAUD2");
      break;
    case HC06_BAUD_RATE_CFG::B_4800:
      cmd = String("AT+BAUD3");
      break;
    case HC06_BAUD_RATE_CFG::B_9600:
      cmd = String("AT+BAUD4");
      break;
    case HC06_BAUD_RATE_CFG::B_19200:
      cmd = String("AT+BAUD5");
      break;
    case HC06_BAUD_RATE_CFG::B_38400:
      cmd = String("AT+BAUD6");
      break;
    case HC06_BAUD_RATE_CFG::B_57600:
      cmd = String("AT+BAUD7");
      break;
    case HC06_BAUD_RATE_CFG::B_115200:
      cmd = String("AT+BAUD8");
      break;
  }
  if (test_communication()) {
    Serial.print(cmd);
    while (!Serial.available()) {}
    while (Serial.available()) { Serial.println(Serial.readString()); }
    return true;
  }
  return false;
}

void setup() {
  Serial.begin(CURRENT_BAUD_RATE);  // Change to current HC-06 baud rate
  while (!Serial) {}
  while (Serial.available()) { Serial.read(); }

#ifdef ONLY_TEST_COMMUNICATION
  // Test communication
  if (test_communication()) {
    Serial.println("\nCommunication works!");
  } else {
    Serial.println("\nCommunication failed!");
  }
#else
  // Set baud rate
  if (set_baud_rate(baud_cfg)) {
    Serial.println("\nBaud rate successfully set!");
  } else {
    Serial.println("\nCouldn't establish communication with HC-06. Make sure to initialize Serial with the correct current baud rate.");
  }
#endif
}

void loop() {}
