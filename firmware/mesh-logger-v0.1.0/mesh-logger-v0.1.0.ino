#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <esp_arduino_version.h>
#include <mbedtls/md.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include "mesh_secrets.h"

// Passive sniffer for authenticated v0.5.1 radio messages.
// NO forwarding, NO transmitting, NO smoke alarm functionality.
constexpr uint32_t MAGIC=0x534D4553;
constexpr uint8_t PROTOCOL=2, CHANNEL=6;
struct __attribute__((packed)) Packet {
 uint32_t magic; uint8_t protocol; uint8_t type; uint32_t networkId;
 uint64_t origin; uint64_t bootNonce; uint32_t sequence; uint32_t uptimeMs;
 uint8_t ttl; uint8_t reserved; uint8_t tag[32];
};
static_assert(sizeof(Packet)==68,"Unexpected packet size");
struct RxEvent { Packet p; uint8_t via[6]; int8_t rssi; uint8_t channel; };
QueueHandle_t queueRx;
uint32_t receiveCount=0, validCount=0, invalidCount=0, queueDrops=0;
volatile uint32_t callbackDrops=0;
uint32_t lastStats=0;
String hex64(uint64_t x) {
 char b[17]; snprintf(b,sizeof(b),"%08lX%08lX",(unsigned long)(x>>32),(unsigned long)x);
 return String(b);
}
String macHex(const uint8_t *mac) {
 char b[18]; snprintf(b,sizeof(b),"%02X:%02X:%02X:%02X:%02X:%02X",mac[0],mac[1],mac[2],mac[3],mac[4],mac[5]);
 return String(b);
}
bool authenticated(const Packet &p) {
 if(p.magic!=MAGIC || p.protocol!=PROTOCOL || p.networkId!=MESH_NETWORK_ID
    || (p.type!=1 && p.type!=2) || p.ttl<1 || p.ttl>3) return false;
 auto *md=mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
 if(!md) return false;
 uint8_t tag[32]={};
 if(mbedtls_md_hmac(md,MESH_SECRET_KEY,sizeof(MESH_SECRET_KEY),
     reinterpret_cast<const unsigned char*>(&p),offsetof(Packet,ttl),tag)!=0) return false;
 uint8_t difference=0;
 for(size_t i=0;i<32;i++) difference|=tag[i]^p.tag[i];
 return difference==0;
}
void pushRx(const uint8_t *src,const uint8_t *data,int length,int8_t rssi,uint8_t channel) {
 if(!queueRx || !src || length!=(int)sizeof(Packet)) return;
 RxEvent event={};
 memcpy(&event.p,data,sizeof(Packet));
 memcpy(event.via,src,6);
 event.rssi=rssi; event.channel=channel;
 if(xQueueSend(queueRx,&event,0)!=pdTRUE) callbackDrops++;
}
#if ESP_ARDUINO_VERSION_MAJOR >= 3
void onReceive(const esp_now_recv_info_t *info,const uint8_t *data,int len) {
 if(!info) return;
 int8_t rssi=0; uint8_t channel=0;
 if(info->rx_ctrl) {rssi=info->rx_ctrl->rssi;channel=info->rx_ctrl->channel;}
 pushRx(info->src_addr,data,len,rssi,channel);
}
#else
void onReceive(const uint8_t *mac,const uint8_t *data,int len) {
 pushRx(mac,data,len,0,0);
}
#endif
void setup() {
 Serial.begin(115200);
 delay(1200);
 Serial.println("# Smoke Mesh Logger v0.1.0 (passive, auth verify, CSV)");
 bool zeroKey=true;for(uint8_t b:MESH_SECRET_KEY)if(b){zeroKey=false;break;}
 if(zeroKey){Serial.println("# ERROR: private key not configured");return;}
 queueRx=xQueueCreate(32,sizeof(RxEvent));
 if(!queueRx){Serial.println("# ERROR: queue");return;}
 WiFi.mode(WIFI_STA); WiFi.disconnect();
 auto e=esp_wifi_set_channel(CHANNEL,WIFI_SECOND_CHAN_NONE);
 if(e!=ESP_OK){Serial.printf("# ERROR: channel=%d\n",(int)e);return;}
 e=esp_now_init();
 if(e!=ESP_OK){Serial.printf("# ERROR: espnow=%d\n",(int)e);return;}
 esp_now_register_recv_cb(onReceive);
 Serial.printf("# MAC=%s channel=%u\n",WiFi.macAddress().c_str(),CHANNEL);
 Serial.println("uptime_ms,origin,via,boot,seq,ttl,hops,type,rssi_dbm,channel,auth");
}
void loop() {
 if(!queueRx){delay(1000);return;}
 RxEvent event;
 while(xQueueReceive(queueRx,&event,0)==pdTRUE){
   receiveCount++;
   bool ok=authenticated(event.p);
   if(!ok){invalidCount++;continue;}
   validCount++;
   Serial.printf("%lu,%s,%s,%s,%lu,%u,%u,%s,%d,%u,OK\n",
     (unsigned long)millis(),hex64(event.p.origin).c_str(),
     macHex(event.via).c_str(),hex64(event.p.bootNonce).c_str(),
     (unsigned long)event.p.sequence,event.p.ttl,(unsigned)(3-event.p.ttl),
     event.p.type==2?"HEARTBEAT":"TEST",(int)event.rssi,event.channel);
 }
 if(millis()-lastStats>=30000) {
   lastStats=millis();
   Serial.printf("# STATS received=%lu verified=%lu invalid=%lu callbackDrops=%lu\n",
     (unsigned long)receiveCount,(unsigned long)validCount,
     (unsigned long)invalidCount,(unsigned long)callbackDrops);
 }
 delay(5);
}
