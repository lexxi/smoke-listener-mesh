#pragma once
// Experimental INMP441 diagnostics. No ALARM frames are transmitted.
// Audio runs in its own task; mesh/OTA loop must remain responsive.
#include <Arduino.h>
#include <driver/i2s.h>
#include <math.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

namespace SmokeAudio {
constexpr int PIN_SCK=6, PIN_WS=3, PIN_SD=10;
constexpr int RATE=16000, BUFFER=512;
constexpr float RMS_ON=150000.0f, RMS_OFF=60000.0f;
constexpr uint32_t MIN_BEEP_MS=400, MAX_BEEP_MS=1500, SILENCE_MS=64;
constexpr uint32_t MIN_GAP_MS=150, MAX_GAP_MS=700, TIMEOUT_MS=1500;
constexpr int FREQ_MIN=3000, FREQ_MAX=4400, FREQ_STEP=100;
constexpr int FREQ_COUNT=(FREQ_MAX-FREQ_MIN)/FREQ_STEP+1;
constexpr float MIN_TONE_RATIO=0.04f;
constexpr float MIN_MATCH_PERCENT=40.0f;

static TaskHandle_t taskHandle=nullptr;
static bool initialized=false;
static int32_t samples[BUFFER];
static float coeffs[FREQ_COUNT];
static bool active=false;
static uint32_t beepStart=0,lastLoud=0,previousEnd=0;
static uint16_t loudFrames=0,validFrames=0;
static float frequencySum=0;
static uint8_t sequenceCount=0;
static uint32_t accepted=0,rejected=0,groups=0,candidates=0,readErrors=0;

inline void clearMetrics() { loudFrames=0;validFrames=0;frequencySum=0; }
inline void finishGroup() {
  if(sequenceCount==0)return;
  ++groups;
  Serial.printf("[AUDIO] GROUP beeps=%u diagnostic_only=1\n",(unsigned)sequenceCount);
  sequenceCount=0;previousEnd=0;
}
inline void analyzeFrequency(int count,float mean,float rms,float &frequency,float &ratio) {
  float amplitude=0;frequency=0;ratio=0;
  for(int f=0;f<FREQ_COUNT;f++) {
    float q1=0,q2=0,coeff=coeffs[f];
    for(int i=0;i<count;i++) {
      float value=(float)(samples[i]>>8)-mean;
      float q0=value+coeff*q1-q2;
      q2=q1;q1=q0;
    }
    float power=q1*q1+q2*q2-coeff*q1*q2;
    if(power>0) {
      float a=2.0f*sqrtf(power)/count;
      if(a>amplitude) {amplitude=a;frequency=FREQ_MIN+f*FREQ_STEP;}
    }
  }
  if(rms>0)ratio=amplitude/rms;
}
inline void finishBeep(uint32_t endTime) {
  active=false;
  const uint32_t duration=endTime-beepStart;
  const float match=loudFrames?100.0f*validFrames/loudFrames:0;
  const float freq=validFrames?frequencySum/validFrames:0;
  const bool valid=duration>=MIN_BEEP_MS&&duration<=MAX_BEEP_MS&&match>=MIN_MATCH_PERCENT;
  Serial.printf("[AUDIO] BEEP duration_ms=%lu freq_hz=%.0f match_pct=%.0f valid=%u\n",
    (unsigned long)duration,freq,match,(unsigned)valid);
  if(!valid){++rejected;clearMetrics();return;}
  ++accepted;
  if(sequenceCount) {
    uint32_t gap=beepStart-previousEnd;
    if(gap<MIN_GAP_MS||gap>MAX_GAP_MS)finishGroup();
  }
  ++sequenceCount;
  previousEnd=endTime;
  if(sequenceCount==3) {
    ++candidates;
    Serial.println("[AUDIO] ALARM_CANDIDATE DIAGNOSTIC_ONLY NO_MESH_ALARM");
  }
  clearMetrics();
}
inline void process(int count) {
  double sum=0;
  for(int i=0;i<count;i++)sum+=(samples[i]>>8);
  const float mean=(float)(sum/count);
  double squares=0;
  for(int i=0;i<count;i++) {
    double d=(double)(samples[i]>>8)-mean;
    squares+=d*d;
  }
  const float rms=sqrt(squares/count);
  const uint32_t now=millis();
  if(!active&&sequenceCount&&now-previousEnd>TIMEOUT_MS)finishGroup();
  if(!active&&rms>=RMS_ON){
    active=true;beepStart=now;lastLoud=now;clearMetrics();
  }
  if(active) {
    if(rms>=RMS_OFF) {
      lastLoud=now;++loudFrames;
      float freq=0,ratio=0;
      analyzeFrequency(count,mean,rms,freq,ratio);
      if(ratio>=MIN_TONE_RATIO && freq>=FREQ_MIN && freq<=FREQ_MAX) {
        ++validFrames;frequencySum+=freq;
      }
    }
    if(now-lastLoud>=SILENCE_MS)finishBeep(lastLoud+32);
    else if(now-beepStart>MAX_BEEP_MS+200){
      active=false;++rejected;clearMetrics();
      Serial.println("[AUDIO] BEEP_TIMEOUT");
    }
  }
}
inline bool init() {
  for(int i=0;i<FREQ_COUNT;i++)coeffs[i]=2.0f*cosf(2.0f*PI*(FREQ_MIN+i*FREQ_STEP)/RATE);
  i2s_config_t cfg={};
  cfg.mode=(i2s_mode_t)(I2S_MODE_MASTER|I2S_MODE_RX);
  cfg.sample_rate=RATE;
  cfg.bits_per_sample=I2S_BITS_PER_SAMPLE_32BIT;
  cfg.channel_format=I2S_CHANNEL_FMT_ONLY_LEFT;
  cfg.communication_format=I2S_COMM_FORMAT_STAND_I2S;
  cfg.intr_alloc_flags=ESP_INTR_FLAG_LEVEL1;
  cfg.dma_buf_count=6;
  cfg.dma_buf_len=256;
  cfg.use_apll=false;
  i2s_pin_config_t pins={};
  pins.bck_io_num=PIN_SCK;
  pins.ws_io_num=PIN_WS;
  pins.data_out_num=I2S_PIN_NO_CHANGE;
  pins.data_in_num=PIN_SD;
  esp_err_t err=i2s_driver_install(I2S_NUM_0,&cfg,0,nullptr);
  if(err!=ESP_OK){Serial.printf("[AUDIO] INIT_FAIL install=%d\n",(int)err);return false;}
  err=i2s_set_pin(I2S_NUM_0,&pins);
  if(err!=ESP_OK){
    Serial.printf("[AUDIO] INIT_FAIL pins=%d\n",(int)err);
    i2s_driver_uninstall(I2S_NUM_0);
    return false;
  }
  initialized=true;
  return true;
}
inline void task(void*) {
  if(!init()) { taskHandle=nullptr;vTaskDelete(nullptr);return; }
  Serial.println("[AUDIO] READY diagnostic_only=1 sample_rate=16000");
  uint32_t lastStats=millis();
  for(;;) {
    size_t bytesRead=0;
    const esp_err_t err=i2s_read(I2S_NUM_0,samples,sizeof(samples),&bytesRead,pdMS_TO_TICKS(250));
    if(err==ESP_OK && bytesRead>=sizeof(int32_t))process((int)(bytesRead/sizeof(int32_t)));
    else {
      ++readErrors;
      if(readErrors==1 || readErrors%100==0)
        Serial.printf("[AUDIO] READ_ERROR count=%lu err=%d\n",(unsigned long)readErrors,(int)err);
      vTaskDelay(pdMS_TO_TICKS(20));
    }
    uint32_t now=millis();
    if((uint32_t)(now-lastStats)>=30000UL){
      lastStats=now;
      Serial.printf("[AUDIO] STATS beeps=%lu rejected=%lu groups=%lu candidates=%lu errors=%lu mesh_alarm=disabled\n",
        (unsigned long)accepted,(unsigned long)rejected,(unsigned long)groups,
        (unsigned long)candidates,(unsigned long)readErrors);
    }
  }
}
} // namespace SmokeAudio

inline void audioMonitorStart() {
  // Do not interfere with safety-critical mesh or OTA if the task cannot start.
  if(SmokeAudio::taskHandle)return;
  BaseType_t ok=xTaskCreate(SmokeAudio::task,"smoke_audio",8192,nullptr,1,&SmokeAudio::taskHandle);
  if(ok!=pdPASS){SmokeAudio::taskHandle=nullptr;Serial.println("[AUDIO] TASK_CREATE_FAIL");}
}
