#pragma once
// Independent build-time switches. Edit BEFORE compiling the firmware.
// Every node keeps ESP-NOW mesh, signed OTA receiver, and authenticated
// remote management target support (including NAME_GET/SET/RESET).
//
// The USB gateway feature enables commands that initiate remote OTA,
// remote management and diagnostic OTA transfers from the serial port.
// Disable it on ordinary smoke listener nodes to avoid unused sender code.
#ifndef FEATURE_GATEWAY
#define FEATURE_GATEWAY 1
#endif
#ifndef FEATURE_AUDIO
#define FEATURE_AUDIO 0
#endif
#ifndef FEATURE_CONFIG_AP
#define FEATURE_CONFIG_AP 0
#endif
// Future features: intentionally rejected until hardware and code exist.
#ifndef FEATURE_BATTERY
#define FEATURE_BATTERY 0
#endif
#ifndef FEATURE_BUZZER
#define FEATURE_BUZZER 0
#endif

#if (FEATURE_GATEWAY != 0 && FEATURE_GATEWAY != 1) || \
    (FEATURE_AUDIO != 0 && FEATURE_AUDIO != 1) || \
    (FEATURE_CONFIG_AP != 0 && FEATURE_CONFIG_AP != 1) || \
    (FEATURE_BATTERY != 0 && FEATURE_BATTERY != 1) || \
    (FEATURE_BUZZER != 0 && FEATURE_BUZZER != 1)
#error "Feature flags must be 0 or 1"
#endif
#if FEATURE_BATTERY || FEATURE_BUZZER
#error "Battery and buzzer are not implemented; keep them disabled"
#endif

#define SMOKE_FEATURE_AUDIO FEATURE_AUDIO
#define SMOKE_FEATURE_AP FEATURE_CONFIG_AP
#define SMOKE_FEATURE_GATEWAY FEATURE_GATEWAY
