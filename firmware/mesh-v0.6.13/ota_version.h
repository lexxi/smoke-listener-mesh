#pragma once
#include <Arduino.h>
// Strict monotone three-component release versions, no prefixes or suffixes.
// This protects against a signed older release, not against physical reflashing.
inline bool parseFirmwareVersion(const String &value,uint16_t parts[3]) {
  size_t start=0;
  for(int i=0;i<3;i++) {
    const int dot=value.indexOf('.',start);
    if((i<2 && dot<0) || (i==2 && dot>=0))return false;
    const size_t end=i==2?value.length():(size_t)dot;
    if(end<=start || end-start>5)return false;
    if(end-start>1 && value[start]=='0')return false;
    uint32_t n=0;
    for(size_t j=start;j<end;j++) {
      const char c=value[j];
      if(c<'0' || c>'9')return false;
      n=n*10+(c-'0');
      if(n>65535)return false;
    }
    parts[i]=(uint16_t)n;
    start=end+1;
  }
  return true;
}
inline bool newerFirmwareVersion(const String &candidate,const char *running) {
  uint16_t next[3]={},current[3]={};
  if(!parseFirmwareVersion(candidate,next) ||
     !parseFirmwareVersion(String(running),current))return false;
  for(int i=0;i<3;i++) {
    if(next[i]>current[i])return true;
    if(next[i]<current[i])return false;
  }
  return false;
}
