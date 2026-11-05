#pragma once
#include <Arduino.h>

// Firmware identity: major.minor.patch.variant, for example 0.6.17.b.
// An old three-number version is accepted for interoperability during USB
// migration. Variant changes at the same code version are allowed; older code
// versions are not. A same-identity reflash is rejected.
inline bool parseFirmwareVersion(const String &value,uint16_t parts[3],char &variant) {
  String v=value;
  variant=0;
  const int last=v.lastIndexOf('.');
  if(last<0)return false;
  if(last==(int)v.length()-2) {
    char suffix=v[last+1];
    if(suffix>='a'&&suffix<='h') {
      variant=suffix;
      v=v.substring(0,last);
    }
  }
  size_t start=0;
  for(int i=0;i<3;i++) {
    int dot=v.indexOf('.',start);
    if((i<2&&dot<0)||(i==2&&dot>=0))return false;
    size_t end=i==2?v.length():(size_t)dot;
    if(end<=start||end-start>5)return false;
    if(end-start>1&&v[start]=='0')return false;
    uint32_t n=0;
    for(size_t j=start;j<end;j++){
      char c=v[j];
      if(c<'0'||c>'9')return false;
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
  char nextVariant=0,currentVariant=0;
  if(!parseFirmwareVersion(candidate,next,nextVariant)||
     !parseFirmwareVersion(String(running),current,currentVariant))return false;
  for(int i=0;i<3;i++){
    if(next[i]>current[i])return true;
    if(next[i]<current[i])return false;
  }
  // Signed variant swap, independent of letter order.
  return nextVariant!=currentVariant;
}
