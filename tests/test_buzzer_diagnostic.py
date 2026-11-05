"""Static regression for opt-in XIAO-C3 buzzer diagnostic integration."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "firmware" / "mesh-v0.6.16"


class BuzzerDiagnosticTests(unittest.TestCase):
    def test_off_by_default_and_battery_still_disallowed(self):
        config = (ROOT / "feature_config.h").read_text(encoding="utf-8")
        self.assertRegex(config, r"#define FEATURE_BUZZER 0")
        self.assertIn("#if FEATURE_BATTERY", config)
        self.assertIn("#define SMOKE_FEATURE_BUZZER FEATURE_BUZZER", config)

    def test_gpio_and_tone_are_bounded(self):
        header = (ROOT / "buzzer_diagnostic.h").read_text(encoding="utf-8")
        self.assertIn("constexpr uint8_t PIN = 5;", header)
        self.assertIn("constexpr uint32_t FREQ_HZ = 2000;", header)
        self.assertIn("constexpr uint32_t TEST_DURATION_MS = 500;", header)
        self.assertIn("ledcAttach(PIN, FREQ_HZ, DUTY_RESOLUTION)", header)
        self.assertIn("ledcWriteTone(PIN, 0)", header)
        self.assertIn("millis() - startedAt", header)

    def test_only_local_serial_commands_can_trigger_tone(self):
        sketch = (ROOT / "mesh-v0.6.16.ino").read_text(encoding="utf-8")
        self.assertIn('#include "buzzer_diagnostic.h"', sketch)
        self.assertIn('command.equalsIgnoreCase("BUZZER TEST")', sketch)
        self.assertIn('command.equalsIgnoreCase("BUZZER STOP")', sketch)
        self.assertEqual(sketch.count("SmokeBuzzer::test();"), 1)
        self.assertIn("SmokeBuzzer::poll();", sketch)


if __name__ == "__main__":
    unittest.main()
