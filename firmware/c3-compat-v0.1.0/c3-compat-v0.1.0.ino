#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <esp_arduino_version.h>

// ESP32-C3 side of the ESP8266 compatibility LAB TEST. Not mesh-v0.5.1!
constexpr uint8_t CHANNEL=6;
constexpr uint32_t MAGIC=0x434F4D50; // COMP
const uint8_t BROADCAST[6]={255,255,255,255,255,255};
struct __attribute__((packed)) TestPacket {
  uint32_t magic;
  uint32_t sequence;
  uint32_t senderId;
  uint32_t uptimeMs;
};
static_assert(sizeof(TestPacket)==16,"Packet size mismatch");
volatile uint32_t rxCount=0;
uint32_t sequence=0,lastTx=0;
uint32_t myId=0;

void receivePacket(const uint8_t *mac,const uint8_t *data,int len,int rssi) {
  if(len!=sizeof(TestPacket))return;
  TestPacket p;
  memcpy(&p,data,sizeof(p));
  if(p.magic!=MAGIC || p.senderId==myId)return;
  rxCount++;
  Serial.printf("[RX] from=%02X:%02X:%02X:%02X:%02X:%02X id=%08lX seq=%lu uptime=%lu rssi=%d dBm\n",
   mac[0],mac[1],mac[2],mac[3],mac[4],mac[5],
   (unsigned long)p.senderId,(unsigned long)p.sequence,(unsigned long)p.uptimeMs,rssi);
}
#if ESP_ARDUINO_VERSION_MAJOR >= 3
void onRx(const esp_now_recv_info_t *info,const uint8_t *data,int len) {
  if(info)receivePacket(info->src_addr,data,len,info->rx_ctrl ? info->rx_ctrl->rssi : 0);
}
#else
void onRx(const uint8_t *mac,const uint8_t *data,int len) {
  receivePacket(mac,data,len,0);
}
#endif
void setup(){
  Serial.begin(115200);delay(1200);
  Serial.println("\nESP32-C3 ESP-NOW compatibility test v0.1.1 (RSSI)");
  WiFi.mode(WIFI_STA); WiFi.disconnect();
  myId=(uint32_t)ESP.getEfuseMac();
  esp_err_t err=esp_wifi_set_channel(CHANNEL,WIFI_SECOND_CHAN_NONE);
  if(err!=ESP_OK){Serial.printf("ERROR: channel=%d\n",(int)err);return;}
  Serial.printf("MAC=%s id=%08lX channel=%u\n",WiFi.macAddress().c_str(),(unsigned long)myId,CHANNEL);
  err=esp_now_init();
  if(err!=ESP_OK){Serial.printf("ERROR: espnow=%d\n",(int)err);return;}
  esp_now_register_recv_cb(onRx);
  esp_now_peer_info_t peer={};
  memcpy(peer.peer_addr,BROADCAST,6);peer.channel=CHANNEL;peer.ifidx=WIFI_IF_STA;peer.encrypt=false;
  err=esp_now_add_peer(&peer);
  if(err!=ESP_OK){Serial.printf("ERROR: broadcast peer=%d\n",(int)err);return;}
  Serial.println("Ready: TEST broadcast every 5s");
  lastTx=millis()-5000;
}
void loop(){
  if(millis()-lastTx>=5000){
    lastTx=millis();
    TestPacket p={MAGIC,++sequence,myId,millis()};
    esp_err_t e=esp_now_send(BROADCAST,(uint8_t*)&p,sizeof(p));
    Serial.printf("[TX] seq=%lu status=%d rx=%lu\n",
      (unsigned long)p.sequence,(int)e,(unsigned long)rxCount);
  }
  delay(10);
}
