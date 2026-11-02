#include <Arduino.h>
#include <WiFi.h>
#include <Preferences.h>
#include <WebServer.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <esp_arduino_version.h>
#include <mbedtls/md.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include "mesh_secrets.h"

// v0.5.4 - experimental, NOT a life-safety alarm system.
// All nodes require the SAME private mesh_secrets.h.
constexpr uint8_t CHANNEL = 6, INITIAL_TTL = 3, PROTOCOL = 2;
constexpr uint32_t MAGIC = 0x534D4553, HEARTBEAT_MS = 15000;
constexpr size_t RX_QUEUE_LENGTH = 20, SEEN_LENGTH = 64, RELAY_LENGTH = 16;
const uint8_t BROADCAST[6] = {255,255,255,255,255,255};

enum PacketType : uint8_t { TEST=1, HEARTBEAT=2 };
// HMAC protects immutable fields. TTL is deliberately excluded so relays can decrement it.
// HMAC is not encryption. Relays cannot invent authentic packets without the key.
struct __attribute__((packed)) Packet {
  uint32_t magic;
  uint8_t protocol;
  uint8_t type;
  uint32_t networkId;
  uint64_t origin;
  uint64_t bootNonce;
  uint32_t sequence;
  uint32_t uptimeMs;
  uint8_t ttl;
  uint8_t reserved;
  uint8_t tag[32];
};
static_assert(sizeof(Packet)==68, "Check packet layout");

struct RxEvent {
  Packet packet;
  uint8_t from[6];
  int8_t rssi;
  uint8_t channel;
};
struct Seen {
  uint64_t origin=0, bootNonce=0;
  uint32_t sequence=0;
  bool used=false;
};
struct Pending {
  Packet packet={};
  uint32_t dueMs=0;
  bool used=false;
};
QueueHandle_t rxQueue=nullptr;
Seen seen[SEEN_LENGTH];
Pending pending[RELAY_LENGTH];
uint32_t seenCursor=0, nextSequence=0, lastHeartbeat=0;
uint32_t rxCount=0, txCount=0, relayCount=0, duplicateCount=0;
uint32_t invalidCount=0, pendingDrops=0, queueDrops=0;
uint64_t nodeId=0, bootNonce=0;
bool ready=false;
Preferences prefs;
WebServer server(80);
bool apMode=false;
uint32_t buttonSince=0, apLastActivity=0;
const uint32_t AP_TIMEOUT_MS=300000;
String nodeName;
String serialLine;
constexpr size_t MAX_NAME_LENGTH=24;

String idString(uint64_t v) {
  char buf[17];
  snprintf(buf,sizeof(buf),"%08lX%08lX",
    (unsigned long)(v>>32), (unsigned long)(v & 0xffffffffULL));
  return String(buf);
}
String macString(const uint8_t *mac) {
  char buf[18];
  snprintf(buf,sizeof(buf),"%02X:%02X:%02X:%02X:%02X:%02X",
    mac[0],mac[1],mac[2],mac[3],mac[4],mac[5]);
  return String(buf);
}

bool validName(const String &name) {
  if(name.length()<1 || name.length()>MAX_NAME_LENGTH) return false;
  for(size_t i=0;i<name.length();i++) {
    char c=name[i];
    if(!((c>='A' && c<='Z') || (c>='a' && c<='z') ||
         (c>='0' && c<='9') || c=='-' || c=='_')) return false;
  }
  return true;
}

