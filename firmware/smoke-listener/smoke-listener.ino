#include <Arduino.h>
#include <driver/i2s.h>
#include <math.h>

// Smoke Listener Mesh v0.3.1 - experimental diagnostic only
#define PIN_SCK 6
#define PIN_WS 3
#define PIN_SD 10
#define SAMPLE_RATE 16000
#define BUFFER_SIZE 512
#define FRAME_MS 32
#define RMS_ON 150000.0f
#define RMS_OFF 60000.0f
#define MIN_BEEP_MS 400
#define MAX_BEEP_MS 1500
#define SILENCE_MS 64
#define MIN_GAP_MS 150
#define MAX_GAP_MS 700
#define SEQUENCE_TIMEOUT_MS 1500
#define FREQ_MIN 3000
#define FREQ_MAX 4400
#define FREQ_STEP 100
#define MIN_TONE_RATIO 0.04f
#define MIN_VALID_FREQ_PERCENT 40
#define NUM_FREQ ((FREQ_MAX-FREQ_MIN)/FREQ_STEP+1)

int32_t samples[BUFFER_SIZE];
float coefficients[NUM_FREQ];
bool beepActive = false;
uint32_t beepStart=0, lastLoudTime=0, previousBeepEnd=0, lastPrint=0;
uint32_t validBeeps=0, rejectedBeeps=0, groups=0;
uint8_t sequenceCount=0;
uint16_t loudFrames=0, validFrequencyFrames=0;
float frequencySum=0, strongestRms=0;

