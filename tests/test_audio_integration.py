"""Static guardrails for the experimental v0.6.15 audio integration."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FIRMWARE=(ROOT/"firmware/mesh-v0.6.15/mesh-v0.6.15.ino").read_text(encoding="utf-8")
AUDIO=(ROOT/"firmware/mesh-v0.6.15/audio_monitor.h").read_text(encoding="utf-8")

class AudioIntegrationTests(unittest.TestCase):
    def test_version_and_monitor_hook(self):
        self.assertIn('CURRENT_FW_VERSION[]="0.6.15"',FIRMWARE)
        self.assertIn('#include "audio_monitor.h"',FIRMWARE)
        self.assertIn("audioMonitorStart();",FIRMWARE)
    def test_no_alarm_mesh_packet_yet(self):
        self.assertIn("enum PacketType : uint8_t { TEST=1, HEARTBEAT=2 };",FIRMWARE)
        self.assertIn("ALARM_CANDIDATE DIAGNOSTIC_ONLY NO_MESH_ALARM",AUDIO)
        self.assertNotIn("sendLocal(ALARM)",FIRMWARE)
    def test_feature_profiles_are_compile_time(self):
        config=(ROOT/"firmware/mesh-v0.6.15/feature_config.h").read_text(encoding="utf-8")
        for profile in range(4):
            self.assertIn(f"// {profile} ",config)
        self.assertIn("#if SMOKE_FEATURE_AUDIO",FIRMWARE)
        self.assertIn("#if SMOKE_FEATURE_AP",FIRMWARE)
        self.assertIn("#include <WebServer.h>",FIRMWARE)
        self.assertIn("WiFi.softAP(",FIRMWARE)
        for command in ('NAME GET','NAME SET ','NAME RESET'):
            self.assertIn(command,FIRMWARE)

    def test_audio_is_task_based(self):
        self.assertIn("xTaskCreate(",AUDIO)
        self.assertIn("i2s_read(",AUDIO)
        self.assertIn("I2S_NUM_0",AUDIO)

if __name__=="__main__":
    unittest.main()