void handleCommand(String command) {
  command.trim();
  if(command.equalsIgnoreCase("NAME GET")) {
    Serial.printf("[CONFIG] name=%s node=%s\n",
      nodeName.length()?nodeName.c_str():"(unset)",idString(nodeId).c_str());
  } else if(command.equalsIgnoreCase("NAME RESET")) {
    if(!prefs.begin("smoke-mesh",false)) {
      Serial.println("[CONFIG] ERROR NVS open"); return;
    }
    bool ok=prefs.remove("name");
    prefs.end();
    if(ok) {nodeName="";Serial.println("[CONFIG] OK name cleared");}
    else Serial.println("[CONFIG] ERROR NVS remove");
  } else if(command.length()>=9 && command.substring(0,9).equalsIgnoreCase("NAME SET ")) {
    String name=command.substring(9);
    name.trim();
    if(!validName(name)) {
      Serial.println("[CONFIG] ERROR name must be 1..24 characters: A-Z a-z 0-9 - _");
      return;
    }
    if(!prefs.begin("smoke-mesh",false)) {
      Serial.println("[CONFIG] ERROR NVS open");return;
    }
    size_t n=prefs.putString("name",name);
    prefs.end();
    if(n==name.length()) {
      nodeName=name;
      Serial.printf("[CONFIG] OK name=%s\n",nodeName.c_str());
    } else Serial.println("[CONFIG] ERROR NVS write");
  } else if(command.equalsIgnoreCase("HELP")) {
    Serial.println("[CONFIG] Commands: NAME GET | NAME SET <name> | NAME RESET | HELP");
  } else if(command.length()) {
    Serial.println("[CONFIG] ERROR unknown command (send HELP)");
  }
}
void pollSerial() {
  // Handle CR, LF and CRLF, with a bounded command buffer.
  while(Serial.available()) {
    char c=(char)Serial.read();
    if(c=='\r' || c=='\n') {
      if(serialLine.length()) {
        handleCommand(serialLine);
        serialLine="";
      }
    } else if(c>=32 && c<=126) {
      if(serialLine.length()<80) serialLine+=c;
      else {
        serialLine="";
        Serial.println("[CONFIG] ERROR command too long");
      }
    }
  }
}

bool calculateTag(const Packet &p, uint8_t output[32]) {
  // Exact byte range ends before ttl; packing is asserted above.
  const size_t protectedBytes=offsetof(Packet,ttl);
  const mbedtls_md_info_t *md=mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  if(!md) return false;
  return mbedtls_md_hmac(md, MESH_SECRET_KEY, sizeof(MESH_SECRET_KEY),
      reinterpret_cast<const unsigned char*>(&p), protectedBytes, output)==0;
}
bool verifyTag(const Packet &p) {
  uint8_t expected[32];
  if(!calculateTag(p,expected))return false;
  uint8_t difference=0;
  for(int i=0;i<32;i++) difference |= expected[i]^p.tag[i];
  return difference==0;
}

void enqueueReceive(const uint8_t *mac,const uint8_t *data,int length,int8_t rssi,uint8_t channel) {
  if(!rxQueue || length!=(int)sizeof(Packet) || !mac) return;
  RxEvent event={};
  memcpy(&event.packet,data,sizeof(Packet));
  memcpy(event.from,mac,6);
  event.rssi=rssi;
  event.channel=channel;
  if(xQueueSend(rxQueue,&event,0)!=pdTRUE) {
    // ISR/callback-safe: avoid Serial calls here.
  }
}
#if ESP_ARDUINO_VERSION_MAJOR >= 3
void onReceive(const esp_now_recv_info_t *info,const uint8_t *data,int length) {
  if(info) enqueueReceive(info->src_addr,data,length,
    info->rx_ctrl ? info->rx_ctrl->rssi : -127,
    info->rx_ctrl ? info->rx_ctrl->channel : 0);
}
#else
void onReceive(const uint8_t *mac,const uint8_t *data,int length) {
  enqueueReceive(mac,data,length,-127,0);
}
#endif

bool alreadySeen(const Packet &p) {
  for(const Seen &s:seen)
    if(s.used && s.origin==p.origin && s.bootNonce==p.bootNonce
       && s.sequence==p.sequence) return true;
  Seen &entry=seen[seenCursor++ % SEEN_LENGTH];
  entry.origin=p.origin;entry.bootNonce=p.bootNonce;
  entry.sequence=p.sequence;entry.used=true;
  return false;
}

