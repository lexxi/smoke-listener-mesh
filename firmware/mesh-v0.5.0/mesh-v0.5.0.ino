#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <esp_arduino_version.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>

// Smoke Listener Mesh v0.5.0 - RADIO LAB ONLY.
// Not a smoke alarm / life-safety communications system.
constexpr uint8_t CHANNEL = 6;
constexpr uint8_t INITIAL_TTL = 3;
constexpr uint32_t HEARTBEAT_MS = 15000;
constexpr uint32_t MAGIC = 0x534D4553;
constexpr uint8_t VERSION = 1;
constexpr size_t RX_QUEUE_LENGTH = 16;
constexpr size_t SEEN_LENGTH = 48;
constexpr size_t RELAY_LENGTH = 16;

enum PacketType : uint8_t { TEST = 1, HEARTBEAT = 2 };
struct __attribute__((packed)) Packet {
  uint32_t magic;
  uint8_t version;
  uint8_t type;
  uint8_t ttl;
  uint8_t reserved;
  uint64_t origin;      // Stable chip ID
  uint32_t sequence;    // Origin-local counter
  uint32_t uptimeMs;    // Origin uptime (diagnostic only)
};
static_assert(sizeof(Packet) == 24, "Unexpected packet size");

struct Seen {
  uint64_t origin = 0;
  uint32_t sequence = 0;
  uint32_t atMs = 0;
  bool used = false;
};
struct Pending {
  Packet packet = {};
  uint32_t dueMs = 0;
  bool used = false;
};

QueueHandle_t rxQueue = nullptr;
Seen seen[SEEN_LENGTH];
Pending pending[RELAY_LENGTH];

uint64_t nodeId = 0;
uint32_t sequence = 0;
uint32_t lastHeartbeat = 0;
uint32_t rxCount = 0, txCount = 0, relayCount = 0;
uint32_t duplicateCount = 0, queueDropCount = 0;
uint32_t seenCursor = 0;
const uint8_t broadcastMac[6] = {255,255,255,255,255,255};
bool ready = false;

void enqueueReceive(const uint8_t *data, int length) {
  if (!rxQueue || length != sizeof(Packet)) return;
  Packet p;
  memcpy(&p, data, sizeof(p));
  if (xQueueSend(rxQueue, &p, 0) != pdTRUE) {
    // No logging or dynamic allocation in radio callback
    // Drop is observable indirectly in application tests.
  }
}

#if ESP_ARDUINO_VERSION_MAJOR >= 3
void onReceive(const esp_now_recv_info_t *info, const uint8_t *data, int length) {
  enqueueReceive(data, length);
}
#else
void onReceive(const uint8_t *mac, const uint8_t *data, int length) {
  enqueueReceive(data, length);
}
#endif

bool alreadySeen(const Packet &p) {
  for (const Seen &s : seen) {
    if (s.used && s.origin == p.origin && s.sequence == p.sequence) return true;
  }
  Seen &s = seen[seenCursor++ % SEEN_LENGTH];
  s.origin = p.origin;
  s.sequence = p.sequence;
  s.atMs = millis();
  s.used = true;
  return false;
}

void sendPacket(const Packet &p, bool relay) {
  esp_err_t err = esp_now_send(broadcastMac, reinterpret_cast<const uint8_t *>(&p), sizeof(p));
  if (err == ESP_OK) {
    txCount++;
    if (relay) relayCount++;
  }
  Serial.printf("[%s] src=%08lX seq=%lu ttl=%u status=%d\n",
    relay ? "RELAY" : "TX", (unsigned long)(p.origin & 0xffffffffULL),
    (unsigned long)p.sequence, p.ttl, (int)err);
}

void scheduleRelay(const Packet &p) {
  for (Pending &slot : pending) {
    if (!slot.used) {
      slot.packet = p;
      slot.packet.ttl--;
      slot.dueMs = millis() + 30 + (esp_random() % 90);
      slot.used = true;
      return;
    }
  }
  queueDropCount++;
}

void handleReceive(const Packet &p) {
  if (p.magic != MAGIC || p.version != VERSION ||
      (p.type != TEST && p.type != HEARTBEAT)) return;
  if (p.origin == nodeId) return; // Never rebroadcast own returning packet
  if (alreadySeen(p)) { duplicateCount++; return; }
  rxCount++;
  Serial.printf("[RX] src=%08lX seq=%lu ttl=%u type=%s\n",
    (unsigned long)(p.origin & 0xffffffffULL), (unsigned long)p.sequence,
    p.ttl, p.type == HEARTBEAT ? "HEARTBEAT" : "TEST");
  if (p.ttl > 1) scheduleRelay(p);
}

void processRelays() {
  uint32_t now = millis();
  for (Pending &slot : pending) {
    if (slot.used && (int32_t)(now - slot.dueMs) >= 0) {
      Packet p = slot.packet;
      slot.used = false;
      sendPacket(p, true);
    }
  }
}

void sendLocal(uint8_t type) {
  Packet p = {};
  p.magic = MAGIC;
  p.version = VERSION;
  p.type = type;
  p.ttl = INITIAL_TTL;
  p.origin = nodeId;
  p.sequence = ++sequence;
  p.uptimeMs = millis();
  sendPacket(p, false);
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println("\nSmoke Listener Mesh v0.5.0 | RADIO TEST ONLY");
  nodeId = ESP.getEfuseMac();
  Serial.printf("Node ID: %08lX%08lX\n",
    (unsigned long)(nodeId >> 32), (unsigned long)nodeId);
  rxQueue = xQueueCreate(RX_QUEUE_LENGTH, sizeof(Packet));
  if (!rxQueue) { Serial.println("ERR: queue allocation"); return; }
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  esp_err_t err = esp_wifi_set_channel(CHANNEL, WIFI_SECOND_CHAN_NONE);
  if (err != ESP_OK) { Serial.printf("ERR channel: %d\n", err); return; }
  Serial.printf("MAC=%s channel=%u\n", WiFi.macAddress().c_str(), CHANNEL);
  err = esp_now_init();
  if (err != ESP_OK) { Serial.printf("ERR esp_now_init: %d\n", err); return; }
  esp_now_register_recv_cb(onReceive);
  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, broadcastMac, 6);
  peer.channel = CHANNEL;
  peer.ifidx = WIFI_IF_STA;
  peer.encrypt = false;
  err = esp_now_add_peer(&peer);
  if (err != ESP_OK) { Serial.printf("ERR add_peer: %d\n", err); return; }
  ready = true;
  Serial.println("ESP-NOW ready; broadcast TEST, HEARTBEAT, TTL forwarding enabled");
  sendLocal(TEST);
  lastHeartbeat = millis();
}

void loop() {
  if (!ready) { delay(1000); return; }
  Packet p;
  // Queue is drained in main loop, not inside the radio callback.
  while (xQueueReceive(rxQueue, &p, 0) == pdTRUE) handleReceive(p);
  processRelays();
  uint32_t now = millis();
  if (now - lastHeartbeat >= HEARTBEAT_MS) {
    lastHeartbeat = now;
    sendLocal(HEARTBEAT);
    Serial.printf("[STATS] rx=%lu tx=%lu relays=%lu duplicates=%lu pendingDrops=%lu\n",
      (unsigned long)rxCount, (unsigned long)txCount,
      (unsigned long)relayCount, (unsigned long)duplicateCount,
      (unsigned long)queueDropCount);
  }
  delay(5);
}
