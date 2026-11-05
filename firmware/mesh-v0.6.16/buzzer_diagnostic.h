#pragma once
// Experimental local buzzer diagnostics for Seeed XIAO ESP32-C3 (D3 = GPIO5).
// Nothing sounds on startup or from incoming Mesh/OTA packets.
// Only compiled with FEATURE_BUZZER=1; no life-safety alarm signaling.
#include <Arduino.h>

namespace SmokeBuzzer {
constexpr uint8_t PIN = 5;
constexpr uint32_t FREQ_HZ = 2000;
constexpr uint8_t DUTY_RESOLUTION = 8;
constexpr uint32_t TEST_DURATION_MS = 500;
static bool available = false;
static bool active = false;
static uint32_t startedAt = 0;

inline void stop() {
  if (!available) return;
  ledcWriteTone(PIN, 0);
  ledcWrite(PIN, 0);
  active = false;
  Serial.println("[BUZZER] STOP");
}
inline void begin() {
  available = ledcAttach(PIN, FREQ_HZ, DUTY_RESOLUTION);
  if (!available) {
    Serial.println("[BUZZER] INIT_FAIL GPIO5");
    return;
  }
  ledcWrite(PIN, 0); // silent on boot
  Serial.println("[BUZZER] READY pin=GPIO5 mode=serial_diagnostic_only");
}
inline void test() {
  if (!available) {
    Serial.println("[BUZZER] ERROR not_initialized");
    return;
  }
  stop();
  if (ledcWriteTone(PIN, FREQ_HZ) == 0) {
    Serial.println("[BUZZER] ERROR tone_failed");
    return;
  }
  active = true;
  startedAt = millis();
  Serial.printf("[BUZZER] TEST freq_hz=%lu duration_ms=%lu pin=GPIO5\n",
    (unsigned long)FREQ_HZ, (unsigned long)TEST_DURATION_MS);
}
inline void poll() {
  if (active && (uint32_t)(millis() - startedAt) >= TEST_DURATION_MS) stop();
}
} // namespace SmokeBuzzer
