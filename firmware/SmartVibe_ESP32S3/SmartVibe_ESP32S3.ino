// SmartVibe ฝั่งบอร์ด — ESP32-S3 + MPU6050 x3
// ไฟล์นี้แค่ประกอบร่าง งานจริงอยู่ใน config / secrets / timebase / sensors / uploader / tasks
// secrets.h ต้องสร้างเอง ดู secrets.h.example

#include "config.h"
#include "timebase.h"
#include "sensors.h"
#include "uploader.h"
#include "tasks.h"

void setup() {
  Serial.begin(115200);
  delay(2000);                 // รอ USB พร้อม ไม่งั้นข้อความแรก ๆ หาย
  Serial.println("\n===== SmartVibe =====");

  if (!sensorsBegin()) { Serial.println("❌ เซ็นเซอร์ล้มเหลว"); ESP.restart(); }
  sensorsScan();               // ไว้ไล่หาสายหลุด

  if (!uploaderBegin()) { Serial.println("❌ เครือข่ายล้มเหลว"); ESP.restart(); }

  Serial.print("sync NTP");
  if (!timebaseBegin()) {
    // ไม่มีเวลาจริง = คีย์ผิด แล้วหน้าเว็บค้าง ยอม restart ดีกว่า
    Serial.println("\n❌ NTP ล้มเหลว → restart");
    delay(2000);
    ESP.restart();
  }
  Serial.printf("\n✅ NTP ok — epoch_ms = %s\n", keyOf(epochMillis()).c_str());

  if (!tasksBegin()) ESP.restart();
  Serial.println("✅ SmartVibe พร้อมทำงาน\n");
}

void loop() {
  vTaskDelay(pdMS_TO_TICKS(1000));   // งานจริงอยู่ใน task หมดแล้ว
}
