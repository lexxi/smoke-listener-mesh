#pragma once
// Choose one firmware package before compiling (Arduino IDE: edit this value).
// 0 CORE: Mesh + signed remote OTA + remote/serial node names
// 1 AUDIO: CORE + INMP441 diagnostics (no transmitted alarms)
// 2 AP: CORE + legacy BOOT-button configuration access point
// 3 FULL: CORE + AUDIO + AP
#ifndef SMOKE_FEATURE_PROFILE
#define SMOKE_FEATURE_PROFILE 1
#endif
#if SMOKE_FEATURE_PROFILE < 0 || SMOKE_FEATURE_PROFILE > 3
#error "SMOKE_FEATURE_PROFILE must be 0 (CORE), 1 (AUDIO), 2 (AP), or 3 (FULL)"
#endif
#define SMOKE_FEATURE_AUDIO ((SMOKE_FEATURE_PROFILE & 1) != 0)
#define SMOKE_FEATURE_AP ((SMOKE_FEATURE_PROFILE & 2) != 0)