void sendPacket(const Packet &p,bool relay) {
  esp_err_t e=esp_now_send(BROADCAST,
      reinterpret_cast<const uint8_t*>(&p),sizeof(p));
  if(e==ESP_OK) {txCount++;if(relay)relayCount++;}
  Serial.printf("[%s] origin=%s boot=%s seq=%lu ttl=%u status=%d\n",
      relay?"RELAY":"TX",idString(p.origin).c_str(),
      idString(p.bootNonce).c_str(),(unsigned long)p.sequence,p.ttl,(int)e);
}
void scheduleRelay(const Packet &p) {
  for(Pending &slot:pending) if(!slot.used) {
    slot.packet=p;
    slot.packet.ttl--;
    slot.dueMs=millis()+30+(esp_random()%90);
    slot.used=true;
    return;
  }
  pendingDrops++;
}
void processRx(const RxEvent &event) {
  const Packet &p=event.packet;
  if(p.magic!=MAGIC || p.protocol!=PROTOCOL ||
     p.networkId!=MESH_NETWORK_ID ||
     (p.type!=TEST && p.type!=HEARTBEAT) ||
     p.ttl<1 || p.ttl>INITIAL_TTL ||
     p.origin==0 || !verifyTag(p)) {
    invalidCount++;
    return;
  }
  if(p.origin==nodeId) return;
  if(alreadySeen(p)) { duplicateCount++; return; }
  rxCount++;
  Serial.printf("[RX] origin=%s via=%s boot=%s seq=%lu ttl=%u hops=%u type=%s rssi=%d dBm channel=%u AUTH=OK\n",
      idString(p.origin).c_str(),macString(event.from).c_str(),
      idString(p.bootNonce).c_str(),(unsigned long)p.sequence,p.ttl,
      INITIAL_TTL-p.ttl,p.type==HEARTBEAT?"HEARTBEAT":"TEST",
      (int)event.rssi,(unsigned)event.channel);
  if(p.ttl>1)scheduleRelay(p);
}
void sendLocal(uint8_t type) {
  Packet p={};
  p.magic=MAGIC;p.protocol=PROTOCOL;p.type=type;
  p.networkId=MESH_NETWORK_ID;
  p.origin=nodeId;p.bootNonce=bootNonce;
  p.sequence=++nextSequence;p.uptimeMs=millis();
  p.ttl=INITIAL_TTL;
  if(calculateTag(p,p.tag))sendPacket(p,false);
  else Serial.println("ERROR: HMAC failed");
}

void configForm() {
  apLastActivity=millis();
  String html=F("<html><meta name='viewport' content='width=device-width,initial-scale=1'><meta charset='UTF-8'><h2>Smoke Mesh</h2><form method='POST' action='/name'><input name='name' maxlength='24' placeholder='Neuer Name' required><button>Speichern</button></form><p>Aktueller Name: ");
  html+=nodeName;
  html+="</p></html>";
  server.send(200,"text/html; charset=utf-8",html);
}
void configSave() {
  apLastActivity=millis();
  String name=server.arg("name"); name.trim();
  if(!validName(name)) {server.send(400,"text/plain","Invalid name");return;}
  if(!prefs.begin("smoke-mesh",false)) {server.send(500,"text/plain","NVS failed");return;}
  size_t written=prefs.putString("name",name);
  prefs.end();
  if(written!=name.length()){server.send(500,"text/plain","NVS write failed");return;}
  nodeName=name;
  Serial.printf("[CONFIG] OK name=%s (web)\n",nodeName.c_str());
  server.send(200,"text/html","<h2>Saved</h2><a href='/'>Back</a>");
}
void beginAP() {
  if(apMode)return;
  String pw=MESH_CONFIG_AP_PASSWORD;
  if(pw.length()<12 || pw=="CHANGE-TO-PRIVATE-LONG-PASSWORD") {
    Serial.println("[CONFIG] ERROR: set private AP password first");return;
  }
  esp_now_deinit();
  ready=false;
  WiFi.mode(WIFI_AP);
  // Use the stable eFuse-derived node ID: WiFi.macAddress() can return zeros in AP mode.
  String ssid="SmokeListener-"+idString(nodeId).substring(10);
  if(!WiFi.softAP(ssid.c_str(),MESH_CONFIG_AP_PASSWORD,CHANNEL)) {
    Serial.println("[CONFIG] AP failed, restarting");ESP.restart();return;
  }
  apMode=true; apLastActivity=millis();
  server.begin();
  Serial.printf("[CONFIG] AP=%s IP=%s; ESP-NOW paused\n",ssid.c_str(),WiFi.softAPIP().toString().c_str());
}
void checkButton() {
  static bool activated=false;
  if(digitalRead(9)==LOW) {
    if(!buttonSince)buttonSince=millis();
    if(!activated && (uint32_t)(millis()-buttonSince)>=5000) {
      activated=true;beginAP();
    }
  } else {buttonSince=0;activated=false;}
}