void initFrequencyAnalysis() {
  for(int i=0;i<NUM_FREQ;i++) {
    float freq=FREQ_MIN+i*FREQ_STEP;
    coefficients[i]=2.0f*cosf(2.0f*PI*freq/SAMPLE_RATE);
  }
}
bool initMicrophone() {
  i2s_config_t cfg={};
  cfg.mode=(i2s_mode_t)(I2S_MODE_MASTER|I2S_MODE_RX);
  cfg.sample_rate=SAMPLE_RATE;
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
  esp_err_t err=i2s_driver_install(I2S_NUM_0,&cfg,0,NULL);
  if(err!=ESP_OK) { Serial.printf("I2S install error: %d\n",err); return false; }
  err=i2s_set_pin(I2S_NUM_0,&pins);
  if(err!=ESP_OK) { Serial.printf("I2S pin error: %d\n",err); return false; }
  return true;
}
void resetBeepMetrics() {
  loudFrames=0;validFrequencyFrames=0;frequencySum=0;strongestRms=0;
}
void finishGroup() {
  if(!sequenceCount)return;
  groups++;
  Serial.printf("\nGROUP #%lu | %u valid beep(s)\n\n",(unsigned long)groups,sequenceCount);
  sequenceCount=0;previousBeepEnd=0;
}
void analyzeFrequency(int count,float mean,float rms,float &bestFreq,float &ratio) {
  float bestAmplitude=0;bestFreq=0;ratio=0;
  for(int f=0;f<NUM_FREQ;f++) {
    float q1=0,q2=0,coeff=coefficients[f];
    for(int i=0;i<count;i++) {
      float v=(float)(samples[i]>>8)-mean;
      float q0=v+coeff*q1-q2;
      q2=q1;q1=q0;
    }
    float power=q1*q1+q2*q2-coeff*q1*q2;
    if(power>0) {
      float amp=2.0f*sqrtf(power)/count;
      if(amp>bestAmplitude) { bestAmplitude=amp;bestFreq=FREQ_MIN+f*FREQ_STEP; }
    }
  }
  if(rms>0)ratio=bestAmplitude/rms;
}
void finishBeep(uint32_t endTime) {
  beepActive=false;
  uint32_t duration=endTime-beepStart;
  float percent=loudFrames?100.0f*validFrequencyFrames/loudFrames:0;
  float averageFrequency=validFrequencyFrames?frequencySum/validFrequencyFrames:0;
  bool accepted=duration>=MIN_BEEP_MS&&duration<=MAX_BEEP_MS&&percent>=MIN_VALID_FREQ_PERCENT;
  Serial.printf("BEEP END | %lu ms | F=%.0f Hz | freq-match=%.0f%% | %s\n",
    (unsigned long)duration,averageFrequency,percent,accepted?"VALID":"REJECTED");
  if(!accepted) { rejectedBeeps++;resetBeepMetrics();return; }
  validBeeps++;
  if(sequenceCount>0) {
    uint32_t gap=beepStart-previousBeepEnd;
    if(gap<MIN_GAP_MS||gap>MAX_GAP_MS)finishGroup();
    else Serial.printf("GAP | %lu ms\n",(unsigned long)gap);
  }
  sequenceCount++;
  previousBeepEnd=endTime;
  Serial.printf("VALID BEEP | Group position: %u\n",sequenceCount);
  if(sequenceCount>=3)Serial.println(">>> ALARM CANDIDATE (DIAGNOSTIC ONLY) <<<");
  resetBeepMetrics();
}
void processAudio(int count) {
  double sum=0;
  for(int i=0;i<count;i++)sum+=(samples[i]>>8);
  float mean=(float)(sum/count);
  double sumSquares=0;
  for(int i=0;i<count;i++) {
    double v=(double)(samples[i]>>8)-mean;
    sumSquares+=v*v;
  }
  float rms=sqrt(sumSquares/count);
  uint32_t now=millis();
  if(!beepActive&&sequenceCount>0&&now-previousBeepEnd>SEQUENCE_TIMEOUT_MS)finishGroup();
  if(!beepActive&&rms>=RMS_ON) {
    beepActive=true;beepStart=now;lastLoudTime=now;resetBeepMetrics();
    Serial.printf("\nBEEP START | RMS=%.0f\n",rms);
  }
  if(beepActive) {
    if(rms>=RMS_OFF) {
      lastLoudTime=now;loudFrames++;
      if(rms>strongestRms)strongestRms=rms;
      float freq=0,ratio=0;
      analyzeFrequency(count,mean,rms,freq,ratio);
      if(ratio>=MIN_TONE_RATIO) {validFrequencyFrames++;frequencySum+=freq;}
    }
    if(now-lastLoudTime>=SILENCE_MS)finishBeep(lastLoudTime+FRAME_MS);
    else if(now-beepStart>MAX_BEEP_MS+200) {
      Serial.println("BEEP TIMEOUT | REJECTED");
      rejectedBeeps++;beepActive=false;resetBeepMetrics();
    }
  }
  if(now-lastPrint>=2000) {
    lastPrint=now;
    Serial.printf("STATUS | RMS=%.0f | valid=%lu | rejected=%lu | groups=%lu\n",
      rms,(unsigned long)validBeeps,(unsigned long)rejectedBeeps,(unsigned long)groups);
  }
}
void setup() {
  Serial.begin(115200);delay(1500);
  Serial.println("\n========================");
  Serial.println("Smoke Listener Mesh");
  Serial.println("Firmware v0.3.1");
  Serial.println("ESP32-C3 / INMP441");
  Serial.println("========================");
  initFrequencyAnalysis();
  if(!initMicrophone()) {Serial.println("Microphone initialization failed");while(true)delay(1000);}
  Serial.println("I2S initialized");
  Serial.println("Audio diagnostics running");
}
void loop() {
  size_t bytesRead=0;
  esp_err_t err=i2s_read(I2S_NUM_0,samples,sizeof(samples),&bytesRead,pdMS_TO_TICKS(1000));
  if(err!=ESP_OK||bytesRead==0) {Serial.println("I2S read error");delay(100);return;}
  int count=bytesRead/sizeof(int32_t);
  if(count>0)processAudio(count);
}
