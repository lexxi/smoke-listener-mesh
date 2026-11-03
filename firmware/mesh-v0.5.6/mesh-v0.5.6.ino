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

// v0.5.6 - OTA RAM transport test; no Flash writes; experimental, NOT a life-safety alarm system.
// All nodes require the SAME private mesh_secrets.h.
constexpr uint8_t CHANNEL = 6, INITIAL_TTL = 3, PROTOCOL = 3;
constexpr uint32_t MAGIC = 0x534D4553, HEARTBEAT_MS = 15000;
constexpr size_t RX_QUEUE_LENGTH = 20, SEEN_LENGTH = 64, RELAY_LENGTH = 16;
constexpr uint8_t OTA_PROTO=1, OTA_DATA=1, OTA_ACK=2;
constexpr uint16_t OTA_TOTAL=16;
constexpr size_t OTA_BYTES=96;

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
  char name[24]; // Authenticated origin name, empty if not configured
  uint8_t ttl;
  uint8_t reserved;
  uint8_t tag[32];
};
static_assert(sizeof(Packet)==92, "Check packet layout");

struct __attribute__((packed)) OtaFrame {
  uint32_t magic;
  uint8_t protocol, kind;
  uint32_t networkId;
  uint64_t origin,target;
  uint32_t session;
  uint16_t index,total;
  uint8_t data[OTA_BYTES];
  uint8_t ttl,reserved;
  uint8_t hmac[32];
};
static_assert(sizeof(OtaFrame)==164,"OTA packet size <=250");
struct OtaCache {
  uint64_t origin=0;
  uint32_t session=0;
  uint16_t index=0;
  uint8_t kind=0;
  bool used=false;
};
struct OtaRelay {
  OtaFrame frame={};
  uint32_t deadline=0;
  bool used=false;
};
struct RxEvent {
  uint16_t size=0;
  OtaFrame ota={};
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
OtaCache otaCache[128];
OtaRelay otaRelays[12];
uint32_t otaCursor=0;
uint64_t otaTarget=0;
uint32_t otaSession=0, otaSentAt=0;
uint16_t otaIndex=0;
uint8_t otaAttempts=0;
bool otaActive=false;
void sendOtaChunk();
void receiveOta(const OtaFrame &f);

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
  } else if(command.startsWith("OTA TEST ")) {
    String value=command.substring(9);value.trim();
    if(value.length()!=16 || otaActive || !ready || apMode) {
      Serial.println("[OTA] ERROR enter 16-hex target; not busy; mesh ready");return;
    }
    uint64_t parsed=0;
    for(size_t i=0;i<16;i++) {
      char c=value[i];
      int nibble=c>='0'&&c<='9'?c-'0':
        c>='A'&&c<='F'?c-'A'+10:c>='a'&&c<='f'?c-'a'+10:-1;
      if(nibble<0){Serial.println("[OTA] ERROR invalid hex");return;}
      parsed=(parsed<<4)|(uint8_t)nibble;
    }
    if(parsed==0 || parsed==nodeId){Serial.println("[OTA] ERROR invalid target");return;}
    otaTarget=parsed;otaSession=esp_random();
    if(!otaSession)otaSession=1;
    otaIndex=0;otaAttempts=0;otaActive=true;
    Serial.printf("[OTA] START target=%s session=%08lX TEST_NO_FLASH\n",
      idString(otaTarget).c_str(),(unsigned long)otaSession);
    sendOtaChunk();
  } else if(command.equalsIgnoreCase("OTA STOP")) {
    otaActive=false;Serial.println("[OTA] STOP");
  } else if(command.equalsIgnoreCase("HELP")) {
    Serial.println("[CONFIG] Commands: NAME GET | NAME SET <name> | NAME RESET | OTA TEST <16hex> | OTA STOP | HELP");
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
  if(!rxQueue || !mac || !data ||
     (length!=(int)sizeof(Packet) && length!=(int)sizeof(OtaFrame)))return;
  RxEvent event={};
  event.size=length;
  if(length==(int)sizeof(Packet))memcpy(&event.packet,data,sizeof(Packet));
  else memcpy(&event.ota,data,sizeof(OtaFrame));
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
String packetName(const Packet &p) {
  size_t length=0;
  while(length<sizeof(p.name) && p.name[length])length++;
  String result;
  for(size_t i=0;i<length;i++) {
    char c=p.name[i];
    if(!((c>='A' && c<='Z') || (c>='a' && c<='z') ||
      (c>='0' && c<='9') || c=='-' || c=='_'))return String("");
    result+=c;
  }
  return result;
}
void processRx(const RxEvent &event) {
  if(event.size==sizeof(OtaFrame)){receiveOta(event.ota);return;}
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
  String sourceName=packetName(p);
  Serial.printf("[RX] name=%s origin=%s via=%s boot=%s seq=%lu ttl=%u hops=%u type=%s rssi=%d dBm channel=%u AUTH=OK\n",
      sourceName.length()?sourceName.c_str():"(unset)",
      idString(p.origin).c_str(),macString(event.from).c_str(),
      idString(p.bootNonce).c_str(),(unsigned long)p.sequence,p.ttl,
      INITIAL_TTL-p.ttl,p.type==HEARTBEAT?"HEARTBEAT":"TEST",
      (int)event.rssi,(unsigned)event.channel);
  if(p.ttl>1)scheduleRelay(p);
}

bool otaSign(const OtaFrame &f,uint8_t out[32]) {
  const mbedtls_md_info_t *md=mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  return md && mbedtls_md_hmac(md,MESH_SECRET_KEY,sizeof(MESH_SECRET_KEY),
      reinterpret_cast<const unsigned char*>(&f),offsetof(OtaFrame,ttl),out)==0;
}
bool otaVerify(const OtaFrame &f) {
  if(f.magic!=MAGIC || f.protocol!=OTA_PROTO || f.networkId!=MESH_NETWORK_ID ||
     (f.kind!=OTA_DATA && f.kind!=OTA_ACK) || !f.origin || !f.target ||
     f.total!=OTA_TOTAL || f.index>=OTA_TOTAL || f.ttl<1 || f.ttl>INITIAL_TTL)
    return false;
  uint8_t expected[32];
  if(!otaSign(f,expected))return false;
  uint8_t difference=0;
  for(size_t i=0;i<32;i++)difference|=expected[i]^f.hmac[i];
  return difference==0;
}
bool otaSeen(const OtaFrame &f) {
  for(const OtaCache &item:otaCache)
    if(item.used && item.origin==f.origin && item.session==f.session &&
       item.index==f.index && item.kind==f.kind)return true;
  OtaCache &item=otaCache[otaCursor++%128];
  item.origin=f.origin;item.session=f.session;
  item.index=f.index;item.kind=f.kind;item.used=true;
  return false;
}
void otaSend(const OtaFrame &f) {
  esp_err_t status=esp_now_send(BROADCAST,
    reinterpret_cast<const uint8_t*>(&f),sizeof(f));
  if(status!=ESP_OK)Serial.printf("[OTA] TX_ERROR status=%d\n",(int)status);
}
void otaForward(const OtaFrame &f) {
  if(f.ttl<=1)return;
  if(otaSeen(f))return;
  for(OtaRelay &item:otaRelays)if(!item.used) {
    item.frame=f;item.frame.ttl--;
    item.deadline=millis()+35+esp_random()%120;
    item.used=true;return;
  }
  Serial.println("[OTA] RELAY_QUEUE_FULL");
}
void sendOtaChunk() {
  if(!otaActive || otaIndex>=OTA_TOTAL)return;
  OtaFrame frame={};
  frame.magic=MAGIC;frame.protocol=OTA_PROTO;frame.kind=OTA_DATA;
  frame.networkId=MESH_NETWORK_ID;
  frame.origin=nodeId;frame.target=otaTarget;frame.session=otaSession;
  frame.index=otaIndex;frame.total=OTA_TOTAL;frame.ttl=INITIAL_TTL;
  for(size_t i=0;i<OTA_BYTES;i++)
    frame.data[i]=(uint8_t)((otaIndex*17+i)&255);
  if(!otaSign(frame,frame.hmac)) {
    otaActive=false;Serial.println("[OTA] HMAC_FAILED");return;
  }
  otaAttempts++;otaSentAt=millis();
  otaSend(frame);
  Serial.printf("[OTA] CHUNK target=%s index=%u/%u attempt=%u\n",
    idString(otaTarget).c_str(),(unsigned)(otaIndex+1),
    (unsigned)OTA_TOTAL,(unsigned)otaAttempts);
}
void receiveOta(const OtaFrame &frame) {
  if(!otaVerify(frame) || frame.origin==nodeId)return;
  if(frame.target!=nodeId) {
    otaForward(frame);
    return;
  }
  if(frame.kind==OTA_ACK) {
    if(!otaActive || frame.origin!=otaTarget || frame.session!=otaSession ||
       frame.index!=otaIndex)return;
    Serial.printf("[OTA] ACK source=%s index=%u/%u hops=%u\n",
      idString(frame.origin).c_str(),(unsigned)(frame.index+1),
      (unsigned)OTA_TOTAL,(unsigned)(INITIAL_TTL-frame.ttl));
    otaIndex++;otaAttempts=0;
    if(otaIndex==OTA_TOTAL) {
      Serial.printf("[OTA] DONE target=%s bytes=%u MODE=RAM_ONLY\n",
        idString(otaTarget).c_str(),(unsigned)(OTA_TOTAL*OTA_BYTES));
      otaActive=false;
    } else sendOtaChunk();
    return;
  }
  bool duplicate=otaSeen(frame);
  if(!duplicate) {
    for(size_t i=0;i<OTA_BYTES;i++)
      if(frame.data[i]!=(uint8_t)((frame.index*17+i)&255)) {
        Serial.printf("[OTA] DATA_INVALID index=%u\n",(unsigned)frame.index);
        return;
      }
    Serial.printf("[OTA] RX_DATA from=%s index=%u/%u hops=%u RAM_ONLY\n",
      idString(frame.origin).c_str(),(unsigned)(frame.index+1),
      (unsigned)OTA_TOTAL,(unsigned)(INITIAL_TTL-frame.ttl));
  }
  // Re-ACK duplicates: previous acknowledgment may have been lost.
  OtaFrame ack={};
  ack.magic=MAGIC;ack.protocol=OTA_PROTO;ack.kind=OTA_ACK;
  ack.networkId=MESH_NETWORK_ID;ack.origin=nodeId;ack.target=frame.origin;
  ack.session=frame.session;ack.index=frame.index;
  ack.total=OTA_TOTAL;ack.ttl=INITIAL_TTL;
  if(otaSign(ack,ack.hmac))otaSend(ack);
}

void sendLocal(uint8_t type) {
  Packet p={};
  p.magic=MAGIC;p.protocol=PROTOCOL;p.type=type;
  p.networkId=MESH_NETWORK_ID;
  p.origin=nodeId;p.bootNonce=bootNonce;
  p.sequence=++nextSequence;p.uptimeMs=millis();
  // HMAC covers name, and relays preserve it unchanged.
  if(validName(nodeName))memcpy(p.name,nodeName.c_str(),nodeName.length());
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
  Serial.println("\nSmoke Listener Mesh v0.5.6 | OTA TEST ONLY; NO FLASH WRITES");
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
  if(otaActive && (uint32_t)(millis()-otaSentAt)>=1250) {
    if(otaAttempts>=5) {
      Serial.printf("[OTA] FAIL target=%s index=%u missing_ack\n",
        idString(otaTarget).c_str(),(unsigned)(otaIndex+1));
      otaActive=false;
    } else sendOtaChunk();
  }
  uint32_t now=millis();
  for(OtaRelay &item:otaRelays) {
    if(item.used && (int32_t)(now-item.deadline)>=0) {
      OtaFrame f=item.frame;item.used=false;otaSend(f);
    }
  }
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