void setup() {
  pinMode(9,INPUT_PULLUP);
  server.on("/",HTTP_GET,configForm);
  server.on("/name",HTTP_POST,configSave);
  Serial.begin(115200);
  delay(1500);
  Serial.println("\nSmoke Listener Mesh v0.5.4 | AUTHENTICATED RADIO TEST ONLY");
  bool emptyKey = true;
  for (uint8_t b : MESH_SECRET_KEY) {
    if (b != 0) {
      emptyKey = false;
      break;
    }
  }
  if (emptyKey) {
    Serial.println("ERROR: Replace the all-zero example secret key!");
    return;
  }
  nodeId = ESP.getEfuseMac();
  if(prefs.begin("smoke-mesh",true)) {
    nodeName=prefs.getString("name","");
    prefs.end();
  } else Serial.println("[CONFIG] WARNING NVS not available");
  if(!validName(nodeName)) nodeName="";
  Serial.printf("[CONFIG] name=%s (NAME GET / NAME SET <name> / NAME RESET)\n",
    nodeName.length()?nodeName.c_str():"(unset)");
  bootNonce=((uint64_t)esp_random()<<32)|esp_random();
  Serial.printf("Node=%s boot=%s network=%08lX\n",
    idString(nodeId).c_str(),idString(bootNonce).c_str(),(unsigned long)MESH_NETWORK_ID);
  rxQueue=xQueueCreate(RX_QUEUE_LENGTH,sizeof(RxEvent));
  if(!rxQueue){Serial.println("ERROR: rx queue");return;}
  WiFi.mode(WIFI_STA);WiFi.disconnect();
  esp_err_t e=esp_wifi_set_channel(CHANNEL,WIFI_SECOND_CHAN_NONE);
  if(e!=ESP_OK){Serial.printf("ERROR: channel %d\n",(int)e);return;}
  Serial.printf("MAC=%s channel=%u\n",WiFi.macAddress().c_str(),CHANNEL);
  e=esp_now_init();
  if(e!=ESP_OK){Serial.printf("ERROR: espnow %d\n",(int)e);return;}
  esp_now_register_recv_cb(onReceive);
  esp_now_peer_info_t peer={};
  memcpy(peer.peer_addr,BROADCAST,6);
  peer.channel=CHANNEL;peer.ifidx=WIFI_IF_STA;peer.encrypt=false;
  e=esp_now_add_peer(&peer);
  if(e!=ESP_OK){Serial.printf("ERROR: add peer %d\n",(int)e);return;}
  ready=true;
  Serial.println("ESP-NOW ready; HMAC authenticated TEST/HEARTBEAT only");
  sendLocal(TEST);
  lastHeartbeat=millis();
}
void loop() {
  pollSerial();
  checkButton();
  if(apMode) {
    server.handleClient();
    if((uint32_t)(millis()-apLastActivity)>=AP_TIMEOUT_MS) ESP.restart();
    delay(5);
    return;
  }
  if(!ready){delay(1000);return;}
  RxEvent event;
  while(xQueueReceive(rxQueue,&event,0)==pdTRUE)processRx(event);
  uint32_t now=millis();
  for(Pending &slot:pending) {
    if(slot.used && (int32_t)(now-slot.dueMs)>=0) {
      Packet p=slot.packet;slot.used=false;sendPacket(p,true);
    }
  }
  if(now-lastHeartbeat>=HEARTBEAT_MS) {
    lastHeartbeat=now;sendLocal(HEARTBEAT);
    Serial.printf("[STATS] rx=%lu tx=%lu relay=%lu duplicate=%lu invalid=%lu pendingDrops=%lu\n",
      (unsigned long)rxCount,(unsigned long)txCount,
      (unsigned long)relayCount,(unsigned long)duplicateCount,
      (unsigned long)invalidCount,(unsigned long)pendingDrops);
  }
  delay(5);
}
