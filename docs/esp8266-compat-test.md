# ESP8266 ↔ ESP32-C3 ESP-NOW interoperability lab test

**No alarm functions. No mesh v0.5.1 authentication. Do not use for smoke detection.**

The test uses an independent 16-byte packet with magic `COMP` (`0x434F4D50`) and 5-second ESP-NOW broadcasts on channel 6. Both devices send and receive. No keys needed; deliberately distinct from the authenticated mesh production-experimental packet.

## ESP8266

Flash [esp8266-compat-v0.1.0.ino](../firmware/esp8266-compat-v0.1.0/esp8266-compat-v0.1.0.ino). In Arduino IDE use **Generic ESP8266 Module**, **1 MB flash**, DIO, upload 115200. For external USB-UART: 3.3 V power only, common GND, TX↔RX. Boot with GPIO0 to GND to flash; release GPIO0 and restart for operation. Use a stable 3.3 V supply with adequate current.

## ESP32-C3

Flash [c3-compat-v0.1.0.ino](../firmware/c3-compat-v0.1.0/c3-compat-v0.1.0.ino) to **one spare** ESP32-C3 SuperMini; keep the existing three mesh v0.5.1 nodes untouched. Arduino IDE board ESP32C3 Dev Module / USB CDC On Boot Enabled.

**Both test nodes** should be within 1 meter; serial monitor 115200 at both. Expect periodic `[TX]`, plus `[RX]` messages if interoperability succeeds. TX `status=0` is only enqueue success, not proof of receipt. Record both logs. This is a compatibility test, not a relay or coverage proof.

The passive v0.5.1 logger will intentionally **not** display these compatibility frames because the packet format is different. To avoid conflicting measurements, keep the separate tests distinct.
