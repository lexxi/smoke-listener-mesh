#include <Arduino.h>
#include <ESP8266WiFi.h>
extern "C" {
#include <espnow.h>
}

// ESP8266 <-> ESP32-C3 interoperability LAB TEST.
// Independent test protocol. No alarm messages or private keys.
constexpr uint8_t CHANNEL = 6;
constexpr uint32_t MAGIC = 0x434F4D50; // COMP
const uint8_t BROADCAST[6] = {0xff,0xff,0xff,0xff,0xff,0xff};
struct __attribute__((packed)) TestPacket {
  uint32_t magic;
  uint32_t sequence;
  uint32_t senderId;
  uint32_t uptimeMs;
};
static_assert(sizeof(TestPacket) == 16, "Packet size mismatch");
volatile uint32_t rxCount = 0;
uint32_t sequence = 0;
uint32_t senderId = 0;
uint32_t lastTx = 0;

void onRx(uint8_t *mac, uint8_t *data, uint8_t len) {
  if (len != sizeof(TestPacket)) return;
  TestPacket p;
  memcpy(&p, data, sizeof(p));
  if (p.magic != MAGIC || p.senderId == senderId) return;
  rxCount++;
  // Short diagnostic: never use this callback for complex processing in production.
  Serial.printf("[RX] from=%02X:%02X:%02X:%02X:%02X:%02X id=%08lX seq=%lu uptime=%lu\n",
    mac[0],mac[1],mac[2],mac[3],mac[4],mac[5],
    (unsigned long)p.senderId,(unsigned long)p.sequence,(unsigned long)p.uptimeMs);
}
void onSent(uint8_t *mac, uint8_t status) {
  Serial.printf("[SEND-CB] status=%u (not end-to-end delivery)\n",(unsigned)status);
}
void setup() {
  Serial.begin(115200);
  delay(700);
  Serial.println("\nESP8266 ESP-NOW compatibility test v0.1.0");
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  wifi_set_channel(CHANNEL);
  senderId = ESP.getChipId();
  Serial.printf("MAC=%s id=%08lX channel=%u flash=%lu\n",
    WiFi.macAddress().c_str(),(unsigned long)senderId,CHANNEL,
    (unsigned long)ESP.getFlashChipRealSize());
  if (esp_now_init() != 0) {Serial.println("ERROR: esp_now_init");return;}
  esp_now_set_self_role(ESP_NOW_ROLE_COMBO);
  esp_now_register_recv_cb(onRx);
  esp_now_register_send_cb(onSent);
  if (esp_now_add_peer((uint8_t*)BROADCAST,ESP_NOW_ROLE_COMBO,CHANNEL,nullptr,0)!=0) {
    Serial.println("ERROR: add broadcast peer");return;
  }
  Serial.println("Ready: TEST broadcast every 5s");
  lastTx=millis()-5000;
}
void loop() {
  if(millis()-lastTx>=5000) {
    lastTx=millis();
    TestPacket p={MAGIC,++sequence,senderId,millis()};
    uint8_t result=esp_now_send((uint8_t*)BROADCAST,(uint8_t*)&p,sizeof(p));
    Serial.printf("[TX] seq=%lu rc=%u rx=%lu\n",
      (unsigned long)p.sequence,(unsigned)result,(unsigned long)rxCount);
  }
  delay(10);
}
