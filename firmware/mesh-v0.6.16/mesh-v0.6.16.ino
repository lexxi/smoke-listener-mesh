#include <Arduino.h>
#include <WiFi.h>
#include <Preferences.h>
#include <esp_ota_ops.h>
#include <esp_app_desc.h>
#include <sdkconfig.h>
#include <esp_partition.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <esp_arduino_version.h>
#include <mbedtls/md.h>
#include <mbedtls/sha256.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include "mesh_secrets.h"
#include "ota_auth.h"
#include "ota_version.h"
#include "feature_config.h"
#if SMOKE_FEATURE_AUDIO
#include "audio_monitor.h"
#endif
#if SMOKE_FEATURE_BUZZER
#include "buzzer_diagnostic.h"
#endif
#if SMOKE_FEATURE_AP
#include <WebServer.h>
#endif

// v0.6.4: read-back verification of a signed staged image; no boot-selection changes.
// Development build: signed staging and local-only guarded boot activation.
// Boot activation deliberately DISABLED; flashing requires local serial arming.
// Experimental prototype; NOT a life-safety alarm system.
// All nodes require the SAME private mesh_secrets.h.
constexpr uint8_t CHANNEL = 6, INITIAL_TTL = 3, PROTOCOL = 3;
constexpr uint32_t MAGIC = 0x534D4553, HEARTBEAT_MS = 15000;
constexpr size_t RX_QUEUE_LENGTH = 20, SEEN_LENGTH = 64, RELAY_LENGTH = 16;
constexpr uint8_t OTA_PROTO=1, OTA_DATA=1, OTA_ACK=2;
constexpr uint8_t IMG_BEGIN=3, IMG_DATA=4, IMG_ACK=5, IMG_RESULT=6;
constexpr uint8_t IMG_AUTH=7, IMG_AUTH_ACK=8, MGMT_REQUEST=9, MGMT_REPLY=10;
constexpr uint16_t IMG_MAX_BLOCKS=13654; // ceil(1310720/96)
constexpr uint16_t OTA_DEFAULT_TOTAL=16, OTA_MAX_TOTAL=4096;
constexpr uint32_t OTA_ACK_TIMEOUT_MS=1750;
constexpr uint8_t OTA_MAX_ATTEMPTS=8;
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
  uint8_t attempt;
  uint8_t data[OTA_BYTES];
  uint8_t ttl,reserved;
  uint8_t hmac[32];
};
static_assert(sizeof(OtaFrame)==165,"OTA packet size <=250");
struct OtaCache {
  uint64_t origin=0;
  uint32_t session=0;
  uint16_t index=0;
  uint8_t kind=0, attempt=0;
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
uint16_t otaIndex=0, otaTotal=OTA_DEFAULT_TOTAL;
uint8_t otaAttempts=0;
bool otaActive=false, otaDebug=false;
uint32_t otaRetries=0, otaStartedAt=0, otaAckHops=0;
uint32_t otaRxData=0, otaRxAck=0, otaRelayData=0, otaRelayAck=0, otaRelayDrops=0, otaAuthRejected=0, otaTxErrors=0;
void sendOtaChunk();
void receiveOta(const OtaFrame &f);
void imageReceive(const OtaFrame &f);
void imageRetry();
void authRetry();
void authReceive(const OtaFrame &f);
bool otaSign(const OtaFrame &f,uint8_t out[32]);
void otaSend(const OtaFrame &f);
void mgmtReceive(const OtaFrame &f);
void mgmtSendSerial(const String &line);
void mgmtPendingWatchdog();
bool validName(const String &name);

uint32_t seenCursor=0, nextSequence=0, lastHeartbeat=0;
uint32_t rxCount=0, txCount=0, relayCount=0, duplicateCount=0;
uint32_t invalidCount=0, pendingDrops=0, queueDrops=0;
uint64_t nodeId=0, bootNonce=0;
bool ready=false;
Preferences prefs;
#if SMOKE_FEATURE_AP
WebServer server(80);
bool apMode=false;
uint32_t buttonSince=0, apLastActivity=0;
const uint32_t AP_TIMEOUT_MS=300000;
#else
constexpr bool apMode=false;
#endif
String nodeName;
String serialLine;
constexpr size_t MAX_NAME_LENGTH=19; // reserve 4 authenticated bytes for version, and one NUL
// The Arduino ESP32 core otherwise marks PENDING_VERIFY as VALID during
// initArduino(), before setup() and before any mesh health check.
// Strong C linkage overrides the weak esp32-hal-misc.c hook.
extern "C" bool verifyRollbackLater() {
  return true;
}

// Release matrix may override the monotone numeric OTA version per build.
#ifndef SMOKE_FIRMWARE_VERSION
#define SMOKE_FIRMWARE_VERSION "0.6.16"
#endif
constexpr char CURRENT_FW_VERSION[]=SMOKE_FIRMWARE_VERSION;
constexpr uint32_t FLASH_ARM_WINDOW_MS=300000UL;
constexpr uint32_t BOOT_ARM_WINDOW_MS=60000UL;
bool bootVerified=false,bootArmed=false,meshPeerVerified=false;
uint32_t bootArmedAt=0;
uint32_t flashArmedAt=0;
bool flashArmed=false;
constexpr uint16_t AUTH_MAX_CHUNKS=6;
struct AuthRx {
  bool active=false,verified=false;
  uint64_t origin=0;
  uint32_t session=0,lastActivity=0,expectedSize=0;
  uint16_t length=0,total=0,next=0;
  uint8_t resultStatus=2; // 1=verified, 2=signature/format error, 3=downgrade
  String version;
  uint8_t data[576]={},expectedHash[32]={};
} authRx;
bool authActive=false,authNeedSerial=false;
uint64_t authTarget=0;
uint32_t authSession=0,authSentAt=0,authRetries=0;
uint16_t authLength=0,authTotal=0,authIndex=0;
uint8_t authAttempts=0,authPayload[OTA_BYTES]={};
void authReply(const OtaFrame &request,uint8_t status) {
  OtaFrame response={};
  response.magic=MAGIC;response.protocol=OTA_PROTO;response.kind=IMG_AUTH_ACK;
  response.networkId=MESH_NETWORK_ID;
  response.origin=nodeId;response.target=request.origin;
  response.session=request.session;response.index=request.index;
  response.total=request.total;response.attempt=request.attempt;
  response.ttl=INITIAL_TTL;response.data[0]=status;
  if(otaSign(response,response.hmac))otaSend(response);
}
void authStop(const char *reason) {
  Serial.printf("[AUTH] FAIL %s index=%u/%u NO_FLASH\n",
    reason,(unsigned)authIndex,(unsigned)authTotal);
  authActive=false;authNeedSerial=false;
}
void authRetry() {
  if(!authActive || authNeedSerial)return;
  if(authAttempts>=OTA_MAX_ATTEMPTS){authStop("missing_ack");return;}
  OtaFrame f={};
  f.magic=MAGIC;f.protocol=OTA_PROTO;f.kind=IMG_AUTH;
  f.networkId=MESH_NETWORK_ID;f.origin=nodeId;f.target=authTarget;
  f.session=authSession;f.index=authIndex;f.total=authTotal;
  f.attempt=++authAttempts;f.ttl=INITIAL_TTL;
  if(authAttempts>1)authRetries++;
  memcpy(f.data,authPayload,OTA_BYTES);
  if(!otaSign(f,f.hmac)){authStop("hmac");return;}
  authSentAt=millis();otaSend(f);
  Serial.printf("[AUTH] SEND index=%u/%u attempt=%u\n",
    (unsigned)(authIndex+1),(unsigned)authTotal,(unsigned)authAttempts);
}
struct ImageReceiver {
  bool active=false, complete=false, valid=false;
  uint64_t origin=0;
  uint32_t session=0, size=0, count=0, lastActivity=0;
  uint16_t total=0, next=0;
  uint8_t shaExpected[32]={};
  bool stage=false,otaOpen=false;
  esp_ota_handle_t otaHandle=0;
  const esp_partition_t *otaPartition=nullptr;
  mbedtls_sha256_context hash;
} imgRx;
bool imgActive=false, imgWaitSerial=false, imgBegin=true, imgStage=false;
uint64_t imgTarget=0;
uint32_t imgSession=0, imgSize=0, imgSentAt=0, imgStartedAt=0, imgRetries=0;
uint16_t imgTotal=0, imgIndex=0;
uint8_t imgAttempts=0, imgPayload[OTA_BYTES]={}, imgSha[32]={};

void authReceive(const OtaFrame &f) {
  if(f.kind==IMG_AUTH_ACK) {
    if(!authActive || authNeedSerial || f.origin!=authTarget ||
       f.session!=authSession || f.index!=authIndex ||
       f.total!=authTotal || f.attempt>authAttempts)return;
    if(f.data[0]==2){authStop("signature_rejected");return;}
    if(f.data[0]==3){authStop("DOWNGRADE_REJECTED");return;}
    if(f.index+1==authTotal) {
      if(f.data[0]!=1){authStop("unverified");return;}
      Serial.printf("[AUTH] PASS target=%s bytes=%u retries=%lu VERIFIED_ON_DEVICE NO_FLASH\n",
        idString(authTarget).c_str(),(unsigned)authLength,(unsigned long)authRetries);
      authActive=false;return;
    }
    if(f.data[0]!=0)return;
    authIndex++;authAttempts=0;authNeedSerial=true;
    Serial.printf("[AUTH] NEXT index=%u/%u\n",
      (unsigned)authIndex,(unsigned)authTotal);
    return;
  }
  if(f.kind!=IMG_AUTH)return;
  // Freeze authorizations during an active image stream.
  if(imgRx.active && !imgRx.complete)return;
  if(f.index==0 && (!authRx.active || authRx.session!=f.session ||
                     authRx.origin!=f.origin)) {
    // Accept a new session only if the old one is complete or has timed out.
    if(authRx.active && authRx.next<authRx.total &&
       (uint32_t)(millis()-authRx.lastActivity)<120000UL)return;
    bootVerified=false;bootArmed=false;
    authRx=AuthRx{};
    authRx.active=true;authRx.origin=f.origin;authRx.session=f.session;
    authRx.total=f.total;
    authRx.length=(uint16_t)f.data[0]|((uint16_t)f.data[1]<<8);
    if(authRx.length<40 || authRx.length>sizeof(authRx.data) ||
       (authRx.length+OTA_BYTES-1)/OTA_BYTES!=f.total){
      authRx.active=false;return;
    }
    Serial.printf("[AUTH] BEGIN source=%s bytes=%u blocks=%u\n",
      idString(f.origin).c_str(),(unsigned)authRx.length,(unsigned)authRx.total);
  }
  if(!authRx.active || f.origin!=authRx.origin ||
     f.session!=authRx.session || f.total!=authRx.total)return;
  authRx.lastActivity=millis();
  if(f.index<authRx.next) {
    authReply(f,f.index+1==authRx.total?authRx.resultStatus:0);
    return;
  }
  if(f.index!=authRx.next)return;
  memcpy(authRx.data+(size_t)f.index*OTA_BYTES,f.data,OTA_BYTES);
  authRx.next++;
  if(authRx.next==authRx.total) {
    authRx.verified=releaseVerify(authRx.data+2,authRx.length-2,
      nodeId,authRx.expectedSize,authRx.expectedHash,authRx.version);
    authRx.resultStatus=authRx.verified?1:2;
    if(authRx.verified && !newerFirmwareVersion(authRx.version,CURRENT_FW_VERSION)) {
      authRx.verified=false;
      authRx.resultStatus=3;
      Serial.printf("[AUTH] REJECT downgrade_or_same_version signed=%s running=%s\n",
        authRx.version.c_str(),CURRENT_FW_VERSION);
    }
    Serial.printf("[AUTH] RESULT source=%s result=%s NO_FLASH\n",
      idString(f.origin).c_str(),
      authRx.resultStatus==1?"SIGNATURE_OK":authRx.resultStatus==3?"DOWNGRADE_REJECTED":"SIGNATURE_FAIL");
    authReply(f,authRx.resultStatus);
  } else authReply(f,0);
}


int imageNibble(char c) {
  if(c>='0'&&c<='9')return c-'0';
  if(c>='a'&&c<='f')return c-'a'+10;
  if(c>='A'&&c<='F')return c-'A'+10;
  return -1;
}
bool imageHex(const String &s,uint8_t *result,size_t n) {
  if(s.length()!=n*2)return false;
  for(size_t i=0;i<n;i++) {
    int hi=imageNibble(s[i*2]),lo=imageNibble(s[i*2+1]);
    if(hi<0||lo<0)return false;
    result[i]=(hi<<4)|lo;
  }
  return true;
}
void imageStop(const char *reason) {
  Serial.printf("[IMAGE] FAIL %s index=%u/%u retries=%lu NO_FLASH\n",
    reason,(unsigned)imgIndex,(unsigned)imgTotal,(unsigned long)imgRetries);
  imgActive=false;imgWaitSerial=false;
}
void imageReply(const OtaFrame &request,uint8_t kind,uint8_t status) {
  OtaFrame response={};
  response.magic=MAGIC;response.protocol=OTA_PROTO;response.kind=kind;
  response.networkId=MESH_NETWORK_ID;
  response.origin=nodeId;response.target=request.origin;response.session=request.session;
  response.index=request.index;response.total=request.total;response.attempt=request.attempt;
  response.ttl=INITIAL_TTL;response.data[0]=status;
  if(otaSign(response,response.hmac))otaSend(response);
}
void imageRetry() {
  if(!imgActive || imgWaitSerial)return;
  if(imgAttempts>=OTA_MAX_ATTEMPTS){imageStop("missing_ack");return;}
  OtaFrame f={};
  f.magic=MAGIC;f.protocol=OTA_PROTO;f.networkId=MESH_NETWORK_ID;
  f.kind=imgBegin?IMG_BEGIN:IMG_DATA;
  f.origin=nodeId;f.target=imgTarget;f.session=imgSession;
  f.total=imgTotal;f.index=imgBegin?0:imgIndex;
  f.ttl=INITIAL_TTL;f.attempt=++imgAttempts;
  if(imgAttempts>1)imgRetries++;
  if(imgBegin){memcpy(f.data,&imgSize,sizeof(imgSize));memcpy(f.data+4,imgSha,32);
    f.data[36]=imgStage?1:0;}
  else memcpy(f.data,imgPayload,OTA_BYTES);
  if(!otaSign(f,f.hmac)){imageStop("hmac");return;}
  imgSentAt=millis();
  otaSend(f);
  if(imgBegin || imgIndex%128==0 || imgAttempts>1)
    Serial.printf("[IMAGE] SEND kind=%s index=%u/%u attempt=%u\n",
      imgBegin?"BEGIN":"DATA",(unsigned)(f.index+1),(unsigned)imgTotal,(unsigned)imgAttempts);
}
void imageReceive(const OtaFrame &f) {
  if(f.kind==IMG_ACK || f.kind==IMG_RESULT) {
    if(!imgActive || f.origin!=imgTarget || f.session!=imgSession ||
       f.total!=imgTotal || f.attempt>imgAttempts || imgWaitSerial)return;
    if(f.kind==IMG_RESULT) {
      if(imgBegin || imgIndex+1!=imgTotal || f.index!=imgIndex)return;
      if(f.data[0]==1){
        Serial.printf("[IMAGE] DONE target=%s bytes=%lu blocks=%u retries=%lu duration_ms=%lu SHA256_OK %s BOOT_UNCHANGED\n",
          idString(imgTarget).c_str(),(unsigned long)imgSize,(unsigned)imgTotal,
          (unsigned long)imgRetries,(unsigned long)(millis()-imgStartedAt),
          imgStage?"STAGED_INACTIVE":"NO_FLASH");
        imgActive=false;
      } else imageStop("target_sha256_mismatch");
      return;
    }
    if(f.data[0]!=0)return;
    if(imgBegin) {
      if(f.index!=0)return;
      imgBegin=false;imgIndex=0;imgAttempts=0;imgWaitSerial=true;
      Serial.printf("[IMAGE] NEXT index=%u/%u\n",(unsigned)imgIndex,(unsigned)imgTotal);
    } else if(f.index==imgIndex && imgIndex+1<imgTotal) {
      imgIndex++;imgAttempts=0;imgWaitSerial=true;
      Serial.printf("[IMAGE] NEXT index=%u/%u\n",(unsigned)imgIndex,(unsigned)imgTotal);
    }
    return;
  }
  if(f.kind==IMG_BEGIN) {
    uint32_t length=0;memcpy(&length,f.data,4);
    if(f.data[36]>1)return;
    bool stageRequested=f.data[36]==1;
    // FAIL CLOSED: only this origin may stream exactly the signed image.
    if(!authRx.active || !authRx.verified || authRx.origin!=f.origin ||
       (uint32_t)(millis()-authRx.lastActivity)>=120000UL ||
       length!=authRx.expectedSize ||
       memcmp(f.data+4,authRx.expectedHash,32)!=0) {
      Serial.println("[IMAGE] REJECT missing_or_mismatched_device_signature");
      return;
    }
    const bool sameImageSession=imgRx.active && imgRx.origin==f.origin &&
      imgRx.session==f.session && imgRx.stage==stageRequested;
    if(stageRequested && !sameImageSession &&
       (!flashArmed || (uint32_t)(millis()-flashArmedAt)>=FLASH_ARM_WINDOW_MS)) {
      flashArmed=false;
      Serial.println("[IMAGE] REJECT target_not_locally_armed_for_flash");
      return;
    }
    if(!length || length>1310720UL ||
       (length+OTA_BYTES-1)/OTA_BYTES!=f.total)return;
    const esp_partition_t *slot=esp_ota_get_next_update_partition(nullptr);
    const esp_partition_t *running=esp_ota_get_running_partition();
    if(!slot || !running || slot==running || length>slot->size)return;
    if(imgRx.active && !imgRx.complete && (imgRx.origin!=f.origin || imgRx.session!=f.session) &&
       (uint32_t)(millis()-imgRx.lastActivity)<120000UL)return;
    if(!imgRx.active || imgRx.origin!=f.origin || imgRx.session!=f.session) {
      if(imgRx.active && !imgRx.complete) {
        mbedtls_sha256_free(&imgRx.hash);
        if(imgRx.otaOpen){esp_ota_abort(imgRx.otaHandle);imgRx.otaOpen=false;}
      }
      imgRx.active=true;imgRx.complete=false;imgRx.valid=false;
      imgRx.origin=f.origin;imgRx.session=f.session;imgRx.total=f.total;
      imgRx.size=length;imgRx.count=0;imgRx.next=0;
      imgRx.stage=stageRequested;imgRx.otaOpen=false;
      imgRx.otaPartition=slot;
      memcpy(imgRx.shaExpected,f.data+4,32);
      if(stageRequested) {
        flashArmed=false; // one-time local authorization is consumed
        esp_err_t e=esp_ota_begin(slot,length,&imgRx.otaHandle);
        if(e!=ESP_OK) {
          imgRx.active=false;
          Serial.printf("[IMAGE] FLASH_BEGIN_FAIL err=%d BOOT_UNCHANGED\n",(int)e);
          return;
        }
        imgRx.otaOpen=true;
      }
      mbedtls_sha256_init(&imgRx.hash);
      if(mbedtls_sha256_starts(&imgRx.hash,0)!=0){
        mbedtls_sha256_free(&imgRx.hash);
        if(imgRx.otaOpen){esp_ota_abort(imgRx.otaHandle);imgRx.otaOpen=false;}
        imgRx.active=false;return;
      }
      Serial.printf("[IMAGE] BEGIN from=%s bytes=%lu blocks=%u mode=%s BOOT_UNCHANGED\n",
        idString(f.origin).c_str(),(unsigned long)length,(unsigned)f.total,
        imgRx.stage?"FLASH_STAGE":"RAM_ONLY");
    } else if(length!=imgRx.size || memcmp(imgRx.shaExpected,f.data+4,32)!=0)return;
    imgRx.lastActivity=millis();imageReply(f,IMG_ACK,0);return;
  }
  if(f.kind!=IMG_DATA || !imgRx.active ||
     f.origin!=imgRx.origin || f.session!=imgRx.session || f.total!=imgRx.total)return;
  imgRx.lastActivity=millis();
  if(f.index<imgRx.next) {
    if(imgRx.complete && f.index==imgRx.total-1)
      imageReply(f,IMG_RESULT,imgRx.valid?1:2);
    else imageReply(f,IMG_ACK,0);
    return;
  }
  if(imgRx.complete || f.index!=imgRx.next)return;
  const uint32_t remaining=imgRx.size-imgRx.count;
  const size_t length=remaining<OTA_BYTES?remaining:OTA_BYTES;
  if(!length || mbedtls_sha256_update(&imgRx.hash,f.data,length)!=0){
    mbedtls_sha256_free(&imgRx.hash);
    if(imgRx.otaOpen){esp_ota_abort(imgRx.otaHandle);imgRx.otaOpen=false;}
    imgRx.active=false;return;
  }
  if(imgRx.stage) {
    esp_err_t e=esp_ota_write(imgRx.otaHandle,f.data,length);
    if(e!=ESP_OK) {
      mbedtls_sha256_free(&imgRx.hash);
      if(imgRx.otaOpen){esp_ota_abort(imgRx.otaHandle);imgRx.otaOpen=false;}
      imgRx.active=false;
      Serial.printf("[IMAGE] FLASH_WRITE_FAIL index=%u err=%d BOOT_UNCHANGED\n",
        (unsigned)f.index,(int)e);
      imageReply(f,IMG_RESULT,2);return;
    }
  }
  imgRx.count+=length;imgRx.next++;
  if(imgRx.next==imgRx.total) {
    uint8_t actual[32]={};
    imgRx.valid=(mbedtls_sha256_finish(&imgRx.hash,actual)==0 &&
                 imgRx.count==imgRx.size);
    mbedtls_sha256_free(&imgRx.hash);
    uint8_t diff=0;
    for(size_t i=0;i<32;i++)diff|=actual[i]^imgRx.shaExpected[i];
    imgRx.valid=imgRx.valid && diff==0;
    if(imgRx.stage && imgRx.otaOpen) {
      if(imgRx.valid) {
        esp_err_t e=esp_ota_end(imgRx.otaHandle);
        imgRx.otaOpen=false;
        if(e!=ESP_OK) {
          imgRx.valid=false;
          Serial.printf("[IMAGE] FLASH_IMAGE_INVALID err=%d BOOT_UNCHANGED\n",(int)e);
        }
      } else {
        esp_ota_abort(imgRx.otaHandle);
        imgRx.otaOpen=false;
      }
    }
    imgRx.complete=true;
    Serial.printf("[IMAGE] RESULT bytes=%lu SHA256_%s %s BOOT_UNCHANGED\n",
      (unsigned long)imgRx.count,imgRx.valid?"OK":"FAIL",
      imgRx.stage?"FLASH_STAGE":"RAM_ONLY");
    imageReply(f,IMG_RESULT,imgRx.valid?1:2);
  } else {
    if(imgRx.next%256==0)
      Serial.printf("[IMAGE] PROGRESS blocks=%u/%u\n",
        (unsigned)imgRx.next,(unsigned)imgRx.total);
    imageReply(f,IMG_ACK,0);
  }
}


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

void printOtaPreflight() {
  const esp_partition_t *running=esp_ota_get_running_partition();
  const esp_partition_t *next=esp_ota_get_next_update_partition(nullptr);
  const esp_partition_t *boot=esp_ota_get_boot_partition();
  Serial.printf("[OTA] PREFLIGHT running=%s size=%lu subtype=%u\n",
    running?running->label:"(none)",(unsigned long)(running?running->size:0),
    (unsigned)(running?running->subtype:0));
  Serial.printf("[OTA] PREFLIGHT next=%s size=%lu subtype=%u\n",
    next?next->label:"(none)",(unsigned long)(next?next->size:0),
    (unsigned)(next?next->subtype:0));
  Serial.printf("[OTA] PREFLIGHT boot=%s\n",boot?boot->label:"(none)");
  if(!running || !next || !boot || running==next ||
     next->type!=ESP_PARTITION_TYPE_APP || next->size<1000000) {
    Serial.println("[OTA] PREFLIGHT FAIL: no separate suitable OTA app slot");
    return;
  }
  esp_ota_img_states_t state=ESP_OTA_IMG_UNDEFINED;
  esp_err_t result=esp_ota_get_state_partition(running,&state);
  Serial.printf("[OTA] PREFLIGHT image_state_result=%d image_state=%d\n",(int)result,(int)state);
  if(result==ESP_OK && state==ESP_OTA_IMG_PENDING_VERIFY) {
    Serial.println("[OTA] PREFLIGHT FAIL: running image still pending validation");
    return;
  }
  Serial.println("[OTA] PREFLIGHT PASS: separate OTA app slot exists; no flash operation attempted");
}

void printBootDiagnostics() {
  const esp_partition_t *running=esp_ota_get_running_partition();
  const esp_partition_t *boot=esp_ota_get_boot_partition();
  const esp_partition_t *next=esp_ota_get_next_update_partition(nullptr);
  Serial.printf("[BOOT] running=%s boot=%s inactive=%s version=%s\n",
    running?running->label:"(none)",boot?boot->label:"(none)",
    next?next->label:"(none)",CURRENT_FW_VERSION);
#if defined(CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE) && CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE
  Serial.println("[BOOT] app_rollback_config=1");
#elif defined(CONFIG_BOOTLOADER_APP_ROLLBACK) && CONFIG_BOOTLOADER_APP_ROLLBACK
  Serial.println("[BOOT] app_rollback_config=1");
#else
  Serial.println("[BOOT] app_rollback_config=0");
#endif
#if defined(CONFIG_BOOTLOADER_APP_ROLLBACK_CONFIRM_BY_APP) && CONFIG_BOOTLOADER_APP_ROLLBACK_CONFIRM_BY_APP
  Serial.println("[BOOT] confirmation_mode=BY_APP");
#elif defined(CONFIG_BOOTLOADER_APP_ROLLBACK_CONFIRM_ON_STARTUP) && CONFIG_BOOTLOADER_APP_ROLLBACK_CONFIRM_ON_STARTUP
  Serial.println("[BOOT] confirmation_mode=ON_STARTUP");
#else
  Serial.println("[BOOT] confirmation_mode=DEFERRED_BY_VERIFY_ROLLBACK_LATER");
#endif
  if(running) {
    esp_ota_img_states_t state=ESP_OTA_IMG_UNDEFINED;
    esp_err_t err=esp_ota_get_state_partition(running,&state);
    Serial.printf("[BOOT] running_state_result=%d running_state=%d\n",(int)err,(int)state);
  }
  if(next) {
    esp_ota_img_states_t state=ESP_OTA_IMG_UNDEFINED;
    esp_err_t err=esp_ota_get_state_partition(next,&state);
    Serial.printf("[BOOT] inactive_state_result=%d inactive_state=%d\n",(int)err,(int)state);
    esp_app_desc_t desc={};
    err=esp_ota_get_partition_description(next,&desc);
    Serial.printf("[BOOT] inactive_image_desc_result=%d app_version=%s project=%s\n",
      (int)err,err==ESP_OK?desc.version:"(unreadable)",
      err==ESP_OK?desc.project_name:"(unreadable)");
  }
  Serial.printf("[BOOT] activation=LOCAL_ARM_ONLY verified=%u arm_valid=%u mesh_peer_verified=%u rollback_hardware_test=NOT_DONE\n",
    (unsigned)bootVerified,
    (unsigned)(bootArmed && (uint32_t)(millis()-bootArmedAt)<BOOT_ARM_WINDOW_MS),
    (unsigned)meshPeerVerified);
}
// Verify exact signed-image bytes from the inactive slot, not only the RAM transfer hash.
// This diagnostic intentionally does NOT change otadata or boot selection.
// Re-send a freshly signed upgrade manifest and stage its matching image in the same
// boot session before running BOOT VERIFY. A reset clears the authorization.
void verifyStagedImageReadback() {
  bootVerified=false;
  const esp_partition_t *running=esp_ota_get_running_partition();
  const esp_partition_t *slot=esp_ota_get_next_update_partition(nullptr);
  if(!running || !slot || running==slot || !ready || apMode ||
     !authRx.verified || !imgRx.complete || !imgRx.valid || !imgRx.stage ||
     imgRx.origin!=authRx.origin ||
     imgRx.size!=authRx.expectedSize ||
     imgRx.size>slot->size || imgRx.otaPartition!=slot ||
     !newerFirmwareVersion(authRx.version,CURRENT_FW_VERSION)) {
    Serial.println("[BOOT] VERIFY FAIL session_or_partition_not_verified BOOT_UNCHANGED");
    return;
  }
  if(memcmp(imgRx.shaExpected,authRx.expectedHash,32)!=0) {
    Serial.println("[BOOT] VERIFY FAIL manifest_hash_mismatch BOOT_UNCHANGED");
    return;
  }
  uint8_t buffer[1024];
  uint8_t actual[32]={};
  mbedtls_sha256_context sha;
  mbedtls_sha256_init(&sha);
  bool ok=mbedtls_sha256_starts(&sha,0)==0;
  for(uint32_t offset=0;ok && offset<imgRx.size;) {
    size_t n=(size_t)(imgRx.size-offset);
    if(n>sizeof(buffer))n=sizeof(buffer);
    if(esp_partition_read(slot,offset,buffer,n)!=ESP_OK ||
       mbedtls_sha256_update(&sha,buffer,n)!=0) {
      ok=false;
      break;
    }
    offset+=(uint32_t)n;
    if((offset&0x3fff)==0)delay(1); // allow system tasks to run
  }
  if(ok)ok=mbedtls_sha256_finish(&sha,actual)==0;
  mbedtls_sha256_free(&sha);
  if(!ok || memcmp(actual,authRx.expectedHash,32)!=0) {
    Serial.println("[BOOT] VERIFY FAIL inactive_flash_sha256 BOOT_UNCHANGED");
    return;
  }
  esp_app_desc_t desc={};
  esp_err_t err=esp_ota_get_partition_description(slot,&desc);
  if(err!=ESP_OK) {
    Serial.printf("[BOOT] VERIFY FAIL image_desc err=%d BOOT_UNCHANGED\n",(int)err);
    return;
  }
  Serial.printf("[BOOT] VERIFY PASS signed=%s bytes=%lu slot=%s SHA256_OK BOOT_UNCHANGED\n",
    authRx.version.c_str(),(unsigned long)imgRx.size,slot->label);
  bootVerified=true;
  Serial.println("[BOOT] VERIFY COMPLETE. Boot selection unchanged; local arming is separate.");
}

void activateStagedSlot() {
  bool validArm=bootArmed && (uint32_t)(millis()-bootArmedAt)<BOOT_ARM_WINDOW_MS;
  bootArmed=false;
  if(!validArm || !bootVerified) {
    Serial.println("[BOOT] ACTIVATE REFUSED missing_arm_or_verification BOOT_UNCHANGED");
    return;
  }
#if !defined(CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE) || !CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE
  Serial.println("[BOOT] ACTIVATE REFUSED rollback_not_enabled BOOT_UNCHANGED");
  return;
#endif
  const esp_partition_t *running=esp_ota_get_running_partition();
  const esp_partition_t *next=esp_ota_get_next_update_partition(nullptr);
  esp_ota_img_states_t runningState=ESP_OTA_IMG_UNDEFINED;
  if(!running || !next || next==running ||
     esp_ota_get_boot_partition()!=running ||
     esp_ota_get_state_partition(running,&runningState)!=ESP_OK ||
     (runningState!=ESP_OTA_IMG_VALID && runningState!=ESP_OTA_IMG_UNDEFINED)) {
    Serial.println("[BOOT] ACTIVATE REFUSED running_slot_state BOOT_UNCHANGED");
    return;
  }
  // Fresh readback immediately before changing the boot selection.
  verifyStagedImageReadback();
  if(!bootVerified) {
    Serial.println("[BOOT] ACTIVATE REFUSED readback_failed BOOT_UNCHANGED");
    return;
  }
  esp_err_t err=esp_ota_set_boot_partition(next);
  if(err!=ESP_OK) {
    Serial.printf("[BOOT] ACTIVATE FAILED esp_ota_set_boot_partition=%d\n",(int)err);
    return;
  }
  bootVerified=false;
  Serial.printf("[BOOT] ACTIVATE SUCCESS next_boot=%s running=%s NO_AUTO_REBOOT\n",
    next->label,running->label);
  Serial.println("[BOOT] WARNING: reboot requires physical operator; rollback not tested");
}

// Remote management extension for experimental web-only updates.
// Management commands are accepted only from explicitly trusted gateway node IDs.
// This embedded allowlist is independent from web/gateways.json; receiver firmware
// must be rebuilt and deployed when trusted gateway identities change.
// A fresh boot-local nonce is required for every state-changing command.
// Successful commands rotate the nonce, so replayed frames do not execute again.
constexpr uint64_t MGMT_TRUST_KUECHE=0x000094457F6E27ACULL;
constexpr uint64_t MGMT_TRUST_GARAGE=0x000058FE7D6E27ACULL;
constexpr uint64_t MGMT_TRUST_GATEWAY=0x00000CEC7E6E27ACULL;
constexpr uint8_t MGMT_STATUS=1,MGMT_ARM=2,MGMT_VERIFY=3,MGMT_ACTIVATE=4,
  MGMT_REBOOT=5,MGMT_CONFIRM=6,MGMT_NAME_GET=7,MGMT_NAME_SET=8,
  MGMT_NAME_RESET=9,MGMT_RESTART=10;
uint64_t mgmtNonce=0;
uint64_t mgmtTarget=0;
uint32_t mgmtRequestSession=0,mgmtRebootAt=0,mgmtRequestAt=0;
bool mgmtActivationDone=false;
uint8_t mgmtRequestedAction=0;
bool mgmtWaiting=false;
bool mgmtAllowed(uint64_t origin){
  return origin==MGMT_TRUST_KUECHE || origin==MGMT_TRUST_GARAGE ||
         origin==MGMT_TRUST_GATEWAY;
}
const char *mgmtActionName(uint8_t action){
  switch(action){
    case MGMT_STATUS:return "STATUS";
    case MGMT_ARM:return "ARM";
    case MGMT_VERIFY:return "VERIFY";
    case MGMT_ACTIVATE:return "ACTIVATE";
    case MGMT_REBOOT:return "REBOOT";
    case MGMT_CONFIRM:return "CONFIRM";
    case MGMT_NAME_GET:return "NAME_GET";
    case MGMT_NAME_SET:return "NAME_SET";
    case MGMT_NAME_RESET:return "NAME_RESET";
    case MGMT_RESTART:return "RESTART";
  }
  return "UNKNOWN";
}
bool mgmtHexId(const String &name,uint64_t &v){
  if(name.length()!=16)return false;
  v=0;
  for(int i=0;i<16;i++) {
    int digit=imageNibble(name[i]);
    if(digit<0)return false;
    v=(v<<4)|(uint64_t)digit;
  }
  return v!=0;
}
void mgmtReply(const OtaFrame &req,uint8_t result){
  OtaFrame f={};
  f.magic=MAGIC;f.protocol=OTA_PROTO;f.kind=MGMT_REPLY;
  f.networkId=MESH_NETWORK_ID;f.origin=nodeId;f.target=req.origin;
  f.session=req.session;f.index=0;f.total=1;f.attempt=req.attempt;
  f.ttl=INITIAL_TTL;
  f.data[0]=req.data[0];f.data[1]=result;
  memcpy(f.data+2,&mgmtNonce,sizeof(mgmtNonce));
  const esp_partition_t *run=esp_ota_get_running_partition();
  const esp_partition_t *boot=esp_ota_get_boot_partition();
  f.data[10]=run&&run->subtype==ESP_PARTITION_SUBTYPE_APP_OTA_0?0:
    run&&run->subtype==ESP_PARTITION_SUBTYPE_APP_OTA_1?1:255;
  f.data[11]=boot&&boot->subtype==ESP_PARTITION_SUBTYPE_APP_OTA_0?0:
    boot&&boot->subtype==ESP_PARTITION_SUBTYPE_APP_OTA_1?1:255;
  esp_ota_img_states_t state=ESP_OTA_IMG_UNDEFINED;
  f.data[12]=run&&esp_ota_get_state_partition(run,&state)==ESP_OK?(uint8_t)state:255;
  f.data[13]=(uint8_t)(imgRx.complete && imgRx.valid && imgRx.stage);
  f.data[14]=(uint8_t)bootVerified;
  f.data[15]=(uint8_t)meshPeerVerified;
  uint16_t versionParts[3]={};
  char variant=0;
  if(parseFirmwareVersion(String(CURRENT_FW_VERSION),versionParts,variant) &&
     versionParts[0]<=255 && versionParts[1]<=255 && versionParts[2]<=255){
    f.data[16]=(uint8_t)versionParts[0];
    f.data[17]=(uint8_t)versionParts[1];
    f.data[18]=(uint8_t)versionParts[2];
    f.data[19]=variant?(uint8_t)(variant-'a'+1):0;
  }
  // Name is transmitted within the already authenticated OTA frame.
  // ASCII permitted characters exclude whitespace and delimiters.
  if(validName(nodeName))memcpy(f.data+20,nodeName.c_str(),nodeName.length());
  if(otaSign(f,f.hmac))otaSend(f);
}
void mgmtReceive(const OtaFrame &f){
  if(f.kind==MGMT_REPLY){
    if(!mgmtWaiting || f.target!=nodeId || f.origin!=mgmtTarget ||
       f.session!=mgmtRequestSession || f.data[0]!=mgmtRequestedAction)return;
    uint64_t nonce=0;memcpy(&nonce,f.data+2,sizeof(nonce));
    char remoteName[MAX_NAME_LENGTH+1]={};
    memcpy(remoteName,f.data+20,MAX_NAME_LENGTH);
    String safeName=String(remoteName);
    if(!validName(safeName))safeName="(unset)";
    Serial.printf("[MGMT] REPLY origin=%s action=%s result=%u nonce=%s running=app%u boot=app%u state=%u staged=%u verified=%u peer=%u version=%u.%u.%u%s name=%s\n",
      idString(f.origin).c_str(),mgmtActionName(f.data[0]),(unsigned)f.data[1],
      idString(nonce).c_str(),(unsigned)f.data[10],(unsigned)f.data[11],
      (unsigned)f.data[12],(unsigned)f.data[13],(unsigned)f.data[14],
      (unsigned)f.data[15],(unsigned)f.data[16],(unsigned)f.data[17],(unsigned)f.data[18],
      (f.data[19]>=1&&f.data[19]<=8?(String(".")+char('a'+f.data[19]-1)):String("")).c_str(),safeName.c_str());
    mgmtWaiting=false;
    return;
  }
  if(!mgmtAllowed(f.origin) || !ready || apMode || f.total!=1 || f.index!=0)return;
  const uint8_t action=f.data[0];
  if(action<MGMT_STATUS || action>MGMT_RESTART)return;
  uint64_t supplied=0;memcpy(&supplied,f.data+2,sizeof(supplied));
  if(action!=MGMT_STATUS && (!mgmtNonce || supplied!=mgmtNonce)){
    mgmtReply(f,2);return;
  }
  uint8_t result=1;
  if(action==MGMT_STATUS){
    result=0;
  } else if(action==MGMT_ARM) {
    if(authRx.active && authRx.verified && authRx.origin==f.origin &&
       (uint32_t)(millis()-authRx.lastActivity)<120000UL &&
       newerFirmwareVersion(authRx.version,CURRENT_FW_VERSION) &&
       !(imgRx.active && !imgRx.complete)){
      flashArmed=true;flashArmedAt=millis();result=0;
    }
  } else if(action==MGMT_VERIFY){
    if(imgRx.complete && imgRx.valid && imgRx.stage && imgRx.origin==f.origin &&
       authRx.verified && authRx.origin==f.origin){
      verifyStagedImageReadback();
      result=bootVerified?0:1;
    }
  } else if(action==MGMT_ACTIVATE){
    if(bootVerified && imgRx.origin==f.origin && authRx.origin==f.origin){
      bootArmed=true;bootArmedAt=millis();
      const esp_partition_t *run=esp_ota_get_running_partition();
      activateStagedSlot();
      result=run && esp_ota_get_boot_partition()!=run?0:1;
      if(result==0)mgmtActivationDone=true;
    }
  } else if(action==MGMT_REBOOT){
    const esp_partition_t *run=esp_ota_get_running_partition();
    const esp_partition_t *boot=esp_ota_get_boot_partition();
    if(run && boot && run!=boot && !mgmtRebootAt && mgmtActivationDone){
      mgmtRebootAt=millis()+1800UL;result=0;
    }
  } else if(action==MGMT_NAME_GET){
    result=0;
  } else if(action==MGMT_NAME_SET){
    char requested[MAX_NAME_LENGTH+1]={};
    memcpy(requested,f.data+20,MAX_NAME_LENGTH);
    String name=String(requested);
    // Reject unterminated/overlong and names containing invalid characters.
    if(validName(name) && f.data[20+name.length()]==0 &&
       prefs.begin("smoke-mesh",false)) {
      size_t written=prefs.putString("name",name);
      prefs.end();
      if(written==name.length()){nodeName=name;result=0;}
    }
  } else if(action==MGMT_NAME_RESET){
    if(prefs.begin("smoke-mesh",false)) {
      bool removed=prefs.remove("name");
      prefs.end();
      if(removed || !nodeName.length()){nodeName="";result=0;}
    }
  } else if(action==MGMT_RESTART){
    // Ordinary restart must NEVER change the boot slot or bypass pending OTA checks.
    const esp_partition_t *run=esp_ota_get_running_partition();
    if(run && esp_ota_get_boot_partition()==run && !mgmtRebootAt &&
       !imgRx.otaOpen && !(imgRx.active && !imgRx.complete)) {
      mgmtRebootAt=millis()+1800UL;result=0;
    }
  } else if(action==MGMT_CONFIRM){
    const esp_partition_t *run=esp_ota_get_running_partition();
    esp_ota_img_states_t state=ESP_OTA_IMG_UNDEFINED;
    if(run && esp_ota_get_state_partition(run,&state)==ESP_OK &&
       state==ESP_OTA_IMG_PENDING_VERIFY && meshPeerVerified &&
       millis()>=15000UL){
      result=esp_ota_mark_app_valid_cancel_rollback()==ESP_OK?0:1;
    }
  }
  if(result==0 && action!=MGMT_STATUS){
    mgmtNonce=((uint64_t)esp_random()<<32)|esp_random();
    if(!mgmtNonce)mgmtNonce=1;
  }
  Serial.printf("[MGMT] COMMAND from=%s action=%s result=%u\n",
    idString(f.origin).c_str(),mgmtActionName(action),(unsigned)result);
  mgmtReply(f,result);
}
#if SMOKE_FEATURE_GATEWAY
void mgmtSendSerial(const String &line){
  // Gateway command: MGMT <16hex-target> <ACTION> [16hex nonce] [NAME]
  // NAME may only appear for NAME_SET; preserve exact case.
  if(!ready || apMode || mgmtWaiting || authActive || imgActive){
    Serial.println("[MGMT] ERROR busy");return;
  }
  String rest=line.substring(5);rest.trim();
  int split=rest.indexOf(' ');
  if(split!=16){Serial.println("[MGMT] ERROR syntax");return;}
  String targetText=rest.substring(0,split);
  String command=rest.substring(split+1);command.trim();
  uint64_t target=0,nonce=0;
  if(!mgmtHexId(targetText,target) || target==nodeId){
    Serial.println("[MGMT] ERROR target");return;
  }
  int space=command.indexOf(' ');
  String actionName=space<0?command:command.substring(0,space);
  actionName.toUpperCase();
  String params=space<0?"":command.substring(space+1);
  params.trim();
  int nextSpace=params.indexOf(' ');
  String nonceText=nextSpace<0?params:params.substring(0,nextSpace);
  String requestedName=nextSpace<0?"":params.substring(nextSpace+1);
  uint8_t action=0;
  if(actionName=="STATUS")action=MGMT_STATUS;
  else if(actionName=="ARM")action=MGMT_ARM;
  else if(actionName=="VERIFY")action=MGMT_VERIFY;
  else if(actionName=="ACTIVATE")action=MGMT_ACTIVATE;
  else if(actionName=="REBOOT")action=MGMT_REBOOT;
  else if(actionName=="CONFIRM")action=MGMT_CONFIRM;
  else if(actionName=="NAME_GET")action=MGMT_NAME_GET;
  else if(actionName=="NAME_SET")action=MGMT_NAME_SET;
  else if(actionName=="NAME_RESET")action=MGMT_NAME_RESET;
  else if(actionName=="RESTART")action=MGMT_RESTART;
  if(!action || (action!=MGMT_STATUS && !mgmtHexId(nonceText,nonce)) ||
     (action==MGMT_STATUS && params.length()) ||
     (action==MGMT_NAME_SET && !validName(requestedName)) ||
     (action!=MGMT_NAME_SET && requestedName.length())){
    Serial.println("[MGMT] ERROR action_or_nonce");return;
  }
  OtaFrame f={};f.magic=MAGIC;f.protocol=OTA_PROTO;f.kind=MGMT_REQUEST;
  f.networkId=MESH_NETWORK_ID;f.origin=nodeId;f.target=target;
  f.session=esp_random();if(!f.session)f.session=1;
  f.total=1;f.index=0;f.attempt=1;f.ttl=INITIAL_TTL;
  f.data[0]=action;memcpy(f.data+2,&nonce,sizeof(nonce));
  if(action==MGMT_NAME_SET)memcpy(f.data+20,requestedName.c_str(),requestedName.length());
  if(!otaSign(f,f.hmac)){Serial.println("[MGMT] ERROR hmac");return;}
  mgmtWaiting=true;mgmtTarget=target;mgmtRequestSession=f.session;mgmtRequestedAction=action;
  mgmtRequestAt=millis();
  otaSend(f);
  Serial.printf("[MGMT] SENT target=%s action=%s session=%lu\n",
    idString(target).c_str(),mgmtActionName(action),(unsigned long)f.session);
}
#endif // SMOKE_FEATURE_GATEWAY
void mgmtPendingWatchdog(){
#if SMOKE_FEATURE_GATEWAY
  if(mgmtWaiting && (uint32_t)(millis()-mgmtRequestAt)>4500UL){
    Serial.println("[MGMT] TIMEOUT no_reply");mgmtWaiting=false;
  }
#endif
  if(mgmtRebootAt && (int32_t)(millis()-mgmtRebootAt)>=0)ESP.restart();
  const esp_partition_t *run=esp_ota_get_running_partition();
  esp_ota_img_states_t state=ESP_OTA_IMG_UNDEFINED;
  if(millis()>90000UL && run &&
     esp_ota_get_state_partition(run,&state)==ESP_OK &&
     state==ESP_OTA_IMG_PENDING_VERIFY){
    Serial.println("[MGMT] PENDING_VERIFY timeout: reboot for bootloader rollback");
    delay(100);ESP.restart();
  }
}

void handleCommand(String command) {
  command.trim();
#if SMOKE_FEATURE_BUZZER
  if(command.equalsIgnoreCase("BUZZER TEST")) {
    SmokeBuzzer::test();
    return;
  } else if(command.equalsIgnoreCase("BUZZER STOP")) {
    SmokeBuzzer::stop();
    return;
  } else
#endif
  if(command.equalsIgnoreCase("BOOT STATUS")) {
    printBootDiagnostics();
  } else if(command.equalsIgnoreCase("BOOT VERIFY")) {
    verifyStagedImageReadback();
  } else if(command.equalsIgnoreCase("BOOT ARM")) {
    if(!bootVerified || !ready || apMode) {
      Serial.println("[BOOT] ARM FAIL requires fresh BOOT VERIFY");
      return;
    }
    bootArmed=true;
    bootArmedAt=millis();
    Serial.println("[BOOT] ARMED local_serial_only window=60s one_shot");
  } else if(command.equalsIgnoreCase("BOOT DISARM")) {
    bootArmed=false;
    Serial.println("[BOOT] DISARMED");
  } else if(command.equalsIgnoreCase("BOOT ACTIVATE")) {
    activateStagedSlot();
  } else if(command.equalsIgnoreCase("BOOT CONFIRM")) {
    const esp_partition_t *running=esp_ota_get_running_partition();
    esp_ota_img_states_t state=ESP_OTA_IMG_UNDEFINED;
    if(!ready || !meshPeerVerified || !running ||
       esp_ota_get_state_partition(running,&state)!=ESP_OK ||
       state!=ESP_OTA_IMG_PENDING_VERIFY) {
      Serial.println("[BOOT] CONFIRM REFUSED requires PENDING_VERIFY and authenticated mesh RX");
      return;
    }
    esp_err_t e=esp_ota_mark_app_valid_cancel_rollback();
    Serial.printf("[BOOT] CONFIRM %s err=%d\n",e==ESP_OK?"OK":"FAIL",(int)e);
  } else if(command.equalsIgnoreCase("FLASH ARM")) {
    if(imgRx.active && !imgRx.complete){
      Serial.println("[FLASH] ERROR receive_in_progress");return;
    }
    flashArmed=true;flashArmedAt=millis();
    Serial.println("[FLASH] ARMED local_serial_only window=300s one_shot BOOT_UNCHANGED");
  } else if(command.equalsIgnoreCase("FLASH DISARM")) {
    flashArmed=false;Serial.println("[FLASH] DISARMED");
  } else if(command.equalsIgnoreCase("FLASH STATUS")) {
    Serial.printf("[FLASH] running=%s armed=%u window_valid=%u staged_valid=%u BOOT_UNCHANGED\n",
      CURRENT_FW_VERSION,(unsigned)flashArmed,
      (unsigned)(flashArmed && (uint32_t)(millis()-flashArmedAt)<FLASH_ARM_WINDOW_MS),
      (unsigned)(imgRx.complete && imgRx.valid && imgRx.stage));
  }
#if SMOKE_FEATURE_GATEWAY
  else if(command.startsWith("MGMT ")) {
    mgmtSendSerial(command);
  } else if(command.startsWith("AUTH BEGIN ")) {
    if(authActive || imgActive || otaActive || !ready || apMode) {
      Serial.println("[AUTH] ERROR busy");return;
    }
    String arg=command.substring(11);
    int space=arg.indexOf(' ');
    if(space!=16){Serial.println("[AUTH] ERROR syntax");return;}
    String name=arg.substring(0,space),n=arg.substring(space+1);n.trim();
    if(!n.length() || n.length()>3){Serial.println("[AUTH] ERROR size");return;}
    for(size_t i=0;i<n.length();i++)if(n[i]<'0'||n[i]>'9'){
      Serial.println("[AUTH] ERROR size");return;
    }
    uint64_t target=0;
    for(size_t i=0;i<16;i++) {
      int v=imageNibble(name[i]);
      if(v<0){Serial.println("[AUTH] ERROR target");return;}
      target=(target<<4)|v;
    }
    unsigned length=n.toInt();
    if(!target || target==nodeId || length<42 || length>576){
      Serial.println("[AUTH] ERROR target_or_size");return;
    }
    authTarget=target;authLength=length;
    authTotal=(length+OTA_BYTES-1)/OTA_BYTES;
    authIndex=0;authSession=esp_random();if(!authSession)authSession=1;
    authActive=true;authNeedSerial=true;authAttempts=0;authRetries=0;
    Serial.printf("[AUTH] START target=%s bytes=%u blocks=%u NO_FLASH\n",
      idString(target).c_str(),length,(unsigned)authTotal);
    Serial.printf("[AUTH] NEXT index=0/%u\n",(unsigned)authTotal);
  } else if(command.startsWith("AUTH DATA ")) {
    if(!authActive || !authNeedSerial){Serial.println("[AUTH] ERROR not_ready");return;}
    String encoded=command.substring(10);encoded.trim();
    if(!imageHex(encoded,authPayload,OTA_BYTES)){
      authStop("invalid_serial_chunk");return;
    }
    authNeedSerial=false;authAttempts=0;authRetry();
  } else if(command.equalsIgnoreCase("AUTH STOP")) {
    authActive=false;authNeedSerial=false;
    Serial.println("[AUTH] STOP NO_FLASH");
  } else if(command.startsWith("IMG BEGIN ")) {
    if(imgActive || otaActive || !ready || apMode) {
      Serial.println("[IMAGE] ERROR busy");return;
    }
    String value=command.substring(10);
    int first=value.indexOf(' '),second=first<0?-1:value.indexOf(' ',first+1);
    if(first!=16 || second<0){Serial.println("[IMAGE] ERROR syntax");return;}
    String target=value.substring(0,first);
    String sizeText=value.substring(first+1,second);
    String digest=value.substring(second+1);digest.trim();
    bool stageRequested=false;
    if(digest.endsWith(" STAGE")) {
      digest.remove(digest.length()-6);stageRequested=true;
    }
    if(sizeText.length()<1 || sizeText.length()>7){
      Serial.println("[IMAGE] ERROR size");return;
    }
    for(size_t i=0;i<sizeText.length();i++)
      if(sizeText[i]<'0'||sizeText[i]>'9'){Serial.println("[IMAGE] ERROR size");return;}
    uint64_t node=0;
    for(size_t i=0;i<target.length();i++) {
      int digit=imageNibble(target[i]);
      if(digit<0){Serial.println("[IMAGE] ERROR target");return;}
      node=(node<<4)|digit;
    }
    uint8_t sha[32]={};
    uint32_t length=sizeText.toInt();
    if(!node || node==nodeId || length<24 || length>1310720UL ||
       !imageHex(digest,sha,32)) {
      Serial.println("[IMAGE] ERROR target/size/digest");return;
    }
    imgTarget=node;imgSize=length;imgStage=stageRequested;memcpy(imgSha,sha,32);
    imgTotal=(length+OTA_BYTES-1)/OTA_BYTES;
    imgSession=esp_random();if(!imgSession)imgSession=1;
    imgIndex=0;imgAttempts=0;imgRetries=0;
    imgBegin=true;imgWaitSerial=false;imgActive=true;imgStartedAt=millis();
    Serial.printf("[IMAGE] START target=%s size=%lu blocks=%u mode=%s BOOT_UNCHANGED\n",
      idString(node).c_str(),(unsigned long)length,(unsigned)imgTotal,
      imgStage?"FLASH_STAGE":"RAM_ONLY");
    imageRetry();
  } else if(command.startsWith("IMG DATA ")) {
    if(!imgActive || !imgWaitSerial || imgBegin){
      Serial.println("[IMAGE] ERROR not_ready");return;
    }
    String encoded=command.substring(9);encoded.trim();
    if(!imageHex(encoded,imgPayload,OTA_BYTES)){
      imageStop("invalid_serial_chunk");return;
    }
    imgWaitSerial=false;imgAttempts=0;imageRetry();
  } else if(command.equalsIgnoreCase("IMG STOP")) {
    imgActive=false;imgWaitSerial=false;
    Serial.println("[IMAGE] STOP NO_FLASH");
  }
#endif // SMOKE_FEATURE_GATEWAY
  else if(command.equalsIgnoreCase("OTA PREFLIGHT")) {
    printOtaPreflight();
  } else if(command.equalsIgnoreCase("NAME GET")) {
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
      Serial.println("[CONFIG] ERROR name must be 1..19 characters: A-Z a-z 0-9 - _");
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
  }
#if SMOKE_FEATURE_GATEWAY
  else if(command.equalsIgnoreCase("OTA STATS")) {
    Serial.printf("[OTA] STATS rx_data=%lu rx_ack=%lu relay_data=%lu relay_ack=%lu relay_drops=%lu invalid=%lu tx_errors=%lu active=%u index=%u/%u retries=%lu\n",
      (unsigned long)otaRxData,(unsigned long)otaRxAck,(unsigned long)otaRelayData,
      (unsigned long)otaRelayAck,(unsigned long)otaRelayDrops,(unsigned long)otaAuthRejected,
      (unsigned long)otaTxErrors,(unsigned)otaActive,(unsigned)otaIndex,(unsigned)otaTotal,
      (unsigned long)otaRetries);
  } else if(command.equalsIgnoreCase("OTA DEBUG ON")) {
    otaDebug=true;Serial.println("[OTA] DEBUG ON");
  } else if(command.equalsIgnoreCase("OTA DEBUG OFF")) {
    otaDebug=false;Serial.println("[OTA] DEBUG OFF");
  } else if(command.startsWith("OTA TEST ")) {
    String value=command.substring(9);value.trim();
    uint16_t requestedTotal=OTA_DEFAULT_TOTAL;
    int space=value.indexOf(' ');
    if(space>=0) {
      String count=value.substring(space+1);count.trim();
      value=value.substring(0,space);
      if(!count.length() || count.length()>4) {Serial.println("[OTA] ERROR invalid block count");return;}
      for(size_t j=0;j<count.length();j++)if(count[j]<'0' || count[j]>'9') {
        Serial.println("[OTA] ERROR invalid block count");return;
      }
      unsigned long n=count.toInt();
      if(n<1 || n>OTA_MAX_TOTAL) {Serial.println("[OTA] ERROR blocks must be 1..4096");return;}
      requestedTotal=(uint16_t)n;
    }
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
    otaTotal=requestedTotal;otaIndex=0;otaAttempts=0;otaRetries=0;otaAckHops=0;
    otaStartedAt=millis();otaActive=true;
    Serial.printf("[OTA] START target=%s session=%08lX blocks=%u bytes=%lu TEST_NO_FLASH\n",
      idString(otaTarget).c_str(),(unsigned long)otaSession,
      (unsigned)otaTotal,(unsigned long)otaTotal*OTA_BYTES);
    sendOtaChunk();
  } else if(command.equalsIgnoreCase("OTA STOP")) {
    otaActive=false;Serial.println("[OTA] STOP");
  }
#endif // SMOKE_FEATURE_GATEWAY
  else if(command.equalsIgnoreCase("HELP")) {
#if SMOKE_FEATURE_GATEWAY
    Serial.println("[CONFIG] Commands: NAME GET | NAME SET <name> | NAME RESET | OTA PREFLIGHT | BOOT STATUS | BOOT VERIFY | BOOT ARM/DISARM/ACTIVATE/CONFIRM | FLASH ARM/DISARM/STATUS | AUTH BEGIN <16hex> <len> | AUTH DATA <192hex> | AUTH STOP | IMG BEGIN <16hex> <size> <sha256> [STAGE] | IMG DATA <192hex> | IMG STOP | OTA TEST <16hex> [1..4096] | OTA STATS | OTA DEBUG ON/OFF | OTA STOP | MGMT <16hex> STATUS/ARM/VERIFY/ACTIVATE/REBOOT/CONFIRM [nonce16] | HELP");
#else
    Serial.println("[CONFIG] Commands: NAME GET | NAME SET <name> | NAME RESET | OTA PREFLIGHT | BOOT STATUS | BOOT VERIFY | BOOT ARM/DISARM/ACTIVATE/CONFIRM | FLASH ARM/DISARM/STATUS | HELP");
#endif
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
      if(serialLine.length()<256) serialLine+=c;
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
  Serial.printf("[%s] origin=%s boot=%s seq=%lu ttl=%u status=%d fw=%s\n",
      relay?"RELAY":"TX",idString(p.origin).c_str(),
      idString(p.bootNonce).c_str(),(unsigned long)p.sequence,p.ttl,(int)e,CURRENT_FW_VERSION);
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
  meshPeerVerified=true;
  String sourceName=packetName(p);
  String fw="unknown";
  const uint8_t versionMarker=(uint8_t)p.name[20];
  if(versionMarker==0xA5 || (versionMarker>=0xB0 && versionMarker<=0xB7)){
    fw=String((uint8_t)p.name[21])+"."+String((uint8_t)p.name[22])+"."+String((uint8_t)p.name[23]);
    if(versionMarker>=0xB0)fw+="."+String(char('a'+versionMarker-0xB0));
  }
  Serial.printf("[RX] name=%s origin=%s via=%s boot=%s seq=%lu ttl=%u hops=%u type=%s rssi=%d dBm channel=%u fw=%s AUTH=OK\n",
      sourceName.length()?sourceName.c_str():"(unset)",
      idString(p.origin).c_str(),macString(event.from).c_str(),
      idString(p.bootNonce).c_str(),(unsigned long)p.sequence,p.ttl,
      INITIAL_TTL-p.ttl,p.type==HEARTBEAT?"HEARTBEAT":"TEST",
      (int)event.rssi,(unsigned)event.channel,fw.c_str());
  if(p.ttl>1)scheduleRelay(p);
}

bool otaSign(const OtaFrame &f,uint8_t out[32]) {
  const mbedtls_md_info_t *md=mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
  return md && mbedtls_md_hmac(md,MESH_SECRET_KEY,sizeof(MESH_SECRET_KEY),
      reinterpret_cast<const unsigned char*>(&f),offsetof(OtaFrame,ttl),out)==0;
}
bool otaVerify(const OtaFrame &f) {
  if(f.magic!=MAGIC || f.protocol!=OTA_PROTO || f.networkId!=MESH_NETWORK_ID ||
     (f.kind<OTA_DATA || f.kind>MGMT_REPLY) || !f.origin || !f.target ||
     f.total<1 || f.total>IMG_MAX_BLOCKS || f.index>=f.total || f.ttl<1 || f.ttl>INITIAL_TTL)
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
       item.index==f.index && item.kind==f.kind &&
       item.attempt==f.attempt)return true;
  OtaCache &item=otaCache[otaCursor++%128];
  item.origin=f.origin;item.session=f.session;
  item.index=f.index;item.kind=f.kind;item.attempt=f.attempt;item.used=true;
  return false;
}
void otaSend(const OtaFrame &f) {
  esp_err_t status=esp_now_send(BROADCAST,
    reinterpret_cast<const uint8_t*>(&f),sizeof(f));
  if(status!=ESP_OK) {
    otaTxErrors++;
    Serial.printf("[OTA] TX_ERROR kind=%u index=%u attempt=%u status=%d\n",
      (unsigned)f.kind,(unsigned)(f.index+1),(unsigned)f.attempt,(int)status);
  }
}
void otaForward(const OtaFrame &f) {
  if(f.ttl<=1)return;
  if(otaSeen(f))return;
  for(OtaRelay &item:otaRelays)if(!item.used) {
    item.frame=f;item.frame.ttl--;
    item.deadline=millis()+35+esp_random()%120;
    item.used=true;
    if(f.kind==OTA_DATA)otaRelayData++;else otaRelayAck++;
    if(otaDebug)Serial.printf("[OTA] RELAY kind=%s origin=%s index=%u/%u attempt=%u ttl=%u\n",
      f.kind==OTA_DATA?"DATA":"ACK",idString(f.origin).c_str(),
      (unsigned)(f.index+1),(unsigned)f.total,(unsigned)f.attempt,(unsigned)(f.ttl-1));
    return;
  }
  otaRelayDrops++;
  Serial.println("[OTA] RELAY_QUEUE_FULL");
}
void sendOtaChunk() {
  if(!otaActive || otaIndex>=otaTotal)return;
  OtaFrame frame={};
  frame.magic=MAGIC;frame.protocol=OTA_PROTO;frame.kind=OTA_DATA;
  frame.networkId=MESH_NETWORK_ID;
  frame.origin=nodeId;frame.target=otaTarget;frame.session=otaSession;
  frame.index=otaIndex;frame.total=otaTotal;frame.ttl=INITIAL_TTL;
  for(size_t i=0;i<OTA_BYTES;i++)
    frame.data[i]=(uint8_t)((otaIndex*17+i)&255);
  otaAttempts++;frame.attempt=otaAttempts;
  if(otaAttempts>1)otaRetries++;
  if(!otaSign(frame,frame.hmac)) {otaActive=false;return;}
  otaSentAt=millis();otaSend(frame);
  Serial.printf("[OTA] CHUNK target=%s index=%u/%u attempt=%u\n",
    idString(otaTarget).c_str(),(unsigned)(otaIndex+1),
    (unsigned)otaTotal,(unsigned)otaAttempts);
}
void receiveOta(const OtaFrame &frame) {
  if(!otaVerify(frame)) {otaAuthRejected++;return;}
  if(frame.origin==nodeId)return;
  if(frame.target!=nodeId) {
    otaForward(frame);
    return;
  }
  if(frame.kind==MGMT_REQUEST || frame.kind==MGMT_REPLY) {mgmtReceive(frame);return;}
  if(frame.kind>=IMG_AUTH) {authReceive(frame);return;}
  if(frame.kind>=IMG_BEGIN) {imageReceive(frame);return;}
  if(frame.kind==OTA_ACK) {
    otaRxAck++;
    if(otaDebug)Serial.printf("[OTA] RX_ACK origin=%s index=%u/%u attempt=%u hops=%u\n",
      idString(frame.origin).c_str(),(unsigned)(frame.index+1),(unsigned)frame.total,
      (unsigned)frame.attempt,(unsigned)(INITIAL_TTL-frame.ttl));
    if(!otaActive || frame.origin!=otaTarget || frame.session!=otaSession ||
       frame.index!=otaIndex || frame.total!=otaTotal || frame.attempt>otaAttempts)return;
    Serial.printf("[OTA] ACK source=%s index=%u/%u hops=%u\n",
      idString(frame.origin).c_str(),(unsigned)(frame.index+1),
      (unsigned)frame.total,(unsigned)(INITIAL_TTL-frame.ttl));
    otaAckHops+=INITIAL_TTL-frame.ttl;
    otaIndex++;otaAttempts=0;
    if(otaIndex==otaTotal) {
      Serial.printf("[OTA] DONE target=%s bytes=%lu blocks=%u retries=%lu duration_ms=%lu ack_hops_total=%lu MODE=RAM_ONLY\n",
        idString(otaTarget).c_str(),(unsigned long)otaTotal*OTA_BYTES,
        (unsigned)otaTotal,(unsigned long)otaRetries,
        (unsigned long)(millis()-otaStartedAt),(unsigned long)otaAckHops);
      otaActive=false;
    } else {
      if(otaIndex%32==0)Serial.printf("[OTA] PROGRESS blocks=%u/%u retries=%lu\n",
        (unsigned)otaIndex,(unsigned)otaTotal,(unsigned long)otaRetries);
      sendOtaChunk();
    }
    return;
  }
  otaRxData++;
  bool duplicate=otaSeen(frame);
  if(!duplicate) {
    for(size_t i=0;i<OTA_BYTES;i++)
      if(frame.data[i]!=(uint8_t)((frame.index*17+i)&255)) {
        Serial.printf("[OTA] DATA_INVALID index=%u\n",(unsigned)frame.index);
        return;
      }
    if(otaDebug || frame.index==0 || frame.index+1==frame.total || (frame.index+1)%32==0)
      Serial.printf("[OTA] RX_DATA from=%s index=%u/%u hops=%u RAM_ONLY\n",
        idString(frame.origin).c_str(),(unsigned)(frame.index+1),
        (unsigned)frame.total,(unsigned)(INITIAL_TTL-frame.ttl));
  }
  // Re-ACK duplicates: previous acknowledgment may have been lost.
  OtaFrame ack={};
  ack.magic=MAGIC;ack.protocol=OTA_PROTO;ack.kind=OTA_ACK;
  ack.networkId=MESH_NETWORK_ID;ack.origin=nodeId;ack.target=frame.origin;
  ack.session=frame.session;ack.index=frame.index;
  ack.total=frame.total;ack.ttl=INITIAL_TTL;ack.attempt=frame.attempt;
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
  // Wire-compatible v3 packet extension. Bytes 20..23 of authenticated name
  // were unused for names <=19 chars. Old firmware stops parsing at NUL.
  // HMAC already covers the complete 24-byte name field.
  uint16_t versionParts[3]={};
  char variant=0;
  if(!parseFirmwareVersion(String(CURRENT_FW_VERSION),versionParts,variant) ||
     versionParts[0]>255 || versionParts[1]>255 || versionParts[2]>255) {
    Serial.println("[FW] ERROR invalid telemetry firmware version");
    return;
  }
  p.name[20]=(char)(variant?0xB0+(variant-'a'):0xA5);
  p.name[21]=(char)versionParts[0];
  p.name[22]=(char)versionParts[1];
  p.name[23]=(char)versionParts[2];
  p.ttl=INITIAL_TTL;
  if(calculateTag(p,p.tag))sendPacket(p,false);
  else Serial.println("ERROR: HMAC failed");
}

#if SMOKE_FEATURE_AP
void configForm() {
  apLastActivity=millis();
  String html=F("<html><meta name='viewport' content='width=device-width,initial-scale=1'><meta charset='UTF-8'><h2>Smoke Mesh</h2><form method='POST' action='/name'><input name='name' maxlength='19' placeholder='Neuer Name' required><button>Speichern</button></form><p>Aktueller Name: ");
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

#endif

void setup() {
#if SMOKE_FEATURE_AP
  pinMode(9,INPUT_PULLUP);
  server.on("/",HTTP_GET,configForm);
  server.on("/name",HTTP_POST,configSave);
#endif
  Serial.begin(115200);
  delay(1500);
  Serial.println("\nSmoke Listener Mesh v0.6.16 | REMOTE OTA MGMT EXPERIMENTAL");
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
  Serial.printf("[FW] version=%s signed_readback=1 ota_boot_activation=LOCAL_NO_AUTO_REBOOT\n",CURRENT_FW_VERSION);
  Serial.printf("[FW] features gateway=%u audio=%u config_ap=%u battery=%u buzzer=%u\n",
    (unsigned)FEATURE_GATEWAY,(unsigned)FEATURE_AUDIO,(unsigned)FEATURE_CONFIG_AP,
    (unsigned)FEATURE_BATTERY,(unsigned)FEATURE_BUZZER);
#if SMOKE_FEATURE_BUZZER
  SmokeBuzzer::begin();
#endif
  if(prefs.begin("smoke-mesh",true)) {
    nodeName=prefs.getString("name","");
    prefs.end();
  } else Serial.println("[CONFIG] WARNING NVS not available");
  // Preserve older 20..24 character names after introducing the version tail.
  // The old configuration stays in NVS; only its on-air representation is shortened.
  if(nodeName.length()>MAX_NAME_LENGTH) {
    nodeName=nodeName.substring(0,MAX_NAME_LENGTH);
    Serial.println("[CONFIG] WARNING long legacy name shortened on air for firmware telemetry");
  }
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
  // Generate management challenge after WiFi has initialized the hardware RNG.
  mgmtNonce=((uint64_t)esp_random()<<32)|esp_random();
  if(!mgmtNonce)mgmtNonce=1;
  esp_now_register_recv_cb(onReceive);
  esp_now_peer_info_t peer={};
  memcpy(peer.peer_addr,BROADCAST,6);
  peer.channel=CHANNEL;peer.ifidx=WIFI_IF_STA;peer.encrypt=false;
  e=esp_now_add_peer(&peer);
  if(e!=ESP_OK){Serial.printf("ERROR: add peer %d\n",(int)e);return;}
  ready=true;
  Serial.println("ESP-NOW ready; HMAC authenticated TEST/HEARTBEAT only");
  Serial.println("[BOOT] Arduino automatic OTA confirmation bypass requested: verifyRollbackLater=true");
  const esp_partition_t *rpart=esp_ota_get_running_partition();
  esp_ota_img_states_t rstate=ESP_OTA_IMG_UNDEFINED;
  if(rpart && esp_ota_get_state_partition(rpart,&rstate)==ESP_OK && rstate==ESP_OTA_IMG_PENDING_VERIFY)
    Serial.println("[BOOT] PENDING_VERIFY: manual BOOT CONFIRM required after authenticated mesh packet");
  sendLocal(TEST);
  lastHeartbeat=millis();
#if SMOKE_FEATURE_AUDIO
  audioMonitorStart();
#endif
}
void loop() {
  pollSerial();
#if SMOKE_FEATURE_BUZZER
  SmokeBuzzer::poll();
#endif
#if SMOKE_FEATURE_AP
  checkButton();
#endif
  mgmtPendingWatchdog();
#if SMOKE_FEATURE_AP
  if(apMode) {
    server.handleClient();
    if((uint32_t)(millis()-apLastActivity)>=AP_TIMEOUT_MS) ESP.restart();
    delay(5);
    return;
  }
#endif
  if(!ready){delay(1000);return;}
  RxEvent event;
  while(xQueueReceive(rxQueue,&event,0)==pdTRUE)processRx(event);
  if(otaActive && (uint32_t)(millis()-otaSentAt)>=OTA_ACK_TIMEOUT_MS) {
    if(otaAttempts>=OTA_MAX_ATTEMPTS) {
      Serial.printf("[OTA] FAIL target=%s index=%u missing_ack retries=%lu duration_ms=%lu\n",
        idString(otaTarget).c_str(),(unsigned)(otaIndex+1),
        (unsigned long)otaRetries,(unsigned long)(millis()-otaStartedAt));
      otaActive=false;
    } else sendOtaChunk();
  }
  if(authActive && !authNeedSerial &&
     (uint32_t)(millis()-authSentAt)>=OTA_ACK_TIMEOUT_MS)
    authRetry();
  if(imgActive && !imgWaitSerial &&
     (uint32_t)(millis()-imgSentAt)>=OTA_ACK_TIMEOUT_MS)imageRetry();
  if(imgRx.active && !imgRx.complete &&
     (uint32_t)(millis()-imgRx.lastActivity)>=120000UL) {
    mbedtls_sha256_free(&imgRx.hash);
    if(imgRx.otaOpen){esp_ota_abort(imgRx.otaHandle);imgRx.otaOpen=false;}
    imgRx.active=false;
    Serial.println("[IMAGE] RECEIVE_TIMEOUT BOOT_UNCHANGED");
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
