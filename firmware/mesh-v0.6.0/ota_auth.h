#pragma once
#include <Arduino.h>
#include <mbedtls/pk.h>
#include <mbedtls/sha256.h>
#include <esp_ota_ops.h>
#include "ota_public_key.h"

// Signed envelope (max 576 B): uint16 LE length + canonical JSON bytes +
// uint8 DER-signature length + DER signature. No private key on the device.
// This verifier NEVER writes to flash or changes boot selection.
inline bool releaseHexNibble(char c,int &n) {
  if(c>='0' && c<='9')n=c-'0';
  else if(c>='a' && c<='f')n=c-'a'+10;
  else return false;
  return true;
}
inline bool releaseVerify(const uint8_t *blob,size_t length,
                          uint64_t deviceId,uint32_t &imageBytes,
                          uint8_t imageSha[32]) {
  if(!blob || length<40 || length>576 || !OTA_PUBLISHER_PUBLIC_KEY_PEM[0])
    return false;
  const size_t textLength=(size_t)blob[0]|((size_t)blob[1]<<8);
  if(textLength<80 || textLength>420 || textLength+3>length)return false;
  const size_t signatureLength=blob[textLength+2];
  if(signatureLength<68 || signatureLength>80 ||
     textLength+signatureLength+3!=length)return false;
  uint8_t digest[32]={};
  if(mbedtls_sha256(blob+2,textLength,digest,0)!=0)return false;
  mbedtls_pk_context key;
  mbedtls_pk_init(&key);
  int rc=mbedtls_pk_parse_public_key(&key,
    reinterpret_cast<const unsigned char*>(OTA_PUBLISHER_PUBLIC_KEY_PEM),
    strlen(OTA_PUBLISHER_PUBLIC_KEY_PEM)+1);
  if(rc==0)rc=mbedtls_pk_verify(&key,MBEDTLS_MD_SHA256,
    digest,sizeof(digest),blob+textLength+3,signatureLength);
  mbedtls_pk_free(&key);
  if(rc!=0)return false;

  String canonical;
  canonical.reserve(textLength);
  for(size_t i=0;i<textLength;i++){
    char c=(char)blob[i+2];
    if(c<32 || c>126)return false;
    canonical+=c;
  }
  // Reconstruct precisely the only allowed canonical JSON layout.
  const String prefix="{\\\"board\\\":\\\"esp32c3\\\",\\\"schema\\\":\\\"smoke-mesh-ota-v1\\\",\\\"sha256\\\":\\\"";
  if(!canonical.startsWith(prefix))return false;
  const String hashText=canonical.substring(prefix.length(),prefix.length()+64);
  if(hashText.length()!=64)return false;
  for(size_t i=0;i<32;i++){
    int a,b;
    if(!releaseHexNibble(hashText[2*i],a) ||
       !releaseHexNibble(hashText[2*i+1],b))return false;
    imageSha[i]=(uint8_t)((a<<4)|b);
  }
  const String mid="\\\",\\\"size\\\":";
  int numStart=prefix.length()+64;
  if(!canonical.substring(numStart).startsWith(mid))return false;
  numStart+=mid.length();
  int numEnd=canonical.indexOf(',',numStart);
  if(numEnd<=numStart)return false;
  const String number=canonical.substring(numStart,numEnd);
  if(number.length()>7 || number[0]=='0')return false;
  for(size_t i=0;i<number.length();i++)
    if(number[i]<'0'||number[i]>'9')return false;
  uint32_t count=number.toInt();
  if(count<24 || count>1310720UL)return false;
  char id[17];
  snprintf(id,sizeof(id),"%08lX%08lX",
    (unsigned long)(deviceId>>32),(unsigned long)deviceId);
  const String tail="\\\",\\\"target\\\":\\\""+String(id)+"\\\",\\\"version\\\":\\\"";
  if(!canonical.substring(numEnd).startsWith(tail))return false;
  int verStart=numEnd+tail.length();
  if(!canonical.endsWith("\\\"}"))return false;
  const String version=canonical.substring(verStart,canonical.length()-2);
  if(!version.length() || version.length()>32)return false;
  for(size_t i=0;i<version.length();i++){
    char c=version[i];
    if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||
         (c>='0'&&c<='9')||c=='.'||c=='_'||c=='-'))return false;
  }
  if(canonical!=prefix+hashText+mid+number+tail+version+"\\\"}")
    return false;
  const esp_partition_t *running=esp_ota_get_running_partition();
  const esp_partition_t *next=esp_ota_get_next_update_partition(nullptr);
  if(!running || !next || running==next || count>next->size)
    return false;
  imageBytes=count;
  return true;
}
