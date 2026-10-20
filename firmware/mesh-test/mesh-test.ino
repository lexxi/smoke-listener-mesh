#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <esp_arduino_version.h>

// Smoke Listener Mesh v0.4.0: ONLY a radio test, not safety signaling.
#define WIFI_CHANNEL 6
#define SEND_INTERVAL_MS 5000
uint8_t broadcastAddress[6]={0xff,0xff,0xff,0xff,0xff,0xff};
struct __attribute__((packed)) MeshPacket {
  uint32_t magic;
  uint32_t sequence;
  uint32_t uptime;
  uint8_t type;
};
const uint32_t MAGIC=0x534D4553;
uint32_t sequenceNumber=0,lastSend=0,receivedCount=0;

#if ESP_ARDUINO_VERSION_MAJOR >= 3
void onReceive(const esp_now_recv_info_t *info,const uint8_t *data,int length) {
#else
void onReceive(const uint8_t *mac,const uint8_t *data,int length) {
#endif
  if(length!=sizeof(MeshPacket))return;
  MeshPacket packet;
  memcpy(&packet,data,sizeof(packet));
  if(packet.magic!=MAGIC)return;
  receivedCount++;
  // Temporary serial callback for lab diagnostics; move to queue in production.
  Serial.printf("[RX] Paket #%lu | Uptime=%lu ms | Typ=%u\n",
    (unsigned long)packet.sequence,(unsigned long)packet.uptime,packet.type);
}
void setup() {
  Serial.begin(115200);delay(1500);
  Serial.println("\n=============================");
  Serial.println("Smoke Listener Mesh");
  Serial.println("Firmware v0.4.0");
  Serial.println("ESP32-C3 / ESP-NOW");
  Serial.println("=============================");
  WiFi.mode(WIFI_STA);WiFi.disconnect();
  esp_err_t err=esp_wifi_set_channel(WIFI_CHANNEL,WIFI_SECOND_CHAN_NONE);
  if(err!=ESP_OK){Serial.printf("Channel error: %d\n",err);return;}
  Serial.print("MAC: ");Serial.println(WiFi.macAddress());
  Serial.printf("Channel: %d\n",WIFI_CHANNEL);
  err=esp_now_init();
  if(err!=ESP_OK){Serial.printf("ESP-NOW init failed: %d\n",err);return;}
  esp_now_register_recv_cb(onReceive);
  esp_now_peer_info_t peer={};
  memcpy(peer.peer_addr,broadcastAddress,6);
  peer.channel=WIFI_CHANNEL;
  peer.ifidx=WIFI_IF_STA;
  peer.encrypt=false;
  err=esp_now_add_peer(&peer);
  if(err!=ESP_OK){Serial.printf("Peer add failed: %d\n",err);return;}
  Serial.println("ESP-NOW initialized");
  Serial.println("Broadcast TEST every 5 seconds");
  lastSend=millis();
}
void loop() {
  uint32_t now=millis();
  if(now-lastSend>=SEND_INTERVAL_MS){
    lastSend=now;
    MeshPacket packet={};
    packet.magic=MAGIC;
    packet.sequence=++sequenceNumber;
    packet.uptime=now;
    packet.type=1;
    esp_err_t err=esp_now_send(broadcastAddress,(uint8_t*)&packet,sizeof(packet));
    Serial.printf("[TX] Paket #%lu | Status=%s | RX gesamt=%lu\n",
      (unsigned long)sequenceNumber,err==ESP_OK?"OK":"ERROR",(unsigned long)receivedCount);
  }
  delay(10);
}
