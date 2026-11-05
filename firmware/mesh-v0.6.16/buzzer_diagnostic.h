#pragma once
// Local-only nonblocking buzzer diagnostics for Seeed XIAO ESP32-C3 D3/GPIO5.
// No sound on boot or from mesh/OTA/audio events. FEATURE_BUZZER=1 required.
// The pattern is strictly bounded and is NOT a real smoke alarm signal.
#include <Arduino.h>

namespace SmokeBuzzer {
constexpr uint8_t PIN = 5;
constexpr uint32_t FREQ_HZ = 2000;
constexpr uint8_t DUTY_RESOLUTION = 8;
constexpr uint32_t TEST_DURATION_MS = 500;
constexpr uint32_t SHORT_GAP_MS = 250;
constexpr uint32_t GROUP_GAP_MS = 1000;
constexpr uint8_t PATTERN_BEEPS = 4;

enum class Mode : uint8_t { IDLE, SINGLE, TWO_BY_TWO };
static bool available = false;
static bool toneOn = false;
static Mode mode = Mode::IDLE;
static uint8_t beepIndex = 0;
static uint32_t phaseStarted = 0;

inline void silence() {
  ledcWriteTone(PIN, 0);
  ledcWrite(PIN, 0);
  toneOn = false;
}
inline void stop() {
  if (!available) return;
  silence();
  mode = Mode::IDLE;
  beepIndex = 0;
  Serial.println("[BUZZER] STOP");
}
inline void begin() {
  available = ledcAttach(PIN, FREQ_HZ, DUTY_RESOLUTION);
  if (!available) {
    Serial.println("[BUZZER] INIT_FAIL GPIO5");
    return;
  }
  silence(); // silent on boot
  Serial.println("[BUZZER] READY pin=GPIO5 mode=serial_diagnostic_only");
}
inline bool startTone() {
  if (ledcWriteTone(PIN, FREQ_HZ) == 0) {
    silence();
    mode = Mode::IDLE;
    Serial.println("[BUZZER] ERROR tone_failed");
    return false;
  }
  toneOn = true;
  phaseStarted = millis();
  return true;
}
inline void test() {
  if (!available) {
    Serial.println("[BUZZER] ERROR not_initialized");
    return;
  }
  stop();
  mode = Mode::SINGLE;
  if (!startTone()) return;
  Serial.printf("[BUZZER] TEST freq_hz=%lu duration_ms=%lu pin=GPIO5\n",
    (unsigned long)FREQ_HZ, (unsigned long)TEST_DURATION_MS);
}
inline void test2x2() {
  if (!available) {
    Serial.println("[BUZZER] ERROR not_initialized");
    return;
  }
  stop();
  mode = Mode::TWO_BY_TWO;
  beepIndex = 0;
  if (!startTone()) return;
  Serial.printf("[BUZZER] PATTERN 2X2 freq_hz=%lu beep_ms=%lu short_gap_ms=%lu group_gap_ms=%lu pin=GPIO5\n",
    (unsigned long)FREQ_HZ, (unsigned long)TEST_DURATION_MS,
    (unsigned long)SHORT_GAP_MS, (unsigned long)GROUP_GAP_MS);
}
inline void poll() {
  if (!available || mode == Mode::IDLE) return;
  uint32_t now = millis();
  if (toneOn) {
    if ((uint32_t)(now - phaseStarted) < TEST_DURATION_MS) return;
    silence();
    phaseStarted = now;
    ++beepIndex;
    if (mode == Mode::SINGLE || beepIndex >= PATTERN_BEEPS) {
      stop();
    }
  } else {
    const uint32_t gap = beepIndex == 2 ? GROUP_GAP_MS : SHORT_GAP_MS;
    if ((uint32_t)(now - phaseStarted) >= gap) startTone();
  }
}
} // namespace SmokeBuzzer
